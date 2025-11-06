"""
Store Factory Tests

Purpose: Test vector store factory pattern for creating different store types.

Type: Unit
Test Count: TBD

Key Test Areas:
1. Store creation by type
2. Environment variable configuration
3. Default behavior
4. Error handling
"""

import os
import pytest
from unittest.mock import patch

from src.utils.store_factory import create_vector_store
from src.memory.azure_search_store import AzureAISearchStore
from src.memory.in_memory_store import InMemoryVectorStore


class TestStoreFactory:
    """Test store factory creation."""

    def test_create_azure_search_store_explicit(self):
        """Test creating Azure Search store with explicit type."""
        with patch('src.memory.azure_search_store.SearchClient'):
            store = create_vector_store(
                store_type='azure_search',
                endpoint='https://test.search.windows.net',
                api_key='test-key',
                index_name='test-index'
            )

            assert isinstance(store, AzureAISearchStore)

    def test_default_store_type_is_in_memory(self):
        """Test that default store type is in_memory."""
        from unittest.mock import Mock

        mock_embedding = Mock()
        with patch.dict(os.environ, {}, clear=True):
            store = create_vector_store(embedding_generator=mock_embedding)

            assert isinstance(store, InMemoryVectorStore)

    def test_invalid_store_type_raises_error(self):
        """Test that invalid store type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid vector store type"):
            create_vector_store(store_type='invalid_type')


@pytest.mark.asyncio
async def test_parametrized_fixture(parametrized_search_store):
    """Test that parametrized fixture works."""
    # This test runs twice: SQLite and Azure (if available)
    record = type('Record', (), {})()
    record.id = 'test-001'
    record.SRM_ID = 'SRM-001'
    record.Name = 'Test'
    record.Description = 'Test'

    await parametrized_search_store.upsert([record])
    result = await parametrized_search_store.get_by_id('test-001')

    assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
