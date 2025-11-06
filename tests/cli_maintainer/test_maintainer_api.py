"""Tests for maintainer API endpoints."""

import pytest
from fastapi.testclient import TestClient
from run_chatbot import app


@pytest.fixture
def test_client():
    """Create test client."""
    return TestClient(app)


def test_maintainer_stats_endpoint(test_client):
    """Test /api/maintainer/stats returns system state."""
    response = test_client.get("/api/maintainer/stats")

    assert response.status_code == 200
    data = response.json()
    assert "total_srms" in data
    assert "temp_srms" in data
    assert "chatbot_url" in data
    assert isinstance(data["total_srms"], int)
