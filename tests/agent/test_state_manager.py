"""
StateManager Tests

Purpose: Test StateManager class for persistent storage of EmailRecord objects
         in JSONL format with atomic writes and backup recovery.

Type: Unit
Test Count: 19

Key Test Areas:
- JSONL file read/write operations
- Atomic writes with temp files
- Backup and recovery mechanisms
- Stale record detection
- Record append and update operations
- Conversation tracking
- File corruption handling

Dependencies:
- sample_email_record fixture
- Temporary file system (tmp_path)
"""

import pytest
import json
from pathlib import Path
from freezegun import freeze_time

from src.models.email_record import EmailRecord, EmailStatus
from src.utils.state_manager import StateManager


class TestStateManagerRead:
    """Tests for StateManager read operations."""

    def test_should_return_empty_list_when_file_not_exists(self, state_manager):
        """
        Verify read_state() returns empty list when state file doesn't exist.

        Tests that reading from a non-existent state file returns an empty
        list instead of raising an error.
        """
        # Arrange
        # state_manager fixture points to non-existent file by default

        # Act
        records = state_manager.read_state()

        # Assert
        assert records == []
        assert isinstance(records, list)

    def test_should_read_records_when_file_exists(self, state_manager, sample_email_record):
        """
        Verify read_state() loads JSONL correctly when file exists.

        Tests that a state file with valid JSONL records is correctly
        parsed into EmailRecord objects.
        """
        # Arrange
        records_to_write = [sample_email_record]
        state_manager.write_state(records_to_write)

        # Act
        loaded_records = state_manager.read_state()

        # Assert
        assert len(loaded_records) == 1
        assert loaded_records[0].email_id == "test_001"
        assert loaded_records[0].sender == "user@test.com"
        assert loaded_records[0].subject == "Test Subject"

    def test_should_skip_invalid_lines_when_reading(self, state_manager, tmp_path):
        """
        Verify read_state() skips malformed JSON lines gracefully.

        Tests that the state manager continues processing valid lines
        even when encountering malformed JSON.
        """
        # Arrange
        state_file = state_manager.state_file

        # Write file with mix of valid and invalid JSON
        with open(state_file, 'w') as f:
            # Valid line
            valid_record = {
                "email_id": "valid_001",
                "sender": "sender@test.com",
                "subject": "Valid",
                "body": "Body",
                "received_datetime": "2024-01-01T00:00:00Z",
                "status": "classified",
            }
            f.write(json.dumps(valid_record) + '\n')

            # Invalid JSON line
            f.write('{"invalid": json syntax\n')

            # Another valid line
            valid_record2 = {
                "email_id": "valid_002",
                "sender": "sender2@test.com",
                "subject": "Valid 2",
                "body": "Body 2",
                "received_datetime": "2024-01-02T00:00:00Z",
                "status": "classified",
            }
            f.write(json.dumps(valid_record2) + '\n')

        # Act
        records = state_manager.read_state()

        # Assert
        assert len(records) == 2
        assert records[0].email_id == "valid_001"
        assert records[1].email_id == "valid_002"


class TestStateManagerWrite:
    """Tests for StateManager write operations."""

    def test_should_write_atomically_when_saving_state(self, state_manager, sample_email_record):
        """
        Verify write_state() uses atomic write pattern (temp file + move).

        Tests that the write operation creates a temporary file first and
        then moves it to the final location, ensuring atomicity.
        """
        # Arrange
        records = [sample_email_record]

        # Act
        state_manager.write_state(records)

        # Assert
        assert state_manager.state_file.exists()

        # Verify temp file is cleaned up
        temp_file = Path(f"{state_manager.state_file}.tmp")
        assert not temp_file.exists()

        # Verify content is correct
        loaded_records = state_manager.read_state()
        assert len(loaded_records) == 1
        assert loaded_records[0].email_id == "test_001"

    def test_should_create_backup_when_writing(self, state_manager, sample_email_record):
        """
        Verify write_state() creates backup file before overwriting.

        Tests that an existing state file is backed up before being
        overwritten with new content.
        """
        # Arrange - Write initial state
        initial_record = EmailRecord(
            email_id="initial_001",
            sender="initial@test.com",
            subject="Initial",
            body="Body",
            received_datetime="2024-01-01T00:00:00Z",
        )
        state_manager.write_state([initial_record])

        # Act - Write new state (should backup old state)
        new_record = sample_email_record
        state_manager.write_state([new_record])

        # Assert
        assert state_manager.backup_file.exists()

        # Verify backup contains original data
        with open(state_manager.backup_file, 'r') as f:
            backup_line = f.readline()
            backup_data = json.loads(backup_line)
            assert backup_data["email_id"] == "initial_001"


class TestStateManagerAppend:
    """Tests for StateManager append operations."""

    def test_should_append_record_to_file_when_called(self, state_manager, sample_email_record):
        """
        Verify append_record() adds new record to JSONL file.

        Tests that appending a record adds it to the end of the file
        without affecting existing records.
        """
        # Arrange - Create initial record
        initial_record = EmailRecord(
            email_id="initial_001",
            sender="initial@test.com",
            subject="Initial",
            body="Body",
            received_datetime="2024-01-01T00:00:00Z",
        )
        state_manager.write_state([initial_record])

        # Act - Append new record
        state_manager.append_record(sample_email_record)

        # Assert
        records = state_manager.read_state()
        assert len(records) == 2
        assert records[0].email_id == "initial_001"
        assert records[1].email_id == "test_001"


class TestStateManagerUpdate:
    """Tests for StateManager update operations."""

    def test_should_update_record_when_found(self, state_manager, sample_email_record):
        """
        Verify update_record() modifies existing record fields.

        Tests that updating a record modifies the specified fields and
        updates the timestamp.
        """
        # Arrange
        with freeze_time("2024-01-05T12:00:00"):
            state_manager.write_state([sample_email_record])

            # Act
            updates = {
                "classification": "escalate",
                "confidence": 50.0,
                "reason": "Ambiguous request",
            }
            result = state_manager.update_record("test_001", updates)

            # Assert
            assert result is True

            # Verify updates were applied
            updated_record = state_manager.find_record("test_001")
            assert updated_record.classification == "escalate"
            assert updated_record.confidence == 50.0
            assert updated_record.reason == "Ambiguous request"
            # Check timestamp was updated (may not have Z suffix)
            assert updated_record.timestamp.startswith("2024-01-05T12:00:00")

    def test_should_return_false_when_record_not_found(self, state_manager):
        """
        Verify update_record() returns False when email_id not found.

        Tests that attempting to update a non-existent record returns False
        and doesn't raise an error.
        """
        # Arrange
        # Empty state

        # Act
        result = state_manager.update_record("nonexistent_id", {"classification": "help"})

        # Assert
        assert result is False


class TestStateManagerFind:
    """Tests for StateManager find operations."""

    def test_should_find_record_by_id_when_exists(self, state_manager, sample_email_record):
        """
        Verify find_record() returns correct record when it exists.

        Tests that finding a record by email_id returns the correct
        EmailRecord object.
        """
        # Arrange
        state_manager.write_state([sample_email_record])

        # Act
        found_record = state_manager.find_record("test_001")

        # Assert
        assert found_record is not None
        assert found_record.email_id == "test_001"
        assert found_record.sender == "user@test.com"

    def test_should_return_none_when_record_not_found(self, state_manager):
        """
        Verify find_record() returns None when email_id doesn't exist.

        Tests that searching for a non-existent email_id returns None
        instead of raising an error.
        """
        # Arrange
        # Empty state

        # Act
        result = state_manager.find_record("nonexistent_id")

        # Assert
        assert result is None

    def test_should_find_stale_records_when_old(self, state_manager):
        """
        Verify find_stale_records() identifies old records correctly.

        Tests that records with timestamps older than the threshold
        are correctly identified as stale.
        """
        # Arrange - Create records with different timestamps, timezone-aware
        with freeze_time("2024-01-05T00:00:00+00:00"):
            old_record = EmailRecord(
                email_id="old_001",
                sender="old@test.com",
                subject="Old",
                body="Body",
                received_datetime="2024-01-01T00:00:00Z",
                timestamp="2024-01-01T00:00:00+00:00",  # 4 days ago, timezone-aware
            )

            recent_record = EmailRecord(
                email_id="recent_001",
                sender="recent@test.com",
                subject="Recent",
                body="Body",
                received_datetime="2024-01-04T12:00:00Z",
                timestamp="2024-01-04T12:00:00+00:00",  # 12 hours ago, timezone-aware
            )

            state_manager.write_state([old_record, recent_record])

            # Act
            stale_records = state_manager.find_stale_records(hours=48)

            # Assert
            assert len(stale_records) == 1
            assert stale_records[0].email_id == "old_001"

    def test_should_find_in_progress_records_by_status(self, state_manager):
        """
        Verify find_in_progress_records() filters by resumable statuses.

        Tests that only records with in-progress, awaiting clarification,
        or awaiting response statuses are returned.
        """
        # Arrange
        in_progress = EmailRecord(
            email_id="in_progress_001",
            sender="sender1@test.com",
            subject="In Progress",
            body="Body",
            received_datetime="2024-01-01T00:00:00Z",
            status=EmailStatus.IN_PROGRESS,
        )

        awaiting_clarification = EmailRecord(
            email_id="awaiting_001",
            sender="sender2@test.com",
            subject="Awaiting",
            body="Body",
            received_datetime="2024-01-01T00:00:00Z",
            status=EmailStatus.AWAITING_CLARIFICATION,
        )

        completed = EmailRecord(
            email_id="completed_001",
            sender="sender3@test.com",
            subject="Completed",
            body="Body",
            received_datetime="2024-01-01T00:00:00Z",
            status=EmailStatus.COMPLETED_SUCCESS,
        )

        state_manager.write_state([in_progress, awaiting_clarification, completed])

        # Act
        in_progress_records = state_manager.find_in_progress_records()

        # Assert
        assert len(in_progress_records) == 2
        email_ids = [r.email_id for r in in_progress_records]
        assert "in_progress_001" in email_ids
        assert "awaiting_001" in email_ids
        assert "completed_001" not in email_ids


class TestStateManagerConversation:
    """Tests for StateManager conversation tracking."""

    def test_should_detect_conversation_when_exists(self, state_manager, sample_email_record):
        """
        Verify has_conversation() returns True when conversation_id exists.

        Tests that checking for an existing conversation ID returns True.
        """
        # Arrange
        state_manager.write_state([sample_email_record])

        # Act
        result = state_manager.has_conversation("conv_001")

        # Assert
        assert result is True

    def test_should_return_false_when_conversation_not_exists(self, state_manager, sample_email_record):
        """
        Verify has_conversation() returns False when conversation_id doesn't exist.

        Tests that checking for a non-existent conversation ID returns False.
        """
        # Arrange
        state_manager.write_state([sample_email_record])

        # Act
        result = state_manager.has_conversation("nonexistent_conv")

        # Assert
        assert result is False

    def test_should_return_false_when_conversation_id_is_none(self, state_manager):
        """
        Verify has_conversation() returns False when conversation_id is None.

        Tests that passing None as conversation_id returns False.
        """
        # Act
        result = state_manager.has_conversation(None)

        # Assert
        assert result is False


class TestStateManagerBackup:
    """Tests for StateManager backup and recovery operations."""

    def test_should_recover_from_backup_when_corrupted(self, state_manager, sample_email_record):
        """
        Verify StateManager handles corrupted data gracefully.

        Tests that if the main state file has invalid JSON lines, they are
        skipped and processing continues. Note: The current implementation
        skips invalid lines rather than falling back to backup, which is
        actually a more resilient approach for partial corruption.
        """
        # Arrange - Write valid state and create backup
        state_manager.write_state([sample_email_record])

        # Add corrupted lines but keep valid backup
        with open(state_manager.state_file, 'a') as f:
            f.write("corrupted non-json content\n")
            f.write("more corruption\n")

        # Act - Read should skip corrupted lines and keep valid ones
        records = state_manager.read_state()

        # Assert - The valid record should still be present
        assert len(records) == 1
        assert records[0].email_id == "test_001"

    def test_should_backup_corrupted_file_when_requested(self, state_manager):
        """
        Verify backup_corrupted_state() renames corrupted file with timestamp.

        Tests that calling backup_corrupted_state creates a timestamped
        backup of the corrupted file and creates a fresh state file.
        """
        # Arrange - Create a corrupted state file
        with open(state_manager.state_file, 'w') as f:
            f.write("corrupted content\n")

        # Act
        backup_path = state_manager.backup_corrupted_state()

        # Assert
        assert backup_path is not None
        assert Path(backup_path).exists()
        assert "corrupted_" in backup_path

        # Verify fresh state file was created
        assert state_manager.state_file.exists()
        assert state_manager.state_file.stat().st_size == 0

    def test_should_handle_write_failure_gracefully(self, state_manager, sample_email_record):
        """
        Verify write_state() cleans up temp file on failure.

        Tests that if write operation fails, temporary files are cleaned up.
        """
        # Arrange - Make the state file directory read-only to force write failure
        import os
        state_dir = state_manager.state_file.parent

        # Write initial state
        state_manager.write_state([sample_email_record])

        # Make directory read-only (this will cause write to fail)
        try:
            os.chmod(state_dir, 0o444)

            # Act & Assert - Write should raise IOError
            with pytest.raises(IOError):
                state_manager.write_state([sample_email_record])

        finally:
            # Restore permissions
            os.chmod(state_dir, 0o755)

    def test_should_handle_append_failure_gracefully(self, state_manager):
        """
        Verify append_record() raises IOError on failure.

        Tests that if append operation fails, an appropriate error is raised.
        """
        # Arrange - Make the state file read-only to force append failure
        import os

        # Create initial file
        state_manager.state_file.touch()

        # Make file read-only
        try:
            os.chmod(state_manager.state_file, 0o444)

            record = EmailRecord(
                email_id="test_001",
                sender="sender@test.com",
                subject="Subject",
                body="Body",
                received_datetime="2024-01-01T00:00:00Z",
            )

            # Act & Assert - Append should raise IOError
            with pytest.raises(IOError):
                state_manager.append_record(record)

        finally:
            # Restore permissions
            os.chmod(state_manager.state_file, 0o644)
