"""
SQLite Search Store Tests

Purpose: Comprehensive testing of SQLiteSearchStore using FTS5 for BM25 search.

Type: Unit + Integration
Test Count: TBD

Key Test Areas:
1. Initialization & Configuration
2. Search Operations (BM25)
3. Upsert Operations
4. Get by ID Operations
5. Feedback Score Updates
6. Error Handling
"""

import os
import pytest
import tempfile
from pathlib import Path

from src.memory.sqlite_search_store import SQLiteSearchStore


class TestSQLiteSearchStoreInitialization:
    """Test SQLite search store initialization."""

    def test_initialization_in_memory(self):
        """Test store initializes with in-memory database."""
        store = SQLiteSearchStore(db_path=":memory:")

        assert store.db_path == ":memory:"
        assert store.conn is not None

    def test_initialization_file_based(self):
        """Test store initializes with file-based database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = SQLiteSearchStore(db_path=db_path)

            assert store.db_path == db_path
            assert store.conn is not None
            assert os.path.exists(db_path)

    def test_initialization_creates_fts_table(self):
        """Test that FTS5 table is created on initialization."""
        store = SQLiteSearchStore(db_path=":memory:")

        # Check table exists
        cursor = store.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='srm_fts'"
        )
        result = cursor.fetchone()

        assert result is not None
        assert result[0] == 'srm_fts'


class TestSQLiteSearchStoreSearch:
    """Test search operations with BM25 ranking."""

    @pytest.mark.asyncio
    async def test_search_successful_with_results(self):
        """Test successful search returning multiple results."""
        store = SQLiteSearchStore(db_path=":memory:")

        # Create test records
        records = []
        for i in range(3):
            record = type('Record', (), {})()
            record.id = f'test-{i:03d}'
            record.SRM_ID = f'SRM-{i+51:03d}'
            record.Name = f'Storage Request {i}'
            record.Description = 'Expand storage capacity for data retention'
            record.URL_Link = f'https://example.com/srm-{i}'
            record.Team = 'Storage Team'
            record.Type = 'Storage'
            record.TechnologiesTeamWorksWith = 'Azure, AWS'
            record.owner_notes = 'Configuration steps'
            record.hidden_notes = 'Internal notes'
            records.append(record)

        # Upsert records
        await store.upsert(records)

        # Search for "storage"
        result_iterator = await store.search(query="storage", top_k=5)

        # Collect results
        results = []
        async for result in result_iterator:
            results.append(result)

        # Verify results
        assert len(results) == 3
        assert all(hasattr(r, 'score') for r in results)
        assert all(hasattr(r, 'record') for r in results)
        assert results[0].record.name == 'Storage Request 0'

    @pytest.mark.asyncio
    async def test_search_with_filters(self):
        """Test search with filter expressions."""
        store = SQLiteSearchStore(db_path=":memory:")

        # Create test records with different teams
        records = []
        for i, team in enumerate(['Storage Team', 'Network Team', 'Storage Team']):
            record = type('Record', (), {})()
            record.id = f'test-{i:03d}'
            record.SRM_ID = f'SRM-{i+51:03d}'
            record.Name = f'Request {i}'
            record.Description = 'Test description'
            record.Team = team
            record.Type = 'Infrastructure'
            records.append(record)

        await store.upsert(records)

        # Search with filter
        result_iterator = await store.search(
            query="request",
            top_k=10,
            filters={"Team": "Storage Team"}
        )

        results = [r async for r in result_iterator]

        # Should only return Storage Team results
        assert len(results) == 2
        assert all(r.record.team == 'Storage Team' for r in results)

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """Test search returning no results."""
        store = SQLiteSearchStore(db_path=":memory:")

        result_iterator = await store.search(query="nonexistent", top_k=5)
        results = [r async for r in result_iterator]

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_respects_top_k(self):
        """Test that search respects top_k limit."""
        store = SQLiteSearchStore(db_path=":memory:")

        # Create 10 records
        records = []
        for i in range(10):
            record = type('Record', (), {})()
            record.id = f'test-{i:03d}'
            record.SRM_ID = f'SRM-{i:03d}'
            record.Name = f'Storage Request {i}'
            record.Description = 'Storage expansion'
            records.append(record)

        await store.upsert(records)

        # Search with top_k=3
        result_iterator = await store.search(query="storage", top_k=3)
        results = [r async for r in result_iterator]

        assert len(results) == 3


class TestSQLiteSearchStoreUpsert:
    """Test upsert operations."""

    @pytest.mark.asyncio
    async def test_upsert_single_record(self):
        """Test upserting a single record."""
        store = SQLiteSearchStore(db_path=":memory:")

        # Create test record
        record = type('Record', (), {})()
        record.id = 'test-001'
        record.SRM_ID = 'SRM-051'
        record.Name = 'Test SRM'
        record.Description = 'Test description'
        record.owner_notes = 'Test notes'
        record.Team = 'Test Team'
        record.Type = 'Test'

        await store.upsert([record])

        # Verify record was inserted
        retrieved = await store.get_by_id('test-001')
        assert retrieved is not None
        assert retrieved.srm_id == 'SRM-051'
        assert retrieved.name == 'Test SRM'

    @pytest.mark.asyncio
    async def test_upsert_batch_records(self):
        """Test upserting multiple records in batch."""
        store = SQLiteSearchStore(db_path=":memory:")

        # Create multiple records
        records = []
        for i in range(5):
            record = type('Record', (), {})()
            record.id = f'test-{i:03d}'
            record.SRM_ID = f'SRM-{i:03d}'
            record.Name = f'Test SRM {i}'
            record.Description = f'Description {i}'
            records.append(record)

        await store.upsert(records)

        # Verify all records were inserted
        for i in range(5):
            retrieved = await store.get_by_id(f'test-{i:03d}')
            assert retrieved is not None
            assert retrieved.name == f'Test SRM {i}'

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_record(self):
        """Test that upsert updates existing records."""
        store = SQLiteSearchStore(db_path=":memory:")

        # Insert initial record
        record = type('Record', (), {})()
        record.id = 'test-001'
        record.SRM_ID = 'SRM-051'
        record.Name = 'Original Name'
        record.Description = 'Original description'

        await store.upsert([record])

        # Update the same record
        record.Name = 'Updated Name'
        record.Description = 'Updated description'

        await store.upsert([record])

        # Verify record was updated, not duplicated
        result_iterator = await store.search(query="updated", top_k=10)
        results = [r async for r in result_iterator]

        assert len(results) == 1
        assert results[0].record.name == 'Updated Name'

    @pytest.mark.asyncio
    async def test_upsert_empty_list(self):
        """Test that upserting empty list does nothing."""
        store = SQLiteSearchStore(db_path=":memory:")

        # Should not raise exception
        await store.upsert([])


class TestSQLiteSearchStoreGetById:
    """Test get_by_id operations."""

    @pytest.mark.asyncio
    async def test_get_by_id_successful(self):
        """Test successfully retrieving a record by ID."""
        store = SQLiteSearchStore(db_path=":memory:")

        # Insert record
        record = type('Record', (), {})()
        record.id = 'test-123'
        record.SRM_ID = 'SRM-051'
        record.Name = 'Storage SRM'
        record.Description = 'Storage description'
        record.owner_notes = 'Owner notes'
        record.hidden_notes = 'Hidden notes'

        await store.upsert([record])

        # Retrieve by ID
        result = await store.get_by_id('test-123')

        assert result is not None
        assert result.id == 'test-123'
        assert result.srm_id == 'SRM-051'
        assert result.name == 'Storage SRM'
        assert result.content == 'Storage description'

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        """Test get_by_id when record doesn't exist."""
        store = SQLiteSearchStore(db_path=":memory:")

        result = await store.get_by_id('nonexistent-id')

        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
