'''
Rerank step - Use LLM to semantically score and select the best SRM recommendations.
'''

import json
from enum import Enum

from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import KernelProcessStep, KernelProcessStepContext

from src.utils.debug_config import debug_print


class RerankStep(KernelProcessStep):
    '''
    Process step to rerank candidates using LLM-based semantic scoring.
    
    This step uses an LLM to analyze each candidate's relevance to the user query
    and selects the top recommendations based on semantic understanding.
    '''
    
    _kernel: Kernel = None
    
    class OutputEvents(Enum):
        '''Output events from the rerank step.'''
        RecommendationSelected = "RecommendationSelected"
    
    @classmethod
    def set_kernel(cls, kernel: Kernel):
        '''Set the kernel for all instances of this step.'''
        cls._kernel = kernel
    
    @property
    def kernel(self) -> Kernel:
        '''Get the kernel instance.'''
        return self.__class__._kernel
    
    @kernel_function(name="rerank_candidates")
    async def rerank_candidates(
        self,
        context: KernelProcessStepContext,
        input_data: dict,
    ) -> None:
        '''
        Rerank candidates using LLM semantic analysis.
        
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
        
        # Use LLM to score candidates
        scored_candidates = await self._llm_score_candidates(candidates, user_query)
        
        # Sort by LLM score
        scored_candidates.sort(key=lambda x: x['llm_score'], reverse=True)
        
        debug_print(f"DEBUG RerankStep: Top 3 scores: {[c['llm_score'] for c in scored_candidates[:3]]}")
        
        # Select top recommendation
        top_candidate = scored_candidates[0]
        
        # Determine confidence based on LLM score
        confidence = self._calculate_confidence(scored_candidates)
        
        # Emit event with all necessary data
        await context.emit_event(
            process_event=self.OutputEvents.RecommendationSelected.value,
            data={
                "selected_srm": top_candidate,
                "confidence": confidence,
                "alternatives": scored_candidates[1:3],  # Always include 2 alternatives
                "ranked_candidates": scored_candidates[:3],
                "user_query": user_query,
                "vector_store": vector_store,
                "session_id": session_id,
            }
        )
    
    async def _llm_score_candidates(self, candidates: list[dict], user_query: str) -> list[dict]:
        '''
        Use LLM to score candidates based on semantic relevance.
        
        Args:
            candidates: List of candidate SRMs
            user_query: User's query
            
        Returns:
            List of candidates with LLM scores
        '''
        # Format candidates for LLM
        candidates_text = ""
        for i, candidate in enumerate(candidates):
            candidates_text += f"\n[{i}] Name: {candidate['name']}\n"
            candidates_text += f"    Category: {candidate['category']}\n"
            candidates_text += f"    Use Case: {candidate['use_case']}\n"
            candidates_text += f"    Team: {candidate['owning_team']}\n"
        
        # Get the reranking plugin
        rerank_plugin = self.kernel.get_plugin("semantic_reranker")
        rerank_function = rerank_plugin["semantic_reranking"]
        
        try:
            # Call LLM to score candidates
            result = await self.kernel.invoke(
                rerank_function,
                user_query=user_query,
                candidates=candidates_text
            )
            
            result_text = str(result).strip()
            debug_print(f"DEBUG RerankStep: LLM response: {result_text[:200]}...")
            
            # Parse JSON response
            rankings_data = json.loads(result_text)
            rankings = rankings_data.get('rankings', [])
            
            # Apply LLM scores to candidates
            for ranking in rankings:
                idx = ranking['candidate_index']
                if 0 <= idx < len(candidates):
                    candidates[idx]['llm_score'] = ranking['score']
                    candidates[idx]['llm_reasoning'] = ranking.get('reasoning', '')
            
            # Ensure all candidates have a score
            for candidate in candidates:
                if 'llm_score' not in candidate:
                    candidate['llm_score'] = 0
                    candidate['llm_reasoning'] = 'No score provided'
            
        except Exception as e:
            debug_print(f"DEBUG RerankStep: LLM scoring failed: {e}")
            # Fallback to original BM25 scores normalized to 0-100
            for candidate in candidates:
                # Normalize BM25 score (typically 0-10) to 0-100
                candidate['llm_score'] = min(100, candidate.get('score', 0) * 10)
                candidate['llm_reasoning'] = 'Fallback to BM25 score'
        
        return candidates
    
    def _calculate_confidence(self, scored_candidates: list[dict]) -> float:
        '''
        Calculate confidence in the top recommendation based on LLM scores.
        
        Args:
            scored_candidates: List of scored candidates (sorted by llm_score)
            
        Returns:
            Confidence score (0-1)
        '''
        if len(scored_candidates) == 0:
            return 0.0
        
        if len(scored_candidates) == 1:
            # Single candidate - confidence based on absolute score
            return min(0.95, scored_candidates[0]['llm_score'] / 100.0)
        
        # Calculate confidence based on score gap and absolute score
        top_score = scored_candidates[0]['llm_score']
        second_score = scored_candidates[1]['llm_score']
        
        gap = top_score - second_score
        
        # High score + large gap = high confidence
        # Score component: 0-100 → 0-0.5
        score_component = (top_score / 100.0) * 0.5
        
        # Gap component: 0-100 → 0-0.5
        gap_component = min(gap / 100.0, 0.5)
        
        confidence = min(0.95, score_component + gap_component)
        
        return confidence

