"""
Pytest configuration and fixtures for agent tests.
"""

import pytest
import asyncio
from typing import Generator


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
