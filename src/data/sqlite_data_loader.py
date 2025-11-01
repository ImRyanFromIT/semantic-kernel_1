"""
SQLite Data Loader for SRM Index.

Loads SRM data from srm_index.csv and indexes it in SQLite FTS5 store.
"""

import csv
from pathlib import Path


class SRMIndexRecord:
    """Simple record matching srm_index.csv structure."""

    def __init__(self, **kwargs):
        """
        Initialize record with arbitrary attributes.

        Args:
            **kwargs: Field names and values from CSV
        """
        for key, value in kwargs.items():
            setattr(self, key, value)


class SQLiteDataLoader:
    """Load SRM data from srm_index.csv for SQLite store."""

    def __init__(self, vector_store):
        """
        Initialize the data loader.

        Args:
            vector_store: The SQLite vector store to populate
        """
        self.vector_store = vector_store

    async def load_and_index(self, csv_path: str) -> int:
        """
        Load CSV and index in SQLite.

        Args:
            csv_path: Path to srm_index.csv file

        Returns:
            Number of records indexed

        Raises:
            FileNotFoundError: If CSV file doesn't exist
        """
        # Check if file exists
        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise FileNotFoundError(f"SRM data file not found: {csv_path}")

        # Read CSV and create records
        records = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Create record with all CSV fields
                record = SRMIndexRecord(
                    id=row['SRM_ID'],
                    SRM_ID=row['SRM_ID'],
                    Name=row['Name'],
                    Description=row['Description'],
                    Team=row['Team'],
                    Type=row['Type'],
                    URL_Link=row['URL_Link'],
                    TechnologiesTeamWorksWith=row.get('TechnologiesTeamWorksWith', ''),
                    owner_notes='',
                    hidden_notes=''
                )
                records.append(record)

        # Upsert to vector store
        await self.vector_store.upsert(records)

        return len(records)
