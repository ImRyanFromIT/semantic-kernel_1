'''End-to-end integration test for hybrid search workflow.'''

import pytest
from src.memory.in_memory_store import InMemoryVectorStore
from src.models.srm_record import SRMRecord
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def e2e_embedding_generator():
    '''Mock embedding generator that returns different embeddings per text.'''
    generator = MagicMock()

    async def generate_mock_embeddings(texts):
        # Generate unique embeddings based on text hash
        return [[hash(text) % 100 / 100.0] * 1536 for text in texts]

    generator.generate_embeddings = AsyncMock(side_effect=generate_mock_embeddings)
    return generator


@pytest.mark.asyncio
async def test_hybrid_search_full_workflow(e2e_embedding_generator):
    '''Test complete hybrid search workflow from initialization to search.'''

    # 1. Initialize store
    store = InMemoryVectorStore(e2e_embedding_generator)
    await store.ensure_collection_exists()

    # 2. Load diverse SRM records
    records = [
        SRMRecord(
            id="vm-prov",
            name="VM Provisioning",
            category="Provisioning",
            owning_team="Cloud Infrastructure",
            use_case="Use when you need to provision a new virtual machine in AWS or Azure",
            text="VM Provisioning Provisioning Use when you need to provision a new virtual machine in AWS or Azure Cloud Infrastructure"
        ),
        SRMRecord(
            id="db-restore",
            name="Database Restore",
            category="Restore",
            owning_team="Database Team",
            use_case="Restore database from backup files when data loss occurs",
            text="Database Restore Restore Restore database from backup files when data loss occurs Database Team"
        ),
        SRMRecord(
            id="vm-snapshot",
            name="VM Snapshot Creation",
            category="Backup",
            owning_team="Cloud Infrastructure",
            use_case="Create point-in-time snapshots of virtual machines",
            text="VM Snapshot Creation Backup Create point-in-time snapshots of virtual machines Cloud Infrastructure"
        ),
        SRMRecord(
            id="network-change",
            name="Network Configuration Change",
            category="Change",
            owning_team="Network Team",
            use_case="Modify network settings, firewall rules, or routing tables",
            text="Network Configuration Change Change Modify network settings, firewall rules, or routing tables Network Team"
        ),
        SRMRecord(
            id="storage-prov",
            name="Storage Provisioning",
            category="Provisioning",
            owning_team="Storage Team",
            use_case="Provision new storage volumes or expand existing storage capacity",
            text="Storage Provisioning Provisioning Provision new storage volumes or expand existing storage capacity Storage Team"
        ),
    ]

    await store.upsert(records)

    # 3. Test exact name match is boosted
    results = []
    async for result in await store.search("VM Provisioning", top_k=3):
        results.append(result)

    assert len(results) > 0, "Should return results for 'VM Provisioning'"
    result_ids = [r.record.id for r in results]
    # Exact name match should be in top-3 results due to fuzzy keyword matching
    assert "vm-prov" in result_ids, "Exact name match should be in top results"

    # 4. Test fuzzy category match
    results = []
    async for result in await store.search("provisionng", top_k=3):  # Typo
        results.append(result)

    result_ids = [r.record.id for r in results]
    # Should find provisioning-related records despite typo
    assert "vm-prov" in result_ids or "storage-prov" in result_ids

    # 5. Test use_case keyword match
    results = []
    async for result in await store.search("backup", top_k=3):
        results.append(result)

    result_ids = [r.record.id for r in results]
    # Should find records with "backup" in use_case
    assert "db-restore" in result_ids or "vm-snapshot" in result_ids

    # 6. Test semantic query (multi-word, conceptual)
    results = []
    async for result in await store.search("create virtual machine", top_k=3):
        results.append(result)

    result_ids = [r.record.id for r in results]
    # Should find VM-related records
    assert "vm-prov" in result_ids or "vm-snapshot" in result_ids

    print("\nHybrid search E2E test passed!")
    print(f"Successfully searched {len(records)} records with multiple query types")
