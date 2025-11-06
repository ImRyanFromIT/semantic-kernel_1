'''
Factory for creating vector store instances based on configuration.
'''

import os
from semantic_kernel.connectors.ai.embeddings.embedding_generator_base import EmbeddingGeneratorBase

from src.memory.vector_store_base import VectorStoreBase
from src.memory.in_memory_store import InMemoryVectorStore


def create_vector_store(
    embedding_generator: EmbeddingGeneratorBase | None = None,
    store_type: str | None = None
) -> VectorStoreBase:
    '''
    Create a vector store instance based on configuration.
    
    Args:
        embedding_generator: The embedding service to use (required for in_memory)
        store_type: Type of store ("in_memory" only).
                   If None, reads from VECTOR_STORE_TYPE env var.
                   Defaults to "in_memory" if not specified.
        **kwargs: Store-specific configuration (reserved for future use)

    Environment Variables:
        VECTOR_STORE_TYPE: Store type ("in_memory")

    Returns:
        VectorStoreBase implementation instance
        
    Raises:
        ValueError: If invalid store type is specified

    Examples:
        # Create In-Memory store (default)
        store = create_vector_store(embedding_generator=my_embedding_gen)
    '''
    # Determine store type
    if store_type is None:
        store_type = os.getenv('VECTOR_STORE_TYPE', 'in_memory')

    store_type = store_type.lower()

    # Create appropriate store
    if store_type == 'azure_search':
        import warnings
        warnings.warn(
            "Azure AI Search integration has been deprecated and archived. "
            "Please use 'in_memory' store type instead. "
            "Azure Search code available in archived/azure_search/ for reference.",
            DeprecationWarning,
            stacklevel=2
        )
        raise ValueError(
            "Azure AI Search integration is no longer supported. "
            "Use VECTOR_STORE_TYPE='in_memory' instead. "
            "See archived/azure_search/ for old implementation."
        )

    elif store_type == 'in_memory':
        if not embedding_generator:
            raise ValueError("embedding_generator is required for in_memory store")
        print("[*] Using In-Memory vector store")
        return InMemoryVectorStore(embedding_generator)
    else:
        raise ValueError(
            f"Invalid vector store type: {store_type}. "
            f"Must be 'in_memory'"
        )


def create_data_loader(vector_store: VectorStoreBase, store_type: str | None = None):
    '''
    Create a data loader for the given vector store.

    Args:
        vector_store: The vector store to load data into
        store_type: Type of store (must be 'in_memory')

    Returns:
        Data loader instance for in-memory store

    Raises:
        ValueError: If Azure Search store type is specified
    '''
    if store_type is None:
        store_type = os.getenv('VECTOR_STORE_TYPE', 'in_memory')

    store_type = store_type.lower()

    if store_type == 'azure_search':
        raise ValueError(
            "Azure AI Search data loader is no longer supported. "
            "Use VECTOR_STORE_TYPE='in_memory' instead. "
            "See archived/azure_search/ for old implementation."
        )

    elif store_type == 'in_memory':
        from src.data.in_memory_loader import InMemoryDataLoader
        return InMemoryDataLoader(vector_store=vector_store)

    else:
        raise ValueError(f"Invalid store type: {store_type}. Must be 'in_memory'.")
