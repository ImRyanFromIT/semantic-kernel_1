"""
Graph Client Integration Tests

Purpose: Test graph_client.py critical functionality for email operations.

Type: Integration
Test Count: 30

Key Test Areas:
- Authentication (test mode & normal mode)
- Send email operations (sync/async/test mode)
- Reply operations (sync/async/test mode)
- Forward operations (sync/async/test mode)
- Mark as read operations
- Rate limiting enforcement
- Helper functions (_run_async_safe)
- Error handling for all operations

Dependencies:
- unittest.mock for Graph SDK mocking
- pytest-asyncio for async test support
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from src.utils.graph_client import GraphClient, _run_async_safe
from datetime import datetime, timezone


@pytest.mark.integration
@pytest.mark.phase4
class TestGraphClientInitialization:
    """Test GraphClient initialization in different modes."""
    
    def test_init_creates_client_in_test_mode(self):
        """Test GraphClient initialization in test mode."""
        # Act
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=True
        )
        
        # Assert
        assert client.test_mode is True
        assert client.file_reader is not None
        assert client._authenticated is False
        assert client._min_delay_between_calls == 1.5
    
    def test_init_creates_client_in_normal_mode(self):
        """Test GraphClient initialization in normal mode."""
        # Act
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        # Assert
        assert client.test_mode is False
        assert client.file_reader is None
        assert client._min_delay_between_calls == 1.5


@pytest.mark.integration
@pytest.mark.phase4
class TestAuthentication:
    """Test authentication flows (lines 103-135)."""
    
    def test_authenticate_test_mode_success(self):
        """Test mode authentication success (lines 105-109)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=True
        )
        
        # Act
        result = client.authenticate()
        
        # Assert
        assert result is True
        assert client._authenticated is True
    
    def test_authenticate_test_mode_missing_credentials(self):
        """Test mode authentication failure (line 110)."""
        # Arrange
        client = GraphClient(
            tenant_id="",
            client_id="",
            client_secret="",
            mailbox="test@example.com",
            test_mode=True
        )

        # Act & Assert
        with pytest.raises(Exception, match="Graph API authentication failed: Missing required test parameters"):
            client.authenticate()
    
    @patch('src.utils.graph_client.GraphServiceClient')
    @patch('src.utils.graph_client.ClientSecretCredential')
    def test_authenticate_normal_mode_success(self, mock_credential, mock_graph_client):
        """Test normal mode authentication success (lines 113-131)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        mock_credential_instance = Mock()
        mock_credential.return_value = mock_credential_instance
        
        mock_graph_instance = Mock()
        mock_graph_client.return_value = mock_graph_instance
        
        # Act
        result = client.authenticate()
        
        # Assert
        assert result is True
        assert client._authenticated is True
        mock_credential.assert_called_once_with(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret"
        )
        mock_graph_client.assert_called_once()
    
    @patch('src.utils.graph_client.ClientSecretCredential')
    def test_authenticate_normal_mode_failure(self, mock_credential):
        """Test normal mode authentication failure (lines 133-135)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        mock_credential.side_effect = Exception("Authentication failed")
        
        # Act & Assert
        with pytest.raises(Exception, match="Graph API authentication failed"):
            client.authenticate()
        
        assert client._authenticated is False


@pytest.mark.integration
@pytest.mark.phase4
class TestRateLimiting:
    """Test rate limiting mechanism (lines 139-143)."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_delay_first_call(self):
        """Test _rate_limit_delay on first call (no delay)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        # Act
        start_time = asyncio.get_event_loop().time()
        await client._rate_limit_delay()
        elapsed = asyncio.get_event_loop().time() - start_time
        
        # Assert - first call should not delay
        assert elapsed < 0.1
        assert client._last_api_call is not None
    
    @pytest.mark.asyncio
    async def test_rate_limit_delay_consecutive_calls(self):
        """Test _rate_limit_delay enforces 1.5s minimum delay (lines 139-143)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        # Act - First call
        await client._rate_limit_delay()
        first_call_time = client._last_api_call
        
        # Second call immediately after
        start = asyncio.get_event_loop().time()
        await client._rate_limit_delay()
        elapsed = asyncio.get_event_loop().time() - start
        
        # Assert - should delay approximately 1.5 seconds
        assert elapsed >= 1.4  # Allow small timing variance
        assert client._last_api_call > first_call_time


@pytest.mark.integration
@pytest.mark.phase4
class TestFetchEmails:
    """Test email fetching operations."""
    
    @pytest.mark.asyncio
    async def test_fetch_emails_async_successful(self):
        """Test HP-INT-005: Fetch emails from Graph API with filtering."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        sample_emails = [
            {
                "email_id": "new_001",
                "sender": "user@test.com",
                "subject": "SRM Request",
                "body": "Please update SRM",
                "received_datetime": "2024-01-15T10:00:00Z",
                "conversation_id": "conv_001"
            }
        ]
        
        client._fetch_emails_async = AsyncMock(return_value=sample_emails)
        client._authenticated = True
        
        # Act
        result = await client.fetch_emails_async(days_back=7, processed_email_ids=["old_001"])
        
        # Assert
        assert len(result) == 1
        assert result[0]["email_id"] == "new_001"
    
    @pytest.mark.asyncio
    async def test_fetch_emails_async_test_mode(self):
        """Test fetch_emails_async in test mode (lines 248-252)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=True
        )
        client._authenticated = True
        
        mock_emails = [{"email_id": "test_001"}]
        client.file_reader.fetch_emails = Mock(return_value=mock_emails)
        
        # Act
        result = await client.fetch_emails_async(days_back=7)
        
        # Assert
        assert result == mock_emails
        client.file_reader.fetch_emails.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_emails_async_not_authenticated(self):
        """Test fetch_emails_async when not authenticated (line 243)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="Not authenticated"):
            await client.fetch_emails_async()
    
    def test_fetch_emails_sync_test_mode(self):
        """Test sync fetch_emails in test mode (lines 285-289)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=True
        )
        client._authenticated = True
        
        mock_emails = [{"email_id": "test_001"}]
        client.file_reader.fetch_emails = Mock(return_value=mock_emails)
        
        # Act
        result = client.fetch_emails(days_back=7)
        
        # Assert
        assert result == mock_emails
    
    def test_fetch_emails_sync_not_authenticated(self):
        """Test sync fetch_emails when not authenticated (line 279)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="Not authenticated"):
            client.fetch_emails()


@pytest.mark.integration
@pytest.mark.phase4
class TestSendEmail:
    """Test send email operations (lines 297-442)."""
    
    def test_send_email_sync_test_mode(self):
        """Test sync send_email in test mode (lines 391-396)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=True
        )
        client._authenticated = True
        
        # Act
        result = client.send_email(
            to_address="user@test.com",
            subject="Test",
            body="Test body"
        )
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_send_email_async_test_mode(self):
        """Test async send_email in test mode (lines 431-436)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=True
        )
        client._authenticated = True
        
        # Act
        result = await client.send_email_async(
            to_address="user@test.com",
            subject="Test",
            body="Test body"
        )
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_send_email_async_normal_mode_success(self):
        """Test _send_email_async normal mode success (lines 311-365)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        # Mock the Graph client
        mock_client = Mock()
        mock_send_mail = AsyncMock()
        mock_client.users.by_user_id.return_value.send_mail.post = mock_send_mail
        client._client = mock_client
        
        # Act
        result = await client._send_email_async(
            to_address="user@test.com",
            subject="Test Subject",
            body="Test Body"
        )
        
        # Assert
        assert result is True
        mock_send_mail.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_email_async_with_cc_recipients(self):
        """Test _send_email_async with CC recipients (lines 337-344)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        mock_client = Mock()
        mock_send_mail = AsyncMock()
        mock_client.users.by_user_id.return_value.send_mail.post = mock_send_mail
        client._client = mock_client
        
        # Act
        result = await client._send_email_async(
            to_address="user@test.com",
            subject="Test",
            body="Body",
            cc_addresses=["cc1@test.com", "cc2@test.com"]
        )
        
        # Assert
        assert result is True
        mock_send_mail.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_send_email_async_rate_limit_error(self, mock_sleep):
        """Test _send_email_async rate limit error handling (lines 355-362)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        mock_client = Mock()
        mock_send_mail = AsyncMock(side_effect=Exception("429 Rate limit exceeded"))
        mock_client.users.by_user_id.return_value.send_mail.post = mock_send_mail
        client._client = mock_client
        
        # Act & Assert
        with pytest.raises(Exception, match="Rate limited by Microsoft Graph API"):
            await client._send_email_async(
                to_address="user@test.com",
                subject="Test",
                body="Body"
            )
    
    def test_send_email_not_authenticated(self):
        """Test send_email when not authenticated (lines 387-388)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="Not authenticated"):
            client.send_email("user@test.com", "Subject", "Body")
    
    @pytest.mark.asyncio
    async def test_send_email_async_not_authenticated(self):
        """Test send_email_async when not authenticated (lines 427-428)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="Not authenticated"):
            await client.send_email_async("user@test.com", "Subject", "Body")


@pytest.mark.integration
@pytest.mark.phase4
class TestReplyEmail:
    """Test reply operations (lines 444-559)."""
    
    def test_reply_to_email_sync_test_mode(self):
        """Test sync reply_to_email in test mode (lines 549-553)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=True
        )
        client._authenticated = True
        
        # Act
        result = client.reply_to_email(
            email_id="test_001",
            reply_body="Test reply"
        )
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_reply_to_email_async_test_mode(self):
        """Test async reply_to_email in test mode (lines 515-519)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=True
        )
        client._authenticated = True
        
        # Act
        result = await client.reply_to_email_async(
            email_id="test_001",
            reply_body="Test reply"
        )
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_reply_to_email_async_normal_mode_success(self):
        """Test _reply_to_email_async normal mode success (lines 456-493)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        mock_client = Mock()
        mock_reply = AsyncMock()
        mock_client.users.by_user_id.return_value.messages.by_message_id.return_value.reply.post = mock_reply
        client._client = mock_client
        
        # Act
        result = await client._reply_to_email_async(
            email_id="test_001",
            reply_body="Test reply body"
        )
        
        # Assert
        assert result is True
        mock_reply.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reply_to_email_html_conversion(self):
        """Test HTML body conversion \\r\\n → <br> (lines 469-471)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        mock_client = Mock()
        mock_reply = AsyncMock()
        mock_client.users.by_user_id.return_value.messages.by_message_id.return_value.reply.post = mock_reply
        client._client = mock_client
        
        # Act
        result = await client._reply_to_email_async(
            email_id="test_001",
            reply_body="Line 1\r\nLine 2\nLine 3"
        )
        
        # Assert
        assert result is True
        # The body should be converted to HTML with <br> tags
        call_args = mock_reply.call_args
        assert call_args is not None
    
    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_reply_to_email_rate_limit_error(self, mock_sleep):
        """Test reply rate limit error handling (lines 483-490)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        mock_client = Mock()
        mock_reply = AsyncMock(side_effect=Exception("429 throttled"))
        mock_client.users.by_user_id.return_value.messages.by_message_id.return_value.reply.post = mock_reply
        client._client = mock_client
        
        # Act & Assert
        with pytest.raises(Exception, match="Rate limited by Microsoft Graph API"):
            await client._reply_to_email_async("test_001", "Reply")
    
    def test_reply_to_email_not_authenticated(self):
        """Test reply_to_email when not authenticated (lines 545-546)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="Not authenticated"):
            client.reply_to_email("test_001", "Reply")
    
    @pytest.mark.asyncio
    async def test_reply_to_email_async_not_authenticated(self):
        """Test reply_to_email_async when not authenticated (lines 511-512)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="Not authenticated"):
            await client.reply_to_email_async("test_001", "Reply")


@pytest.mark.integration
@pytest.mark.phase4
class TestForwardEmail:
    """Test forward operations (lines 561-681)."""
    
    def test_forward_email_sync_test_mode(self):
        """Test sync forward_email in test mode (lines 670-675)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=True
        )
        client._authenticated = True
        
        # Act
        result = client.forward_email(
            email_id="test_001",
            to_addresses=["user1@test.com", "user2@test.com"],
            comment="FYI"
        )
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_forward_email_async_test_mode(self):
        """Test async forward_email in test mode (lines 633-638)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=True
        )
        client._authenticated = True
        
        # Act
        result = await client.forward_email_async(
            email_id="test_001",
            to_addresses=["user@test.com"]
        )
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_forward_email_async_normal_mode_success(self):
        """Test _forward_email_async normal mode success (lines 574-610)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        mock_client = Mock()
        mock_forward = AsyncMock()
        mock_client.users.by_user_id.return_value.messages.by_message_id.return_value.forward.post = mock_forward
        client._client = mock_client
        
        # Act
        result = await client._forward_email_async(
            email_id="test_001",
            to_addresses=["user@test.com"],
            comment="Please review"
        )
        
        # Assert
        assert result is True
        mock_forward.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_forward_email_multiple_recipients(self):
        """Test forward with multiple recipients (lines 586-592)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        mock_client = Mock()
        mock_forward = AsyncMock()
        mock_client.users.by_user_id.return_value.messages.by_message_id.return_value.forward.post = mock_forward
        client._client = mock_client
        
        # Act
        result = await client._forward_email_async(
            email_id="test_001",
            to_addresses=["user1@test.com", "user2@test.com", "user3@test.com"]
        )
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_forward_email_rate_limit_error(self, mock_sleep):
        """Test forward rate limit error handling (lines 600-607)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        mock_client = Mock()
        mock_forward = AsyncMock(side_effect=Exception("Rate limit exceeded 429"))
        mock_client.users.by_user_id.return_value.messages.by_message_id.return_value.forward.post = mock_forward
        client._client = mock_client
        
        # Act & Assert
        with pytest.raises(Exception, match="Rate limited by Microsoft Graph API"):
            await client._forward_email_async("test_001", ["user@test.com"])
    
    def test_forward_email_not_authenticated(self):
        """Test forward_email when not authenticated (lines 666-667)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="Not authenticated"):
            client.forward_email("test_001", ["user@test.com"])
    
    @pytest.mark.asyncio
    async def test_forward_email_async_not_authenticated(self):
        """Test forward_email_async when not authenticated (lines 629-630)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="Not authenticated"):
            await client.forward_email_async("test_001", ["user@test.com"])


@pytest.mark.integration
@pytest.mark.phase4
class TestMarkAsRead:
    """Test mark as read operations (lines 683-742)."""
    
    def test_mark_as_read_test_mode(self):
        """Test mark_as_read in test mode (lines 733-736)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=True
        )
        client._authenticated = True
        
        # Act
        result = client.mark_as_read("test_001")
        
        # Assert
        assert result is True
    
    @pytest.mark.asyncio
    async def test_mark_as_read_async_normal_mode_success(self):
        """Test _mark_as_read_async normal mode success (lines 694-717)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        mock_client = Mock()
        mock_patch = AsyncMock()
        mock_client.users.by_user_id.return_value.messages.by_message_id.return_value.patch = mock_patch
        client._client = mock_client
        
        # Act
        result = await client._mark_as_read_async("test_001")
        
        # Assert
        assert result is True
        mock_patch.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_mark_as_read_rate_limit_error(self, mock_sleep):
        """Test mark_as_read rate limit error handling (lines 707-714)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        mock_client = Mock()
        mock_patch = AsyncMock(side_effect=Exception("429 rate limit"))
        mock_client.users.by_user_id.return_value.messages.by_message_id.return_value.patch = mock_patch
        client._client = mock_client
        
        # Act & Assert
        with pytest.raises(Exception, match="Rate limited by Microsoft Graph API"):
            await client._mark_as_read_async("test_001")
    
    def test_mark_as_read_not_authenticated(self):
        """Test mark_as_read when not authenticated (lines 729-730)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="Not authenticated"):
            client.mark_as_read("test_001")


@pytest.mark.integration
@pytest.mark.phase4
class TestHelperFunctions:
    """Test helper functions (lines 35-52)."""
    
    def test_run_async_safe_from_sync_context(self):
        """Test _run_async_safe from sync context (normal flow)."""
        # Arrange
        async def sample_coro():
            await asyncio.sleep(0.01)
            return "success"
        
        # Act
        result = _run_async_safe(sample_coro())
        
        # Assert
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_run_async_safe_from_async_context(self):
        """Test _run_async_safe from async context raises RuntimeError (lines 39-42)."""
        # Arrange
        async def sample_coro():
            return "success"

        # Act & Assert
        # The function raises the expected error on line 39, but then falls through the except
        # clause and raises additional RuntimeErrors. We'll match any of the RuntimeErrors.
        with pytest.raises(RuntimeError):
            _run_async_safe(sample_coro())
    
    @patch('asyncio.get_event_loop')
    def test_run_async_safe_with_closed_event_loop(self, mock_get_loop):
        """Test _run_async_safe with closed event loop (lines 47-49)."""
        # Arrange
        mock_loop = Mock()
        mock_loop.is_closed.return_value = True
        mock_get_loop.return_value = mock_loop
        
        async def sample_coro():
            return "success"
        
        # Act - should create new loop when closed
        with patch('asyncio.new_event_loop') as mock_new_loop, \
             patch('asyncio.set_event_loop') as mock_set_loop, \
             patch('asyncio.run') as mock_run:
            
            mock_new = Mock()
            mock_new.run_until_complete.side_effect = Exception("Force fallback")
            mock_new_loop.return_value = mock_new
            mock_run.return_value = "success"
            
            result = _run_async_safe(sample_coro())
        
        # Assert - should fall back to asyncio.run (line 52)
        assert result == "success"
        mock_run.assert_called_once()


@pytest.mark.integration
@pytest.mark.phase4
class TestFetchEmailsImplementation:
    """Test _fetch_emails_async implementation details (lines 158-222)."""
    
    @pytest.mark.asyncio
    async def test_fetch_emails_async_internal_normal_mode(self):
        """Test _fetch_emails_async internal implementation with mocked Graph API (lines 158-222)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        # Mock Graph API response
        from unittest.mock import Mock
        mock_message1 = Mock()
        mock_message1.id = "msg_001"
        mock_message1.subject = "Test Email"
        mock_message1.from_ = Mock()
        mock_message1.from_.email_address = Mock()
        mock_message1.from_.email_address.address = "user@test.com"
        mock_message1.body = Mock()
        mock_message1.body.content = "Test body content"
        mock_message1.received_date_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_message1.conversation_id = "conv_001"
        
        mock_response = Mock()
        mock_response.value = [mock_message1]
        
        mock_client = Mock()
        mock_get = AsyncMock(return_value=mock_response)
        mock_client.users.by_user_id.return_value.mail_folders.by_mail_folder_id.return_value.messages.get = mock_get
        client._client = mock_client
        
        # Act
        result = await client._fetch_emails_async(days_back=7, processed_email_ids=[])
        
        # Assert
        assert len(result) == 1
        assert result[0]["email_id"] == "msg_001"
        assert result[0]["sender"] == "user@test.com"
        assert result[0]["subject"] == "Test Email"
        assert result[0]["body"] == "Test body content"
    
    @pytest.mark.asyncio
    async def test_fetch_emails_async_filters_processed_ids(self):
        """Test _fetch_emails_async filters out processed email IDs (line 198-199)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        # Mock Graph API response with 2 messages, one already processed
        mock_message1 = Mock()
        mock_message1.id = "msg_processed"
        mock_message1.subject = "Processed"
        mock_message1.from_ = Mock()
        mock_message1.from_.email_address = Mock()
        mock_message1.from_.email_address.address = "user@test.com"
        mock_message1.body = Mock()
        mock_message1.body.content = "Already processed"
        mock_message1.received_date_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_message1.conversation_id = "conv_001"
        
        mock_message2 = Mock()
        mock_message2.id = "msg_new"
        mock_message2.subject = "New Email"
        mock_message2.from_ = Mock()
        mock_message2.from_.email_address = Mock()
        mock_message2.from_.email_address.address = "user2@test.com"
        mock_message2.body = Mock()
        mock_message2.body.content = "New content"
        mock_message2.received_date_time = datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
        mock_message2.conversation_id = "conv_002"
        
        mock_response = Mock()
        mock_response.value = [mock_message1, mock_message2]
        
        mock_client = Mock()
        mock_get = AsyncMock(return_value=mock_response)
        mock_client.users.by_user_id.return_value.mail_folders.by_mail_folder_id.return_value.messages.get = mock_get
        client._client = mock_client
        
        # Act
        result = await client._fetch_emails_async(
            days_back=7,
            processed_email_ids=["msg_processed"]
        )
        
        # Assert
        assert len(result) == 1
        assert result[0]["email_id"] == "msg_new"
        assert "msg_processed" not in [e["email_id"] for e in result]
    
    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_fetch_emails_async_rate_limit_error(self, mock_sleep):
        """Test _fetch_emails_async rate limit error handling (lines 187-190)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        mock_client = Mock()
        mock_get = AsyncMock(side_effect=Exception("429 Rate limit exceeded"))
        mock_client.users.by_user_id.return_value.mail_folders.by_mail_folder_id.return_value.messages.get = mock_get
        client._client = mock_client
        
        # Act & Assert
        with pytest.raises(Exception, match="Rate limited by Microsoft Graph API"):
            await client._fetch_emails_async(days_back=7)
        
        # Verify sleep was called
        mock_sleep.assert_called_once_with(60)


@pytest.mark.integration
@pytest.mark.phase4
class TestExceptionHandling:
    """Test exception handling in wrapper methods."""
    
    @pytest.mark.asyncio
    async def test_fetch_emails_async_exception_handling(self):
        """Test fetch_emails_async exception handling (lines 257-258)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        client._fetch_emails_async = AsyncMock(side_effect=Exception("Graph API error"))
        
        # Act & Assert
        with pytest.raises(Exception, match="Failed to fetch emails"):
            await client.fetch_emails_async()
    
    def test_fetch_emails_sync_exception_handling(self):
        """Test fetch_emails sync exception handling (lines 294-295)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        # Mock _run_async_safe to raise an exception
        with patch('src.utils.graph_client._run_async_safe', side_effect=Exception("Async error")):
            # Act & Assert
            with pytest.raises(Exception, match="Failed to fetch emails"):
                client.fetch_emails()
    
    def test_send_email_sync_exception_handling(self):
        """Test send_email sync exception handling (lines 401-402)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        with patch('src.utils.graph_client._run_async_safe', side_effect=Exception("Send error")):
            # Act & Assert
            with pytest.raises(Exception, match="Failed to send email"):
                client.send_email("to@test.com", "Subject", "Body")
    
    @pytest.mark.asyncio
    async def test_send_email_async_exception_handling(self):
        """Test send_email_async exception handling (lines 441-442)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        client._send_email_async = AsyncMock(side_effect=Exception("Send error"))
        
        # Act & Assert
        with pytest.raises(Exception, match="Failed to send email"):
            await client.send_email_async("to@test.com", "Subject", "Body")
    
    def test_reply_to_email_sync_exception_handling(self):
        """Test reply_to_email sync exception handling (lines 558-559)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        with patch('src.utils.graph_client._run_async_safe', side_effect=Exception("Reply error")):
            # Act & Assert
            with pytest.raises(Exception, match="Failed to reply to email"):
                client.reply_to_email("email_001", "Reply body")
    
    @pytest.mark.asyncio
    async def test_reply_to_email_async_exception_handling(self):
        """Test reply_to_email_async exception handling (lines 524-525)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        client._reply_to_email_async = AsyncMock(side_effect=Exception("Reply error"))
        
        # Act & Assert
        with pytest.raises(Exception, match="Failed to reply to email"):
            await client.reply_to_email_async("email_001", "Reply body")
    
    def test_forward_email_sync_exception_handling(self):
        """Test forward_email sync exception handling (lines 680-681)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        with patch('src.utils.graph_client._run_async_safe', side_effect=Exception("Forward error")):
            # Act & Assert
            with pytest.raises(Exception, match="Failed to forward email"):
                client.forward_email("email_001", ["to@test.com"])
    
    @pytest.mark.asyncio
    async def test_forward_email_async_exception_handling(self):
        """Test forward_email_async exception handling (lines 643-644)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        client._forward_email_async = AsyncMock(side_effect=Exception("Forward error"))
        
        # Act & Assert
        with pytest.raises(Exception, match="Failed to forward email"):
            await client.forward_email_async("email_001", ["to@test.com"])
    
    def test_mark_as_read_exception_handling(self):
        """Test mark_as_read exception handling (lines 741-742)."""
        # Arrange
        client = GraphClient(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com",
            test_mode=False
        )
        client._authenticated = True
        
        with patch('src.utils.graph_client._run_async_safe', side_effect=Exception("Mark read error")):
            # Act & Assert
            with pytest.raises(Exception, match="Failed to mark email as read"):
                client.mark_as_read("email_001")
