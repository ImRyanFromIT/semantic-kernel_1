'''
Data loader for SRM catalog from CSV files.
'''

import pandas as pd
from pathlib import Path

from src.models.srm_record import SRMRecord
from src.memory.vector_store_base import VectorStoreBase


class SRMDataLoader:
    '''
    Load and process SRM catalog data from CSV files.
    '''
    
    def __init__(self, vector_store: VectorStoreBase):
        '''
        Initialize the data loader.
        
        Args:
            vector_store: The vector store to populate with SRM records
        '''
        self.vector_store = vector_store
    
    def parse_srm_metadata(self, metadata_str: str) -> tuple[str, str]:
        '''
        Parse the srm_metadata field.
        
        Format: "name=<name>; category=<category>"
        
        Args:
            metadata_str: The metadata string to parse
            
        Returns:
            Tuple of (name, category)
        '''
        parts = metadata_str.split(';')
        name = ""
        category = ""
        
        for part in parts:
            part = part.strip()
            if part.startswith('name='):
                name = part[5:].strip()
            elif part.startswith('category='):
                category = part[9:].strip()
        
        return name, category
    
    async def load_srm_catalog(self, csv_path: str | Path) -> list[SRMRecord]:
        '''
        Load SRM catalog from CSV file.
        
        Args:
            csv_path: Path to the srm_catalog.csv file
            
        Returns:
            List of SRMRecord objects
        '''
        csv_path = Path(csv_path)
        
        if not csv_path.exists():
            raise FileNotFoundError(f"SRM catalog file not found: {csv_path}")
        
        # Read CSV
        df = pd.read_csv(csv_path)
        
        # Parse and create SRM records
        records = []
        for _, row in df.iterrows():
            # Parse metadata
            name, category = self.parse_srm_metadata(row['srm_metadata'])
            
            # Create record
            record = SRMRecord(
                name=name,
                category=category,
                owning_team=row['owning_team'],
                use_case=row['use_case'],
                text=f"{name} {category} {row['use_case']} {row['owning_team']}",
            )
            records.append(record)
        
        return records
    
    async def load_and_index(self, csv_path: str | Path = "data/srm_catalog.csv") -> int:
        '''
        Load SRM catalog and index it in the vector store.
        
        Args:
            csv_path: Path to the srm_catalog.csv file
            
        Returns:
            Number of records indexed
        '''
        # Ensure collection exists
        await self.vector_store.ensure_collection_exists()
        
        # Load records
        records = await self.load_srm_catalog(csv_path)
        
        # Upsert to vector store
        await self.vector_store.upsert(records)
        
        return len(records)

