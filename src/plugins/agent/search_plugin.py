"""
Search plugin for Azure AI Search operations.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Annotated
from semantic_kernel.functions import kernel_function

from src.utils.error_handler import ErrorHandler, ErrorType


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
        self.logger = logging.getLogger(__name__)
    
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
        description=(
            "Search for Service Request Model (SRM) documents in Azure AI Search by title or keywords. "
            "WHEN TO USE: When you need to find an SRM mentioned in an email or chat conversation. "
            "The user might say 'update SRM for storage expansion' - use this function to find the exact SRM_ID. "
            "RETURNS: JSON array of matching SRMs with SRM_ID, SRM_Title, Category, Owner, and other metadata. "
            "If multiple matches, show the user the top results and ask which one they mean."
        ),
        name="search_srm"
    )
    async def search_srm(
        self,
        query: Annotated[str, "The SRM title or keywords to search for (e.g., 'storage expansion', 'VM capacity request')"],
        top_k: Annotated[int, "Maximum number of results to return (default: 10, use lower for focused results)"] = 10
    ) -> Annotated[str, "JSON array of matching SRM documents with SRM_ID, SRM_Title, and metadata, or error message"]:
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
        description=(
            "Update SRM document fields in Azure AI Search index with new owner_notes or hidden_notes. "
            "CRITICAL: This function MUST be called IMMEDIATELY after user confirms they want to update an SRM. "
            "DO NOT just say 'I'll update it' - STOP and CALL THIS FUNCTION FIRST. "
            "WHEN TO USE: After user confirms update (e.g., 'yes, make the change', 'go ahead', 'update it'). "
            "PROCESS: 1) User confirms update → 2) Call this function → 3) Wait for result → 4) Report what happened. "
            "PARAMETERS: document_id is the SRM_ID (like 'SRM-051'), updates is JSON string like '{\"owner_notes\": \"new text\"}'. "
            "RETURN VALUE: JSON with before/after values - SAVE THIS, you'll need it if user wants email notifications. "
            "IMPORTANT: After calling, ask 'Would you like me to send a notification email about this change?'"
        ),
        name="update_srm_document"
    )
    async def update_srm_document(
        self,
        document_id: Annotated[str, "The SRM_ID of the document to update (e.g., 'SRM-051', 'SRM-123')"],
        updates: Annotated[str, "JSON string of field updates, e.g., '{\"owner_notes\": \"Updated text\"}' or '{\"hidden_notes\": \"Internal notes\"}'"]
    ) -> Annotated[str, "JSON with success status, srm_id, srm_title, and changes array with before/after values for each field"]:
        """
        Update SRM document fields in the search index.
        
        Args:
            document_id: ID of document to update
            updates: JSON string of field updates
            
        Returns:
            JSON string with update result including before/after values
        """
        try:
            self._initialize_client()
            
            # Parse updates
            update_data = json.loads(updates)
            
            # First, retrieve the current document to capture "before" state
            before_state = {}
            srm_title = None
            
            if not self.mock_updates and self._client and self._client != "mock_client":
                try:
                    # Get current document
                    doc_result = self._client.get_document(key=document_id)
                    if doc_result:
                        srm_title = doc_result.get('SRM_Title') or doc_result.get('srm_title')
                        # Capture before values for fields being updated
                        for field in update_data.keys():
                            # Map field names to index schema
                            if field in ["owner_notes", "Owner_Notes"]:
                                before_state["owner_notes"] = doc_result.get('owner_notes', '')
                            elif field in ["hidden_notes", "Hidden_Notes"]:
                                before_state["hidden_notes"] = doc_result.get('hidden_notes', '')
                            else:
                                before_state[field] = doc_result.get(field, '')
                except Exception as e:
                    # If we can't get the before state, log warning but continue
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Could not retrieve before state for {document_id}: {e}")
            
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
                    f"SRM_ID: {document_id}\n"
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
                            # SRM_ID is the KEY field in this index
                            # Prepare update document using SRM_ID as the key
                            update_doc = {
                                "SRM_ID": document_id,  # SRM_ID is the key field in your index
                                "@search.action": "merge"
                            }
                            
                            # Map field names to match index schema (lowercase with underscores)
                            mapped_updates = {}
                            for field, value in update_data.items():
                                # Convert owner_notes/hidden_notes to match index schema
                                if field == "owner_notes":
                                    mapped_updates["owner_notes"] = value
                                elif field == "hidden_notes":
                                    mapped_updates["hidden_notes"] = value
                                elif field == "Owner_Notes":
                                    mapped_updates["owner_notes"] = value
                                elif field == "Hidden_Notes":
                                    mapped_updates["hidden_notes"] = value
                                else:
                                    mapped_updates[field] = value
                            
                            update_doc.update(mapped_updates)
                            
                            logger.info(f"Updating document with SRM_ID: {document_id}")
                            logger.info(f"Mapped update fields: {list(mapped_updates.keys())}")
                            
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
                # Build structured response with before/after values
                changes = []
                for field, after_value in update_data.items():
                    # Normalize field name
                    normalized_field = field
                    if field in ["Owner_Notes", "owner_notes"]:
                        normalized_field = "owner_notes"
                    elif field in ["Hidden_Notes", "hidden_notes"]:
                        normalized_field = "hidden_notes"
                    
                    changes.append({
                        "field": normalized_field,
                        "before": before_state.get(normalized_field, ""),
                        "after": after_value
                    })
                
                response = {
                    "success": True,
                    "srm_id": document_id,
                    "srm_title": srm_title or document_id,
                    "changes": changes,
                    "mocked": result.get("mocked", False)
                }
                
                return json.dumps(response, indent=2)
            else:
                error_response = {
                    "success": False,
                    "srm_id": document_id,
                    "error": result.get("error", "Unknown error")
                }
                return json.dumps(error_response, indent=2)
                
        except json.JSONDecodeError as e:
            error_response = {
                "success": False,
                "srm_id": document_id,
                "error": f"Invalid JSON in updates: {e}"
            }
            return json.dumps(error_response, indent=2)
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.AZURE_SEARCH_OPERATION,
                e,
                "update_srm_document"
            )
            error_response = {
                "success": False,
                "srm_id": document_id,
                "error": f"Document update failed: {e}"
            }
            return json.dumps(error_response, indent=2)
    
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
