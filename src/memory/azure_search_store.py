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
    
    async def update_feedback_scores(
        self, 
        srm_id: str, 
        query: str, 
        feedback_type: str,
        user_id: str | None = None
    ) -> None:
        '''
        Update document with feedback metadata.
        
        For Azure AI Search, we store feedback as metadata in the document.
        The srm_id should be the SRM_ID field (e.g., "SRM-053") from the index.
        
        Args:
            srm_id: SRM_ID from the index (e.g., "SRM-053")
            query: Query associated with the feedback
            feedback_type: Type of feedback ('positive' or 'negative')
            user_id: Optional user ID for personalized adjustments
        '''
        try:
            # For Azure AI Search, we need to find the document by SRM_ID field
            # since the 'id' field might be different from SRM_ID
            
            # Search for the document by SRM_ID
            search_results = self.search_client.search(
                search_text="*",
                filter=f"SRM_ID eq '{srm_id}'",
                select=["id", "SRM_ID", "Name", "AzureSearch_DocumentKey"],
                top=1
            )
            
            doc_id = None
            azure_doc_key = None
            for result in search_results:
                doc_id = result.get('id')
                azure_doc_key = result.get('AzureSearch_DocumentKey')
                break
            
            if not doc_id:
                print(f"[!] Document with SRM_ID '{srm_id}' not found for feedback update")
                print(f"[*] Feedback is still recorded and will be used in reranking")
                return
            
            # Azure Search keys can only contain letters, digits, underscore (_), dash (-), or equal sign (=)
            # Try different key strategies in order of preference
            
            keys_to_try = []
            
            # Strategy 1: Use SRM_ID directly (e.g., "SRM-055") - this should be valid
            keys_to_try.append((srm_id, "SRM_ID"))
            
            # Strategy 2: Use the original id field (base64 encoded)
            if doc_id:
                keys_to_try.append((doc_id, "id"))
            
            # Strategy 3: Extract just the row number from AzureSearch_DocumentKey if it has the pattern
            if azure_doc_key and ';' in azure_doc_key:
                row_number = azure_doc_key.split(';')[-1]
                if row_number.isdigit():
                    keys_to_try.append((f"row_{row_number}", "row_number"))
            
            doc = None
            successful_key = None
            successful_key_type = None
            
            for key_to_try, key_type in keys_to_try:
                try:
                    doc = self.search_client.get_document(key=key_to_try)
                    successful_key = key_to_try
                    successful_key_type = key_type
                    break
                except Exception:
                    continue
            
            if not doc:
                print(f"[!] Document {doc_id} not found for feedback update")
                print(f"[*] Feedback is still recorded and will be used in reranking")
                return
            
            # Initialize feedback fields if they don't exist or are None
            if 'negative_feedback_queries' not in doc or doc['negative_feedback_queries'] is None:
                doc['negative_feedback_queries'] = []
            if 'positive_feedback_queries' not in doc or doc['positive_feedback_queries'] is None:
                doc['positive_feedback_queries'] = []
            if 'feedback_score_adjustment' not in doc or doc['feedback_score_adjustment'] is None:
                doc['feedback_score_adjustment'] = 0.0
            
            # Update feedback metadata
            if feedback_type == 'negative':
                if query not in doc['negative_feedback_queries']:
                    doc['negative_feedback_queries'].append(query)
                # Lower score by 0.1 for each negative feedback
                doc['feedback_score_adjustment'] -= 0.1
            elif feedback_type == 'positive':
                if query not in doc['positive_feedback_queries']:
                    doc['positive_feedback_queries'].append(query)
                # Boost score by 0.2 for each positive feedback
                doc['feedback_score_adjustment'] += 0.2
            elif feedback_type == 'reset':
                # Reset all feedback fields (used by feedback wipe utility)
                doc['negative_feedback_queries'] = []
                doc['positive_feedback_queries'] = []
                doc['feedback_score_adjustment'] = 0.0
            
            # Ensure the document has the correct key field for the update
            # Azure Search needs the key field to match what was used for retrieval
            if successful_key_type == "SRM_ID":
                # If we used SRM_ID as the key, make sure it's set correctly
                doc['SRM_ID'] = successful_key
            elif successful_key_type == "id":
                # If we used id as the key, make sure it's set correctly  
                doc['id'] = successful_key
            elif successful_key_type == "row_number":
                # If we used a constructed row key, we might need to handle this differently
                # For now, try to preserve the original structure
                pass
            
            # Update the document
            self.search_client.merge_or_upload_documents(documents=[doc])
            print(f"[+] Updated feedback scores for SRM {srm_id} ({feedback_type})")
            
        except Exception as e:
            # Azure AI Search may not support custom fields in the index
            # Log but don't fail - feedback will still be stored in FeedbackStore
            print(f"[!] Could not update feedback scores in Azure AI Search: {e}")
            print(f"[*] Feedback is still recorded and will be used in reranking")

