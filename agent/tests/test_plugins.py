"""
Unit tests for agent plugins.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch

from ..plugins.email_plugin import EmailPlugin
from ..plugins.state_plugin import StatePlugin
from ..plugins.search_plugin import SearchPlugin
from ..plugins.classification_plugin import ClassificationPlugin
from ..plugins.extraction_plugin import ExtractionPlugin
from ..utils.graph_client import GraphClient
from ..utils.state_manager import StateManager
from ..utils.error_handler import ErrorHandler
from ..models.email_record import EmailRecord, EmailStatus


class TestEmailPlugin:
    """Test cases for EmailPlugin."""
    
    @pytest.fixture
    def mock_graph_client(self):
        """Mock GraphClient for testing."""
        client = Mock(spec=GraphClient)
        client.authenticate.return_value = True
        client.fetch_emails.return_value = []
        client.send_email.return_value = True
        client.reply_to_email.return_value = True
        client.forward_email.return_value = True
        return client
    
    @pytest.fixture
    def mock_error_handler(self):
        """Mock ErrorHandler for testing."""
        handler = Mock(spec=ErrorHandler)
        handler.with_retry = lambda error_type: lambda func: func
        return handler
    
    @pytest.fixture
    def email_plugin(self, mock_graph_client, mock_error_handler):
        """EmailPlugin instance for testing."""
        return EmailPlugin(mock_graph_client, mock_error_handler)
    
    def test_authenticate_success(self, email_plugin, mock_graph_client):
        """Test successful authentication."""
        mock_graph_client.authenticate.return_value = True
        
        result = email_plugin.authenticate()
        
        assert "Successfully authenticated" in result
        mock_graph_client.authenticate.assert_called_once()
    
    def test_authenticate_failure(self, email_plugin, mock_graph_client):
        """Test authentication failure."""
        mock_graph_client.authenticate.return_value = False
        
        result = email_plugin.authenticate()
        
        assert "Failed to authenticate" in result
    
    def test_fetch_emails(self, email_plugin, mock_graph_client):
        """Test fetching emails."""
        mock_emails = [
            {
                "email_id": "test_1",
                "sender": "user@test.com",
                "subject": "Test Email",
                "body": "Test body",
                "received_datetime": "2024-01-01T00:00:00Z"
            }
        ]
        mock_graph_client.fetch_emails.return_value = mock_emails
        
        result = email_plugin.fetch_emails(days_back=7, processed_email_ids="")
        
        emails = json.loads(result)
        assert len(emails) == 1
        assert emails[0]["email_id"] == "test_1"
    
    def test_send_email(self, email_plugin, mock_graph_client):
        """Test sending email."""
        mock_graph_client.send_email.return_value = True
        
        result = email_plugin.send_email(
            to_address="test@example.com",
            subject="Test Subject",
            body="Test Body"
        )
        
        assert "sent successfully" in result
        mock_graph_client.send_email.assert_called_once()


class TestStatePlugin:
    """Test cases for StatePlugin."""
    
    @pytest.fixture
    def mock_state_manager(self):
        """Mock StateManager for testing."""
        manager = Mock(spec=StateManager)
        manager.read_state.return_value = []
        manager.append_record.return_value = None
        manager.update_record.return_value = True
        manager.find_record.return_value = None
        return manager
    
    @pytest.fixture
    def mock_error_handler(self):
        """Mock ErrorHandler for testing."""
        return Mock(spec=ErrorHandler)
    
    @pytest.fixture
    def state_plugin(self, mock_state_manager, mock_error_handler):
        """StatePlugin instance for testing."""
        return StatePlugin(mock_state_manager, mock_error_handler)
    
    def test_load_state_empty(self, state_plugin, mock_state_manager):
        """Test loading empty state."""
        mock_state_manager.read_state.return_value = []
        
        result = state_plugin.load_state()
        
        records = json.loads(result)
        assert records == []
    
    def test_load_state_with_records(self, state_plugin, mock_state_manager):
        """Test loading state with records."""
        mock_record = EmailRecord(
            email_id="test_1",
            sender="user@test.com",
            subject="Test",
            body="Test body",
            received_datetime="2024-01-01T00:00:00Z"
        )
        mock_state_manager.read_state.return_value = [mock_record]
        
        result = state_plugin.load_state()
        
        records = json.loads(result)
        assert len(records) == 1
        assert records[0]["email_id"] == "test_1"
    
    def test_add_email_record(self, state_plugin, mock_state_manager):
        """Test adding email record."""
        email_data = {
            "email_id": "test_1",
            "sender": "user@test.com",
            "subject": "Test",
            "body": "Test body",
            "received_datetime": "2024-01-01T00:00:00Z"
        }
        
        result = state_plugin.add_email_record(json.dumps(email_data))
        
        assert "added to state" in result
        mock_state_manager.append_record.assert_called_once()
    
    def test_update_email_record(self, state_plugin, mock_state_manager):
        """Test updating email record."""
        mock_state_manager.update_record.return_value = True
        
        updates = {"status": "classified", "classification": "help"}
        result = state_plugin.update_email_record("test_1", json.dumps(updates))
        
        assert "updated successfully" in result
        mock_state_manager.update_record.assert_called_once()


class TestSearchPlugin:
    """Test cases for SearchPlugin."""
    
    @pytest.fixture
    def mock_error_handler(self):
        """Mock ErrorHandler for testing."""
        handler = Mock(spec=ErrorHandler)
        handler.with_retry = lambda error_type: lambda func: func
        return handler
    
    @pytest.fixture
    def search_plugin(self, mock_error_handler):
        """SearchPlugin instance for testing."""
        return SearchPlugin(
            search_endpoint="https://test.search.windows.net",
            index_name="test-index",
            api_key="test-key",
            error_handler=mock_error_handler
        )
    
    def test_search_srm(self, search_plugin):
        """Test SRM search functionality."""
        result = search_plugin.search_srm("Application Server", top_k=5)
        
        # Should return mock results
        results = json.loads(result)
        assert isinstance(results, list)
        if results:  # Mock returns one result
            assert "srm_id" in results[0]
    
    def test_get_srm_document(self, search_plugin):
        """Test getting SRM document by ID."""
        result = search_plugin.get_srm_document("srm_001")
        
        document = json.loads(result)
        assert "srm_id" in document
        assert document["srm_id"] == "srm_001"
    
    def test_update_srm_document(self, search_plugin):
        """Test updating SRM document."""
        updates = {"owner_notes": "Updated notes"}
        
        result = search_plugin.update_srm_document("srm_001", json.dumps(updates))
        
        assert "updated successfully" in result


class TestClassificationPlugin:
    """Test cases for ClassificationPlugin."""
    
    @pytest.fixture
    def mock_kernel(self):
        """Mock Kernel for testing."""
        kernel = Mock()
        
        # Mock classification function
        mock_function = AsyncMock()
        mock_function.invoke.return_value = json.dumps({
            "classification": "help",
            "confidence": 95,
            "reason": "Clear SRM update request"
        })
        
        kernel.get_function.return_value = mock_function
        return kernel
    
    @pytest.fixture
    def mock_error_handler(self):
        """Mock ErrorHandler for testing."""
        handler = Mock(spec=ErrorHandler)
        handler.with_retry = lambda error_type: lambda func: func
        return handler
    
    @pytest.fixture
    def classification_plugin(self, mock_kernel, mock_error_handler):
        """ClassificationPlugin instance for testing."""
        return ClassificationPlugin(mock_kernel, mock_error_handler)
    
    @pytest.mark.asyncio
    async def test_classify_email_help(self, classification_plugin):
        """Test classifying help email."""
        result = await classification_plugin.classify_email(
            subject="SRM Update Request",
            sender="user@test.com",
            body="Please update the Application Server SRM notes"
        )
        
        classification = json.loads(result)
        assert classification["classification"] == "help"
        assert classification["confidence"] == 95
    
    def test_validate_classification_high_confidence(self, classification_plugin):
        """Test validation with high confidence."""
        classification_result = json.dumps({
            "classification": "help",
            "confidence": 95,
            "reason": "Clear request"
        })
        
        result = classification_plugin.validate_classification(classification_result, 70)
        
        validated = json.loads(result)
        assert validated["classification"] == "help"  # Should remain unchanged
    
    def test_validate_classification_low_confidence(self, classification_plugin):
        """Test validation with low confidence."""
        classification_result = json.dumps({
            "classification": "help",
            "confidence": 50,
            "reason": "Unclear request"
        })
        
        result = classification_plugin.validate_classification(classification_result, 70)
        
        validated = json.loads(result)
        assert validated["classification"] == "escalate"  # Should be overridden


class TestExtractionPlugin:
    """Test cases for ExtractionPlugin."""
    
    @pytest.fixture
    def mock_kernel(self):
        """Mock Kernel for testing."""
        kernel = Mock()
        
        # Mock extraction function
        mock_function = AsyncMock()
        mock_function.invoke.return_value = json.dumps({
            "srm_title": "Application Server SRM",
            "change_type": "update_owner_notes",
            "change_description": "Update contact information",
            "new_owner_notes_content": "Contact platform-team@company.com",
            "recommendation_logic": None,
            "exclusion_criteria": None,
            "requester_team": "Platform Team",
            "reason_for_change": "Centralizing requests",
            "completeness_score": 95
        })
        
        kernel.get_function.return_value = mock_function
        return kernel
    
    @pytest.fixture
    def mock_error_handler(self):
        """Mock ErrorHandler for testing."""
        handler = Mock(spec=ErrorHandler)
        handler.with_retry = lambda error_type: lambda func: func
        return handler
    
    @pytest.fixture
    def extraction_plugin(self, mock_kernel, mock_error_handler):
        """ExtractionPlugin instance for testing."""
        return ExtractionPlugin(mock_kernel, mock_error_handler)
    
    @pytest.mark.asyncio
    async def test_extract_change_request(self, extraction_plugin):
        """Test extracting change request data."""
        result = await extraction_plugin.extract_change_request(
            subject="SRM Update Request",
            sender="user@platform.com",
            body="Please update Application Server SRM owner notes"
        )
        
        extracted = json.loads(result)
        assert extracted["srm_title"] == "Application Server SRM"
        assert extracted["completeness_score"] == 95
    
    def test_validate_completeness_complete(self, extraction_plugin):
        """Test validation of complete data."""
        extracted_data = json.dumps({
            "srm_title": "Application Server SRM",
            "change_type": "update_owner_notes",
            "new_owner_notes_content": "Updated notes",
            "completeness_score": 95
        })
        
        result = extraction_plugin.validate_completeness(extracted_data)
        
        validation = json.loads(result)
        assert validation["is_complete"] is True
        assert validation["completeness_score"] == 95
    
    def test_validate_completeness_incomplete(self, extraction_plugin):
        """Test validation of incomplete data."""
        extracted_data = json.dumps({
            "srm_title": None,
            "change_type": None,
            "completeness_score": 20
        })
        
        result = extraction_plugin.validate_completeness(extracted_data)
        
        validation = json.loads(result)
        assert validation["is_complete"] is False
        assert validation["needs_clarification"] is True
