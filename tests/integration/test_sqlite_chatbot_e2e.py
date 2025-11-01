"""
End-to-End SQLite Chatbot Integration Tests

Purpose: Test complete SQLite chatbot startup flow from kernel creation
         through data loading and query execution.

Type: Integration (E2E)
Test Count: 2

Key Test Areas:
1. Complete startup sequence (kernel → store → load → query)
2. Data searchability verification
3. Record structure validation
4. Error handling for missing CSV files

Dependencies:
- pytest-asyncio for async test support
- Real data file: data/srm_index.csv (55 records)
- src.utils.kernel_builder.create_kernel
- src.utils.store_factory.create_vector_store
- src.data.sqlite_data_loader.SQLiteDataLoader
"""

import pytest
import os
from pathlib import Path

from src.utils.kernel_builder import create_kernel
from src.utils.store_factory import create_vector_store
from src.data.sqlite_data_loader import SQLiteDataLoader


class TestSQLiteChatbotE2E:
    """End-to-end test for SQLite chatbot startup and query flow."""

    @pytest.mark.asyncio
    async def test_full_startup_and_query_flow(self):
        """Test complete flow: create store, load data, query."""
        # Simulate startup sequence

        # 1. Create kernel
        kernel = create_kernel()
        assert kernel is not None

        # 2. Create SQLite store
        store = create_vector_store(store_type='sqlite', db_path=':memory:')
        assert store is not None

        # 3. Load data (simulating startup_event)
        loader = SQLiteDataLoader(store)
        csv_path = Path("data/srm_index.csv")

        assert csv_path.exists(), "data/srm_index.csv must exist"

        num_records = await loader.load_and_index(csv_path)
        assert num_records > 0, "Should load records from CSV"
        print(f"Loaded {num_records} records")

        # 4. Verify data is searchable
        results = await store.search("AI Ops", top_k=5)

        found_results = []
        async for result in results:
            found_results.append(result)

        assert len(found_results) > 0, "Should find results for 'AI Ops' query"

        # 5. Verify record structure
        first_result = found_results[0]
        assert hasattr(first_result.record, 'srm_id')
        assert hasattr(first_result.record, 'name')
        assert hasattr(first_result.record, 'content')
        assert hasattr(first_result.record, 'team')

        # 6. Cleanup
        store.close()

    @pytest.mark.asyncio
    async def test_startup_fails_gracefully_without_csv(self):
        """Test that startup fails with clear error if CSV missing."""
        store = create_vector_store(store_type='sqlite', db_path=':memory:')
        loader = SQLiteDataLoader(store)

        with pytest.raises(FileNotFoundError) as exc_info:
            await loader.load_and_index("data/missing.csv")

        error_msg = str(exc_info.value).lower()
        assert "not found" in error_msg
        assert "missing.csv" in error_msg

        store.close()
