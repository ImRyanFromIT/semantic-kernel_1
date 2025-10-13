'''
Abstract base class for vector store implementations.

This allows easy swapping between InMemory and Azure AI Search.
'''

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator


class VectorStoreBase(ABC):
    '''
    Abstract base class for vector store operations.
    
    Implementations should provide methods for upserting records,
    searching by semantic similarity, and retrieving by ID.
    '''
    
    @abstractmethod
    async def ensure_collection_exists(self) -> None:
        '''Ensure the collection/index exists.'''
        pass
    
    @abstractmethod
    async def upsert(self, records: list[Any]) -> None:
        '''
        Insert or update records in the vector store.
        
        Args:
            records: List of record objects to upsert
        '''
        pass
    
    @abstractmethod
    async def search(self, query: str, top_k: int = 8, filters: dict | None = None) -> AsyncIterator[Any]:
        '''
        Search for similar records using vector similarity.
        
        Args:
            query: The search query text
            top_k: Number of top results to return
            filters: Optional filters to apply (e.g., {'team': 'Data Storage'})
            
        Returns:
            AsyncIterator of search results with scores
        '''
        pass
    
    @abstractmethod
    async def get_by_id(self, record_id: str) -> Any | None:
        '''
        Retrieve a specific record by ID.
        
        Args:
            record_id: The unique identifier of the record
            
        Returns:
            The record if found, None otherwise
        '''
        pass

