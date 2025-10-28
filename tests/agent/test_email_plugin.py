"""
Tests for EmailPlugin - Microsoft Graph API email operations.

Test Coverage:
1. Authentication with Graph API
2. Fetching emails with filtering
3. Sending emails
4. Replying to emails
5. Escalating emails
6. Sending update notifications with validation
7. Error handling for invalid domains
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.plugins.agent.email_plugin import EmailPlugin


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_graph_client():
    """
    Mock GraphClient for testing email operations.

    Mocks all async methods: authenticate, fetch_emails_async,
    send_email_async, reply_to_email_async, forward_email_async.
    """
    client = Mock()
    client.authenticate = Mock(return_value=True)
    client.fetch_emails_async = AsyncMock(return_value=[])
    client.send_email_async = AsyncMock(return_value=True)
    client.reply_to_email_async = AsyncMock(return_value=True)
    client.forward_email_async = AsyncMock(return_value=True)
    return client


@pytest.fixture
def email_plugin(mock_graph_client, mock_error_handler):
    """EmailPlugin instance with mocked dependencies."""
    return EmailPlugin(
        graph_client=mock_graph_client,
        error_handler=mock_error_handler
    )


@pytest.fixture
def sample_emails():
    """Sample email data for testing."""
    return [
        {
            "email_id": "email_001",
            "subject": "SRM Update Request",
            "sender": "user@greatvaluelab.com",
            "body": "Please update SRM-051 owner notes",
            "received_time": "2024-01-15T10:00:00Z",
            "conversation_id": "conv_001"
        },
        {
            "email_id": "email_002",
            "subject": "Question about SRM",
            "sender": "another@greatvaluelab.com",
            "body": "What is the status of SRM-052?",
            "received_time": "2024-01-15T11:00:00Z",
            "conversation_id": "conv_002"
        }
    ]


@pytest.fixture
def sample_changes_json():
    """Sample changes JSON from update_srm_document."""
    return json.dumps({
        "success": True,
        "srm_id": "SRM-051",
        "srm_title": "Storage Expansion Request",
        "changes": [
            {
                "field": "owner_notes",
                "before": "Old notes",
                "after": "New notes with updated information"
            }
        ]
    })


# ============================================================================
# Test 1: Authentication
# ============================================================================

def test_authenticate_success(email_plugin, mock_graph_client):
    """
    Test successful authentication with Microsoft Graph API.

    Verifies:
    - authenticate() calls graph_client.authenticate()
    - Returns success message on True
    - Returns error message on False
    """
    # Test successful authentication
    mock_graph_client.authenticate.return_value = True
    result = email_plugin.authenticate()

    assert "Successfully authenticated" in result
    assert mock_graph_client.authenticate.called

    # Test failed authentication
    mock_graph_client.authenticate.return_value = False
    result = email_plugin.authenticate()

    assert "Failed to authenticate" in result


def test_authenticate_exception(email_plugin, mock_graph_client, mock_error_handler):
    """
    Test authentication with exception handling.

    Verifies:
    - Exceptions are caught and handled
    - Error handler is called with correct error type
    - Returns error message
    """
    mock_graph_client.authenticate.side_effect = Exception("Connection timeout")

    result = email_plugin.authenticate()

    assert "Authentication failed" in result
    assert "Connection timeout" in result
    assert mock_error_handler.handle_error.called


# ============================================================================
# Test 2: Fetch Emails
# ============================================================================

@pytest.mark.asyncio
async def test_fetch_emails_success(email_plugin, mock_graph_client, sample_emails):
    """
    Test fetching emails with filtering of processed IDs.

    Verifies:
    - fetch_emails() calls graph_client.fetch_emails_async()
    - Passes days_back parameter correctly
    - Filters out processed email IDs
    - Returns JSON array of emails
    """
    mock_graph_client.fetch_emails_async.return_value = sample_emails

    result = await email_plugin.fetch_emails(
        days_back=7,
        processed_email_ids="email_003,email_004"
    )

    # Verify call was made with correct parameters
    mock_graph_client.fetch_emails_async.assert_called_once()
    call_args = mock_graph_client.fetch_emails_async.call_args
    assert call_args[0][0] == 7  # days_back
    assert call_args[0][1] == ["email_003", "email_004"]  # processed_ids

    # Verify result is JSON
    parsed = json.loads(result)
    assert len(parsed) == 2
    assert parsed[0]["email_id"] == "email_001"


@pytest.mark.asyncio
async def test_fetch_emails_empty_processed_ids(email_plugin, mock_graph_client, sample_emails):
    """
    Test fetching emails with no processed IDs filter.

    Verifies:
    - Empty processed_email_ids string results in empty list
    - All emails are returned
    """
    mock_graph_client.fetch_emails_async.return_value = sample_emails

    result = await email_plugin.fetch_emails(days_back=3, processed_email_ids="")

    # Verify empty list passed for processed IDs
    call_args = mock_graph_client.fetch_emails_async.call_args
    assert call_args[0][1] == []  # empty processed_ids list

    parsed = json.loads(result)
    assert len(parsed) == 2


# ============================================================================
# Test 3: Send Email
# ============================================================================

@pytest.mark.asyncio
async def test_send_email_success(email_plugin, mock_graph_client):
    """
    Test sending a new email with CC recipients.

    Verifies:
    - send_email() calls graph_client.send_email_async()
    - CC addresses are parsed correctly from comma-separated string
    - Returns success message
    """
    mock_graph_client.send_email_async.return_value = True

    result = await email_plugin.send_email(
        to_address="recipient@greatvaluelab.com",
        subject="Test Subject",
        body="Test body content",
        cc_addresses="cc1@greatvaluelab.com, cc2@greatvaluelab.com"
    )

    # Verify call was made
    mock_graph_client.send_email_async.assert_called_once()
    call_args = mock_graph_client.send_email_async.call_args

    assert call_args[0][0] == "recipient@greatvaluelab.com"
    assert call_args[0][1] == "Test Subject"
    assert call_args[0][2] == "Test body content"
    assert call_args[0][3] == ["cc1@greatvaluelab.com", "cc2@greatvaluelab.com"]

    assert "Email sent successfully" in result
    assert "recipient@greatvaluelab.com" in result


# ============================================================================
# Test 4: Reply to Email
# ============================================================================

@pytest.mark.asyncio
async def test_reply_to_email_success(email_plugin, mock_graph_client):
    """
    Test replying to an existing email thread.

    Verifies:
    - reply_to_email() calls graph_client.reply_to_email_async()
    - Email ID and reply body are passed correctly
    - Returns success message with email ID
    """
    mock_graph_client.reply_to_email_async.return_value = True

    result = await email_plugin.reply_to_email(
        email_id="email_001",
        reply_body="Thank you for your request. I will process this shortly."
    )

    # Verify call was made
    mock_graph_client.reply_to_email_async.assert_called_once_with(
        "email_001",
        "Thank you for your request. I will process this shortly."
    )

    assert "Reply sent successfully" in result
    assert "email_001" in result


@pytest.mark.asyncio
async def test_reply_to_email_failure(email_plugin, mock_graph_client):
    """
    Test reply failure handling.

    Verifies:
    - Returns failure message when graph_client returns False
    """
    mock_graph_client.reply_to_email_async.return_value = False

    result = await email_plugin.reply_to_email(
        email_id="email_001",
        reply_body="Test reply"
    )

    assert "Failed to send reply" in result
    assert "email_001" in result


# ============================================================================
# Test 5: Escalate Email
# ============================================================================

@pytest.mark.asyncio
async def test_escalate_email_success(email_plugin, mock_graph_client):
    """
    Test escalating email to support team.

    Verifies:
    - escalate_email() calls graph_client.forward_email_async()
    - Support addresses are parsed from comma-separated string
    - Escalation comment is formatted correctly with reason
    - Returns success message
    """
    mock_graph_client.forward_email_async.return_value = True

    result = await email_plugin.escalate_email(
        email_id="email_001",
        to_addresses="support@greatvaluelab.com, team@greatvaluelab.com",
        escalation_reason="Request is ambiguous and requires manual review"
    )

    # Verify call was made
    mock_graph_client.forward_email_async.assert_called_once()
    call_args = mock_graph_client.forward_email_async.call_args

    # Check email ID
    assert call_args[0][0] == "email_001"

    # Check support addresses parsed correctly
    assert call_args[0][1] == ["support@greatvaluelab.com", "team@greatvaluelab.com"]

    # Check escalation comment formatting
    comment = call_args[0][2]
    assert "[SRM Agent Escalation]" in comment
    assert "Request is ambiguous and requires manual review" in comment
    assert "email_001" in comment

    assert "escalated successfully" in result


# ============================================================================
# Test 6: Send Update Notification - Success
# ============================================================================

@pytest.mark.asyncio
async def test_send_update_notification_success(
    email_plugin,
    mock_graph_client,
    sample_changes_json
):
    """
    Test sending update notification with valid recipients.

    Verifies:
    - send_update_notification() validates @greatvaluelab.com domain
    - Parses changes_json correctly
    - Formats notification email with before/after values
    - Sends to all valid recipients
    - Returns success message with recipient count
    """
    mock_graph_client.send_email_async.return_value = True

    result = await email_plugin.send_update_notification(
        recipients="user1@greatvaluelab.com, user2@greatvaluelab.com",
        changes_json=sample_changes_json,
        requester_name="Test User"
    )

    # Verify emails were sent
    assert mock_graph_client.send_email_async.call_count == 2

    # Verify first email call
    first_call = mock_graph_client.send_email_async.call_args_list[0]
    assert first_call[0][0] == "user1@greatvaluelab.com"

    # Verify subject contains SRM ID
    subject = first_call[0][1]
    assert "SRM-051" in subject

    # Verify body formatting
    body = first_call[0][2]
    assert "SRM Update Notification" in body
    assert "SRM ID: SRM-051" in body
    assert "Updated By: Test User" in body
    assert "Owner Notes" in body  # Field name is formatted as title case
    assert "Old notes" in body
    assert "New notes with updated information" in body

    # Verify success message
    assert "Notification sent successfully to 2 recipient(s)" in result
    assert "user1@greatvaluelab.com" in result
    assert "user2@greatvaluelab.com" in result


# ============================================================================
# Test 7: Send Update Notification - Email Validation
# ============================================================================

@pytest.mark.asyncio
async def test_send_update_notification_invalid_domain(
    email_plugin,
    mock_graph_client,
    sample_changes_json
):
    """
    Test update notification with invalid email domains.

    Verifies:
    - Rejects non-@greatvaluelab.com email addresses
    - Returns error message listing invalid emails
    - Does not send any emails when validation fails
    """
    result = await email_plugin.send_update_notification(
        recipients="user@external.com, another@wrongdomain.org",
        changes_json=sample_changes_json,
        requester_name="Test User"
    )

    # Verify no emails were sent
    mock_graph_client.send_email_async.assert_not_called()

    # Verify error message
    assert "Error" in result
    assert "not valid @greatvaluelab.com addresses" in result
    assert "user@external.com" in result
    assert "another@wrongdomain.org" in result


@pytest.mark.asyncio
async def test_send_update_notification_mixed_domains(
    email_plugin,
    mock_graph_client,
    sample_changes_json
):
    """
    Test update notification with mix of valid and invalid domains.

    Verifies:
    - Identifies and rejects invalid domains
    - Does not proceed with any emails if any recipient is invalid
    """
    result = await email_plugin.send_update_notification(
        recipients="valid@greatvaluelab.com, invalid@external.com",
        changes_json=sample_changes_json,
        requester_name="Test User"
    )

    # Should reject and not send to anyone
    mock_graph_client.send_email_async.assert_not_called()

    assert "Error" in result
    assert "invalid@external.com" in result


@pytest.mark.asyncio
async def test_send_update_notification_partial_failure(
    email_plugin,
    mock_graph_client,
    sample_changes_json
):
    """
    Test update notification with partial send failures.

    Verifies:
    - Handles cases where some emails succeed and others fail
    - Returns accurate count of successes and failures
    """
    # First email succeeds, second fails
    mock_graph_client.send_email_async.side_effect = [True, False]

    result = await email_plugin.send_update_notification(
        recipients="user1@greatvaluelab.com, user2@greatvaluelab.com",
        changes_json=sample_changes_json,
        requester_name="Test User"
    )

    # Verify partial success message
    assert "Notification sent to 1 recipient(s)" in result
    assert "failed for:" in result
    assert "user2@greatvaluelab.com" in result
