'''
Tests for chatbot startup behavior with different store types.
'''

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


class TestChatbotStartupDataLoading:
    """Test that startup correctly loads data based on store type."""

    @pytest.mark.asyncio
    async def test_sqlite_store_loads_srm_index_csv(self):
        """Test that SQLite store loads data from srm_index.csv on startup."""
        # Mock the vector store
        mock_store = MagicMock()
        mock_store.upsert = AsyncMock()
        mock_store.ensure_collection_exists = AsyncMock()

        # Create mock app state
        mock_app_state = MagicMock()
        mock_app_state.vector_store = mock_store

        # Simulate SQLite startup logic
        from src.data.sqlite_data_loader import SQLiteDataLoader

        # Check that srm_index.csv exists
        csv_path = Path("data/srm_index.csv")
        assert csv_path.exists(), "data/srm_index.csv must exist for SQLite startup"

        # Load data
        loader = SQLiteDataLoader(mock_store)
        count = await loader.load_and_index(str(csv_path))

        # Verify data was loaded
        assert count > 0, "Should load at least one record from srm_index.csv"
        mock_store.upsert.assert_called_once()

        # Verify records have correct structure
        call_args = mock_store.upsert.call_args[0][0]
        first_record = call_args[0]

        # Check required attributes exist
        assert hasattr(first_record, 'SRM_ID')
        assert hasattr(first_record, 'Name')
        assert hasattr(first_record, 'Description')
        assert hasattr(first_record, 'Team')
        assert hasattr(first_record, 'Type')

    @pytest.mark.asyncio
    async def test_sqlite_loader_fails_on_missing_csv(self):
        """Test that startup fails gracefully if CSV is missing."""
        mock_store = MagicMock()

        from src.data.sqlite_data_loader import SQLiteDataLoader
        loader = SQLiteDataLoader(mock_store)

        with pytest.raises(FileNotFoundError) as exc_info:
            await loader.load_and_index("data/nonexistent.csv")

        assert "not found" in str(exc_info.value).lower()
