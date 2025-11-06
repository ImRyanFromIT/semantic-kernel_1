"""Tests for CLI maintainer API client plugin."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.plugins.cli_maintainer.api_client_plugin import MaintainerAPIClientPlugin


@pytest.mark.asyncio
async def test_search_srm_calls_api():
    """Test search_srm makes HTTP call to chatbot API."""
    # Arrange
    plugin = MaintainerAPIClientPlugin(base_url="http://localhost:8000")

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
        result = await plugin.search_srm(query="storage", top_k=5)

    # Assert
    assert "SRM-001" in result
    assert "Storage" in result


@pytest.mark.asyncio
async def test_update_srm_metadata_calls_api():
    """Test update_srm_metadata makes HTTP call to chatbot API."""
    # Arrange
    plugin = MaintainerAPIClientPlugin(base_url="http://localhost:8000")

    # Use MagicMock for response (httpx response.json() is sync)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "srm_id": "SRM-001",
        "srm_name": "Storage",
        "changes": [{"field": "owner_notes", "before": "old", "after": "new"}]
    }

    # Act
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock, return_value=mock_response):
        result = await plugin.update_srm_metadata(
            srm_id="SRM-001",
            updates='{"owner_notes": "new notes"}'
        )

    # Assert
    assert "success" in result.lower()
    assert "SRM-001" in result
