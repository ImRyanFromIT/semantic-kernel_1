"""Tests for concierge API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from run_chatbot import app


@pytest.fixture
def test_client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_concierge_plugin():
    """Mock concierge plugin."""
    plugin = AsyncMock()
    return plugin


def test_concierge_stats_endpoint(test_client):
    """Test /api/concierge/stats returns system state."""
    response = test_client.get("/api/concierge/stats")

    assert response.status_code == 200
    data = response.json()
    assert "total_srms" in data
    assert "temp_srms" in data
    assert "chatbot_url" in data
    assert isinstance(data["total_srms"], int)


def test_batch_update_endpoint(test_client, mock_concierge_plugin):
    """Test /api/concierge/batch/update updates multiple SRMs."""
    # Arrange
    mock_concierge_plugin.batch_update_srms.return_value = '''{
        "success": true,
        "updated_count": 5,
        "updated_ids": ["SRM-011", "SRM-012", "SRM-013", "SRM-014", "SRM-015"],
        "failures": []
    }'''
    app.state.concierge_plugin = mock_concierge_plugin

    # Act
    response = test_client.post(
        "/api/concierge/batch/update",
        json={
            "filter": {"team": "Database Services Team"},
            "updates": {"owner_notes": "Contact DBA team first"}
        }
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "updated_count" in data
    assert "updated_ids" in data
    assert isinstance(data["updated_ids"], list)
