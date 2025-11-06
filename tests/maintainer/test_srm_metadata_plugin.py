"""Tests for SRM metadata plugin."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.plugins.maintainer.srm_metadata_plugin import SRMMetadataPlugin
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
