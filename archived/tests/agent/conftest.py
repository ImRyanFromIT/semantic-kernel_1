"""
Pytest Configuration and Fixtures for Agent Tests

This module provides shared fixtures for all agent tests:
- Core Models & State Management fixtures
- Plugin Testing fixtures
- Process Step Testing fixtures
- Integration Testing fixtures
- Utility fixtures for mocking external services

Fixture Organization:
- Session-scoped fixtures for expensive resources (event_loop, integration clients)
- Function-scoped fixtures for test isolation (mocks, sample data)
- Factory fixtures for customizable test data (create_process_input_data)

Example:
    def test_something(sample_email_record, mock_kernel):
        # Fixtures automatically injected by pytest
        assert sample_email_record.email_id == "test_001"
"""

import pytest
import asyncio
import os
from typing import Generator
from datetime import datetime, timezone




@pytest.fixture(scope="module")
def parametrized_search_store():
    """
    Provides Azure AI Search store for integration tests.

    Returns Azure AI Search store if credentials are available,
    otherwise skips the test.

    Environment Variables:
        SKIP_AZURE_TESTS=1 - Skip Azure Search tests entirely
        AZURE_AI_SEARCH_ENDPOINT - Azure endpoint (required)
        AZURE_AI_SEARCH_API_KEY - Azure API key (required)
        AZURE_AI_SEARCH_INDEX_NAME - Azure index name (required)

    Returns:
        AzureAISearchStore: Azure AI Search store instance

    Usage:
        @pytest.mark.integration
        def test_search(parametrized_search_store):
            store = parametrized_search_store
            await store.upsert([...])
            results = await store.search("query")
    """
    # Skip Azure tests if environment variable set
    if os.getenv("SKIP_AZURE_TESTS"):
        pytest.skip("Azure Search tests skipped (SKIP_AZURE_TESTS=1)")

    # Check for Azure credentials
    endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
    index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME")
    api_key = os.getenv("AZURE_AI_SEARCH_API_KEY")

    if not all([endpoint, index_name, api_key]):
        pytest.skip("Azure Search credentials not configured for integration tests")

    from src.memory.azure_search_store import AzureAISearchStore
    store = AzureAISearchStore(
        endpoint=endpoint,
        api_key=api_key,
        index_name=index_name
    )
    yield store
    # No cleanup needed for Azure


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    Create an instance of the default event loop for the test session.

    Scope: session - Shared across all tests to avoid event loop issues.

    Returns:
        asyncio.AbstractEventLoop: Event loop for async test execution

    Usage:
        Automatically used by pytest-asyncio for all async tests.
        No explicit use required in test functions.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """
    Mock agent configuration for testing.

    Provides a complete AgentConfig with all required fields populated
    with test-safe values.

    Returns:
        AgentConfig: Fully populated configuration object

    Fields:
        - agent_name: "Test_Agent"
        - state_file: "test_state.jsonl"
        - Graph API credentials (mocked)
        - Azure Search config (mocked)
        - LLM config (gpt-4, temp=0.3)

    Usage:
        def test_something(mock_config):
            assert mock_config.agent_name == "Test_Agent"
    """
    from src.models.agent_config import AgentConfig, GraphApiConfig, AzureSearchConfig, LlmConfig

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

    # Use timezone-aware datetimes consistently
    now_utc = datetime.now(timezone.utc).isoformat()

    return EmailRecord(
        email_id="test_001",
        sender="user@test.com",
        subject="Test Subject",
        body="Test body content",
        received_datetime=now_utc,  # Timezone-aware
        conversation_id="conv_001",
        classification="help",
        confidence=85.0,
        reason="Clear SRM request",
        status=EmailStatus.CLASSIFIED,
        timestamp=now_utc,  # Timezone-aware
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
    All methods return AsyncMock or Mock for easy assertion.

    Returns:
        Mock(spec=Kernel): Mocked Semantic Kernel instance

    Methods Mocked:
        - invoke: AsyncMock for async function invocation
        - get_function: Mock for retrieving registered functions
        - add_plugin: Mock for plugin registration

    Usage:
        def test_plugin(mock_kernel):
            plugin = MyPlugin(mock_kernel)
            await plugin.some_method()
            mock_kernel.invoke.assert_called_once()
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


# Phase 3 Fixtures: Process Step Testing

@pytest.fixture
def mock_process_context():
    """
    Provides a mock KernelProcessStepContext for process step testing.

    Mocks the emit_event method to verify event emissions in process steps.

    Returns:
        Mock: Mocked KernelProcessStepContext

    Methods Mocked:
        - emit_event: AsyncMock for event emission verification

    Usage:
        async def test_step(mock_process_context):
            step = MyStep()
            await step.execute(mock_process_context, {...})
            mock_process_context.emit_event.assert_called_once_with(
                process_event="EventName",
                data={...}
            )
    """
    from unittest.mock import Mock, AsyncMock

    context = Mock()
    context.emit_event = AsyncMock()

    return context


@pytest.fixture
def mock_graph_client():
    """
    Provides a mock Microsoft Graph client for email fetching tests.

    Mocks the fetch_emails_async method used by FetchNewEmailsStep.
    """
    from unittest.mock import Mock, AsyncMock

    client = Mock()
    client.fetch_emails_async = AsyncMock()

    return client


@pytest.fixture
def mock_agent():
    """
    Provides a mock ChatCompletionAgent for clarification tests.

    Mocks the invoke method used by ClarificationStep.
    """
    from unittest.mock import Mock, AsyncMock

    agent = Mock()
    agent.invoke = AsyncMock()

    return agent


@pytest.fixture
def mock_response_handler():
    """
    Provides a mock email response handler for process step testing.

    Mocks methods for sending emails (replies, notifications, escalations).
    """
    from unittest.mock import Mock, AsyncMock

    handler = Mock()
    handler.send_reply_async = AsyncMock()
    handler.send_notification_async = AsyncMock()
    handler.send_escalation_async = AsyncMock()
    # Add actual method names used by implementation
    handler.send_rejection_response = AsyncMock()
    handler.send_escalation = AsyncMock()

    return handler


@pytest.fixture
def sample_graph_emails():
    """
    Provides sample email data from Microsoft Graph API.

    Returns various email scenarios for FetchNewEmailsStep testing.
    """
    return {
        "normal": [
            {
                "email_id": "email_001",
                "sender": "user1@test.com",  # Flat string, not nested
                "subject": "SRM Update Request",
                "body": "Please update the SRM",
                "received_datetime": "2024-01-01T10:00:00Z",  # Snake case
                "conversation_id": "conv_001"  # Snake case
            },
            {
                "email_id": "email_002",
                "sender": "user2@test.com",
                "subject": "Another Request",
                "body": "Need help with SRM",
                "received_datetime": "2024-01-01T11:00:00Z",
                "conversation_id": "conv_002"
            }
        ],
        "with_self_email": [
            {
                "email_id": "email_001",
                "sender": "user1@test.com",
                "subject": "Request from user",
                "body": "User request",
                "received_datetime": "2024-01-01T10:00:00Z",
                "conversation_id": "conv_001"
            },
            {
                "email_id": "email_002",
                "sender": "test@example.com",  # self-email (matches config mailbox)
                "subject": "Sent by bot",
                "body": "Bot's own email",
                "received_datetime": "2024-01-01T11:00:00Z",
                "conversation_id": "conv_002"
            }
        ],
        "with_duplicates": [
            {
                "email_id": "email_001",
                "sender": "user1@test.com",
                "subject": "First in conversation",
                "body": "Original message",
                "received_datetime": "2024-01-01T10:00:00Z",
                "conversation_id": "conv_001"
            },
            {
                "email_id": "email_002",
                "sender": "user1@test.com",
                "subject": "Re: First in conversation",
                "body": "Reply in same conversation",
                "received_datetime": "2024-01-01T11:00:00Z",
                "conversation_id": "conv_001"  # Same conversation
            }
        ],
        "mass_email": [
            {
                "email_id": f"email_{i:03d}",
                "sender": f"user{i}@test.com",
                "subject": f"Request {i}",
                "body": f"Body {i}",
                "received_datetime": f"2024-01-01T{10+i:02d}:00:00Z",
                "conversation_id": f"conv_{i:03d}"
            }
            for i in range(25)  # 25 emails exceeds typical threshold
        ]
    }


@pytest.fixture
def create_process_input_data(mock_kernel, mock_config, state_manager, mock_graph_client, mock_response_handler):
    """
    Creates a complete input_data dict for process step testing.

    Returns a factory function that accepts optional overrides and returns
    a fully populated input_data dict with all common dependencies.

    Returns:
        callable: Factory function that creates input_data dict

    Factory Function Signature:
        _create(**overrides) -> dict

    Base Fields:
        - kernel: mock_kernel
        - config: mock_config
        - state_manager: state_manager (with temp file)
        - graph_client: mock_graph_client
        - response_handler: mock_response_handler

    Usage:
        def test_step(create_process_input_data):
            # Use defaults
            input_data = create_process_input_data()

            # Or override specific fields
            custom_kernel = Mock()
            input_data = create_process_input_data(kernel=custom_kernel)

            # Pass to process step
            await step.execute(context, input_data)
    """
    def _create(**overrides):
        base_data = {
            "kernel": mock_kernel,
            "config": mock_config,
            "state_manager": state_manager,
            "graph_client": mock_graph_client,
            "response_handler": mock_response_handler
        }
        base_data.update(overrides)
        return base_data

    return _create


# Phase 4 Fixtures: Integration Testing

@pytest.fixture(scope="module")
def integration_kernel():
    """
    Provides a real Semantic Kernel with real Azure OpenAI services.

    Used for critical integration tests that require real LLM behavior.

    Scope: module - Expensive resource, shared across module tests

    Requires Environment Variables:
        - AZURE_OPENAI_ENDPOINT: Azure OpenAI service endpoint
        - AZURE_OPENAI_API_KEY: API key for authentication
        - AZURE_OPENAI_CHAT_DEPLOYMENT_NAME: Chat model deployment
        - AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME: Embedding model deployment

    Returns:
        Kernel: Real Semantic Kernel with live Azure OpenAI connection

    Usage:
        @pytest.mark.requires_openai
        async def test_real_classification(integration_kernel):
            plugin = ClassificationPlugin(integration_kernel)
            result = await plugin.classify(email)  # Real API call
            assert result.classification in ["help", "dont_help", "escalate"]

    Note:
        - Makes real API calls - incurs costs
        - Requires valid Azure credentials
        - Use sparingly for critical tests only
        - Mock LLM for non-critical tests
    """
    from src.utils.kernel_builder import create_kernel

    return create_kernel()


@pytest.fixture
def mock_llm_kernel():
    """
    Provides a Kernel with mocked AI services for non-critical tests.

    Used for integration tests where deterministic mocked responses
    are sufficient and real API calls are not required.
    """
    from unittest.mock import Mock, AsyncMock
    from semantic_kernel import Kernel
    from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

    kernel = Kernel()

    # Create mock chat service
    mock_chat_service = Mock(spec=AzureChatCompletion)
    mock_chat_service.get_chat_message_content = AsyncMock()
    mock_chat_service.service_id = "mock-chat"

    # Add to kernel
    kernel.add_service(mock_chat_service)

    return kernel


@pytest.fixture(scope="module")
def real_graph_client():
    """
    Provides a real Microsoft Graph client for integration tests.

    Connects to actual Graph API using environment variables:
    - TENANT_ID
    - CLIENT_ID
    - CLIENT_SECRET
    - MAILBOX_EMAIL

    Note: This will make real API calls to fetch emails from the test mailbox.
    """
    import os
    from src.utils.graph_client import GraphEmailClient
    from azure.identity import ClientSecretCredential

    tenant_id = os.getenv("TENANT_ID")
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    mailbox_email = os.getenv("MAILBOX_EMAIL")

    if not all([tenant_id, client_id, client_secret, mailbox_email]):
        pytest.skip("Graph API credentials not configured for integration tests")

    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )

    return GraphEmailClient(
        credential=credential,
        mailbox_email=mailbox_email
    )


@pytest.fixture(scope="module")
def real_search_client():
    """
    DEPRECATED: Use parametrized_search_store instead.

    Provides a real Azure Search client for integration tests.

    This fixture is maintained for backward compatibility but will
    be removed in a future version. New tests should use
    parametrized_search_store which supports both SQLite and Azure.

    Connects to actual Azure AI Search index using environment variables:
    - AZURE_AI_SEARCH_ENDPOINT
    - AZURE_AI_SEARCH_INDEX_NAME
    - AZURE_AI_SEARCH_API_KEY

    Note: This will make real API calls to search and update documents.
    Use a dedicated test index to avoid affecting production data.
    """
    import warnings
    warnings.warn(
        "real_search_client is deprecated, use parametrized_search_store instead",
        DeprecationWarning,
        stacklevel=2
    )

    import os
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential

    endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
    index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME")
    api_key = os.getenv("AZURE_AI_SEARCH_API_KEY")

    if not all([endpoint, index_name, api_key]):
        pytest.skip("Azure Search credentials not configured for integration tests")

    return SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(api_key)
    )


@pytest.fixture
def integration_test_emails():
    """
    Provides sample email data specifically for integration tests.

    These emails represent realistic end-to-end scenarios.
    """
    return {
        "help_request": {
            "email_id": "int_test_001",
            "sender": "user@greatvaluelab.com",
            "subject": "SRM Update: Storage Expansion Request",
            "body": """Hi,

I need to update the owner notes for the Storage Expansion Request SRM.
The change is to add new configuration steps for setting up email notifications.

Change Type: Update Owner Notes
New Content: Configure email notifications in the settings panel under Notifications > Email Alerts. Enable the checkbox for storage threshold alerts.

Thanks!""",
            "received_datetime": "2024-01-15T14:30:00Z",
            "conversation_id": "int_conv_001"
        },
        "dont_help_request": {
            "email_id": "int_test_002",
            "sender": "spam@external.com",
            "subject": "BUY CHEAP PRODUCTS NOW!!!",
            "body": "This is obvious spam content with no relation to SRM work.",
            "received_datetime": "2024-01-15T14:35:00Z",
            "conversation_id": "int_conv_002"
        },
        "escalate_request": {
            "email_id": "int_test_003",
            "sender": "confused@greatvaluelab.com",
            "subject": "Help???",
            "body": "I need something but I'm not sure what. Can you help?",
            "received_datetime": "2024-01-15T14:40:00Z",
            "conversation_id": "int_conv_003"
        },
        "incomplete_request": {
            "email_id": "int_test_004",
            "sender": "user@greatvaluelab.com",
            "subject": "SRM Update Needed",
            "body": "Please update the Storage SRM. Thanks!",
            "received_datetime": "2024-01-15T14:45:00Z",
            "conversation_id": "int_conv_004"
        }
    }
