"""
Pytest configuration and fixtures for agent tests.
"""

import pytest
import asyncio
from typing import Generator
from datetime import datetime


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """Mock agent configuration for testing."""
    from ..models.agent_config import AgentConfig, GraphApiConfig, AzureSearchConfig, LlmConfig

    return AgentConfig(
        agent_name="Test_Agent",
        description="Test agent for unit tests",
        state_file="test_state.jsonl",
        log_file="test_actions.log",
        email_scan_interval_seconds=30,
        mass_email_threshold=20,
        confidence_threshold_for_classification=70,
        graph_api=GraphApiConfig(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            mailbox="test@example.com"
        ),
        azure_search=AzureSearchConfig(
            endpoint="https://test.search.windows.net",
            index_name="test-index",
            api_key="test-key"
        ),
        llm_config=LlmConfig(
            model="gpt-4",
            temperature=0.3,
            max_tokens=1500
        )
    )


# Phase 1 Fixtures: Models & State Management

@pytest.fixture
def sample_email_record():
    """
    Provides a sample EmailRecord for testing.

    Returns a minimal but valid EmailRecord with all required fields populated.
    """
    from src.models.email_record import EmailRecord, EmailStatus

    return EmailRecord(
        email_id="test_001",
        sender="user@test.com",
        subject="Test Subject",
        body="Test body content",
        received_datetime="2024-01-01T00:00:00Z",
        conversation_id="conv_001",
        classification="help",
        confidence=85.0,
        reason="Clear SRM request",
        status=EmailStatus.CLASSIFIED,
        timestamp=datetime.utcnow().isoformat(),
    )


@pytest.fixture
def state_manager(tmp_path):
    """
    Provides a StateManager instance with temporary file for testing.

    Uses pytest's tmp_path fixture to create an isolated state file
    for each test. The file is automatically cleaned up after the test.
    """
    from src.utils.state_manager import StateManager

    state_file = tmp_path / "test_state.jsonl"
    return StateManager(str(state_file))


# Phase 2 Fixtures: Plugin Testing

@pytest.fixture
def mock_kernel():
    """
    Provides a mock Semantic Kernel for plugin testing.

    Mocks the key methods: invoke, get_function, add_plugin.
    """
    from unittest.mock import Mock, AsyncMock
    from semantic_kernel import Kernel

    kernel = Mock(spec=Kernel)
    kernel.invoke = AsyncMock()
    kernel.get_function = Mock()
    kernel.add_plugin = Mock()

    return kernel


@pytest.fixture
def mock_error_handler():
    """
    Provides a mock ErrorHandler for plugin testing.

    Mocks retry decorator and error handling methods.
    """
    from unittest.mock import Mock
    from src.utils.error_handler import ErrorHandler, ErrorType

    error_handler = Mock(spec=ErrorHandler)

    # Mock with_retry to return the original function
    def mock_with_retry(error_type):
        def decorator(func):
            return func
        return decorator

    error_handler.with_retry = Mock(side_effect=mock_with_retry)
    error_handler.handle_error = Mock()
    error_handler.get_error_type = Mock(return_value=ErrorType.UNKNOWN)

    return error_handler


@pytest.fixture
def sample_classification_result():
    """
    Provides sample classification results for testing.

    Returns a dict with common classification outputs.
    """
    return {
        "help": {
            "classification": "help",
            "confidence": 85,
            "reason": "User is requesting an SRM update"
        },
        "dont_help": {
            "classification": "dont_help",
            "confidence": 95,
            "reason": "Email is off-topic spam"
        },
        "escalate": {
            "classification": "escalate",
            "confidence": 40,
            "reason": "Request is ambiguous and unclear"
        },
        "low_confidence": {
            "classification": "help",
            "confidence": 35,
            "reason": "Possibly an SRM request but very unclear"
        }
    }


@pytest.fixture
def sample_extraction_result():
    """
    Provides sample extraction results for testing.

    Returns a dict with various extraction scenarios.
    """
    return {
        "complete": {
            "srm_title": "Test SRM - Configure Email Notifications",
            "change_type": "update_owner_notes",
            "change_description": "Update owner notes with new configuration steps",
            "new_owner_notes_content": "Configure email notifications in settings panel",
            "recommendation_logic": None,
            "exclusion_criteria": None,
            "requester_team": "Engineering",
            "reason_for_change": "Documentation update needed",
            "completeness_score": 85
        },
        "partial": {
            "srm_title": "Test SRM",
            "change_type": None,
            "change_description": "Update something",
            "new_owner_notes_content": None,
            "recommendation_logic": None,
            "exclusion_criteria": None,
            "requester_team": None,
            "reason_for_change": None,
            "completeness_score": 30
        },
        "with_markdown": """```json
{
    "srm_title": "Test SRM",
    "completeness_score": 75,
    "new_owner_notes_content": "Test content"
}
```""",
        "minimal": {
            "srm_title": None,
            "completeness_score": 10
        }
    }


@pytest.fixture
def sample_conflict_result():
    """
    Provides sample conflict detection results for testing.

    Returns a dict with various conflict scenarios.
    """
    return {
        "no_conflict": {
            "has_conflicts": False,
            "conflict_details": "No conflicts detected",
            "severity": "low",
            "safe_to_proceed": True,
            "conflicts": []
        },
        "contradiction": {
            "has_conflicts": True,
            "conflict_details": "Request contains contradictory information about approval status",
            "severity": "high",
            "safe_to_proceed": False,
            "conflicts": ["Approval status is contradictory", "Multiple values for same field"]
        },
        "ambiguous": {
            "has_conflicts": True,
            "conflict_details": "Request is ambiguous about which SRM to update",
            "severity": "medium",
            "safe_to_proceed": False,
            "conflicts": ["Multiple SRMs mentioned", "Unclear which to update"]
        }
    }


@pytest.fixture
def mock_chat_service():
    """
    Provides a mock chat completion service for testing.

    Mocks get_chat_message_content method used by generate_clarification
    and detect_conflicts.
    """
    from unittest.mock import Mock, AsyncMock

    service = Mock()
    service.get_chat_message_content = AsyncMock()
    return service


@pytest.fixture
def mock_search_client():
    """
    Provides a mock Azure Search client for testing.

    Mocks search, get_document, and upload_documents methods.
    """
    from unittest.mock import Mock, MagicMock

    client = Mock()

    # Mock search method - returns iterable of results
    client.search = Mock()

    # Mock get_document method
    client.get_document = Mock()

    # Mock upload_documents method
    upload_result = Mock()
    upload_result.succeeded = True
    upload_result.error_message = None
    client.upload_documents = Mock(return_value=[upload_result])

    return client


@pytest.fixture
def sample_srm_documents():
    """
    Provides sample SRM documents for testing.

    Returns various SRM document structures for search tests.
    """
    return {
        "single_match": [
            {
                "SRM_ID": "SRM-051",
                "SRM_Title": "Storage Expansion Request",
                "Category": "Storage",
                "Owner": "Storage Team",
                "owner_notes": "Current configuration details",
                "hidden_notes": "Internal recommendation logic",
                "@search.score": 0.95
            }
        ],
        "multiple_matches": [
            {
                "SRM_ID": "SRM-051",
                "SRM_Title": "Storage Expansion Request",
                "Category": "Storage",
                "@search.score": 0.95
            },
            {
                "SRM_ID": "SRM-052",
                "SRM_Title": "Storage Migration Request",
                "Category": "Storage",
                "@search.score": 0.85
            }
        ],
        "document_detail": {
            "SRM_ID": "SRM-051",
            "SRM_Title": "Storage Expansion Request",
            "Category": "Storage",
            "Owner": "Storage Team",
            "owner_notes": "Original owner notes content",
            "hidden_notes": "Original hidden notes content"
        }
    }
