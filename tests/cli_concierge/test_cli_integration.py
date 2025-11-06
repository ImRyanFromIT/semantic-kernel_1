"""Integration tests for CLI concierge."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from run_cli_concierge import CLIConciergeAgent


@pytest.mark.asyncio
async def test_cli_agent_initialization():
    """Test CLI agent can initialize."""
    # Arrange
    agent = CLIConciergeAgent(chatbot_url="http://localhost:8000")

    # Act
    success = await agent.initialize()

    # Assert
    assert success is True
    assert agent.kernel is not None
    assert agent.agent is not None
    assert agent.history is not None


@pytest.mark.asyncio
async def test_cli_agent_can_search_via_plugin():
    """Test CLI agent can call search function through plugin."""
    # Arrange
    agent = CLIConciergeAgent(chatbot_url="http://localhost:8000")
    await agent.initialize()

    # Use MagicMock for response (httpx response.json() is sync)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"id": "SRM-001", "name": "Storage", "score": 0.95}
        ]
    }

    # Act
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock, return_value=mock_response):
        # Get the plugin from kernel
        result = await agent.kernel.invoke(
            plugin_name="api_client",
            function_name="search_srm",
            query="storage",
            top_k=5
        )

    # Assert
    assert result is not None
    result_str = str(result)
    assert "SRM-001" in result_str
