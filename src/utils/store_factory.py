'''
Factory for creating vector store instances based on configuration.
'''

import os
from typing import Optional
from semantic_kernel.connectors.ai.embeddings.embedding_generator_base import EmbeddingGeneratorBase

from src.memory.vector_store_base import VectorStoreBase
from src.memory.in_memory_store import InMemoryVectorStore
from src.memory.azure_search_store import AzureAISearchStore


def create_vector_store(
    embedding_generator: EmbeddingGeneratorBase | None = None,
    store_type: str | None = None,
    **kwargs
) -> VectorStoreBase:
    '''
    Create a vector store instance based on configuration.

    Args:
        embedding_generator: The embedding service to use (required for in_memory)
        store_type: Type of store ("azure_search" or "in_memory").
                   If None, reads from VECTOR_STORE_TYPE env var.
                   Defaults to "in_memory" if not specified.
        **kwargs: Store-specific configuration:
            - endpoint, api_key, index_name: Azure Search config

    Environment Variables:
        VECTOR_STORE_TYPE: Store type ("azure_search" or "in_memory")
        AZURE_AI_SEARCH_ENDPOINT: Azure endpoint
        AZURE_AI_SEARCH_API_KEY: Azure API key
        AZURE_AI_SEARCH_INDEX_NAME: Azure index name

    Returns:
        VectorStoreBase implementation instance

    Raises:
        ValueError: If invalid store type is specified

    Examples:
        # Create In-Memory store (default)
        store = create_vector_store(embedding_generator=my_embedding_gen)

        # Create Azure Search store
        store = create_vector_store(
            store_type='azure_search',
            endpoint='https://test.search.windows.net',
            api_key='key',
            index_name='index'
        )
    '''
    # Determine store type (default to in_memory)
    if store_type is None:
        store_type = os.getenv('VECTOR_STORE_TYPE', 'in_memory')

    store_type = store_type.lower()

    # Create appropriate store
    if store_type == 'azure_search':
        print("[*] Using Azure AI Search text-only store")
        return AzureAISearchStore(
            endpoint=kwargs.get('endpoint'),
            api_key=kwargs.get('api_key'),
            index_name=kwargs.get('index_name')
        )

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


def create_data_loader(vector_store: VectorStoreBase, store_type: str | None = None):
    '''
    Create a data loader for the given vector store.

    Args:
        vector_store: The vector store to load data into
        store_type: Type of store (auto-detected if None)

    Returns:
        Data loader instance appropriate for the store type
    '''
    if store_type is None:
        store_type = os.getenv('VECTOR_STORE_TYPE', 'in_memory')

    store_type = store_type.lower()

    if store_type == 'azure_search':
        from src.data.azure_search_loader import AzureSearchDataLoader
        return AzureSearchDataLoader(vector_store=vector_store)

    elif store_type == 'in_memory':
        from src.data.in_memory_loader import InMemoryDataLoader
        return InMemoryDataLoader(vector_store=vector_store)

    else:
        raise ValueError(f"Invalid store type: {store_type}")

