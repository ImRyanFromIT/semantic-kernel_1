'''
Retrieval step - Perform vector search to find candidate SRMs.
'''

import logging
from enum import Enum

from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import KernelProcessStep, KernelProcessStepContext
from semantic_kernel.processes.kernel_process.kernel_process_step_metadata import kernel_process_step_metadata

from src.memory.vector_store_base import VectorStoreBase


# Configure logger
logger = logging.getLogger(__name__)


@kernel_process_step_metadata("RetrievalStep.V1")
class RetrievalStep(KernelProcessStep):
    '''
    Process step to retrieve candidate SRMs using vector search.
    
    This step performs semantic search over the SRM catalog to find
    relevant candidates based on the user's query.
    
    Note: VectorStore is passed through event data due to SK ProcessBuilder constraints.
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
            input_data: Dictionary containing key_terms, user_query, session_id
        '''
        # Extract data from input
        key_terms = input_data.get('key_terms', [])
        user_query = input_data.get('user_query', '')
        session_id = input_data.get('session_id', '')
        vector_store = input_data.get('vector_store')
        kernel = input_data.get('kernel')
        result_container = input_data.get('result_container', {})
        
        logger.info("Searching for SRM candidates", extra={"session_id": session_id, "query": user_query, "key_terms": key_terms})
        
        # Build enhanced query using key terms
        search_query = self._build_search_query(user_query, key_terms)
        logger.debug("Enhanced search query built", extra={"session_id": session_id, "search_query": search_query})
        
        # Perform vector search using vector_store from input_data
        top_k = 5  # Get top 5 candidates for reranking
        try:
            logger.debug("Calling vector store search", extra={"session_id": session_id, "top_k": top_k})
            results = await vector_store.search(search_query, top_k=top_k)
            logger.debug("Search completed", extra={"session_id": session_id})
        except Exception as e:
            logger.error("Search failed", extra={"session_id": session_id, "error": str(e)})
            await context.emit_event(
                process_event=self.OutputEvents.NoCandidates.value,
                data={"error": str(e), "user_query": user_query, "session_id": session_id}
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
                # Use record.srm_id (SRM_ID field from Azure Search) instead of record.id (document key)
                candidates.append({
                    'srm_id': record.srm_id if hasattr(record, 'srm_id') and record.srm_id else record.id,
                    'name': record.name if hasattr(record, 'name') else '',
                    'category': record.category if hasattr(record, 'category') else 'General',
                    'owning_team': record.owning_team if hasattr(record, 'owning_team') else '',
                    'use_case': record.use_case if hasattr(record, 'use_case') else '',
                    'score': result.score,
                    'url': record.url if hasattr(record, 'url') else '',
                    'owner_notes': record.owner_notes if hasattr(record, 'owner_notes') else '',
                    'hidden_notes': record.hidden_notes if hasattr(record, 'hidden_notes') else '',
                })
        
        logger.info("Candidate search completed", extra={"session_id": session_id, "candidate_count": len(candidates)})
        
        # Emit appropriate event with dependencies
        if len(candidates) > 0:
            # Pass candidates to reranker for LLM-based scoring
            await context.emit_event(
                process_event=self.OutputEvents.CandidatesFound.value,
                data={
                    "candidates": candidates,
                    "user_query": user_query,
                    "search_query": search_query,
                    "session_id": session_id,
                    "vector_store": vector_store,
                    "kernel": kernel,
                    "result_container": result_container,
                    "feedback_processor": input_data.get('feedback_processor'),
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
                    "session_id": session_id,
                    "vector_store": vector_store,
                    "kernel": kernel,
                    "result_container": result_container,
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

