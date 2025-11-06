"""Tests for SRM metadata plugin."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.plugins.concierge.srm_metadata_plugin import SRMMetadataPlugin
from src.models.srm_record import SRMRecord


@pytest.mark.asyncio
async def test_update_owner_notes():
    """Test updating owner notes for an SRM."""
    # Arrange
    mock_vector_store = AsyncMock()
    existing_record = SRMRecord(
        id="SRM-001",
        name="Storage Expansion",
        category="Storage",
        owning_team="Infrastructure Team",
        use_case="Expand storage capacity",
        text="Storage Expansion for Infrastructure",
        owner_notes="Old notes",
        embedding=[0.1, 0.2, 0.3]
    )
    mock_vector_store.get_by_id.return_value = existing_record

    plugin = SRMMetadataPlugin(vector_store=mock_vector_store)

    # Act
    result = await plugin.update_srm_metadata(
        srm_id="SRM-001",
        updates='{"owner_notes": "New notes about storage"}'
    )

    # Assert
    assert "success" in result.lower()
    assert "SRM-001" in result
    mock_vector_store.get_by_id.assert_called_once_with("SRM-001")
    mock_vector_store.upsert.assert_called_once()

    # Check that upsert was called with updated record
    updated_record = mock_vector_store.upsert.call_args[0][0][0]
    assert updated_record.owner_notes == "New notes about storage"


@pytest.mark.asyncio
async def test_search_srm():
    """Test searching for SRMs."""
    # Arrange
    mock_vector_store = AsyncMock()

    # Create mock search results
    class MockSearchResult:
        def __init__(self, record, score):
            self.record = record
            self.score = score

    search_records = [
        SRMRecord(
            id="SRM-001",
            name="Storage Expansion",
            category="Storage",
            owning_team="Infrastructure Team",
            use_case="Expand storage capacity",
            text="Storage Expansion for Infrastructure",
            embedding=[0.1, 0.2, 0.3]
        ),
        SRMRecord(
            id="SRM-002",
            name="File Share Provisioning",
            category="Storage",
            owning_team="File Services Team",
            use_case="Provision new file share",
            text="File Share Provisioning",
            embedding=[0.2, 0.3, 0.4]
        )
    ]

    async def mock_search(query, top_k):
        for i, record in enumerate(search_records[:top_k]):
            yield MockSearchResult(record, 0.95 - i * 0.1)

    mock_vector_store.search = mock_search

    plugin = SRMMetadataPlugin(vector_store=mock_vector_store)

    # Act
    result = await plugin.search_srm(query="storage", top_k=5)

    # Assert
    import json
    results = json.loads(result)
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["id"] == "SRM-001"
    assert results[0]["name"] == "Storage Expansion"
    assert "score" in results[0]


@pytest.mark.asyncio
async def test_get_srm_by_id():
    """Test retrieving SRM by ID."""
    # Arrange
    mock_vector_store = AsyncMock()
    existing_record = SRMRecord(
        id="SRM-001",
        name="Storage Expansion",
        category="Storage",
        owning_team="Infrastructure Team",
        use_case="Expand storage capacity",
        text="Storage Expansion for Infrastructure",
        owner_notes="Contact storage team",
        hidden_notes="Internal note",
        embedding=[0.1, 0.2, 0.3]
    )
    mock_vector_store.get_by_id.return_value = existing_record

    plugin = SRMMetadataPlugin(vector_store=mock_vector_store)

    # Act
    result = await plugin.get_srm_by_id(srm_id="SRM-001")

    # Assert
    import json
    response = json.loads(result)
    assert response["success"] is True
    assert "srm" in response
    srm_data = response["srm"]
    assert srm_data["id"] == "SRM-001"
    assert srm_data["name"] == "Storage Expansion"
    assert srm_data["category"] == "Storage"
    assert srm_data["use_case"] == "Expand storage capacity"
    assert srm_data["owner_notes"] == "Contact storage team"
    assert srm_data["hidden_notes"] == "Internal note"
    mock_vector_store.get_by_id.assert_called_once_with("SRM-001")


@pytest.mark.asyncio
async def test_get_srm_by_id_not_found():
    """Test retrieving SRM that doesn't exist."""
    # Arrange
    mock_vector_store = AsyncMock()
    mock_vector_store.get_by_id.return_value = None

    plugin = SRMMetadataPlugin(vector_store=mock_vector_store)

    # Act
    result = await plugin.get_srm_by_id(srm_id="SRM-999")

    # Assert
    import json
    response = json.loads(result)
    assert response["success"] is False
    assert "error" in response
    assert "SRM-999" in response["error"]
