"""
Tests for ClarificationPlugin - Multi-turn clarification conversations.

Test Coverage:
1. Sending clarification emails
2. Checking for user replies
3. Merging replies with original context
4. Detecting human escalation requests
5. Recording unsatisfactory replies
6. Tracking clarification attempts
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone, timedelta

from src.plugins.agent.clarification_plugin import ClarificationPlugin
from src.models.email_record import EmailRecord, EmailStatus


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_response_handler():
    """Mock ResponseHandler for sending clarification emails."""
    handler = Mock()
    handler.send_clarification_request = AsyncMock(return_value=True)
    return handler


@pytest.fixture
def mock_graph_client_clarification():
    """Mock GraphClient for fetching reply emails."""
    client = Mock()
    client.fetch_emails_async = AsyncMock(return_value=[])
    return client


@pytest.fixture
def clarification_plugin(
    mock_response_handler,
    state_manager,
    mock_graph_client_clarification
):
    """ClarificationPlugin instance with mocked dependencies."""
    return ClarificationPlugin(
        response_handler=mock_response_handler,
        state_manager=state_manager,
        graph_client=mock_graph_client_clarification
    )


@pytest.fixture
def sample_email_for_clarification(state_manager):
    """Create and save a sample email record for clarification testing."""
    record = EmailRecord(
        email_id="email_clar_001",
        sender="user@greatvaluelab.com",
        subject="SRM Update Request",
        body="Please update the SRM",
        received_datetime="2024-01-15T10:00:00Z",
        conversation_id="conv_001",
        classification="help",
        confidence=60.0,
        reason="Unclear request",
        status=EmailStatus.CLASSIFIED,
        timestamp=datetime.now(timezone.utc).isoformat(),
        clarification_attempts=0,
        clarification_history=[]
    )
    state_manager.append_record(record)
    return record


# ============================================================================
# Test 1: Send Clarification Email - Success
# ============================================================================

@pytest.mark.asyncio
async def test_send_clarification_email_success(
    clarification_plugin,
    mock_response_handler,
    state_manager,
    sample_email_for_clarification
):
    """
    Test sending a clarification email successfully.

    Verifies:
    - send_clarification_email() calls response_handler
    - Updates record status to AWAITING_CLARIFICATION
    - Stores clarification question in record
    - Returns success with attempt count
    """
    question = "Which SRM ID would you like me to update?"

    result = await clarification_plugin.send_clarification_email(
        email_id="email_clar_001",
        question=question
    )

    # Verify response handler was called
    mock_response_handler.send_clarification_request.assert_called_once_with(
        email_id="email_clar_001",
        clarification_text=question
    )

    # Verify record was updated
    updated_record = state_manager.find_record("email_clar_001")
    assert updated_record.status == EmailStatus.AWAITING_CLARIFICATION
    assert updated_record.last_clarification_question == question
    assert updated_record.clarification_sent_datetime is not None

    # Verify result
    result_data = json.loads(result)
    assert result_data["success"] is True
    assert "Clarification sent" in result_data["message"]
    assert result_data["attempts"] == 0
    assert result_data["max_attempts"] == 2


# ============================================================================
# Test 2: Send Clarification Email - Email Not Found
# ============================================================================

@pytest.mark.asyncio
async def test_send_clarification_email_not_found(
    clarification_plugin,
    mock_response_handler
):
    """
    Test sending clarification email for non-existent email.

    Verifies:
    - Returns error when email_id not found
    - Does not call response_handler
    """
    result = await clarification_plugin.send_clarification_email(
        email_id="nonexistent_email",
        question="Test question"
    )

    # Verify response handler was NOT called
    mock_response_handler.send_clarification_request.assert_not_called()

    # Verify error response
    result_data = json.loads(result)
    assert result_data["success"] is False
    assert "not found" in result_data["error"]


# ============================================================================
# Test 3: Check for Reply - Has Reply
# ============================================================================

@pytest.mark.asyncio
async def test_check_for_reply_has_reply(
    clarification_plugin,
    mock_graph_client_clarification,
    state_manager,
    sample_email_for_clarification
):
    """
    Test checking for reply when user has replied.

    Verifies:
    - check_for_reply() fetches emails from GraphClient
    - Filters emails by sender, conversation_id, and time
    - Returns reply with has_reply=True
    """
    # Set up clarification sent time
    clarification_time = datetime.now(timezone.utc) - timedelta(hours=1)
    state_manager.update_record("email_clar_001", {
        "clarification_sent_datetime": clarification_time.isoformat()
    })

    # Mock reply email (after clarification)
    reply_time = datetime.now(timezone.utc)
    mock_graph_client_clarification.fetch_emails_async.return_value = [
        {
            "email_id": "reply_001",
            "sender": "user@greatvaluelab.com",  # Same sender
            "conversation_id": "conv_001",  # Same conversation
            "body": "I want to update SRM-051",
            "received_datetime": reply_time.isoformat()
        }
    ]

    result = await clarification_plugin.check_for_reply("email_clar_001")

    # Verify GraphClient was called
    mock_graph_client_clarification.fetch_emails_async.assert_called_once()

    # Verify result
    result_data = json.loads(result)
    assert result_data["has_reply"] is True
    assert "SRM-051" in result_data["reply_body"]
    assert result_data["reply_sender"] == "user@greatvaluelab.com"


# ============================================================================
# Test 4: Check for Reply - No Reply Yet
# ============================================================================

@pytest.mark.asyncio
async def test_check_for_reply_no_reply(
    clarification_plugin,
    mock_graph_client_clarification,
    state_manager,
    sample_email_for_clarification
):
    """
    Test checking for reply when user has not replied.

    Verifies:
    - Returns has_reply=False
    - Provides helpful message
    """
    # Set up clarification sent time
    clarification_time = datetime.now(timezone.utc) - timedelta(hours=1)
    state_manager.update_record("email_clar_001", {
        "clarification_sent_datetime": clarification_time.isoformat()
    })

    # Mock no reply emails (empty list)
    mock_graph_client_clarification.fetch_emails_async.return_value = []

    result = await clarification_plugin.check_for_reply("email_clar_001")

    # Verify result
    result_data = json.loads(result)
    assert result_data["has_reply"] is False
    assert "No reply yet" in result_data["message"]


@pytest.mark.asyncio
async def test_check_for_reply_filters_by_time(
    clarification_plugin,
    mock_graph_client_clarification,
    state_manager,
    sample_email_for_clarification
):
    """
    Test that check_for_reply only finds emails after clarification.

    Verifies:
    - Emails sent before clarification are ignored
    - Only emails after clarification time are considered
    """
    clarification_time = datetime.now(timezone.utc) - timedelta(hours=1)
    state_manager.update_record("email_clar_001", {
        "clarification_sent_datetime": clarification_time.isoformat()
    })

    # Mock email BEFORE clarification (should be ignored)
    old_email_time = clarification_time - timedelta(hours=2)
    mock_graph_client_clarification.fetch_emails_async.return_value = [
        {
            "email_id": "old_email",
            "sender": "user@greatvaluelab.com",
            "conversation_id": "conv_001",
            "body": "Old email before clarification",
            "received_datetime": old_email_time.isoformat()
        }
    ]

    result = await clarification_plugin.check_for_reply("email_clar_001")

    # Verify no reply found (old email filtered out)
    result_data = json.loads(result)
    assert result_data["has_reply"] is False


# ============================================================================
# Test 5: Merge Reply with Original
# ============================================================================

@pytest.mark.asyncio
async def test_merge_reply_with_original_success(
    clarification_plugin,
    state_manager,
    sample_email_for_clarification
):
    """
    Test merging user's reply with original request.

    Verifies:
    - merge_reply_with_original() builds merged context
    - Updates clarification history
    - Updates record body with merged text
    - Sets status to IN_PROGRESS
    """
    # Set up clarification
    state_manager.update_record("email_clar_001", {
        "last_clarification_question": "Which SRM ID?",
        "original_body": "Please update the SRM"
    })

    reply = "I want to update SRM-051"

    result = await clarification_plugin.merge_reply_with_original(
        email_id="email_clar_001",
        reply_body=reply
    )

    # Verify result
    result_data = json.loads(result)
    assert result_data["success"] is True
    assert "Ready for re-extraction" in result_data["message"]
    assert result_data["history_length"] == 1

    # Verify record was updated
    updated_record = state_manager.find_record("email_clar_001")
    assert updated_record.status == EmailStatus.IN_PROGRESS
    assert len(updated_record.clarification_history) == 1
    assert updated_record.clarification_history[0]["question"] == "Which SRM ID?"
    assert updated_record.clarification_history[0]["answer"] == reply

    # Verify merged body format
    assert "ORIGINAL REQUEST:" in updated_record.body
    assert "CLARIFICATION EXCHANGE:" in updated_record.body
    assert "LATEST REPLY:" in updated_record.body
    assert "SRM-051" in updated_record.body


@pytest.mark.asyncio
async def test_merge_reply_with_original_multiple_exchanges(
    clarification_plugin,
    state_manager,
    sample_email_for_clarification
):
    """
    Test merging with multiple clarification exchanges.

    Verifies:
    - Handles multiple Q&A exchanges
    - Preserves full history
    """
    # Set up existing history
    state_manager.update_record("email_clar_001", {
        "last_clarification_question": "What notes should I add?",
        "original_body": "Please update the SRM",
        "clarification_history": [
            {
                "question": "Which SRM ID?",
                "answer": "SRM-051",
                "timestamp": "2024-01-15T10:00:00Z"
            }
        ]
    })

    reply = "Add notes about new configuration"

    result = await clarification_plugin.merge_reply_with_original(
        email_id="email_clar_001",
        reply_body=reply
    )

    # Verify history length
    result_data = json.loads(result)
    assert result_data["history_length"] == 2

    # Verify both exchanges in body
    updated_record = state_manager.find_record("email_clar_001")
    assert "Clarification 1:" in updated_record.body
    assert "Clarification 2:" in updated_record.body


# ============================================================================
# Test 6: Check for Human Escalation Request - Detected
# ============================================================================

def test_check_for_human_escalation_request_detected(clarification_plugin):
    """
    Test detecting human escalation request in reply.

    Verifies:
    - check_for_human_escalation_request() detects escalation keywords
    - Returns is_escalation_request=True
    - Lists detected phrases
    """
    reply = "I don't understand your question. Can you connect me with a human?"

    result = clarification_plugin.check_for_human_escalation_request(reply)

    result_data = json.loads(result)
    assert result_data["is_escalation_request"] is True
    assert "connect me with a human" in result_data["detected_phrases"]
    assert "User requested human assistance" in result_data["message"]


def test_check_for_human_escalation_request_multiple_keywords(
    clarification_plugin
):
    """
    Test detecting multiple escalation keywords.

    Verifies:
    - Detects multiple keywords in same reply
    """
    reply = "This is too confusing. I need a human. Please escalate this to support."

    result = clarification_plugin.check_for_human_escalation_request(reply)

    result_data = json.loads(result)
    assert result_data["is_escalation_request"] is True
    assert len(result_data["detected_phrases"]) >= 2  # Multiple keywords found


# ============================================================================
# Test 7: Check for Human Escalation Request - Not Detected
# ============================================================================

def test_check_for_human_escalation_request_not_detected(clarification_plugin):
    """
    Test normal reply without escalation request.

    Verifies:
    - Returns is_escalation_request=False
    - No detected phrases
    """
    reply = "I want to update SRM-051 with new owner notes about configuration."

    result = clarification_plugin.check_for_human_escalation_request(reply)

    result_data = json.loads(result)
    assert result_data["is_escalation_request"] is False
    assert len(result_data["detected_phrases"]) == 0
    assert "No escalation request detected" in result_data["message"]


# ============================================================================
# Test 8: Record Unsatisfactory Reply
# ============================================================================

def test_record_unsatisfactory_reply_increment_attempts(
    clarification_plugin,
    state_manager,
    sample_email_for_clarification
):
    """
    Test recording an unsatisfactory reply.

    Verifies:
    - record_unsatisfactory_reply() increments attempts counter
    - Returns updated attempt count
    - Indicates whether can_retry
    """
    result = clarification_plugin.record_unsatisfactory_reply(
        email_id="email_clar_001",
        reason="User's reply was still too vague"
    )

    # Verify result
    result_data = json.loads(result)
    assert result_data["success"] is True
    assert result_data["attempts"] == 1
    assert result_data["max_attempts"] == 2
    assert result_data["can_retry"] is True

    # Verify record was updated
    updated_record = state_manager.find_record("email_clar_001")
    assert updated_record.clarification_attempts == 1


def test_record_unsatisfactory_reply_max_attempts_reached(
    clarification_plugin,
    state_manager,
    sample_email_for_clarification
):
    """
    Test recording unsatisfactory reply when at max attempts.

    Verifies:
    - After 2nd attempt, can_retry is False
    """
    # First unsatisfactory reply
    clarification_plugin.record_unsatisfactory_reply(
        email_id="email_clar_001",
        reason="Still vague"
    )

    # Second unsatisfactory reply
    result = clarification_plugin.record_unsatisfactory_reply(
        email_id="email_clar_001",
        reason="Still unclear"
    )

    # Verify max attempts reached
    result_data = json.loads(result)
    assert result_data["attempts"] == 2
    assert result_data["can_retry"] is False


# ============================================================================
# Test 9: Get Clarification Attempts
# ============================================================================

def test_get_clarification_attempts(
    clarification_plugin,
    state_manager,
    sample_email_for_clarification
):
    """
    Test getting current clarification attempt count.

    Verifies:
    - get_clarification_attempts() returns current count
    - Shows remaining attempts
    - Indicates can_retry status
    """
    # Initial state (0 attempts)
    result = clarification_plugin.get_clarification_attempts("email_clar_001")

    result_data = json.loads(result)
    assert result_data["attempts"] == 0
    assert result_data["max_attempts"] == 2
    assert result_data["can_retry"] is True
    assert result_data["remaining"] == 2

    # After 1 attempt
    state_manager.update_record("email_clar_001", {"clarification_attempts": 1})

    result = clarification_plugin.get_clarification_attempts("email_clar_001")
    result_data = json.loads(result)
    assert result_data["attempts"] == 1
    assert result_data["remaining"] == 1

    # After 2 attempts (max)
    state_manager.update_record("email_clar_001", {"clarification_attempts": 2})

    result = clarification_plugin.get_clarification_attempts("email_clar_001")
    result_data = json.loads(result)
    assert result_data["attempts"] == 2
    assert result_data["can_retry"] is False
    assert result_data["remaining"] == 0
