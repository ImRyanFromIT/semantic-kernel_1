"""
State Plugin Tests

Purpose: Test state plugin wrapping StateManager with kernel_function
         methods for state operations.

Type: Unit
Test Count: 7

Key Test Areas:
- Loading state from JSONL file
- Appending records
- Updating existing records
- Kernel function registration
- Error handling

Dependencies:
- state_plugin fixture
- mock_state_manager fixture
"""

import pytest
import json

from src.plugins.agent.state_plugin import StatePlugin
from src.models.email_record import EmailRecord, EmailStatus


@pytest.fixture
def state_plugin(state_manager, mock_error_handler):
    """
    Provides a StatePlugin instance with test state manager.
    """
    return StatePlugin(state_manager, mock_error_handler)


class TestLoadState:
    """Tests for load_state method."""

    def test_should_load_empty_state(self, state_plugin):
        """
        Verify load_state returns empty list when no records exist.

        Tests that loading state from an empty file returns an
        empty JSON array.
        """
        # Act
        result = state_plugin.load_state()

        # Assert
        records = json.loads(result)
        assert records == []
        assert isinstance(records, list)

    def test_should_load_state_with_records(self, state_plugin, state_manager, sample_email_record):
        """
        Verify load_state returns records when they exist.

        Tests that loading state with existing records returns them
        as a JSON array.
        """
        # Arrange - Add record to state
        state_manager.write_state([sample_email_record])

        # Act
        result = state_plugin.load_state()

        # Assert
        records = json.loads(result)
        assert len(records) == 1
        assert records[0]["email_id"] == "test_001"
        assert records[0]["sender"] == "user@test.com"


class TestAddEmailRecord:
    """Tests for add_email_record method."""

    def test_should_add_email_record(self, state_plugin, state_manager):
        """
        Verify add_email_record adds new record to state.

        Tests that calling add_email_record appends a new record
        and it can be retrieved.
        """
        # Arrange
        email_data = json.dumps({
            "email_id": "new_001",
            "sender": "sender@example.com",
            "subject": "New Email",
            "body": "Email body",
            "received_datetime": "2024-01-01T00:00:00Z",
            "conversation_id": "conv_new"
        })

        # Act
        result = state_plugin.add_email_record(email_data)

        # Assert
        assert "new_001" in result
        assert "added to state" in result

        # Verify record was actually added
        record = state_manager.find_record("new_001")
        assert record is not None
        assert record.email_id == "new_001"
        assert record.sender == "sender@example.com"

    def test_should_handle_invalid_json_input(self, state_plugin):
        """
        Verify add_email_record handles invalid JSON gracefully.

        Tests that passing invalid JSON returns an error message
        instead of raising an exception.
        """
        # Arrange - Invalid JSON
        invalid_json = "not valid json {bad}"

        # Act
        result = state_plugin.add_email_record(invalid_json)

        # Assert
        assert "Invalid JSON" in result
        assert "email_data" in result


class TestUpdateEmailRecord:
    """Tests for update_email_record method."""

    def test_should_update_email_record(self, state_plugin, state_manager, sample_email_record):
        """
        Verify update_email_record modifies existing record.

        Tests that updating a record changes its fields and
        returns success message.
        """
        # Arrange - Add initial record
        state_manager.write_state([sample_email_record])

        updates = json.dumps({
            "classification": "escalate",
            "confidence": 50.0,
            "reason": "Changed to escalate"
        })

        # Act
        result = state_plugin.update_email_record("test_001", updates)

        # Assert
        assert "test_001" in result
        assert "updated successfully" in result

        # Verify update was applied
        record = state_manager.find_record("test_001")
        assert record.classification == "escalate"
        assert record.confidence == 50.0
        assert record.reason == "Changed to escalate"

    def test_should_handle_status_enum_conversion(self, state_plugin, state_manager, sample_email_record):
        """
        Verify update_email_record converts status string to enum.

        Tests that when updating status field, the string value
        is properly converted to EmailStatus enum.
        """
        # Arrange
        state_manager.write_state([sample_email_record])

        updates = json.dumps({
            "status": "in_progress"
        })

        # Act
        result = state_plugin.update_email_record("test_001", updates)

        # Assert
        assert "updated successfully" in result

        # Verify status was converted to enum
        record = state_manager.find_record("test_001")
        assert record.status == EmailStatus.IN_PROGRESS
        assert isinstance(record.status, EmailStatus)


class TestGetEmailRecord:
    """Tests for get_email_record method."""

    def test_should_find_record_by_id(self, state_plugin, state_manager, sample_email_record):
        """
        Verify get_email_record retrieves record by ID.

        Tests that finding a record by ID returns its complete data.
        """
        # Arrange
        state_manager.write_state([sample_email_record])

        # Act
        result = state_plugin.get_email_record("test_001")

        # Assert
        record_data = json.loads(result)
        assert record_data["email_id"] == "test_001"
        assert record_data["sender"] == "user@test.com"
        assert record_data["subject"] == "Test Subject"
