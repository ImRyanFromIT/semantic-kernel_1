"""
Search plugin for Azure AI Search operations.
"""

import json
from typing import List, Dict, Any, Optional
from semantic_kernel.functions import kernel_function

from ..utils.error_handler import ErrorHandler, ErrorType


class SearchPlugin:
    """
    Semantic Kernel plugin for Azure AI Search operations.
    
    Note: This is a skeleton implementation. In a real implementation,
    you would integrate with the existing Azure Search store from src/memory/.
    """
    
    def __init__(self, 
                 search_endpoint: str, 
                 index_name: str, 
                 api_key: str,
                 error_handler: ErrorHandler,
                 mock_updates: bool = True):
        """
        Initialize search plugin.
        
        Args:
            search_endpoint: Azure Search service endpoint
            index_name: Name of the search index
            api_key: API key for authentication
            error_handler: ErrorHandler for retry logic
            mock_updates: If True, mock updates; if False, actually update index
        """
        self.search_endpoint = search_endpoint
        self.index_name = index_name
        self.api_key = api_key
        self.error_handler = error_handler
        self.mock_updates = mock_updates
        self._client = None
    
    def _initialize_client(self):
        """Initialize Azure Search client."""
        if self._client is None:
            try:
                from azure.search.documents import SearchClient
                from azure.core.credentials import AzureKeyCredential
                
                credential = AzureKeyCredential(self.api_key)
                self._client = SearchClient(
                    endpoint=self.search_endpoint,
                    index_name=self.index_name,
                    credential=credential
                )
                print(f"[INFO] Azure Search client initialized for index: {self.index_name}")
            except ImportError:
                print("[WARNING] azure-search-documents not installed. Install with: pip install azure-search-documents")
                self._client = "mock_client"
            except Exception as e:
                print(f"[WARNING] Failed to initialize Azure Search client: {e}")
                self._client = "mock_client"
    
    @kernel_function(
        description="Search for SRM documents by title or keywords",
        name="search_srm"
    )
    async def search_srm(self, query: str, top_k: int = 5) -> str:
        """
        Search for SRM documents in the index.
        
        Args:
            query: Search query (SRM title or keywords)
            top_k: Number of results to return
            
        Returns:
            JSON string of search results or error message
        """
        try:
            self._initialize_client()
            
            @self.error_handler.with_retry(ErrorType.AZURE_SEARCH_OPERATION)
            def _search():
                # Use real Azure Search if client is initialized
                if self._client and self._client != "mock_client":
                    try:
                        results = self._client.search(
                            search_text=query,
                            top=top_k,
                            include_total_count=True
                        )
                        
                        # Convert search results to list of dicts
                        result_list = []
                        for result in results:
                            # Convert search result to dict
                            result_dict = dict(result)
                            # Add search score if available
                            if hasattr(result, '@search.score'):
                                result_dict['search_score'] = getattr(result, '@search.score')
                            result_list.append(result_dict)
                        
                        print(f"[SEARCH] Query: '{query}' | Results: {len(result_list)}")
                        return result_list
                    except Exception as e:
                        print(f"[SEARCH ERROR] {e}")
                        raise
                else:
                    # Fallback to mock results if client not initialized
                    print(f"[MOCK SEARCH] Query: '{query}' - returning empty results")
                    return []  # Return empty for testing "no match" scenario
            
            results = _search()
            return json.dumps(results, indent=2)
            
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.AZURE_SEARCH_OPERATION,
                e,
                "search_srm"
            )
            return f"Search failed: {e}"
    
    @kernel_function(
        description="Get specific SRM document by ID",
        name="get_srm_document"
    )
    async def get_srm_document(self, document_id: str) -> str:
        """
        Retrieve specific SRM document by ID.
        
        Args:
            document_id: ID of the SRM document
            
        Returns:
            JSON string of document or error message
        """
        try:
            self._initialize_client()
            
            @self.error_handler.with_retry(ErrorType.AZURE_SEARCH_OPERATION)
            def _get():
                # Use real Azure Search if client is initialized
                if self._client and self._client != "mock_client":
                    try:
                        document = self._client.get_document(key=document_id)
                        print(f"[GET DOCUMENT] ID: {document_id} - Found")
                        return dict(document)
                    except Exception as e:
                        print(f"[GET DOCUMENT ERROR] ID: {document_id} - {e}")
                        raise
                else:
                    # Fallback to mock
                    print(f"[MOCK GET] Document ID: {document_id}")
                    return None
            
            document = _get()
            return json.dumps(document, indent=2)
            
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.AZURE_SEARCH_OPERATION,
                e,
                "get_srm_document"
            )
            return f"Document retrieval failed: {e}"
    
    @kernel_function(
        description="Update SRM document fields in the search index",
        name="update_srm_document"
    )
    async def update_srm_document(self, document_id: str, updates: str) -> str:
        """
        Update SRM document fields in the search index.
        
        Args:
            document_id: ID of document to update
            updates: JSON string of field updates
            
        Returns:
            Success or error message
        """
        try:
            self._initialize_client()
            
            # Parse updates
            update_data = json.loads(updates)
            
            @self.error_handler.with_retry(ErrorType.AZURE_SEARCH_OPERATION)
            def _update():
                import logging
                logger = logging.getLogger(__name__)
                
                # Log what we're about to do
                log_message = (
                    f"\n{'='*80}\n"
                    f"{'[MOCK UPDATE]' if self.mock_updates else '[LIVE UPDATE]'} "
                    f"{'Would update' if self.mock_updates else 'Updating'} Azure AI Search index\n"
                    f"{'='*80}\n"
                    f"Document ID: {document_id}\n"
                    f"Index: {self.index_name}\n"
                    f"Fields to update:\n"
                )
                
                for field, value in update_data.items():
                    # Truncate long values for logging
                    value_str = str(value)
                    if len(value_str) > 200:
                        value_str = value_str[:200] + "... (truncated)"
                    log_message += f"  - {field}: {value_str}\n"
                
                log_message += f"{'='*80}\n"
                
                logger.info(log_message)
                print(log_message)
                
                # Perform actual update if not mocking
                if not self.mock_updates:
                    if self._client and self._client != "mock_client":
                        try:
                            # Prepare update document
                            update_doc = {
                                "SRM_ID": document_id,
                                "@search.action": "merge"
                            }
                            update_doc.update(update_data)
                            
                            # Upload to index
                            result = self._client.upload_documents(documents=[update_doc])
                            
                            # Check result
                            if result and len(result) > 0 and result[0].succeeded:
                                logger.info(f"[SUCCESS] Updated document {document_id} in Azure AI Search")
                                return {"succeeded": True, "mocked": False}
                            else:
                                error_msg = f"Failed to update document {document_id}"
                                if result and len(result) > 0:
                                    error_msg += f": {result[0].error_message}"
                                logger.error(error_msg)
                                return {"succeeded": False, "error": error_msg}
                        except Exception as e:
                            logger.error(f"[ERROR] Updating document {document_id}: {e}")
                            raise
                    else:
                        logger.warning("Cannot perform live update - Azure Search client not initialized")
                        return {"succeeded": False, "error": "Client not initialized"}
                else:
                    # Mock mode - just return success
                    return {"succeeded": True, "mocked": True}
            
            result = _update()
            
            if result.get("succeeded"):
                return f"Document {document_id} updated successfully"
            else:
                return f"Failed to update document {document_id}"
                
        except json.JSONDecodeError as e:
            return f"Invalid JSON in updates: {e}"
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.AZURE_SEARCH_OPERATION,
                e,
                "update_srm_document"
            )
            return f"Document update failed: {e}"
    
    @kernel_function(
        description="Find SRM documents with similarity score above threshold",
        name="find_similar_srms"
    )
    async def find_similar_srms(self, query: str, similarity_threshold: float = 0.7) -> str:
        """
        Find SRM documents with similarity above threshold.
        
        Args:
            query: Search query
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            
        Returns:
            JSON string of similar documents or error message
        """
        try:
            self._initialize_client()
            
            @self.error_handler.with_retry(ErrorType.AZURE_SEARCH_OPERATION)
            def _find_similar():
                # Return mock similar results for similarity scoring
                mock_results = [
                    {
                        "srm_id": "srm_001",
                        "name": "Application Server SRM",
                        "similarity_score": 0.95
                    },
                    {
                        "srm_id": "srm_002", 
                        "name": "Web Server SRM",
                        "similarity_score": 0.78
                    }
                ]
                
                # Filter by threshold
                filtered_results = [
                    result for result in mock_results 
                    if result["similarity_score"] >= similarity_threshold
                ]
                
                return filtered_results
            
            results = _find_similar()
            return json.dumps(results, indent=2)
            
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.AZURE_SEARCH_OPERATION,
                e,
                "find_similar_srms"
            )
            return f"Similarity search failed: {e}"
