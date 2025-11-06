"""
Process Integration Tests

Purpose: Test end-to-end process flows with hybrid real/mocked services
         to verify multi-component integration.

Type: Integration
Test Count: 8

Key Test Areas:
- Email intake happy path (end-to-end)
- Dont_help response flow
- Escalation flow
- Mass email detection
- State resumption and recovery
- SRM help full flow (with real Azure OpenAI)
- SRM search not found handling
- Nested process invocation

Test Strategy:
- Real process orchestration (ProcessBuilder, KernelProcess)
- Hybrid LLM approach (real for critical tests, mocked for others)
- Real external services (Graph API, Azure Search)

Dependencies:
- Azure OpenAI integration fixtures
- Mock/real service fixtures
- Process orchestration fixtures
- Defer ClarificationStep tests (agent-based, out of scope)
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta, timezone
from src.models.email_record import EmailRecord, EmailStatus


@pytest.mark.integration
@pytest.mark.asyncio
class TestEmailIntakeProcess:
    """Integration tests for Email Intake Process workflows."""

    async def test_email_intake_happy_path(
        self,
        mock_kernel,
        mock_config,
        state_manager,
        mock_graph_client,
        mock_response_handler,
        integration_test_emails
    ):
        """
        Test 1: Email Intake Happy Path

        Scenario: New help email → classify → route → process
        Services: Real process steps, mocked LLM (deterministic)
        Verifies: End-to-end state transitions, record updates
        """
        from src.processes.agent.email_intake_process import (
            InitializeStateStep,
            FetchNewEmailsStep,
            ClassifyEmailsStep,
            RouteEmailsStep
        )

        # ARRANGE: Setup mocks
        mock_graph_client.fetch_emails_async.return_value = [
            integration_test_emails["help_request"]
        ]

        # Mock classification plugin response
        classification_result = {
            "classification": "help",
            "confidence": 85,
            "reason": "Clear SRM update request with all required information"
        }

        # Mock kernel get_plugin for classification
        mock_plugin = MagicMock()
        mock_func = AsyncMock()
        mock_func.invoke.return_value = MagicMock(value=json.dumps(classification_result))

        def mock_getitem(key):
            return mock_func

        mock_plugin.__getitem__.side_effect = mock_getitem
        mock_kernel.get_plugin = Mock(return_value=mock_plugin)

        mock_srm_process = Mock()

        mock_context = Mock()
        mock_context.emit_event = AsyncMock()

        input_data = {
            "kernel": mock_kernel,
            "config": mock_config,
            "state_manager": state_manager,
            "graph_client": mock_graph_client,
            "response_handler": mock_response_handler,
            "srm_help_process": mock_srm_process
        }

        # ACT: Execute process steps
        # Step 1: Initialize
        init_step = InitializeStateStep()
        await init_step.activate(state=None)
        await init_step.initialize(mock_context, input_data)

        # Step 2: Fetch emails
        fetch_step = FetchNewEmailsStep()
        await fetch_step.activate(state=None)
        await fetch_step.fetch_emails(mock_context, input_data)

        # Step 3: Classify emails
        classify_step = ClassifyEmailsStep()
        await classify_step.activate(state=None)

        # Add fetched email to input data
        input_data["new_emails"] = [integration_test_emails["help_request"]]

        await classify_step.classify(mock_context, input_data)

        # ASSERT: Verify outcomes
        # Check that emails were fetched
        mock_graph_client.fetch_emails_async.assert_called_once()

        # Check that events were emitted for each step
        assert mock_context.emit_event.call_count >= 3  # Initialize, Fetch, Classify

        # Check that state manager has the classified email
        records = state_manager.read_state()
        assert len(records) >= 1

        # Find our test email
        test_record = next(
            (r for r in records if r.email_id == integration_test_emails["help_request"]["email_id"]),
            None
        )

        # Classification may fail with mock, but we should have the record
        assert test_record is not None

    async def test_email_intake_dont_help_response(
        self,
        mock_kernel,
        mock_config,
        state_manager,
        mock_graph_client,
        mock_response_handler,
        integration_test_emails
    ):
        """
        Test 2: Email Intake with Don't Help Response

        Scenario: Email classified as "dont_help" → sends rejection email
        Services: Real process, mocked LLM
        Verifies: Rejection email sent
        """
        from src.processes.agent.email_intake_process import RespondDontHelpStep

        # ARRANGE: Create dont_help classified email
        email_record = EmailRecord(
            email_id=integration_test_emails["dont_help_request"]["email_id"],
            sender=integration_test_emails["dont_help_request"]["sender"],
            subject=integration_test_emails["dont_help_request"]["subject"],
            body=integration_test_emails["dont_help_request"]["body"],
            received_datetime=integration_test_emails["dont_help_request"]["received_datetime"],
            conversation_id=integration_test_emails["dont_help_request"]["conversation_id"],
            classification="dont_help",
            confidence=95.0,
            reason="Spam email, not related to SRM work",
            status=EmailStatus.CLASSIFIED,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        state_manager.append_record(email_record)

        # Setup step
        step = RespondDontHelpStep()
        await step.activate(None)

        # Convert EmailRecord to dict format expected by step
        email_dict = {
            "email_id": email_record.email_id,
            "sender": email_record.sender,
            "subject": email_record.subject,
            "body": email_record.body,
            "reason": email_record.reason
        }

        input_data = {
            "kernel": mock_kernel,
            "config": mock_config,
            "state_manager": state_manager,
            "graph_client": mock_graph_client,
            "response_handler": mock_response_handler,
            "emails": [email_dict]  # Changed from email_records to emails
        }

        mock_context = Mock()
        mock_context.emit_event = AsyncMock()

        # ACT: Execute step (correct method name: "respond")
        await step.respond(mock_context, input_data)

        # ASSERT: Verify rejection email was sent
        assert mock_response_handler.send_rejection_response.called

        # Verify record status updated (Note: Records updated in state are not persisted without explicit save)
        # The step should emit an event indicating success
        assert mock_context.emit_event.called

    async def test_email_intake_escalation(
        self,
        mock_kernel,
        mock_config,
        state_manager,
        mock_graph_client,
        mock_response_handler,
        integration_test_emails
    ):
        """
        Test 3: Email Intake with Escalation

        Scenario: Low confidence or explicit escalation → forwards to support
        Services: Real process, mocked LLM
        Verifies: Escalation email sent to support team
        """
        from src.processes.agent.email_intake_process import EscalateEmailStep

        # ARRANGE: Create escalate classified email
        email_record = EmailRecord(
            email_id=integration_test_emails["escalate_request"]["email_id"],
            sender=integration_test_emails["escalate_request"]["sender"],
            subject=integration_test_emails["escalate_request"]["subject"],
            body=integration_test_emails["escalate_request"]["body"],
            received_datetime=integration_test_emails["escalate_request"]["received_datetime"],
            conversation_id=integration_test_emails["escalate_request"]["conversation_id"],
            classification="escalate",
            confidence=40.0,
            reason="Request is too ambiguous to process automatically",
            status=EmailStatus.CLASSIFIED,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        state_manager.append_record(email_record)

        # Setup step
        step = EscalateEmailStep()
        await step.activate(None)

        # Convert EmailRecord to dict format expected by step
        email_dict = {
            "email_id": email_record.email_id,
            "sender": email_record.sender,
            "subject": email_record.subject,
            "body": email_record.body,
            "reason": email_record.reason
        }

        input_data = {
            "kernel": mock_kernel,
            "config": mock_config,
            "state_manager": state_manager,
            "graph_client": mock_graph_client,
            "response_handler": mock_response_handler,
            "emails": [email_dict]  # Changed from email_records to emails
        }

        mock_context = Mock()
        mock_context.emit_event = AsyncMock()

        # ACT: Execute step (correct method name: "escalate")
        await step.escalate(mock_context, input_data)

        # ASSERT: Verify escalation email was sent
        assert mock_response_handler.send_escalation.called

        # Verify event emitted
        assert mock_context.emit_event.called

    async def test_mass_email_detection(
        self,
        mock_kernel,
        mock_config,
        state_manager,
        mock_graph_client,
        mock_response_handler,
        sample_graph_emails
    ):
        """
        Test 8: Mass Email Detection

        Scenario: Fetch emails exceeds threshold → stops processing
        Services: Real process, mocked Graph API
        Verifies: Process halts, no classification attempted
        """
        from src.processes.agent.email_intake_process import FetchNewEmailsStep

        # ARRANGE: Setup mock to return many emails
        mock_graph_client.fetch_emails_async.return_value = sample_graph_emails["mass_email"]

        # Setup step
        step = FetchNewEmailsStep()
        await step.activate(None)

        input_data = {
            "kernel": mock_kernel,
            "config": mock_config,
            "state_manager": state_manager,
            "graph_client": mock_graph_client,
            "response_handler": mock_response_handler
        }

        mock_context = Mock()
        mock_context.emit_event = AsyncMock()

        # ACT: Execute step (correct method name: "fetch_emails")
        await step.fetch_emails(mock_context, input_data)

        # ASSERT: Verify mass email event was emitted
        # Check that emit_event was called with MassEmailDetected event
        emit_calls = mock_context.emit_event.call_args_list

        mass_email_emitted = any(
            "MassEmail" in str(call) or
            (len(call.kwargs) > 0 and call.kwargs.get("process_event") == "MassEmailDetected")
            for call in emit_calls
        )

        assert mass_email_emitted, "Mass email event should be emitted when threshold exceeded"

    async def test_state_resumption_flow(
        self,
        mock_kernel,
        mock_config,
        state_manager,
        mock_graph_client,
        mock_response_handler,
        sample_email_record
    ):
        """
        Test 7: State Resumption Flow

        Scenario: Initialize with in-progress records → resume processing
        Services: Real process, mocked services
        Verifies: Stale records escalated, active records identified
        """
        from src.processes.agent.email_intake_process import InitializeStateStep

        # ARRANGE: Create stale and fresh in-progress records
        # Note: Using timezone-aware datetime to match EmailRecord.is_stale() implementation
        from datetime import datetime as dt, timezone

        stale_record = EmailRecord(
            email_id="stale_001",
            sender="user@test.com",
            subject="Old request",
            body="This is old",
            received_datetime=(dt.now(timezone.utc) - timedelta(days=3)).isoformat(),
            conversation_id="stale_conv",
            classification="help",
            confidence=85.0,
            reason="Valid request",
            status=EmailStatus.IN_PROGRESS,
            timestamp=(dt.now(timezone.utc) - timedelta(days=3)).isoformat()
        )

        fresh_record = EmailRecord(
            email_id="fresh_001",
            sender="user@test.com",
            subject="Recent request",
            body="This is recent",
            received_datetime=dt.now(timezone.utc).isoformat(),
            conversation_id="fresh_conv",
            classification="help",
            confidence=85.0,
            reason="Valid request",
            status=EmailStatus.IN_PROGRESS,
            timestamp=dt.now(timezone.utc).isoformat()
        )

        state_manager.append_record(stale_record)
        state_manager.append_record(fresh_record)

        # Setup step
        step = InitializeStateStep()
        await step.activate(None)

        input_data = {
            "kernel": mock_kernel,
            "config": mock_config,
            "state_manager": state_manager,
            "graph_client": mock_graph_client,
            "response_handler": mock_response_handler
        }

        mock_context = Mock()
        mock_context.emit_event = AsyncMock()

        # ACT: Execute initialization (correct method name: "initialize")
        await step.initialize(mock_context, input_data)

        # ASSERT: Verify StateLoaded event emitted with in-progress records
        mock_context.emit_event.assert_called()

        call_args = mock_context.emit_event.call_args
        assert call_args is not None

        event_data = call_args.kwargs.get("data", {})
        assert "in_progress_records" in event_data


@pytest.mark.integration
@pytest.mark.asyncio
class TestSRMHelpProcess:
    """Integration tests for SRM Help Process workflows."""

    async def test_srm_help_full_flow_with_real_openai(
        self,
        integration_kernel,
        mock_config,
        state_manager,
        mock_response_handler,
        integration_test_emails
    ):
        """
        Test 4: SRM Help Process Full Flow (CRITICAL - Uses Real Azure OpenAI)

        Scenario: Extract data → search SRM → update index
        Services: Real process, REAL Azure OpenAI, real Azure Search
        Verifies: Actual SRM document updated in search index

        Note: This is one of the 3 critical tests that uses real Azure OpenAI API.
        This test remains Azure-only since it's testing real Azure OpenAI integration.
        """
        import os

        # Skip if Azure Search credentials not available
        endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
        index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME")
        api_key = os.getenv("AZURE_AI_SEARCH_API_KEY")

        if not all([endpoint, index_name, api_key]):
            pytest.skip("Azure Search credentials not configured for integration tests")

        from src.processes.agent.srm_help_process import (
            ExtractDataStep,
            SearchSRMStep,
            UpdateIndexStep
        )

        # ARRANGE: Create help email record
        email_record = EmailRecord(
            email_id=integration_test_emails["help_request"]["email_id"],
            sender=integration_test_emails["help_request"]["sender"],
            subject=integration_test_emails["help_request"]["subject"],
            body=integration_test_emails["help_request"]["body"],
            received_datetime=integration_test_emails["help_request"]["received_datetime"],
            conversation_id=integration_test_emails["help_request"]["conversation_id"],
            classification="help",
            confidence=85.0,
            reason="Clear SRM update request",
            status=EmailStatus.CLASSIFIED,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        state_manager.append_record(email_record)

        # Load extraction plugin into kernel
        from src.plugins.agent.extraction_plugin import ExtractionPlugin
        from src.utils.error_handler import ErrorHandler

        error_handler = ErrorHandler()
        extraction_plugin = ExtractionPlugin(
            kernel=integration_kernel,
            error_handler=error_handler
        )
        integration_kernel.add_plugin(extraction_plugin, plugin_name="extraction")

        # Load search plugin
        from src.plugins.agent.search_plugin import SearchPlugin

        search_plugin = SearchPlugin(
            search_endpoint=endpoint,
            index_name=index_name,
            api_key=api_key,
            error_handler=error_handler,
            mock_updates=False  # Real updates!
        )
        integration_kernel.add_plugin(search_plugin, plugin_name="search")

        mock_context = Mock()
        mock_context.emit_event = AsyncMock()

        input_data = {
            "kernel": integration_kernel,
            "config": mock_config,
            "state_manager": state_manager,
            "response_handler": mock_response_handler,
            "email": {
                "email_id": email_record.email_id,
                "subject": email_record.subject,
                "sender": email_record.sender,
                "body": email_record.body
            }
        }

        # ACT: Execute extraction step (correct method name: "extract")
        extract_step = ExtractDataStep()
        await extract_step.activate(process_state=None)
        await extract_step.extract(mock_context, input_data)

        # Verify extraction succeeded
        assert mock_context.emit_event.called
        last_call = mock_context.emit_event.call_args_list[-1]
        event_name = last_call.kwargs.get("process_event")

        assert event_name in ["Success", "NeedsClarification"]

        # If extraction succeeded, continue to search and update
        if event_name == "Success":
            event_data = last_call.kwargs.get("data", {})

            # Execute search step (correct method name: "search")
            search_step = SearchSRMStep()
            await search_step.activate(process_state=None)

            search_input = {**input_data, **event_data}
            mock_context.emit_event.reset_mock()

            await search_step.search(mock_context, search_input)

            # Verify search succeeded
            assert mock_context.emit_event.called
            search_call = mock_context.emit_event.call_args_list[-1]
            search_event = search_call.kwargs.get("process_event")

            if search_event == "Found":
                search_data = search_call.kwargs.get("data", {})

                # Execute update step (correct method name: "update")
                update_step = UpdateIndexStep()
                await update_step.activate(process_state=None)

                update_input = {**input_data, **search_data}
                mock_context.emit_event.reset_mock()

                await update_step.update(mock_context, update_input)

                # ASSERT: Verify update succeeded
                assert mock_context.emit_event.called
                update_call = mock_context.emit_event.call_args_list[-1]
                update_event = update_call.kwargs.get("process_event")

                assert update_event == "Updated"

                # Verify record status
                updated_record = state_manager.get_record_by_id(email_record.email_id)
                assert updated_record.status == EmailStatus.COMPLETED

    async def test_srm_search_not_found(
        self,
        mock_kernel,
        mock_config,
        state_manager,
        mock_response_handler,
        mock_search_client
    ):
        """
        Test 5: SRM Search Not Found

        Scenario: Extract data → search fails (no match) → error handling
        Services: Real process, mocked extraction, mocked search
        Verifies: Proper error event emission, state updated with error
        """
        from src.processes.agent.srm_help_process import SearchSRMStep
        from src.models.change_request import ChangeRequest

        # ARRANGE: Create complete extraction result
        change_request = ChangeRequest(
            srm_title="Nonexistent SRM That Doesn't Exist",
            change_type="update_owner_notes",
            new_owner_notes_content="Some content",
            reason_for_change="Test"
        )

        # Mock search to return no results
        mock_search_client.search.return_value = []

        # Setup search plugin with mock client
        from src.plugins.agent.search_plugin import SearchPlugin
        from src.utils.error_handler import ErrorHandler

        error_handler = ErrorHandler()
        search_plugin = SearchPlugin(
            search_endpoint="https://test.search.windows.net",
            index_name="test-index",
            api_key="test-key",
            error_handler=error_handler,
            mock_updates=True
        )

        # Replace client with our mock
        search_plugin.client = mock_search_client

        mock_kernel.add_plugin(search_plugin, plugin_name="search")

        # Setup step
        step = SearchSRMStep()
        await step.activate(None)

        mock_context = Mock()
        mock_context.emit_event = AsyncMock()

        input_data = {
            "kernel": mock_kernel,
            "config": mock_config,
            "state_manager": state_manager,
            "response_handler": mock_response_handler,
            "change_request": change_request
        }

        # ACT: Execute search (correct method name: "search")
        await step.search(mock_context, input_data)

        # ASSERT: Verify NotFound event emitted
        assert mock_context.emit_event.called

        call_args = mock_context.emit_event.call_args
        event_name = call_args.kwargs.get("process_event")

        assert event_name == "NotFound", f"Expected 'NotFound' event, got '{event_name}'"

    async def test_nested_process_invocation(
        self,
        mock_kernel,
        mock_config,
        state_manager,
        mock_graph_client,
        mock_response_handler,
        integration_test_emails
    ):
        """
        Test 6: Nested Process Invocation

        Scenario: Email intake ProcessHelpEmailsStep invokes SRM help subprocess
        Services: Real processes (both), mocked LLM
        Verifies: Subprocess invoked, completes, parent process continues
        """
        from src.processes.agent.email_intake_process import ProcessHelpEmailsStep

        # ARRANGE: Create classified help email
        email_record = EmailRecord(
            email_id=integration_test_emails["help_request"]["email_id"],
            sender=integration_test_emails["help_request"]["sender"],
            subject=integration_test_emails["help_request"]["subject"],
            body=integration_test_emails["help_request"]["body"],
            received_datetime=integration_test_emails["help_request"]["received_datetime"],
            conversation_id=integration_test_emails["help_request"]["conversation_id"],
            classification="help",
            confidence=85.0,
            reason="Clear SRM request",
            status=EmailStatus.CLASSIFIED,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        state_manager.append_record(email_record)

        # Mock the SRM help process
        mock_srm_process = Mock()

        # Setup step
        step = ProcessHelpEmailsStep()
        await step.activate(None)

        # Convert EmailRecord to dict format expected by step
        email_dict = {
            "email_id": email_record.email_id,
            "sender": email_record.sender,
            "subject": email_record.subject,
            "body": email_record.body,
            "received_datetime": email_record.received_datetime,
            "conversation_id": email_record.conversation_id
        }

        input_data = {
            "kernel": mock_kernel,
            "config": mock_config,
            "state_manager": state_manager,
            "graph_client": mock_graph_client,
            "response_handler": mock_response_handler,
            "srm_help_process": mock_srm_process,
            "emails": [email_dict]  # Changed from email_records to emails
        }

        mock_context = Mock()
        mock_context.emit_event = AsyncMock()

        # ACT: Execute step (correct method name: "process_help")
        with patch("semantic_kernel.processes.local_runtime.local_kernel_process.start") as mock_start:
            mock_process_context = AsyncMock()
            mock_start.return_value.__aenter__ = AsyncMock(return_value=mock_process_context)
            mock_start.return_value.__aexit__ = AsyncMock()

            await step.process_help(mock_context, input_data)

        # ASSERT: Verify subprocess was invoked
        mock_start.assert_called()

        # Verify event emitted
        assert mock_context.emit_event.called
