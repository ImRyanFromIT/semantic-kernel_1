'''
Azure AI Search text-only store implementation.
'''

import os
from typing import Any, AsyncIterator

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

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
    Azure AI Search implementation for text-only search.
    
    Uses BM25 keyword search for retrieval.
    Works with direct SRM records containing service request information.
    '''
    
    def __init__(
        self, 
        endpoint: str | None = None,
        api_key: str | None = None,
        index_name: str | None = None
    ):
        '''
        Initialize Azure AI Search store.
        
        Args:
            endpoint: Azure AI Search endpoint (or from env AZURE_AI_SEARCH_ENDPOINT)
            api_key: Azure AI Search API key (or from env AZURE_AI_SEARCH_API_KEY)
            index_name: Index name (or from env AZURE_AI_SEARCH_INDEX_NAME)
        '''
        # Get configuration from parameters or environment
        self.endpoint = endpoint or os.getenv('AZURE_AI_SEARCH_ENDPOINT')
        self.api_key = api_key or os.getenv('AZURE_AI_SEARCH_API_KEY')
        # Use text-only index for BM25 search
        self.index_name = index_name or os.getenv('AZURE_AI_SEARCH_INDEX_NAME', 'search-semantics')
        
        if not self.endpoint:
            raise ValueError("Azure AI Search endpoint must be provided via parameter or AZURE_AI_SEARCH_ENDPOINT env var")
        if not self.api_key:
            raise ValueError("Azure AI Search API key must be provided via parameter or AZURE_AI_SEARCH_API_KEY env var")
        
        # Create search client pointing to the text-only index
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
        Search using text-only BM25 keyword search.
        
        Uses BM25 keyword search for retrieval based on exact and fuzzy text matching.
        
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
        
        # Perform text-only BM25 search
        results = self.search_client.search(
            search_text=query,  # Keyword/full-text search (BM25)
            select=["id", "SRM_ID", "Name", "Description", "URL_Link", "Team", "Type"],
            top=top_k,
            filter=filter_str,
            query_type="full"  # Use full Lucene query syntax for keyword matching
        )
        
        # Convert results to our format
        async def result_generator():
            for result in results:
                # Map Azure AI Search field names to internal format
                # Index fields: id, SRM_ID, Name, Description, URL_Link, Team, Type
                # Description → the actual service description text
                # Name → service name
                # Team → owning team
                # Type → service type
                record_id = result.get('id', '')
                srm_id = result.get('SRM_ID', '')
                name = result.get('Name', '')
                description = result.get('Description', '')  # The description/content text
                team = result.get('Team', '')
                record_type = result.get('Type', 'Services')
                url_link = result.get('URL_Link', '')
                
                # Create a simple object to hold the result data
                record = type('Record', (), {
                    'id': record_id,
                    'srm_id': srm_id,
                    'name': name,
                    'content': description,  # Use Description field
                    'use_case': description,  # Use Description field
                    'category': record_type,
                    'kind': record_type,
                    'owning_team': team,
                    'team': team,
                    'technologies': '',  # Not available in this index
                    'url': url_link,
                })()
                
                score = result.get('@search.score', 0.0)
                yield SearchResult(record=record, score=score)
        
        return result_generator()
    
    async def get_by_id(self, record_id: str) -> Any | None:
        '''
        Retrieve a specific record by ID.
        
        Args:
            record_id: The unique identifier of the record (id field)
            
        Returns:
            The record if found, None otherwise
        '''
        try:
            result = self.search_client.get_document(key=record_id)
            
            # Convert to object format
            if result:
                # Map Azure AI Search field names to internal format
                srm_id = result.get('SRM_ID', '')
                name = result.get('Name', '')
                description = result.get('Description', '')
                team = result.get('Team', '')
                record_type = result.get('Type', 'Services')
                url_link = result.get('URL_Link', '')
                
                record = type('Record', (), {
                    'id': record_id,
                    'srm_id': srm_id,
                    'name': name,
                    'content': description,  # Use Description field
                    'use_case': description,  # Use Description field
                    'category': record_type,
                    'kind': record_type,
                    'owning_team': team,
                    'team': team,
                    'technologies': '',  # Not available in this index
                    'url': url_link,
                })()
                return record
            
            return None
        except Exception as e:
            print(f"Error retrieving document {record_id}: {e}")
            return None

