"""Integration tests for concierge workflows."""

import pytest
from fastapi.testclient import TestClient
from run_chatbot import app


@pytest.fixture(scope="function")
def test_client():
    """Create test client with startup/shutdown lifecycle."""
    with TestClient(app) as client:
        yield client


def test_help_command_workflow(test_client):
    """Test complete help command workflow."""
    # Get stats (which is what help command uses)
    stats_response = test_client.get("/api/concierge/stats")
    assert stats_response.status_code == 200

    stats = stats_response.json()
    assert "total_srms" in stats
    assert "temp_srms" in stats
    assert "chatbot_url" in stats
    assert stats["chatbot_url"] == "http://localhost:8000"

    # Verify data types
    assert isinstance(stats["total_srms"], int)
    assert isinstance(stats["temp_srms"], int)
    assert stats["temp_srms"] >= 0


def test_batch_update_workflow(test_client):
    """Test complete batch update workflow."""
    # First, search for SRMs to understand what's available
    search_response = test_client.post(
        "/api/concierge/search",
        json={"query": "database", "top_k": 10}
    )
    assert search_response.status_code == 200

    # Batch update Database Services Team SRMs
    batch_response = test_client.post(
        "/api/concierge/batch/update",
        json={
            "filter": {"team": "Database Services Team"},
            "updates": {"owner_notes": "Integration test note"}
        }
    )
    assert batch_response.status_code == 200
    batch_data = batch_response.json()
    assert batch_data["success"] is True
    assert "updated_count" in batch_data
    assert "updated_ids" in batch_data
    assert isinstance(batch_data["updated_ids"], list)

    # Verify update was applied by checking one of the updated SRMs
    if batch_data["updated_count"] > 0:
        first_srm_id = batch_data["updated_ids"][0]
        get_response = test_client.post(
            "/api/concierge/get",
            json={"srm_id": first_srm_id}
        )
        assert get_response.status_code == 200
        srm_data = get_response.json()
        assert srm_data["owner_notes"] == "Integration test note"


def test_temp_srm_workflow(test_client):
    """Test complete temp SRM workflow."""
    # Create temp SRM
    create_response = test_client.post(
        "/api/concierge/temp/create",
        json={
            "name": "Integration Test Temp SRM",
            "category": "Services",
            "owning_team": "Integration Test Team",
            "use_case": "Testing temp SRM functionality in workflow test"
        }
    )
    assert create_response.status_code == 200
    create_data = create_response.json()
    assert create_data["success"] is True
    assert "srm_id" in create_data
    temp_id = create_data["srm_id"]
    assert temp_id.startswith("SRM-TEMP-")
    assert "srm" in create_data

    # List temp SRMs - should include the one we just created
    list_response = test_client.get("/api/concierge/temp/list")
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert "temp_srms" in list_data
    assert len(list_data["temp_srms"]) > 0

    # Verify our temp SRM is in the list
    temp_ids = [srm["id"] for srm in list_data["temp_srms"]]
    assert temp_id in temp_ids

    # Search should include temp SRM
    search_response = test_client.post(
        "/api/concierge/search",
        json={"query": "Integration Test Temp", "top_k": 5}
    )
    assert search_response.status_code == 200
    search_data = search_response.json()
    # Should have at least one result
    assert len(search_data["results"]) > 0

    # Delete temp SRM
    delete_response = test_client.post(
        "/api/concierge/temp/delete",
        json={"srm_id": temp_id}
    )
    assert delete_response.status_code == 200
    delete_data = delete_response.json()
    assert delete_data["success"] is True

    # Verify deleted - list should no longer include it
    list_response2 = test_client.get("/api/concierge/temp/list")
    list_data2 = list_response2.json()
    temp_ids2 = [srm["id"] for srm in list_data2["temp_srms"]]
    assert temp_id not in temp_ids2
