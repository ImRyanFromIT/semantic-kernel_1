"""
Unit tests for agent processes.
"""

import pytest
from unittest.mock import Mock, AsyncMock

from src.processes.agent.email_intake_process import (
    EmailIntakeProcess,
    InitializeStateStep,
    FetchNewEmailsStep,
    ClassifyEmailsStep
)
from src.processes.agent.srm_help_process import (
    SrmHelpProcess,
    ExtractDataStep,
    SearchSRMStep
)


class TestEmailIntakeProcess:
    """Test cases for EmailIntakeProcess."""
    
    def test_create_process(self):
        """Test process creation."""
        process_builder = EmailIntakeProcess.create_process()
        
        assert process_builder is not None
        # Process builder should be configured with steps and transitions
    
    def test_process_events_defined(self):
        """Test that process events are properly defined."""
        events = EmailIntakeProcess.ProcessEvents
        
        assert hasattr(events, 'StartProcess')
        assert hasattr(events, 'ProcessComplete')
        assert hasattr(events, 'ProcessError')
        assert hasattr(events, 'MassEmailDetected')


class TestInitializeStateStep:
    """Test cases for InitializeStateStep."""
    
    @pytest.fixture
    def mock_context(self):
        """Mock KernelProcessStepContext."""
        context = Mock()
        context.get_state_manager.return_value = Mock()
        context.emit_event = AsyncMock()
        return context
    
    @pytest.mark.asyncio
    async def test_initialize_state_success(self, mock_context):
        """Test successful state initialization."""
        step = InitializeStateStep()
        mock_state_manager = mock_context.get_state_manager.return_value
        mock_state_manager.read_state.return_value = []
        
        await step.initialize_state(mock_context)
        
        mock_context.emit_event.assert_called_once()
        args = mock_context.emit_event.call_args[0]
        assert args[0] == InitializeStateStep.OutputEvents.StateLoaded
    
    @pytest.mark.asyncio
    async def test_initialize_state_error(self, mock_context):
        """Test state initialization error handling."""
        step = InitializeStateStep()
        mock_state_manager = mock_context.get_state_manager.return_value
        mock_state_manager.read_state.side_effect = Exception("State file error")
        
        await step.initialize_state(mock_context)
        
        mock_context.emit_event.assert_called_once()
        args = mock_context.emit_event.call_args[0]
        assert args[0] == InitializeStateStep.OutputEvents.StateError


class TestFetchNewEmailsStep:
    """Test cases for FetchNewEmailsStep."""
    
    @pytest.fixture
    def mock_context(self):
        """Mock KernelProcessStepContext."""
        context = Mock()
        
        # Mock email plugin
        mock_email_plugin = AsyncMock()
        mock_email_plugin.fetch_emails.return_value = '[]'
        context.get_email_plugin.return_value = mock_email_plugin
        
        # Mock state manager
        mock_state_manager = Mock()
        mock_state_manager.read_state.return_value = []
        context.get_state_manager.return_value = mock_state_manager
        
        context.emit_event = AsyncMock()
        return context
    
    @pytest.mark.asyncio
    async def test_fetch_new_emails_success(self, mock_context):
        """Test successful email fetching."""
        step = FetchNewEmailsStep()
        
        await step.fetch_new_emails(mock_context)
        
        mock_context.emit_event.assert_called_once()
        args = mock_context.emit_event.call_args[0]
        assert args[0] == FetchNewEmailsStep.OutputEvents.EmailsFetched
    
    @pytest.mark.asyncio
    async def test_fetch_new_emails_error(self, mock_context):
        """Test email fetching error handling."""
        step = FetchNewEmailsStep()
        mock_email_plugin = mock_context.get_email_plugin.return_value
        mock_email_plugin.fetch_emails.side_effect = Exception("API error")
        
        await step.fetch_new_emails(mock_context)
        
        mock_context.emit_event.assert_called_once()
        args = mock_context.emit_event.call_args[0]
        assert args[0] == FetchNewEmailsStep.OutputEvents.FetchError


class TestClassifyEmailsStep:
    """Test cases for ClassifyEmailsStep."""
    
    @pytest.fixture
    def mock_context(self):
        """Mock KernelProcessStepContext."""
        context = Mock()
        
        # Mock classification plugin
        mock_classification_plugin = AsyncMock()
        mock_classification_plugin.classify_email.return_value = '{"classification": "help", "confidence": 95, "reason": "Clear request"}'
        mock_classification_plugin.validate_classification.return_value = '{"classification": "help", "confidence": 95, "reason": "Clear request"}'
        context.get_classification_plugin.return_value = mock_classification_plugin
        
        # Mock state manager
        mock_state_manager = Mock()
        context.get_state_manager.return_value = mock_state_manager
        
        # Mock config
        mock_config = Mock()
        mock_config.confidence_threshold_for_classification = 70
        context.get_config.return_value = mock_config
        
        context.emit_event = AsyncMock()
        return context
    
    @pytest.mark.asyncio
    async def test_classify_emails_success(self, mock_context):
        """Test successful email classification."""
        step = ClassifyEmailsStep()
        
        data = {
            "new_emails": [
                {
                    "email_id": "test_1",
                    "sender": "user@test.com",
                    "subject": "SRM Update",
                    "body": "Please update SRM",
                    "received_datetime": "2024-01-01T00:00:00Z"
                }
            ]
        }
        
        await step.classify_emails(mock_context, data)
        
        mock_context.emit_event.assert_called_once()
        args = mock_context.emit_event.call_args[0]
        assert args[0] == ClassifyEmailsStep.OutputEvents.EmailsClassified


class TestSrmHelpProcess:
    """Test cases for SrmHelpProcess."""
    
    def test_create_process(self):
        """Test process creation."""
        process_builder = SrmHelpProcess.create_process()
        
        assert process_builder is not None
    
    def test_process_events_defined(self):
        """Test that process events are properly defined."""
        events = SrmHelpProcess.ProcessEvents
        
        assert hasattr(events, 'StartProcess')
        assert hasattr(events, 'ProcessComplete')
        assert hasattr(events, 'ProcessError')
        assert hasattr(events, 'ClarificationNeeded')


class TestExtractChangeRequestStep:
    """Test cases for ExtractChangeRequestStep."""
    
    @pytest.fixture
    def mock_context(self):
        """Mock KernelProcessStepContext."""
        context = Mock()
        
        # Mock extraction plugin
        mock_extraction_plugin = AsyncMock()
        mock_extraction_plugin.extract_change_request.return_value = '{"srm_title": "Test SRM", "completeness_score": 95}'
        context.get_extraction_plugin.return_value = mock_extraction_plugin
        
        # Mock state manager
        mock_state_manager = Mock()
        context.get_state_manager.return_value = mock_state_manager
        
        context.emit_event = AsyncMock()
        return context
    
    @pytest.mark.asyncio
    async def test_extract_change_request_success(self, mock_context):
        """Test successful data extraction."""
        step = ExtractChangeRequestStep()
        
        data = {
            "email": {
                "email_id": "test_1",
                "subject": "SRM Update",
                "sender": "user@test.com",
                "body": "Please update SRM"
            }
        }
        
        await step.extract_change_request_details(mock_context, data)
        
        mock_context.emit_event.assert_called_once()
        args = mock_context.emit_event.call_args[0]
        assert args[0] == ExtractChangeRequestStep.OutputEvents.DataExtracted


class TestValidateCompletenessStep:
    """Test cases for ValidateCompletenessStep."""
    
    @pytest.fixture
    def mock_context(self):
        """Mock KernelProcessStepContext."""
        context = Mock()
        
        # Mock extraction plugin
        mock_extraction_plugin = Mock()
        mock_extraction_plugin.validate_completeness.return_value = '{"is_complete": true, "completeness_score": 95}'
        context.get_extraction_plugin.return_value = mock_extraction_plugin
        
        context.emit_event = AsyncMock()
        return context
    
    @pytest.mark.asyncio
    async def test_validate_completeness_complete(self, mock_context):
        """Test validation of complete data."""
        step = ValidateCompletenessStep()
        
        data = {
            "email": {"email_id": "test_1"},
            "extracted_data": '{"srm_title": "Test SRM", "completeness_score": 95}'
        }
        
        await step.validate_completeness(mock_context, data)
        
        mock_context.emit_event.assert_called_once()
        args = mock_context.emit_event.call_args[0]
        assert args[0] == ValidateCompletenessStep.OutputEvents.DataComplete
    
    @pytest.mark.asyncio
    async def test_validate_completeness_incomplete(self, mock_context):
        """Test validation of incomplete data."""
        step = ValidateCompletenessStep()
        
        # Mock incomplete validation result
        mock_extraction_plugin = mock_context.get_extraction_plugin.return_value
        mock_extraction_plugin.validate_completeness.return_value = '{"is_complete": false, "completeness_score": 30}'
        
        data = {
            "email": {"email_id": "test_1"},
            "extracted_data": '{"srm_title": null, "completeness_score": 30}'
        }
        
        await step.validate_completeness(mock_context, data)
        
        mock_context.emit_event.assert_called_once()
        args = mock_context.emit_event.call_args[0]
        assert args[0] == ValidateCompletenessStep.OutputEvents.DataIncomplete
