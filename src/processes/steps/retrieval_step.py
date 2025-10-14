'''
Retrieval step - Perform vector search to find candidate SRMs.
'''

from enum import Enum

from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import KernelProcessStep, KernelProcessStepContext

from src.utils.debug_config import debug_print

class RetrievalStep(KernelProcessStep):
    '''
    Process step to retrieve candidate SRMs using vector search.
    
    This step performs semantic search over the SRM catalog to find
    relevant candidates based on the user's query.
    '''
    
    class OutputEvents(Enum):
        '''Output events from the retrieval step.'''
        CandidatesFound = "CandidatesFound"
        NoCandidates = "NoCandidates"
    
    @kernel_function(name="search_srms")
    async def search_srms(
        self,
        context: KernelProcessStepContext,
        input_data: dict,
    ) -> None:
        '''
        Search for candidate SRMs using vector similarity.
        
        Args:
            context: Process step context
            input_data: Dictionary containing key_terms, user_query, vector_store, session_id
        '''
        # Extract data from input
        key_terms = input_data.get('key_terms', [])
        user_query = input_data.get('user_query', '')
        vector_store = input_data.get('vector_store')
        session_id = input_data.get('session_id', '')
        
        debug_print(f"DEBUG RetrievalStep: Called with user_query='{user_query}', key_terms={key_terms}, session_id='{session_id}'")
        
        # Build enhanced query using key terms
        search_query = self._build_search_query(user_query, key_terms)
        debug_print(f"DEBUG RetrievalStep: Search query: '{search_query}'")
        
        # Perform vector search
        top_k = 8  # Get top 8 candidates for reranking
        try:
            debug_print(f"DEBUG RetrievalStep: Calling vector_store.search('{search_query}', top_k={top_k})")
            results = await vector_store.search(search_query, top_k=top_k)
            debug_print(f"DEBUG RetrievalStep: Search completed, results type: {type(results)}")
        except Exception as e:
            debug_print(f"DEBUG RetrievalStep: Search failed with error: {e}")
            await context.emit_event(
                process_event=self.OutputEvents.NoCandidates.value,
                data={"error": str(e), "user_query": user_query, "vector_store": vector_store, "session_id": session_id}
            )
            return
        
        # Collect results
        candidates = []
        async for result in results:
            record = result.record
            
            # Handle team-based results from Azure AI Search
            # If the record has srm_names, create candidates for each SRM
            if hasattr(record, 'srm_names') and record.srm_names:
                # Team record with multiple SRMs
                for i, srm_name in enumerate(record.srm_names):
                    srm_url = record.srm_urls[i] if i < len(record.srm_urls) else "#"
                    candidates.append({
                        'srm_id': f"{record.id}_srm_{i}",
                        'name': srm_name,
                        'category': record.category if hasattr(record, 'category') else 'General',
                        'owning_team': record.owning_team if hasattr(record, 'owning_team') else record.team if hasattr(record, 'team') else '',
                        'use_case': record.use_case if hasattr(record, 'use_case') else record.content if hasattr(record, 'content') else '',
                        'score': result.score,
                        'team_name': record.name if hasattr(record, 'name') else '',
                        'services_offered': record.services_offered if hasattr(record, 'services_offered') else [],
                        'url': srm_url,
                    })
            else:
                # Standard SRM record
                candidates.append({
                    'srm_id': record.id,
                    'name': record.name if hasattr(record, 'name') else '',
                    'category': record.category if hasattr(record, 'category') else 'General',
                    'owning_team': record.owning_team if hasattr(record, 'owning_team') else '',
                    'use_case': record.use_case if hasattr(record, 'use_case') else '',
                    'score': result.score,
                    'url': record.url if hasattr(record, 'url') else '',
                })
        
        debug_print(f"DEBUG RetrievalStep: Found {len(candidates)} candidates")
        
        # Emit appropriate event
        if len(candidates) > 0:
            # Pass candidates to reranker for LLM-based scoring
            await context.emit_event(
                process_event=self.OutputEvents.CandidatesFound.value,
                data={
                    "candidates": candidates,
                    "user_query": user_query,
                    "search_query": search_query,
                    "vector_store": vector_store,
                    "session_id": session_id,
                }
            )
        else:
            await context.emit_event(
                process_event=self.OutputEvents.NoCandidates.value,
                data={
                    "selected_srm": None,
                    "confidence": 0.0,
                    "alternatives": [],
                    "query": search_query,
                    "user_query": user_query,
                    "vector_store": vector_store,
                    "session_id": session_id,
                }
            )
    
    def _build_search_query(self, user_query: str, key_terms: list[str]) -> str:
        '''
        Build an enhanced search query.
        
        Args:
            user_query: Original user query
            key_terms: Extracted key terms
            
        Returns:
            Enhanced search query
        '''
        # For now, just use the original query
        # In production, you might enhance with key terms or synonyms
        if key_terms:
            # Add key terms to boost relevance
            enhanced_query = f"{user_query} {' '.join(key_terms)}"
            return enhanced_query
        
        return user_query

