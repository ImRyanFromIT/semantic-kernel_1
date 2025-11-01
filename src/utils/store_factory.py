'''
Factory for creating vector store instances based on configuration.
'''

import os
from semantic_kernel.connectors.ai.embeddings.embedding_generator_base import EmbeddingGeneratorBase

from src.memory.vector_store_base import VectorStoreBase
from src.memory.in_memory_store import InMemoryVectorStore
from src.memory.azure_search_store import AzureAISearchStore
from src.memory.sqlite_search_store import SQLiteSearchStore


def create_vector_store(
    embedding_generator: EmbeddingGeneratorBase | None = None,
    store_type: str | None = None,
    **kwargs
) -> VectorStoreBase:
    '''
    Create a vector store instance based on configuration.

    Args:
        embedding_generator: The embedding service to use (required for in_memory, optional for others)
        store_type: Type of store ("sqlite", "azure_search", or "in_memory").
                   If None, reads from VECTOR_STORE_TYPE env var.
                   Defaults to "sqlite" if not specified.
        **kwargs: Store-specific configuration:
            - db_path: SQLite database path (default ":memory:")
            - endpoint, api_key, index_name: Azure Search config

    Environment Variables:
        VECTOR_STORE_TYPE: Store type ("sqlite", "azure_search", "in_memory")
        SQLITE_DB_PATH: SQLite database path (optional, defaults to ":memory:")
        AZURE_AI_SEARCH_ENDPOINT: Azure endpoint
        AZURE_AI_SEARCH_API_KEY: Azure API key
        AZURE_AI_SEARCH_INDEX_NAME: Azure index name

    Returns:
        VectorStoreBase implementation instance

    Raises:
        ValueError: If invalid store type is specified

    Examples:
        # Create SQLite store (default)
        store = create_vector_store()

        # Create SQLite with custom path
        store = create_vector_store(store_type='sqlite', db_path='/tmp/test.db')

        # Create Azure Search store
        store = create_vector_store(
            store_type='azure_search',
            endpoint='https://test.search.windows.net',
            api_key='key',
            index_name='index'
        )

        # Create In-Memory store
        store = create_vector_store(
            store_type='in_memory',
            embedding_generator=my_embedding_gen
        )
    '''
    # Determine store type (default to sqlite)
    if store_type is None:
        store_type = os.getenv('VECTOR_STORE_TYPE', 'sqlite')

    store_type = store_type.lower()

    # Create appropriate store
    if store_type == 'sqlite':
        # Get db_path from kwargs or environment or default
        db_path = kwargs.get('db_path') or os.getenv('SQLITE_DB_PATH', ':memory:')
        print(f"[*] Using SQLite FTS5 store (db_path: {db_path})")
        return SQLiteSearchStore(db_path=db_path)

    elif store_type == 'azure_search':
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
            f"Must be 'sqlite', 'azure_search', or 'in_memory'"
        )

