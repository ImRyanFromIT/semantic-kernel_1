"""Tests for CLI maintainer API client plugin."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from src.plugins.cli_concierge.api_client_plugin import ConciergeAPIClientPlugin


@pytest.mark.asyncio
async def test_search_srm_calls_api():
    """Test search_srm makes HTTP call to chatbot API."""
    # Arrange
    plugin = ConciergeAPIClientPlugin(base_url="http://localhost:8000")

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
    plugin = ConciergeAPIClientPlugin(base_url="http://localhost:8000")

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


@pytest.mark.asyncio
async def test_get_stats_calls_api():
    """Test get_stats makes HTTP call to chatbot API."""
    # Arrange
    plugin = ConciergeAPIClientPlugin(base_url="http://localhost:8000")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "total_srms": 56,
        "temp_srms": 2,
        "chatbot_url": "http://localhost:8000",
        "status": "healthy"
    }

    # Act
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock, return_value=mock_response):
        result = await plugin.get_stats()

    # Assert
    assert "56" in result
    assert "2" in result
    data = json.loads(result)
    assert data["total_srms"] == 56
    assert data["temp_srms"] == 2


@pytest.mark.asyncio
async def test_batch_update_srms_calls_api():
    """Test batch_update_srms makes HTTP call to chatbot API."""
    # Arrange
    plugin = ConciergeAPIClientPlugin(base_url="http://localhost:8000")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "updated_count": 5,
        "updated_ids": ["SRM-011", "SRM-012", "SRM-013", "SRM-014", "SRM-015"],
        "failures": []
    }

    # Act
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock, return_value=mock_response):
        result = await plugin.batch_update_srms(
            filter_json='{"team": "Database Services Team"}',
            updates_json='{"owner_notes": "Contact DBA first"}'
        )

    # Assert
    assert "SRM-011" in result
    data = json.loads(result)
    assert data["updated_count"] == 5
