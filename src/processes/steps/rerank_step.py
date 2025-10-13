'''
Rerank step - Score and select the best SRM recommendations.
'''

from enum import Enum

from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import KernelProcessStep, KernelProcessStepContext

from src.utils.debug_config import debug_print


class RerankStep(KernelProcessStep):
    '''
    Process step to rerank candidates and select the best recommendations.
    
    This step uses simple scoring to rank candidates based on task match and
    owner relevance, then selects the top 1-3 recommendations.
    '''
    
    class OutputEvents(Enum):
        '''Output events from the rerank step.'''
        RecommendationSelected = "RecommendationSelected"
        MultipleOptions = "MultipleOptions"
    
    @kernel_function(name="rerank_candidates")
    async def rerank_candidates(
        self,
        context: KernelProcessStepContext,
        input_data: dict,
    ) -> None:
        '''
        Rerank candidates and select the best recommendations.
        
        Args:
            context: Process step context
            input_data: Dictionary containing candidates, user_query, vector_store, session_id
        '''
        # Extract data from input
        candidates = input_data.get('candidates', [])
        user_query = input_data.get('user_query', '')
        vector_store = input_data.get('vector_store')
        session_id = input_data.get('session_id', '')
        
        debug_print(f"DEBUG RerankStep: Called with {len(candidates) if candidates else 0} candidates, session_id='{session_id}'")
        
        if not candidates:
            # No candidates to rerank
            await context.emit_event(
                process_event=self.OutputEvents.RecommendationSelected.value,
                data={
                    "selected_srm": None,
                    "confidence": 0.0,
                    "alternatives": [],
                    "user_query": user_query,
                    "vector_store": vector_store,
                    "session_id": session_id,
                },
            )
            return
        
        # For initial implementation, use simple scoring
        # In production, use LLM to score each candidate
        scored_candidates = self._score_candidates(candidates, user_query)
        
        # Sort by score
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Select top recommendation
        top_candidate = scored_candidates[0]
        
        # Determine confidence
        confidence = self._calculate_confidence(scored_candidates)
        
        # Emit event with all necessary data
        await context.emit_event(
            process_event=self.OutputEvents.RecommendationSelected.value,
            data={
                "selected_srm": top_candidate,
                "confidence": confidence,
                "alternatives": scored_candidates[1:3],
                "ranked_candidates": scored_candidates[:3],
                "user_query": user_query,
                "vector_store": vector_store,
                "session_id": session_id,
            }
        )
    
    def _score_candidates(self, candidates: list[dict], user_query: str) -> list[dict]:
        '''
        Score candidates based on relevance.
        
        Args:
            candidates: List of candidate SRMs
            user_query: User's query
            
        Returns:
            List of candidates with updated scores
        '''
        # Simple scoring based on keyword matching
        # In production, use LLM for better scoring
        query_lower = user_query.lower()
        
        for candidate in candidates:
            # Start with vector similarity score
            base_score = candidate.get('score', 0.5)
            
            # Boost score if category or use_case match query terms
            category_boost = 0.0
            if candidate['category'].lower() in query_lower:
                category_boost = 0.1
            
            use_case_boost = 0.0
            use_case_words = candidate['use_case'].lower().split()
            query_words = query_lower.split()
            overlap = len(set(use_case_words) & set(query_words))
            use_case_boost = min(0.2, overlap * 0.05)
            
            # Update score
            candidate['score'] = min(1.0, base_score + category_boost + use_case_boost)
        
        return candidates
    
    def _calculate_confidence(self, scored_candidates: list[dict]) -> float:
        '''
        Calculate confidence in the top recommendation.
        
        Args:
            scored_candidates: List of scored candidates (sorted)
            
        Returns:
            Confidence score (0-1)
        '''
        if len(scored_candidates) == 0:
            return 0.0
        
        if len(scored_candidates) == 1:
            return 0.9
        
        # Calculate confidence based on score gap
        top_score = scored_candidates[0]['score']
        second_score = scored_candidates[1]['score'] if len(scored_candidates) > 1 else 0.0
        
        gap = top_score - second_score
        
        # Confidence increases with score gap
        confidence = min(0.95, 0.5 + gap)
        
        return confidence

