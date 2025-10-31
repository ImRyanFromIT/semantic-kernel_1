"""
Email Intake Process Steps Tests

Purpose: Test process steps handling the email intake workflow from
         initialization through routing and responses.

Type: Integration
Test Count: 17

Key Test Areas:
- InitializeStateStep (state loading, stale detection)
- FetchNewEmailsStep (email fetching, deduplication)
- ClassifyEmailsStep (email classification integration)
- RouteEmailsStep (routing logic by classification)
- ProcessHelpEmailsStep (subprocess invocation)
- RespondDontHelpStep (dont_help responses)
- EscalateEmailStep (escalation handling)

Dependencies:
- mock_process_context fixture
- create_process_input_data fixture
- sample_email_record fixture
- EscalateEmailStep
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, Mock


class TestInitializeStateStep:
    """Test InitializeStateStep functionality."""

    @pytest.mark.asyncio
    async def test_initialize_should_load_state_and_emit_event(
        self, mock_process_context, create_process_input_data, sample_email_record
    ):
        """Test InitializeStateStep loads state and emits StateLoaded event."""
        # Arrange
        from src.processes.agent.email_intake_process import InitializeStateStep

        input_data = create_process_input_data()
        state_manager = input_data["state_manager"]

        # Add a sample record to state
        state_manager.append_record(sample_email_record)

        step = InitializeStateStep()
        await step.activate(state=None)

        # Act
        await step.initialize(mock_process_context, input_data)

        # Assert
        mock_process_context.emit_event.assert_called_once()
        call_args = mock_process_context.emit_event.call_args
        assert call_args[1]["process_event"] == "StateLoaded"
        # Actual implementation emits in_progress_records and awaiting_clarification_records
        assert "in_progress_records" in call_args[1]["data"]
        assert "awaiting_clarification_records" in call_args[1]["data"]
        assert "escalated_stale_count" in call_args[1]["data"]
        # Sample record is CLASSIFIED status, not in-progress or awaiting, so both lists are empty
        assert isinstance(call_args[1]["data"]["in_progress_records"], list)
        assert isinstance(call_args[1]["data"]["awaiting_clarification_records"], list)

    @pytest.mark.asyncio
    async def test_initialize_should_escalate_stale_records(
        self, mock_process_context, create_process_input_data
    ):
        """Test InitializeStateStep escalates stale records (24h in-progress, 48h clarification)."""
        # Arrange
        from src.processes.agent.email_intake_process import InitializeStateStep
        from src.models.email_record import EmailRecord, EmailStatus

        input_data = create_process_input_data()
        state_manager = input_data["state_manager"]

        # Create stale in-progress record (26 hours old) - use timezone-aware datetimes
        from datetime import timezone
        stale_in_progress = EmailRecord(
            email_id="stale_001",
            sender="user@test.com",
            subject="Stale In Progress",
            body="Test",
            received_datetime=(datetime.now(timezone.utc) - timedelta(hours=26)).isoformat(),
            conversation_id="conv_001",
            classification="help",
            confidence=85.0,
            reason="Test",
            status=EmailStatus.IN_PROGRESS,
            timestamp=(datetime.now(timezone.utc) - timedelta(hours=26)).isoformat()
        )

        # Create stale clarification record (50 hours old)
        stale_clarification = EmailRecord(
            email_id="stale_002",
            sender="user2@test.com",
            subject="Stale Clarification",
            body="Test",
            received_datetime=(datetime.now(timezone.utc) - timedelta(hours=50)).isoformat(),
            conversation_id="conv_002",
            classification="help",
            confidence=85.0,
            reason="Test",
            status=EmailStatus.AWAITING_CLARIFICATION,
            timestamp=(datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()
        )

        state_manager.append_record(stale_in_progress)
        state_manager.append_record(stale_clarification)

        step = InitializeStateStep()
        await step.activate(state=None)

        # Act
        await step.initialize(mock_process_context, input_data)

        # Assert - Check both records were escalated
        escalated_1 = state_manager.find_record("stale_001")
        escalated_2 = state_manager.find_record("stale_002")

        # Actual implementation sets status to ESCALATED (not ESCALATING)
        assert escalated_1.status == EmailStatus.ESCALATED
        assert escalated_2.status == EmailStatus.ESCALATED

        # Verify escalated count in event data
        call_args = mock_process_context.emit_event.call_args
        assert call_args[1]["data"]["escalated_stale_count"] == 2

    @pytest.mark.asyncio
    async def test_initialize_should_emit_error_on_failure(
        self, mock_process_context, create_process_input_data
    ):
        """Test InitializeStateStep emits StateError when state loading fails."""
        # Arrange
        from src.processes.agent.email_intake_process import InitializeStateStep
        from unittest.mock import Mock

        input_data = create_process_input_data()

        # Mock state_manager.read_state to raise exception
        input_data["state_manager"].read_state = Mock(
            side_effect=Exception("State file corrupted")
        )

        step = InitializeStateStep()
        await step.activate(state=None)

        # Act
        await step.initialize(mock_process_context, input_data)

        # Assert
        mock_process_context.emit_event.assert_called_once()
        call_args = mock_process_context.emit_event.call_args
        assert call_args[1]["process_event"] == "StateError"
        # Actual implementation uses "error" key, not "error_message"
        assert "error" in call_args[1]["data"]


class TestFetchNewEmailsStep:
    """Test FetchNewEmailsStep functionality."""

    @pytest.mark.asyncio
    async def test_fetch_should_return_new_emails(
        self, mock_process_context, create_process_input_data, sample_graph_emails
    ):
        """Test FetchNewEmailsStep fetches new emails and emits EmailsFetched event."""
        # Arrange
        from src.processes.agent.email_intake_process import FetchNewEmailsStep

        input_data = create_process_input_data()
        graph_client = input_data["graph_client"]

        # Mock Graph API to return normal emails
        graph_client.fetch_emails_async.return_value = sample_graph_emails["normal"]

        step = FetchNewEmailsStep()
        await step.activate(state=None)

        # Act
        await step.fetch_emails(mock_process_context, input_data)

        # Assert
        mock_process_context.emit_event.assert_called_once()
        call_args = mock_process_context.emit_event.call_args
        assert call_args[1]["process_event"] == "EmailsFetched"
        # Actual implementation uses "new_emails" key
        assert "new_emails" in call_args[1]["data"]
        assert len(call_args[1]["data"]["new_emails"]) == 2

    @pytest.mark.asyncio
    async def test_fetch_should_filter_self_emails(
        self, mock_process_context, create_process_input_data, sample_graph_emails
    ):
        """Test FetchNewEmailsStep filters out emails sent by the bot itself."""
        # Arrange
        from src.processes.agent.email_intake_process import FetchNewEmailsStep

        input_data = create_process_input_data()
        graph_client = input_data["graph_client"]

        # Mock Graph API to return emails including self-email
        graph_client.fetch_emails_async.return_value = sample_graph_emails["with_self_email"]

        step = FetchNewEmailsStep()
        await step.activate(state=None)

        # Act
        await step.fetch_emails(mock_process_context, input_data)

        # Assert
        call_args = mock_process_context.emit_event.call_args
        emails = call_args[1]["data"]["new_emails"]  # Correct key

        # Should only have 1 email (self-email filtered out)
        assert len(emails) == 1
        # Fixture now uses flat sender field
        assert emails[0]["sender"] == "user1@test.com"

    @pytest.mark.asyncio
    async def test_fetch_should_filter_duplicate_conversations(
        self, mock_process_context, create_process_input_data, sample_graph_emails, sample_email_record
    ):
        """Test FetchNewEmailsStep filters emails from conversations already in state."""
        # Arrange
        from src.processes.agent.email_intake_process import FetchNewEmailsStep
        from src.models.email_record import EmailStatus

        input_data = create_process_input_data()
        graph_client = input_data["graph_client"]
        state_manager = input_data["state_manager"]

        # Add an existing record for conv_001 to state (not awaiting clarification)
        existing_record = sample_email_record
        existing_record.conversation_id = "conv_001"
        existing_record.status = EmailStatus.COMPLETED_SUCCESS
        state_manager.append_record(existing_record)

        # Mock Graph API to return emails including one from conv_001
        graph_client.fetch_emails_async.return_value = sample_graph_emails["with_duplicates"]

        step = FetchNewEmailsStep()
        await step.activate(state=None)

        # Act
        await step.fetch_emails(mock_process_context, input_data)

        # Assert
        call_args = mock_process_context.emit_event.call_args

        # Should filter out both emails from conv_001 since it's already in state
        # (and not awaiting clarification), resulting in NoNewEmails event
        assert call_args[1]["process_event"] == "NoNewEmails"

    @pytest.mark.asyncio
    async def test_fetch_should_detect_mass_email(
        self, mock_process_context, create_process_input_data, sample_graph_emails
    ):
        """Test FetchNewEmailsStep detects when email count exceeds mass_email_threshold."""
        # Arrange
        from src.processes.agent.email_intake_process import FetchNewEmailsStep

        input_data = create_process_input_data()
        graph_client = input_data["graph_client"]

        # Mock Graph API to return mass emails (25 emails, threshold is 20)
        graph_client.fetch_emails_async.return_value = sample_graph_emails["mass_email"]

        step = FetchNewEmailsStep()
        await step.activate(state=None)

        # Act
        await step.fetch_emails(mock_process_context, input_data)

        # Assert
        mock_process_context.emit_event.assert_called_once()
        call_args = mock_process_context.emit_event.call_args
        assert call_args[1]["process_event"] == "MassEmailDetected"
        # Actual implementation uses "email_count" key
        assert call_args[1]["data"]["email_count"] == 25
        assert call_args[1]["data"]["threshold"] == 20
        assert "sample_subjects" in call_args[1]["data"]

    @pytest.mark.asyncio
    async def test_fetch_should_sort_chronologically(
        self, mock_process_context, create_process_input_data
    ):
        """Test FetchNewEmailsStep sorts emails chronologically (oldest first)."""
        # Arrange
        from src.processes.agent.email_intake_process import FetchNewEmailsStep

        input_data = create_process_input_data()
        graph_client = input_data["graph_client"]

        # Create emails in non-chronological order
        unsorted_emails = [
            {
                "email_id": "email_003",
                "sender": "user3@test.com",
                "subject": "Request 3",
                "body": "Body 3",
                "received_datetime": "2024-01-01T15:00:00Z",  # Latest (snake_case)
                "conversation_id": "conv_003"
            },
            {
                "email_id": "email_001",
                "sender": "user1@test.com",
                "subject": "Request 1",
                "body": "Body 1",
                "received_datetime": "2024-01-01T10:00:00Z",  # Earliest
                "conversation_id": "conv_001"
            },
            {
                "email_id": "email_002",
                "sender": "user2@test.com",
                "subject": "Request 2",
                "body": "Body 2",
                "received_datetime": "2024-01-01T12:00:00Z",  # Middle
                "conversation_id": "conv_002"
            }
        ]

        graph_client.fetch_emails_async.return_value = unsorted_emails

        step = FetchNewEmailsStep()
        await step.activate(state=None)

        # Act
        await step.fetch_emails(mock_process_context, input_data)

        # Assert
        call_args = mock_process_context.emit_event.call_args
        emails = call_args[1]["data"]["new_emails"]  # Correct key

        # Verify sorted order (oldest first)
        assert emails[0]["email_id"] == "email_001"
        assert emails[1]["email_id"] == "email_002"
        assert emails[2]["email_id"] == "email_003"


class TestClassifyEmailsStep:
    """Test ClassifyEmailsStep functionality."""

    @pytest.mark.asyncio
    async def test_classify_should_classify_each_email(
        self, mock_process_context, create_process_input_data, sample_classification_result
    ):
        """Test ClassifyEmailsStep classifies each email and emits EmailsClassified."""
        # Arrange
        from src.processes.agent.email_intake_process import ClassifyEmailsStep
        from unittest.mock import AsyncMock

        input_data = create_process_input_data()
        kernel = input_data["kernel"]
        state_manager = input_data["state_manager"]

        # Emails in format expected by implementation
        emails = [
            {
                "email_id": "email_001",
                "sender": "user1@test.com",
                "subject": "Test 1",
                "body": "Body 1",
                "received_datetime": "2024-01-01T10:00:00Z",
                "conversation_id": "conv_001"
            },
            {
                "email_id": "email_002",
                "sender": "user2@test.com",
                "subject": "Test 2",
                "body": "Body 2",
                "received_datetime": "2024-01-01T11:00:00Z",
                "conversation_id": "conv_002"
            }
        ]

        # Implementation expects "new_emails", not "emails"
        input_data["new_emails"] = emails

        # Implementation uses kernel.invoke_prompt directly, not a plugin
        kernel.invoke_prompt = AsyncMock(
            return_value='{"classification": "help", "confidence": 85, "reason": "Clear SRM request"}'
        )

        step = ClassifyEmailsStep()
        await step.activate(None)  # Positional parameter

        # Act - actual function is classify(), not classify_emails()
        await step.classify(mock_process_context, input_data)

        # Assert
        mock_process_context.emit_event.assert_called_once()
        call_args = mock_process_context.emit_event.call_args
        assert call_args[1]["process_event"] == "EmailsClassified"

        # Verify both emails were classified and stored
        record_1 = state_manager.find_record("email_001")
        record_2 = state_manager.find_record("email_002")
        assert record_1 is not None
        assert record_2 is not None
        assert record_1.classification == "help"
        assert record_2.classification == "help"

    @pytest.mark.asyncio
    async def test_classify_should_detect_clarification_reply(
        self, mock_process_context, create_process_input_data, sample_email_record
    ):
        """Test ClassifyEmailsStep detects when email is a clarification reply."""
        # Arrange
        from src.processes.agent.email_intake_process import ClassifyEmailsStep
        from src.models.email_record import EmailStatus

        input_data = create_process_input_data()
        state_manager = input_data["state_manager"]

        # Add existing record awaiting clarification
        existing_record = sample_email_record
        existing_record.status = EmailStatus.AWAITING_CLARIFICATION
        state_manager.append_record(existing_record)

        # New email with same conversation_id (reply) - use correct format
        emails = [
            {
                "email_id": "email_reply",
                "sender": "user@test.com",
                "subject": "Re: Test Subject",
                "body": "Here is my clarification",
                "received_datetime": "2024-01-02T00:00:00Z",
                "conversation_id": existing_record.conversation_id  # Same conversation
            }
        ]

        input_data["new_emails"] = emails  # Correct key

        step = ClassifyEmailsStep()
        await step.activate(None)  # Positional parameter

        # Act - actual function is classify()
        await step.classify(mock_process_context, input_data)

        # Assert
        # Implementation collects reply in emails_with_replies dict, not on the record
        call_args = mock_process_context.emit_event.call_args
        emails_with_replies = call_args[1]["data"]["emails_with_replies"]

        # Should have mapping from original email to reply
        assert existing_record.email_id in emails_with_replies
        assert emails_with_replies[existing_record.email_id]["reply_email_id"] == "email_reply"
        assert "reply_body" in emails_with_replies[existing_record.email_id]

    @pytest.mark.asyncio
    async def test_classify_should_skip_reply_record_creation(
        self, mock_process_context, create_process_input_data, sample_email_record
    ):
        """Test ClassifyEmailsStep doesn't create new record for clarification replies."""
        # Arrange
        from src.processes.agent.email_intake_process import ClassifyEmailsStep
        from src.models.email_record import EmailStatus

        input_data = create_process_input_data()
        state_manager = input_data["state_manager"]

        # Add existing record awaiting clarification
        existing_record = sample_email_record
        existing_record.status = EmailStatus.AWAITING_CLARIFICATION
        state_manager.append_record(existing_record)

        # Reply email - use correct format
        emails = [
            {
                "email_id": "email_reply",
                "sender": "user@test.com",
                "subject": "Re: Test Subject",
                "body": "Here is my clarification",
                "received_datetime": "2024-01-02T00:00:00Z",
                "conversation_id": existing_record.conversation_id
            }
        ]

        input_data["new_emails"] = emails  # Correct key

        step = ClassifyEmailsStep()
        await step.activate(None)  # Positional parameter

        # Act - actual function is classify()
        await step.classify(mock_process_context, input_data)

        # Assert
        # Should NOT create a new record for the reply
        reply_record = state_manager.find_record("email_reply")
        assert reply_record is None  # No new record created

        # Original record should still exist
        original_record = state_manager.find_record(existing_record.email_id)
        assert original_record is not None

        # Verify classified_emails list does NOT contain the reply
        call_args = mock_process_context.emit_event.call_args
        classified_emails = call_args[1]["data"]["classified_emails"]
        assert len(classified_emails) == 0  # Reply was skipped


class TestRouteEmailsStep:
    """Test RouteEmailsStep functionality."""

    @pytest.mark.asyncio
    async def test_route_should_emit_help_event(
        self, mock_process_context, create_process_input_data, sample_email_record
    ):
        """Test RouteEmailsStep emits HelpEmails event for help classification."""
        # Arrange
        from src.processes.agent.email_intake_process import RouteEmailsStep

        input_data = create_process_input_data()
        state_manager = input_data["state_manager"]

        # Add help email to state
        help_record = sample_email_record
        help_record.classification = "help"
        state_manager.append_record(help_record)

        # Implementation expects "classified_emails", not "records"
        input_data["classified_emails"] = [help_record.to_dict()]

        step = RouteEmailsStep()
        await step.activate(None)  # Positional parameter

        # Act - actual function is route(), not route_emails()
        await step.route(mock_process_context, input_data)

        # Assert - Should emit HelpEmails at least once
        assert mock_process_context.emit_event.call_count >= 1
        help_event_found = False

        for call in mock_process_context.emit_event.call_args_list:
            if call[1]["process_event"] == "HelpEmails":
                help_event_found = True
                # Actual implementation uses "emails" key, not "help_emails"
                assert "emails" in call[1]["data"]

        assert help_event_found

    @pytest.mark.asyncio
    async def test_route_should_emit_dont_help_event(
        self, mock_process_context, create_process_input_data, sample_email_record
    ):
        """Test RouteEmailsStep emits DontHelpEmails event for dont_help classification."""
        # Arrange
        from src.processes.agent.email_intake_process import RouteEmailsStep

        input_data = create_process_input_data()
        state_manager = input_data["state_manager"]

        # Add dont_help email to state
        dont_help_record = sample_email_record
        dont_help_record.email_id = "dont_help_001"
        dont_help_record.classification = "dont_help"
        state_manager.append_record(dont_help_record)

        # Implementation expects "classified_emails", not "records"
        input_data["classified_emails"] = [dont_help_record.to_dict()]

        step = RouteEmailsStep()
        await step.activate(None)  # Positional parameter

        # Act - actual function is route()
        await step.route(mock_process_context, input_data)

        # Assert
        dont_help_event_found = False

        for call in mock_process_context.emit_event.call_args_list:
            if call[1]["process_event"] == "DontHelpEmails":
                dont_help_event_found = True
                # Actual implementation uses "emails" key
                assert "emails" in call[1]["data"]

        assert dont_help_event_found

    @pytest.mark.asyncio
    async def test_route_should_emit_escalate_event(
        self, mock_process_context, create_process_input_data, sample_email_record
    ):
        """Test RouteEmailsStep emits EscalateEmails event for escalate classification."""
        # Arrange
        from src.processes.agent.email_intake_process import RouteEmailsStep

        input_data = create_process_input_data()
        state_manager = input_data["state_manager"]

        # Add escalate email to state
        escalate_record = sample_email_record
        escalate_record.email_id = "escalate_001"
        escalate_record.classification = "escalate"
        state_manager.append_record(escalate_record)

        # Implementation expects "classified_emails", not "records"
        input_data["classified_emails"] = [escalate_record.to_dict()]

        step = RouteEmailsStep()
        await step.activate(None)  # Positional parameter

        # Act - actual function is route()
        await step.route(mock_process_context, input_data)

        # Assert
        escalate_event_found = False

        for call in mock_process_context.emit_event.call_args_list:
            if call[1]["process_event"] == "EscalateEmails":
                escalate_event_found = True
                # Actual implementation uses "emails" key
                assert "emails" in call[1]["data"]

        assert escalate_event_found


class TestAdditionalProcessSteps:
    """Test ProcessHelpEmailsStep, RespondDontHelpStep, and EscalateEmailStep."""

    @pytest.mark.asyncio
    async def test_process_help_should_invoke_subprocess(
        self, mock_process_context, create_process_input_data, sample_email_record
    ):
        """Test ProcessHelpEmailsStep invokes SRM Help subprocess."""
        # Arrange
        from src.processes.agent.email_intake_process import ProcessHelpEmailsStep

        input_data = create_process_input_data()

        # Mock subprocess
        mock_srm_help_process = AsyncMock()
        input_data["srm_help_process"] = mock_srm_help_process

        help_emails = [sample_email_record.to_dict()]
        # Implementation expects "emails", not "help_emails"
        input_data["emails"] = help_emails

        step = ProcessHelpEmailsStep()
        await step.activate(None)  # Positional parameter

        # Mock the start function for subprocess invocation (imported from Semantic Kernel)
        with patch("semantic_kernel.processes.local_runtime.local_kernel_process.start") as mock_start:
            mock_process = AsyncMock()
            mock_start.return_value.__aenter__ = AsyncMock(return_value=mock_process)
            mock_start.return_value.__aexit__ = AsyncMock()

            # Act - actual function is process_help()
            await step.process_help(mock_process_context, input_data)

            # Assert - Verify subprocess was invoked
            assert mock_start.called

    @pytest.mark.asyncio
    async def test_respond_should_send_rejection(
        self, mock_process_context, create_process_input_data, sample_email_record
    ):
        """Test RespondDontHelpStep sends rejection email."""
        # Arrange
        from src.processes.agent.email_intake_process import RespondDontHelpStep

        input_data = create_process_input_data()
        response_handler = input_data["response_handler"]

        dont_help_emails = [sample_email_record.to_dict()]
        # Implementation expects "emails", not "dont_help_emails"
        input_data["emails"] = dont_help_emails

        step = RespondDontHelpStep()
        await step.activate(None)  # Positional parameter

        # Act - actual function is respond()
        await step.respond(mock_process_context, input_data)

        # Assert - actual method is send_rejection_response()
        response_handler.send_rejection_response.assert_called()
        mock_process_context.emit_event.assert_called()

    @pytest.mark.asyncio
    async def test_escalate_should_notify_support(
        self, mock_process_context, create_process_input_data, sample_email_record
    ):
        """Test EscalateEmailStep escalates to human support."""
        # Arrange
        from src.processes.agent.email_intake_process import EscalateEmailStep

        input_data = create_process_input_data()
        response_handler = input_data["response_handler"]

        escalate_emails = [sample_email_record.to_dict()]
        # Implementation expects "emails", not "escalate_emails"
        input_data["emails"] = escalate_emails

        step = EscalateEmailStep()
        await step.activate(None)  # Positional parameter

        # Act - actual function is escalate()
        await step.escalate(mock_process_context, input_data)

        # Assert - actual method is send_escalation()
        response_handler.send_escalation.assert_called()
        mock_process_context.emit_event.assert_called()
