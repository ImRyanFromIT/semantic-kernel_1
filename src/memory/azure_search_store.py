'''
Azure AI Search vector store implementation.
'''

import os
from typing import Any, AsyncIterator

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from semantic_kernel.connectors.ai.embeddings.embedding_generator_base import EmbeddingGeneratorBase

from src.memory.vector_store_base import VectorStoreBase


class SearchResult:
    '''Wrapper for search results to match expected interface.'''
    
    def __init__(self, record: Any, score: float):
        '''
        Initialize search result.
        
        Args:
            record: The record object
            score: Search relevance score
        '''
        self.record = record
        self.score = score


class AzureAISearchStore(VectorStoreBase):
    '''
    Azure AI Search implementation for vector store.
    
    Uses hybrid search combining keyword (BM25) and vector search with
    Reciprocal Rank Fusion (RRF) for optimal retrieval quality.
    Works with direct SRM records containing service request information.
    '''
    
    def __init__(
        self, 
        embedding_generator: EmbeddingGeneratorBase,
        endpoint: str | None = None,
        api_key: str | None = None,
        index_name: str | None = None,
        vector_field_name: str | None = None
    ):
        '''
        Initialize Azure AI Search store.
        
        Args:
            embedding_generator: Service to generate embeddings for queries
            endpoint: Azure AI Search endpoint (or from env AZURE_AI_SEARCH_ENDPOINT)
            api_key: Azure AI Search API key (or from env AZURE_AI_SEARCH_API_KEY)
            index_name: Vector index name (or from env AZURE_AI_SEARCH_VECTOR_INDEX_NAME)
            vector_field_name: Name of the vector field in the index (or from env AZURE_AI_SEARCH_VECTOR_FIELD)
        '''
        self.embedding_generator = embedding_generator
        
        # Get configuration from parameters or environment
        self.endpoint = endpoint or os.getenv('AZURE_AI_SEARCH_ENDPOINT')
        self.api_key = api_key or os.getenv('AZURE_AI_SEARCH_API_KEY')
        # Use vector index for hybrid search (keyword + vector)
        self.index_name = index_name or os.getenv('AZURE_AI_SEARCH_VECTOR_INDEX_NAME', 'vector-search')
        self.vector_field_name = vector_field_name or os.getenv('AZURE_AI_SEARCH_VECTOR_FIELD', 'text_vector')
        
        if not self.endpoint:
            raise ValueError("Azure AI Search endpoint must be provided via parameter or AZURE_AI_SEARCH_ENDPOINT env var")
        if not self.api_key:
            raise ValueError("Azure AI Search API key must be provided via parameter or AZURE_AI_SEARCH_API_KEY env var")
        
        # Create search client pointing to the vector index
        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=self.index_name,
            credential=AzureKeyCredential(self.api_key)
        )
    
    async def ensure_collection_exists(self) -> None:
        '''
        Ensure the collection/index exists.
        
        For Azure AI Search, we assume the index already exists.
        This is a no-op since the index is managed externally.
        '''
        # No-op: Azure AI Search index is pre-created
        pass
    
    async def upsert(self, records: list[Any]) -> None:
        '''
        Insert or update records in Azure AI Search.
        
        Args:
            records: List of record objects to upsert
        '''
        # Convert records to dictionaries for Azure AI Search
        documents = []
        for record in records:
            if hasattr(record, '__dict__'):
                doc = {k: v for k, v in record.__dict__.items() if v is not None}
                documents.append(doc)
        
        if documents:
            # Upload documents to Azure AI Search
            result = self.search_client.upload_documents(documents=documents)
            print(f"[+] Uploaded {len(result)} documents to Azure AI Search")
    
    async def search(
        self, 
        query: str, 
        top_k: int = 8, 
        filters: dict | None = None
    ) -> AsyncIterator[SearchResult]:
        '''
        Search using hybrid search (keyword + vector with RRF).
        
        Combines BM25 keyword search with semantic vector search using
        Reciprocal Rank Fusion (RRF) to rank results. This provides superior
        retrieval quality by leveraging both exact matching and semantic similarity.
        
        Args:
            query: The search query text
            top_k: Number of top results to return
            filters: Optional filters to apply
            
        Returns:
            AsyncIterator of SearchResult objects with records and scores
        '''
        # Build filter string if provided
        filter_str = None
        if filters:
            filter_parts = []
            for key, value in filters.items():
                if isinstance(value, str):
                    filter_parts.append(f"{key} eq '{value}'")
                else:
                    filter_parts.append(f"{key} eq {value}")
            filter_str = " and ".join(filter_parts)
        
        # Generate query embeddings for vector search
        # Note: The vector field contains embeddings of the Description field
        vector_queries = []
        try:
            # Generate embeddings using the embedding service
            query_embedding = await self.embedding_generator.generate_embeddings([query])
            
            # Create vectorized query for hybrid search
            # This will search against text_vector field (embeddings of Description)
            vector_query = VectorizedQuery(
                vector=query_embedding[0],  # First (and only) embedding
                k_nearest_neighbors=top_k,
                fields=self.vector_field_name
            )
            vector_queries.append(vector_query)
            print(f"[+] Generated query embedding for hybrid search")
        except Exception as e:
            # Fall back to keyword-only search if embedding generation fails
            print(f"[!] Warning: Failed to generate embeddings, falling back to keyword-only search: {e}")
        
        # Perform hybrid search (keyword + vector with RRF)
        # When both search_text and vector_queries are provided, Azure AI Search
        # automatically uses Reciprocal Rank Fusion (RRF) to combine results
        results = self.search_client.search(
            search_text=query,  # Keyword/full-text search (BM25)
            vector_queries=vector_queries if vector_queries else None,  # Semantic vector search
            select=["chunk_id", "parent_id", "chunk", "Name", "Team", "Type", "URL_Link"],
            top=top_k,
            filter=filter_str,
            query_type="full"  # Use full Lucene query syntax for keyword matching
        )
        
        # Convert results to our format
        async def result_generator():
            for result in results:
                # Map Azure AI Search field names to internal format
                # Index fields: chunk_id, parent_id, chunk, Name, Team, Type, text_vector
                # chunk → the actual service description text
                # Name → service name
                # Team → owning team
                # Type → service type
                chunk_id = result.get('chunk_id', '')
                parent_id = result.get('parent_id', '')
                chunk = result.get('chunk', '')  # The description/content text
                name = result.get('Name', '')
                team = result.get('Team', '')
                record_type = result.get('Type', 'Services')
                
                # Use chunk_id as the record ID
                record_id = chunk_id if chunk_id else parent_id
                
                # Create a simple object to hold the result data
                record = type('Record', (), {
                    'id': record_id,
                    'name': name,
                    'content': chunk,  # Use chunk field which contains the description
                    'use_case': chunk,  # Use chunk field which contains the description
                    'category': record_type,
                    'kind': record_type,
                    'owning_team': team,
                    'team': team,
                    'technologies': '',  # Not available in this index
                    'url': result.get('URL_Link', ''),  # URL link to SRM documentation
                })()
                
                score = result.get('@search.score', 0.0)
                yield SearchResult(record=record, score=score)
        
        return result_generator()
    
    async def get_by_id(self, record_id: str) -> Any | None:
        '''
        Retrieve a specific record by ID.
        
        Args:
            record_id: The unique identifier of the record (chunk_id)
            
        Returns:
            The record if found, None otherwise
        '''
        try:
            result = self.search_client.get_document(key=record_id)
            
            # Convert to object format
            if result:
                # Map Azure AI Search field names to internal format
                chunk = result.get('chunk', '')
                name = result.get('Name', '')
                team = result.get('Team', '')
                record_type = result.get('Type', 'Services')
                
                record = type('Record', (), {
                    'id': record_id,
                    'name': name,
                    'content': chunk,  # Use chunk field which contains the description
                    'use_case': chunk,  # Use chunk field which contains the description
                    'category': record_type,
                    'kind': record_type,
                    'owning_team': team,
                    'team': team,
                    'technologies': '',  # Not available in this index
                    'url': result.get('URL_Link', ''),  # URL link to SRM documentation
                })()
                return record
            
            return None
        except Exception as e:
            print(f"Error retrieving document {record_id}: {e}")
            return None

