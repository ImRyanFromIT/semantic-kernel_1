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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
