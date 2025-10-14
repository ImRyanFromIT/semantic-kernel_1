'''
Factory for creating vector store instances based on configuration.
'''

import os
from semantic_kernel.connectors.ai.embeddings.embedding_generator_base import EmbeddingGeneratorBase

from src.memory.vector_store_base import VectorStoreBase
from src.memory.in_memory_store import InMemoryVectorStore
from src.memory.azure_search_store import AzureAISearchStore


def create_vector_store(
    embedding_generator: EmbeddingGeneratorBase | None = None,
    store_type: str | None = None
) -> VectorStoreBase:
    '''
    Create a vector store instance based on configuration.
    
    Args:
        embedding_generator: The embedding service to use (required for in_memory, optional for azure_search)
        store_type: Type of store ("azure_search" or "in_memory").
                   If None, reads from VECTOR_STORE_TYPE env var.
                   Defaults to "azure_search" if not specified.
    
    Returns:
        VectorStoreBase implementation instance
        
    Raises:
        ValueError: If invalid store type is specified
    '''
    # Determine store type
    if store_type is None:
        store_type = os.getenv('VECTOR_STORE_TYPE', 'azure_search')
    
    store_type = store_type.lower()
    
    # Create appropriate store
    if store_type == 'azure_search':
        print("[*] Using Azure AI Search text-only store")
        return AzureAISearchStore()
    elif store_type == 'in_memory':
        if not embedding_generator:
            raise ValueError("embedding_generator is required for in_memory store")
        print("[*] Using In-Memory vector store")
        return InMemoryVectorStore(embedding_generator)
    else:
        raise ValueError(
            f"Invalid vector store type: {store_type}. "
            f"Must be 'azure_search' or 'in_memory'"
        )

