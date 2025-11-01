"""
SQLite Data Loader Tests

Purpose: Test SQLiteDataLoader for loading srm_index.csv into SQLite store.

Type: Unit + Integration
Test Count: 6

Key Test Areas:
1. Successful CSV loading
2. Record count verification
3. Field mapping validation
4. File not found error handling
5. CSV malformed error handling
6. Upsert integration with SQLite store

Dependencies:
- pytest-asyncio for async test support
- SQLiteSearchStore for integration testing
"""

import pytest
import tempfile
import csv
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from src.data.sqlite_data_loader import SQLiteDataLoader, SRMIndexRecord
from src.memory.sqlite_search_store import SQLiteSearchStore


class TestSQLiteDataLoader:
    """Test SQLite data loader functionality."""

    @pytest.fixture
    def sample_csv_data(self):
        """Sample CSV data matching srm_index.csv structure."""
        return [
            {
                'SRM_ID': 'SRM-001',
                'Name': 'Test SRM 1',
                'Description': 'Test description 1',
                'URL_Link': 'https://example.com/1',
                'Team': 'Test Team',
                'TechnologiesTeamWorksWith': 'Python, JavaScript',
                'Type': 'Services'
            },
            {
                'SRM_ID': 'SRM-002',
                'Name': 'Test SRM 2',
                'Description': 'Test description 2',
                'URL_Link': 'https://example.com/2',
                'Team': 'Another Team',
                'TechnologiesTeamWorksWith': 'Java, Go',
                'Type': 'Consultation'
            }
        ]

    @pytest.fixture
    def temp_csv_file(self, sample_csv_data, tmp_path):
        """Create temporary CSV file with sample data."""
        csv_path = tmp_path / "test_srm_index.csv"

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['SRM_ID', 'Name', 'Description', 'URL_Link', 'Team', 'TechnologiesTeamWorksWith', 'Type']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sample_csv_data)

        return csv_path

    @pytest.fixture
    def sqlite_store(self):
        """Create in-memory SQLite store for testing."""
        return SQLiteSearchStore(db_path=":memory:")

    @pytest.fixture
    def data_loader(self, sqlite_store):
        """Create SQLiteDataLoader instance."""
        return SQLiteDataLoader(sqlite_store)

    @pytest.mark.asyncio
    async def test_load_and_index_success(self, data_loader, temp_csv_file):
        """Test successful CSV loading and indexing."""
        # Act
        num_records = await data_loader.load_and_index(str(temp_csv_file))

        # Assert
        assert num_records == 2

    @pytest.mark.asyncio
    async def test_file_not_found_error(self, data_loader):
        """Test FileNotFoundError when CSV doesn't exist."""
        # Arrange
        nonexistent_path = "/nonexistent/path/to/file.csv"

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            await data_loader.load_and_index(nonexistent_path)

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_record_field_mapping(self, data_loader, temp_csv_file, sample_csv_data):
        """Test that CSV fields are correctly mapped to SRMIndexRecord."""
        # Arrange
        mock_store = Mock()
        mock_store.upsert = AsyncMock()
        data_loader.vector_store = mock_store

        # Act
        await data_loader.load_and_index(str(temp_csv_file))

        # Assert
        mock_store.upsert.assert_called_once()
        records = mock_store.upsert.call_args[0][0]

        assert len(records) == 2

        # Check first record
        record = records[0]
        assert hasattr(record, 'id')
        assert record.SRM_ID == 'SRM-001'
        assert record.Name == 'Test SRM 1'
        assert record.Description == 'Test description 1'
        assert record.URL_Link == 'https://example.com/1'
        assert record.Team == 'Test Team'
        assert record.TechnologiesTeamWorksWith == 'Python, JavaScript'
        assert record.Type == 'Services'
        assert record.owner_notes == ''
        assert record.hidden_notes == ''

    @pytest.mark.asyncio
    async def test_integration_with_sqlite_store(self, data_loader, temp_csv_file, sqlite_store):
        """Test full integration with SQLite store."""
        # Act
        num_records = await data_loader.load_and_index(str(temp_csv_file))

        # Assert - verify records were actually stored
        assert num_records == 2

        # Search for a record to verify it was stored
        results = []
        search_results = await sqlite_store.search("Test SRM 1", top_k=5)
        async for result in search_results:
            results.append(result)

        assert len(results) > 0
        # Check record fields (note: SQLite store uses lowercase field names)
        assert any('Test SRM 1' in str(r.record.name) for r in results)

    @pytest.mark.asyncio
    async def test_empty_optional_fields(self, data_loader, tmp_path):
        """Test handling of missing optional field (TechnologiesTeamWorksWith)."""
        # Arrange - create CSV without TechnologiesTeamWorksWith
        csv_path = tmp_path / "test_minimal.csv"
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['SRM_ID', 'Name', 'Description', 'URL_Link', 'Team', 'Type']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow({
                'SRM_ID': 'SRM-999',
                'Name': 'Minimal SRM',
                'Description': 'Minimal description',
                'URL_Link': 'https://example.com/999',
                'Team': 'Minimal Team',
                'Type': 'Services'
            })

        # Act
        num_records = await data_loader.load_and_index(str(csv_path))

        # Assert
        assert num_records == 1

    @pytest.mark.asyncio
    async def test_malformed_csv_error(self, data_loader, tmp_path):
        """Test that malformed CSV raises exception."""
        # Arrange - create malformed CSV
        csv_path = tmp_path / "malformed.csv"
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write("SRM_ID,Name\n")
            f.write("SRM-001,\"Unclosed quote\n")
            f.write("This is broken\n")

        # Act & Assert - let Python's csv module raise its exception
        with pytest.raises(Exception):  # csv.Error or similar
            await data_loader.load_and_index(str(csv_path))


class TestSRMIndexRecord:
    """Test SRMIndexRecord class."""

    def test_record_creation(self):
        """Test SRMIndexRecord creation with kwargs."""
        # Act
        record = SRMIndexRecord(
            id='SRM-001',
            SRM_ID='SRM-001',
            Name='Test SRM',
            Description='Test description',
            URL_Link='https://example.com',
            Team='Test Team',
            Type='Services',
            TechnologiesTeamWorksWith='Python',
            owner_notes='',
            hidden_notes=''
        )

        # Assert
        assert record.id == 'SRM-001'
        assert record.SRM_ID == 'SRM-001'
        assert record.Name == 'Test SRM'
        assert record.Description == 'Test description'
        assert record.URL_Link == 'https://example.com'
        assert record.Team == 'Test Team'
        assert record.Type == 'Services'
        assert record.TechnologiesTeamWorksWith == 'Python'
        assert record.owner_notes == ''
        assert record.hidden_notes == ''

    def test_record_dynamic_attributes(self):
        """Test that SRMIndexRecord accepts arbitrary attributes."""
        # Act
        record = SRMIndexRecord(foo='bar', baz=123)

        # Assert
        assert record.foo == 'bar'
        assert record.baz == 123
