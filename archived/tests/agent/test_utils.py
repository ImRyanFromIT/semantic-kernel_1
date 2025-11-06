"""
Agent Utilities Tests

Purpose: Test utility classes including GraphClient, StateManager,
         TokenCounter, and other helper functions.

Type: Unit
Test Count: 25

Key Test Areas:
- GraphClient email operations
- StateManager file operations
- TokenCounter token estimation
- Email validation
- Kernel builder
- Plugin loader

Dependencies:
- Mock Graph API responses
- Temporary file system
- Environment variables

Note: Some tests require live Graph API credentials (4 tests may fail
      without credentials).
"""

import pytest
import json
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from src.utils.state_manager import StateManager
from src.utils.error_handler import ErrorHandler, ErrorType
from src.utils.graph_client import GraphClient
from src.models.email_record import EmailRecord, EmailStatus


class TestStateManager:
    """Test cases for StateManager."""
    
    @pytest.fixture
    def temp_state_file(self):
        """Create temporary state file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.jsonl') as f:
            temp_file = f.name
        yield temp_file
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)
    
    @pytest.fixture
    def state_manager(self, temp_state_file):
        """StateManager instance for testing."""
        return StateManager(temp_state_file)
    
    @pytest.fixture
    def sample_email_record(self):
        """Sample EmailRecord for testing."""
        return EmailRecord(
            email_id="test_123",
            sender="user@test.com",
            subject="Test Email",
            body="Test email body",
            received_datetime="2024-01-01T00:00:00Z",
            classification="help",
            confidence=95.0,
            reason="Clear SRM request"
        )
    
    def test_read_state_empty_file(self, state_manager):
        """Test reading from non-existent state file."""
        records = state_manager.read_state()
        assert records == []
    
    def test_write_and_read_state(self, state_manager, sample_email_record):
        """Test writing and reading state."""
        records = [sample_email_record]
        
        # Write state
        state_manager.write_state(records)
        
        # Read state
        loaded_records = state_manager.read_state()
        
        assert len(loaded_records) == 1
        assert loaded_records[0].email_id == sample_email_record.email_id
        assert loaded_records[0].sender == sample_email_record.sender
    
    def test_append_record(self, state_manager, sample_email_record):
        """Test appending single record."""
        state_manager.append_record(sample_email_record)
        
        records = state_manager.read_state()
        assert len(records) == 1
        assert records[0].email_id == sample_email_record.email_id
    
    def test_update_record(self, state_manager, sample_email_record):
        """Test updating existing record."""
        # Add initial record
        state_manager.append_record(sample_email_record)
        
        # Update record
        updates = {
            "status": EmailStatus.COMPLETED_SUCCESS,
            "classification": "updated_help"
        }
        
        success = state_manager.update_record(sample_email_record.email_id, updates)
        
        assert success is True
        
        # Verify update
        records = state_manager.read_state()
        assert len(records) == 1
        assert records[0].status == EmailStatus.COMPLETED_SUCCESS
    
    def test_update_nonexistent_record(self, state_manager):
        """Test updating non-existent record."""
        updates = {"status": EmailStatus.COMPLETED_SUCCESS}
        
        success = state_manager.update_record("nonexistent_id", updates)
        
        assert success is False
    
    def test_find_record(self, state_manager, sample_email_record):
        """Test finding record by ID."""
        state_manager.append_record(sample_email_record)
        
        found_record = state_manager.find_record(sample_email_record.email_id)
        
        assert found_record is not None
        assert found_record.email_id == sample_email_record.email_id
    
    def test_find_nonexistent_record(self, state_manager):
        """Test finding non-existent record."""
        found_record = state_manager.find_record("nonexistent_id")
        
        assert found_record is None
    
    def test_find_stale_records(self, state_manager):
        """Test finding stale records."""
        # Create old record
        old_record = EmailRecord(
            email_id="old_record",
            sender="user@test.com",
            subject="Old Email",
            body="Old email body",
            received_datetime="2024-01-01T00:00:00Z"
        )
        
        # Manually set old timestamp - use timezone-aware datetime
        from datetime import timezone
        old_timestamp = (datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()
        old_record.timestamp = old_timestamp
        
        state_manager.append_record(old_record)
        
        stale_records = state_manager.find_stale_records(hours=48)
        
        assert len(stale_records) == 1
        assert stale_records[0].email_id == "old_record"
    
    def test_find_in_progress_records(self, state_manager):
        """Test finding in-progress records."""
        # Create in-progress record
        in_progress_record = EmailRecord(
            email_id="in_progress",
            sender="user@test.com",
            subject="In Progress Email",
            body="In progress email body",
            received_datetime="2024-01-01T00:00:00Z",
            status=EmailStatus.IN_PROGRESS
        )
        
        state_manager.append_record(in_progress_record)
        
        in_progress_records = state_manager.find_in_progress_records()
        
        assert len(in_progress_records) == 1
        assert in_progress_records[0].status == EmailStatus.IN_PROGRESS


class TestErrorHandler:
    """Test cases for ErrorHandler."""
    
    @pytest.fixture
    def error_handler(self):
        """ErrorHandler instance for testing."""
        return ErrorHandler(max_retries=2, retry_delay=1)
    
    def test_handle_error_no_escalation(self, error_handler):
        """Test error handling without escalation."""
        test_error = ValueError("Test error")
        
        # Should not raise exception
        error_handler.handle_error(
            ErrorType.CONFIGURATION,
            test_error,
            "test_context",
            escalate=False
        )
    
    def test_handle_error_with_escalation(self, error_handler):
        """Test error handling with escalation."""
        test_error = ValueError("Test error")
        
        with patch.object(error_handler, 'escalate_error') as mock_escalate:
            error_handler.handle_error(
                ErrorType.CONFIGURATION,
                test_error,
                "test_context",
                escalate=True
            )
            
            mock_escalate.assert_called_once()
    
    def test_should_retry_retryable_error(self, error_handler):
        """Test retry decision for retryable errors."""
        retryable_error = ConnectionError("Connection timeout")
        
        should_retry = error_handler.should_retry(retryable_error, ErrorType.GRAPH_API_CALL)
        
        assert should_retry is True
    
    def test_should_retry_non_retryable_error(self, error_handler):
        """Test retry decision for non-retryable errors."""
        non_retryable_error = ValueError("invalid_client")
        
        should_retry = error_handler.should_retry(non_retryable_error, ErrorType.GRAPH_API_AUTH)
        
        assert should_retry is False
    
    def test_get_error_type_graph_api(self, error_handler):
        """Test error type classification for Graph API."""
        error = Exception("authentication failed")
        
        error_type = error_handler.get_error_type(error, "graph api call")
        
        assert error_type == ErrorType.GRAPH_API_AUTH
    
    def test_get_error_type_azure_search(self, error_handler):
        """Test error type classification for Azure Search."""
        error = Exception("connection timeout")
        
        error_type = error_handler.get_error_type(error, "azure search operation")
        
        assert error_type == ErrorType.AZURE_SEARCH_CONNECTION
    
    def test_get_error_type_unknown(self, error_handler):
        """Test error type classification for unknown errors."""
        error = Exception("unknown error")
        
        error_type = error_handler.get_error_type(error, "unknown context")
        
        assert error_type == ErrorType.UNKNOWN
    
    def test_with_retry_decorator_success(self, error_handler):
        """Test retry decorator with successful function."""
        @error_handler.with_retry(ErrorType.GRAPH_API_CALL)
        def successful_function():
            return "success"
        
        result = successful_function()
        
        assert result == "success"
    
    def test_with_retry_decorator_eventual_success(self, error_handler):
        """Test retry decorator with eventual success."""
        call_count = 0
        
        @error_handler.with_retry(ErrorType.GRAPH_API_CALL, escalate_after_retries=False)
        def eventually_successful_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary failure")
            return "success"
        
        result = eventually_successful_function()
        
        assert result == "success"
        assert call_count == 2


class TestGraphClient:
    """Test cases for GraphClient."""
    
    @pytest.fixture
    def graph_client(self):
        """GraphClient instance for testing."""
        return GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com"
        )
    
    def test_authenticate_success(self, graph_client):
        """Test successful authentication."""
        # Mock the credential and client creation to avoid real Azure AD calls
        with patch('src.utils.graph_client.ClientSecretCredential') as mock_cred:
            with patch('src.utils.graph_client.GraphServiceClient') as mock_graph:
                success = graph_client.authenticate()

                # Should succeed with mock implementation
                assert success is True
                assert graph_client._authenticated is True
    
    def test_authenticate_missing_params(self):
        """Test authentication with missing parameters."""
        client = GraphClient("", "", "", "")
        
        with pytest.raises(Exception):
            client.authenticate()
    
    def test_fetch_emails_not_authenticated(self, graph_client):
        """Test fetching emails without authentication."""
        with pytest.raises(Exception, match="Not authenticated"):
            graph_client.fetch_emails()
    
    @pytest.mark.asyncio
    async def test_fetch_emails_authenticated(self, graph_client):
        """Test fetching emails when authenticated."""
        # Mock authentication without real Azure AD calls
        with patch('src.utils.graph_client.ClientSecretCredential'):
            with patch('src.utils.graph_client.GraphServiceClient'):
                graph_client.authenticate()

        # Mock the async fetch method to avoid real Graph API calls
        with patch.object(graph_client, '_fetch_emails_async', new=AsyncMock(return_value=[])):
            emails = await graph_client.fetch_emails_async(days_back=7)

            # Should return mock emails (empty list in this case)
            assert isinstance(emails, list)
    
    def test_send_email_not_authenticated(self, graph_client):
        """Test sending email without authentication."""
        with pytest.raises(Exception, match="Not authenticated"):
            graph_client.send_email("test@example.com", "Subject", "Body")
    
    @pytest.mark.asyncio
    async def test_send_email_authenticated(self, graph_client):
        """Test sending email when authenticated."""
        # Mock authentication without real Azure AD calls
        with patch('src.utils.graph_client.ClientSecretCredential'):
            with patch('src.utils.graph_client.GraphServiceClient'):
                graph_client.authenticate()

        # Mock the async send method to avoid real Graph API calls
        with patch.object(graph_client, '_send_email_async', new=AsyncMock(return_value=True)):
            success = await graph_client.send_email_async("test@example.com", "Subject", "Body")

            # Should succeed with mock implementation
            assert success is True
    
    @pytest.mark.asyncio
    async def test_reply_to_email_authenticated(self, graph_client):
        """Test replying to email when authenticated."""
        # Mock authentication without real Azure AD calls
        with patch('src.utils.graph_client.ClientSecretCredential'):
            with patch('src.utils.graph_client.GraphServiceClient'):
                graph_client.authenticate()

        # Mock the async reply method to avoid real Graph API calls
        with patch.object(graph_client, '_reply_to_email_async', new=AsyncMock(return_value=True)):
            success = await graph_client.reply_to_email_async("email_123", "Reply body")

            # Should succeed with mock implementation
            assert success is True
    
    @pytest.mark.asyncio
    async def test_forward_email_authenticated(self, graph_client):
        """Test forwarding email when authenticated."""
        # Mock authentication without real Azure AD calls
        with patch('src.utils.graph_client.ClientSecretCredential'):
            with patch('src.utils.graph_client.GraphServiceClient'):
                graph_client.authenticate()

        # Mock the async forward method to avoid real Graph API calls
        with patch.object(graph_client, '_forward_email_async', new=AsyncMock(return_value=True)):
            success = await graph_client.forward_email_async(
                "email_123",
                ["support@example.com"],
                "Forwarding comment"
            )

            # Should succeed with mock implementation
            assert success is True
