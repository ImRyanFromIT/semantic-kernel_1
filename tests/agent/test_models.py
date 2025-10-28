"""
Tests for EmailRecord model.

This module tests the core EmailRecord data model including serialization,
deserialization, status management, and staleness detection.
"""

import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time

from src.models.email_record import EmailRecord, EmailStatus


class TestEmailRecordSerialization:
    """Tests for EmailRecord serialization methods."""

    def test_should_serialize_to_dict_when_all_fields_present(self, sample_email_record):
        """
        Verify to_dict() serializes all fields correctly when all are present.

        Tests that a fully populated EmailRecord converts to a dictionary
        with all fields present and properly formatted.
        """
        # Arrange
        record = sample_email_record
        record.extracted_data = {"srm_title": "Test SRM"}
        record.update_payload = {"field": "value"}
        record.clarification_history = [{"question": "What?", "answer": "This."}]

        # Act
        result = record.to_dict()

        # Assert
        assert result["email_id"] == "test_001"
        assert result["sender"] == "user@test.com"
        assert result["subject"] == "Test Subject"
        assert result["body"] == "Test body content"
        assert result["received_datetime"] == "2024-01-01T00:00:00Z"
        assert result["conversation_id"] == "conv_001"
        assert result["classification"] == "help"
        assert result["confidence"] == 85.0
        assert result["reason"] == "Clear SRM request"
        assert result["status"] == "classified"
        assert "timestamp" in result
        assert result["extracted_data"] == {"srm_title": "Test SRM"}
        assert result["update_payload"] == {"field": "value"}
        assert result["processing_attempts"] == 0
        assert result["clarification_attempts"] == 0
        assert result["clarification_history"] == [{"question": "What?", "answer": "This."}]

    def test_should_serialize_to_dict_when_optional_fields_none(self):
        """
        Verify to_dict() serializes correctly with minimal required fields.

        Tests that an EmailRecord with only required fields (optional fields None)
        serializes properly without errors.
        """
        # Arrange
        record = EmailRecord(
            email_id="minimal_001",
            sender="sender@test.com",
            subject="Minimal",
            body="Body",
            received_datetime="2024-01-01T00:00:00Z",
        )

        # Act
        result = record.to_dict()

        # Assert
        assert result["email_id"] == "minimal_001"
        assert result["sender"] == "sender@test.com"
        assert result["conversation_id"] is None
        assert result["classification"] is None
        assert result["confidence"] is None
        assert result["extracted_data"] is None
        assert result["update_payload"] is None
        assert result["clarification_history"] is None

    def test_should_deserialize_from_dict_when_valid_data(self):
        """
        Verify from_dict() creates correct EmailRecord from valid dictionary.

        Tests that a dictionary with valid email data can be deserialized
        into a proper EmailRecord object with all fields populated.
        """
        # Arrange
        data = {
            "email_id": "test_002",
            "sender": "sender@example.com",
            "subject": "Test Subject",
            "body": "Email body",
            "received_datetime": "2024-01-02T10:00:00Z",
            "conversation_id": "conv_002",
            "classification": "dont_help",
            "confidence": 95.5,
            "reason": "Out of scope",
            "status": "completed_dont_help",
            "timestamp": "2024-01-02T10:05:00Z",
            "processing_attempts": 1,
            "clarification_attempts": 0,
        }

        # Act
        record = EmailRecord.from_dict(data)

        # Assert
        assert record.email_id == "test_002"
        assert record.sender == "sender@example.com"
        assert record.subject == "Test Subject"
        assert record.body == "Email body"
        assert record.received_datetime == "2024-01-02T10:00:00Z"
        assert record.conversation_id == "conv_002"
        assert record.classification == "dont_help"
        assert record.confidence == 95.5
        assert record.reason == "Out of scope"
        assert record.status == EmailStatus.COMPLETED_DONT_HELP
        assert record.timestamp == "2024-01-02T10:05:00Z"
        assert record.processing_attempts == 1

    def test_should_handle_status_enum_when_deserializing(self):
        """
        Verify from_dict() correctly converts status string to EmailStatus enum.

        Tests that the status field is properly converted from string to
        EmailStatus enum during deserialization.
        """
        # Arrange
        data = {
            "email_id": "test_003",
            "sender": "test@example.com",
            "subject": "Subject",
            "body": "Body",
            "received_datetime": "2024-01-01T00:00:00Z",
            "status": "awaiting_clarification",
        }

        # Act
        record = EmailRecord.from_dict(data)

        # Assert
        assert isinstance(record.status, EmailStatus)
        assert record.status == EmailStatus.AWAITING_CLARIFICATION
        assert record.status.value == "awaiting_clarification"

    def test_should_roundtrip_successfully_when_serializing(self, sample_email_record):
        """
        Verify to_dict → from_dict maintains data integrity.

        Tests that an EmailRecord can be serialized and deserialized without
        losing or corrupting any data.
        """
        # Arrange
        original = sample_email_record
        original.extracted_data = {"field": "value"}
        original.clarification_history = [{"q": "question", "a": "answer"}]

        # Act
        dict_form = original.to_dict()
        restored = EmailRecord.from_dict(dict_form)

        # Assert
        assert restored.email_id == original.email_id
        assert restored.sender == original.sender
        assert restored.subject == original.subject
        assert restored.body == original.body
        assert restored.received_datetime == original.received_datetime
        assert restored.conversation_id == original.conversation_id
        assert restored.classification == original.classification
        assert restored.confidence == original.confidence
        assert restored.reason == original.reason
        assert restored.status == original.status
        assert restored.extracted_data == original.extracted_data
        assert restored.clarification_history == original.clarification_history


class TestEmailRecordStaleDetection:
    """Tests for EmailRecord staleness detection."""

    def test_should_calculate_stale_correctly_when_old_timestamp(self):
        """
        Verify is_stale() returns True for records older than threshold.

        Tests that an EmailRecord with a timestamp older than the specified
        hours is correctly identified as stale.
        """
        # Arrange - Use freeze_time to set "now" to Jan 3, 2024
        with freeze_time("2024-01-03T00:00:00"):
            # Record from 3 days ago (72 hours) - Dec 31, 2023
            record = EmailRecord(
                email_id="old_001",
                sender="sender@test.com",
                subject="Old Email",
                body="Body",
                received_datetime="2023-12-31T00:00:00Z",
                timestamp="2023-12-31T00:00:00",
            )

            # Act
            result = record.is_stale(hours=48)

            # Assert
            assert result is True

    def test_should_calculate_not_stale_when_recent_timestamp(self):
        """
        Verify is_stale() returns False for recent records.

        Tests that an EmailRecord with a recent timestamp is correctly
        identified as not stale.
        """
        # Arrange - Use freeze_time to set "now" to Jan 1, 2024 at noon
        with freeze_time("2024-01-01T12:00:00"):
            # Record from 1 hour ago
            record = EmailRecord(
                email_id="recent_001",
                sender="sender@test.com",
                subject="Recent Email",
                body="Body",
                received_datetime="2024-01-01T11:00:00Z",
                timestamp="2024-01-01T11:00:00",
            )

            # Act
            result = record.is_stale(hours=48)

            # Assert
            assert result is False


class TestEmailRecordStatusUpdate:
    """Tests for EmailRecord status update methods."""

    def test_should_update_status_and_timestamp_when_called(self):
        """
        Verify update_status() updates both status and timestamp.

        Tests that calling update_status changes the status field and
        updates the timestamp to the current time.
        """
        # Arrange & Act
        with freeze_time("2024-01-01T12:00:00"):
            record = EmailRecord(
                email_id="test_001",
                sender="sender@test.com",
                subject="Subject",
                body="Body",
                received_datetime="2024-01-01T10:00:00Z",
                timestamp="2024-01-01T10:00:00",
                status=EmailStatus.CLASSIFIED,
            )

            # Act
            record.update_status(EmailStatus.IN_PROGRESS)

            # Assert
            assert record.status == EmailStatus.IN_PROGRESS
            # Check that timestamp was updated (without the 'Z' suffix)
            assert record.timestamp.startswith("2024-01-01T12:00:00")

    def test_should_increment_attempts_when_updating_status(self):
        """
        Verify update_status() increments processing_attempts counter.

        Tests that each call to update_status increments the processing
        attempts counter.
        """
        # Arrange
        record = EmailRecord(
            email_id="test_001",
            sender="sender@test.com",
            subject="Subject",
            body="Body",
            received_datetime="2024-01-01T10:00:00Z",
            processing_attempts=0,
        )

        # Act
        record.update_status(EmailStatus.IN_PROGRESS)
        record.update_status(EmailStatus.AWAITING_CLARIFICATION)

        # Assert
        assert record.processing_attempts == 2
        assert record.status == EmailStatus.AWAITING_CLARIFICATION
