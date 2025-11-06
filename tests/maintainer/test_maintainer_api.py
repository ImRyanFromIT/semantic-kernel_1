"""Tests for maintainer API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from run_chatbot import app


@pytest.fixture
def test_client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_maintainer_plugin():
    """Mock maintainer plugin."""
    plugin = AsyncMock()
    plugin.search_srm.return_value = '[{"id": "SRM-001", "name": "Test SRM", "category": "Storage", "use_case": "Test use case", "score": 0.95}]'
    return plugin


def test_maintainer_search_endpoint(test_client, mock_maintainer_plugin):
    """Test maintainer search endpoint."""
    # Arrange
    app.state.maintainer_plugin = mock_maintainer_plugin

    # Act
    response = test_client.post(
        "/api/maintainer/search",
        json={"query": "storage", "top_k": 5}
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) > 0


def test_maintainer_get_by_id_endpoint(test_client, mock_maintainer_plugin):
    """Test maintainer get by ID endpoint."""
    # Arrange
    mock_maintainer_plugin.get_srm_by_id.return_value = '{"success": true, "srm": {"id": "SRM-001", "name": "Test SRM", "category": "Storage", "use_case": "Test use case", "owner_notes": "Test notes", "hidden_notes": "Hidden"}}'
    app.state.maintainer_plugin = mock_maintainer_plugin

    # Act
    response = test_client.post(
        "/api/maintainer/get",
        json={"srm_id": "SRM-001"}
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "srm" in data
    assert data["srm"]["id"] == "SRM-001"


def test_maintainer_update_endpoint(test_client, mock_maintainer_plugin):
    """Test maintainer update endpoint."""
    # Arrange
    mock_maintainer_plugin.update_srm_metadata.return_value = '''{
        "success": true,
        "srm_id": "SRM-001",
        "srm_name": "Test SRM",
        "changes": [{"field": "owner_notes", "before": "old", "after": "new"}]
    }'''
    app.state.maintainer_plugin = mock_maintainer_plugin

    # Act
    response = test_client.post(
        "/api/maintainer/update",
        json={
            "srm_id": "SRM-001",
            "updates": {"owner_notes": "new notes"}
        }
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["srm_id"] == "SRM-001"
    assert len(data["changes"]) > 0


def test_search_validation_empty_query(test_client):
    """Test search endpoint with empty query."""
    # Act
    response = test_client.post(
        "/api/maintainer/search",
        json={"query": "", "top_k": 5}
    )

    # Assert
    assert response.status_code == 400
    assert "Query cannot be empty" in response.json()["detail"]


def test_search_validation_whitespace_query(test_client):
    """Test search endpoint with whitespace-only query."""
    # Act
    response = test_client.post(
        "/api/maintainer/search",
        json={"query": "   ", "top_k": 5}
    )

    # Assert
    assert response.status_code == 400
    assert "Query cannot be empty" in response.json()["detail"]


def test_get_validation_empty_srm_id(test_client):
    """Test get endpoint with empty SRM ID."""
    # Act
    response = test_client.post(
        "/api/maintainer/get",
        json={"srm_id": ""}
    )

    # Assert
    assert response.status_code == 400
    assert "SRM ID cannot be empty" in response.json()["detail"]


def test_get_validation_whitespace_srm_id(test_client):
    """Test get endpoint with whitespace-only SRM ID."""
    # Act
    response = test_client.post(
        "/api/maintainer/get",
        json={"srm_id": "   "}
    )

    # Assert
    assert response.status_code == 400
    assert "SRM ID cannot be empty" in response.json()["detail"]


def test_update_validation_empty_srm_id(test_client):
    """Test update endpoint with empty SRM ID."""
    # Act
    response = test_client.post(
        "/api/maintainer/update",
        json={"srm_id": "", "updates": {"owner_notes": "test"}}
    )

    # Assert
    assert response.status_code == 400
    assert "SRM ID cannot be empty" in response.json()["detail"]


def test_update_validation_empty_updates(test_client):
    """Test update endpoint with empty updates dict."""
    # Act
    response = test_client.post(
        "/api/maintainer/update",
        json={"srm_id": "SRM-001", "updates": {}}
    )

    # Assert
    assert response.status_code == 400
    assert "Updates cannot be empty" in response.json()["detail"]


def test_maintainer_health_endpoint(test_client, mock_maintainer_plugin):
    """Test maintainer health check endpoint."""
    # Arrange
    app.state.maintainer_plugin = mock_maintainer_plugin
    app.state.vector_store = MagicMock()

    # Act
    response = test_client.get("/api/maintainer/health")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"
    assert data["service"] == "maintainer-api"
    assert data["plugin_initialized"] is True
    assert data["vector_store_initialized"] is True
    assert "timestamp" in data
