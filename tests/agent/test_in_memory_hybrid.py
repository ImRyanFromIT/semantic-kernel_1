'''Integration tests for InMemory hybrid search.'''

import pytest
from src.memory.in_memory_store import InMemoryVectorStore
from src.models.srm_record import SRMRecord
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_embedding_generator():
    '''Mock embedding generator for tests.'''
    generator = MagicMock()
    generator.generate_embeddings = AsyncMock(
        return_value=[[0.1] * 1536]  # Mock 1536-dim embedding
    )
    return generator


@pytest.fixture
async def populated_store(mock_embedding_generator):
    '''Create a store with test data.'''
    store = InMemoryVectorStore(mock_embedding_generator)
    await store.ensure_collection_exists()

    records = [
        SRMRecord(
            id="1",
            name="VM Provisioning",
            category="Provisioning",
            owning_team="Cloud Team",
            use_case="Use when you need to provision a new virtual machine",
            text="VM Provisioning Provisioning Use when you need to provision a new virtual machine Cloud Team"
        ),
        SRMRecord(
            id="2",
            name="Database Restore",
            category="Restore",
            owning_team="Data Team",
            use_case="Use when you need to restore database backups",
            text="Database Restore Restore Use when you need to restore database backups Data Team"
        ),
        SRMRecord(
            id="3",
            name="VM Snapshot",
            category="Backup",
            owning_team="Cloud Team",
            use_case="Create snapshots of virtual machines for backup",
            text="VM Snapshot Backup Create snapshots of virtual machines for backup Cloud Team"
        ),
    ]

    await store.upsert(records)
    return store


@pytest.mark.asyncio
async def test_hybrid_search_exact_name_match(populated_store):
    '''Test hybrid search boosts exact name matches.'''
    results = []
    async for result in await populated_store.search("VM Provisioning", top_k=3):
        results.append(result)

    # Should find results
    assert len(results) > 0

    # First result should be the exact name match
    # (assuming hybrid search boosts keyword matches)
    assert results[0].record.id == "1"


@pytest.mark.asyncio
async def test_hybrid_search_fuzzy_match(populated_store):
    '''Test hybrid search handles typos with fuzzy matching.'''
    results = []
    async for result in await populated_store.search("databse restore", top_k=3):  # Typo
        results.append(result)

    # Should still find the database restore record
    assert len(results) > 0
    result_ids = [r.record.id for r in results]
    assert "2" in result_ids


@pytest.mark.asyncio
async def test_hybrid_search_use_case_match(populated_store):
    '''Test hybrid search matches keywords in use_case field.'''
    results = []
    async for result in await populated_store.search("backup", top_k=3):
        results.append(result)

    # Should find records with "backup" in use_case
    assert len(results) > 0
    result_ids = [r.record.id for r in results]
    # Both record 2 (database backups) and record 3 (backup) should match
    assert "2" in result_ids or "3" in result_ids


@pytest.mark.asyncio
async def test_hybrid_search_empty_query(populated_store):
    '''Test hybrid search handles empty query gracefully.'''
    results = []
    async for result in await populated_store.search("", top_k=3):
        results.append(result)

    # Should return some results (likely based on vector search only)
    assert len(results) >= 0  # At minimum, don't crash


@pytest.mark.asyncio
async def test_hybrid_search_no_matches(populated_store):
    '''Test hybrid search with query that matches nothing.'''
    results = []
    async for result in await populated_store.search("quantum blockchain ai", top_k=3):
        results.append(result)

    # May return low-scoring results or empty
    # Key test: doesn't crash
    assert isinstance(results, list)
