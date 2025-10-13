'''
In-memory vector store implementation using Semantic Kernel.
'''

from typing import Any, AsyncIterator

from semantic_kernel.connectors.ai.embeddings.embedding_generator_base import EmbeddingGeneratorBase
from semantic_kernel.connectors.in_memory import InMemoryStore

from src.memory.vector_store_base import VectorStoreBase
from src.models.srm_record import SRMRecord


class InMemoryVectorStore(VectorStoreBase):
    '''
    In-memory vector store implementation for SRM records.
    
    Uses Semantic Kernel's InMemoryStore with embeddings.
    '''
    
    def __init__(self, embedding_generator: EmbeddingGeneratorBase):
        '''
        Initialize the in-memory vector store.
        
        Args:
            embedding_generator: The embedding generator service to use
        '''
        self.embedding_generator = embedding_generator
        self.store = InMemoryStore()
        self.collection = None
    
    async def ensure_collection_exists(self) -> None:
        '''Ensure the collection exists in the store.'''
        # Don't pass embedding_generator here since we manually generate embeddings
        self.collection = self.store.get_collection(
            record_type=SRMRecord
        )
        await self.collection.ensure_collection_exists()
    
    async def upsert(self, records: list[SRMRecord]) -> None:
        '''
        Insert or update SRM records with embeddings.
        
        Args:
            records: List of SRMRecord objects to upsert
        '''
        if not self.collection:
            await self.ensure_collection_exists()
        
        # Generate embeddings for records that need them
        for record in records:
            if isinstance(record.embedding, str):
                # The embedding field contains text - generate the actual embedding
                embeddings = await self.embedding_generator.generate_embeddings([record.embedding])
                # Convert numpy array to plain Python list if needed
                embedding = embeddings[0]
                if hasattr(embedding, 'tolist'):
                    embedding = embedding.tolist()
                record.embedding = embedding
        
        # Upsert to collection
        await self.collection.upsert(records)
    
    async def search(
        self, 
        query: str, 
        top_k: int = 8, 
        filters: dict | None = None
    ) -> AsyncIterator[Any]:
        '''
        Search for similar SRM records using vector similarity.
        
        Args:
            query: The search query text
            top_k: Number of top results to return
            filters: Optional filters (not fully implemented for InMemory)
            
        Returns:
            AsyncIterator of search results with scores and records
        '''
        if not self.collection:
            await self.ensure_collection_exists()
        
        # Perform vector search
        results = await self.collection.search(query, top=top_k)
        
        # Return results as async iterator
        return results.results
    
    async def get_by_id(self, record_id: str) -> SRMRecord | None:
        '''
        Retrieve a specific SRM record by ID.
        
        Args:
            record_id: The unique identifier of the record
            
        Returns:
            The SRMRecord if found, None otherwise
        '''
        if not self.collection:
            await self.ensure_collection_exists()
        
        result = await self.collection.get(record_id)
        return result

