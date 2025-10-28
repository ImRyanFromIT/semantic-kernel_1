'''
Rerank step - Use LLM to semantically score and select the best SRM recommendations.
'''

import json
import logging
from enum import Enum

from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import KernelProcessStep, KernelProcessStepContext
from semantic_kernel.processes.kernel_process.kernel_process_step_metadata import kernel_process_step_metadata


# Configure logger
logger = logging.getLogger(__name__)


@kernel_process_step_metadata("RerankStep.V1")
class RerankStep(KernelProcessStep):
    '''
    Process step to rerank candidates using LLM-based semantic scoring.
    
    This step uses an LLM to analyze each candidate's relevance to the user query
    and selects the top recommendations based on semantic understanding.
    
    Note: Kernel is passed through event data due to SK ProcessBuilder constraints.
    '''
    
    class OutputEvents(Enum):
        '''Output events from the rerank step.'''
        RecommendationSelected = "RecommendationSelected"
    
    @kernel_function(name="rerank_candidates")
    async def rerank_candidates(
        self,
        context: KernelProcessStepContext,
        input_data: dict,
    ) -> None:
        '''
        Rerank candidates using LLM semantic analysis with feedback integration.
        
        Args:
            context: Process step context
            input_data: Dictionary containing candidates, user_query, session_id, feedback_processor
        '''
        # Extract data from input
        candidates = input_data.get('candidates', [])
        user_query = input_data.get('user_query', '')
        session_id = input_data.get('session_id', '')
        vector_store = input_data.get('vector_store')
        kernel = input_data.get('kernel')
        result_container = input_data.get('result_container', {})
        feedback_processor = input_data.get('feedback_processor')
        
        logger.info("Reranking candidates", extra={"session_id": session_id, "candidate_count": len(candidates) if candidates else 0})
        
        # Get feedback context for this query if feedback_processor is available
        feedback_context = None
        if feedback_processor:
            feedback_context = feedback_processor.get_feedback_for_query_context(user_query)
            if feedback_context.get('has_feedback'):
                logger.info(
                    "Applying feedback to reranking", 
                    extra={
                        "session_id": session_id, 
                        "negative_srms": len(feedback_context.get('negative_srms', [])),
                        "positive_srms": len(feedback_context.get('positive_srms', []))
                    }
                )
        
        if not candidates:
            # No candidates to rerank
            logger.warning("No candidates to rerank", extra={"session_id": session_id})
            await context.emit_event(
                process_event=self.OutputEvents.RecommendationSelected.value,
                data={
                    "selected_srm": None,
                    "confidence": 0.0,
                    "alternatives": [],
                    "user_query": user_query,
                    "session_id": session_id,
                    "vector_store": vector_store,
                    "kernel": kernel,
                    "result_container": result_container,
                },
            )
            return
        
        # Use LLM to score candidates using kernel from input_data
        scored_candidates = await self._llm_score_candidates(candidates, user_query, kernel)
        
        # Apply feedback adjustments to scores
        if feedback_context and feedback_context.get('has_feedback'):
            scored_candidates = self._apply_feedback_adjustments(
                scored_candidates, 
                feedback_context
            )
        
        # Sort by adjusted LLM score
        scored_candidates.sort(key=lambda x: x['llm_score'], reverse=True)
        
        top_scores = [c['llm_score'] for c in scored_candidates[:3]]
        logger.debug("Candidates ranked", extra={"session_id": session_id, "top_3_scores": top_scores})
        
        # Select top recommendation
        top_candidate = scored_candidates[0]
        
        # Determine confidence based on LLM score
        confidence = self._calculate_confidence(scored_candidates)
        
        logger.info("Recommendation selected", extra={"session_id": session_id, "top_srm": top_candidate['name'], "confidence": confidence})
        
        # Emit event with dependencies
        await context.emit_event(
            process_event=self.OutputEvents.RecommendationSelected.value,
            data={
                "selected_srm": top_candidate,
                "confidence": confidence,
                "alternatives": scored_candidates[1:3],  # Always include 2 alternatives
                "ranked_candidates": scored_candidates[:3],
                "user_query": user_query,
                "session_id": session_id,
                "vector_store": vector_store,
                "kernel": kernel,
                "result_container": result_container,
            }
        )
    
    async def _llm_score_candidates(self, candidates: list[dict], user_query: str, kernel: Kernel) -> list[dict]:
        '''
        Use LLM to score candidates based on semantic relevance.
        
        Args:
            candidates: List of candidate SRMs
            user_query: User's query
            kernel: Semantic Kernel instance
            
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
        rerank_plugin = kernel.get_plugin("semantic_reranker")
        rerank_function = rerank_plugin["semantic_reranking"]
        
        try:
            # Call LLM to score candidates
            result = await kernel.invoke(
                rerank_function,
                user_query=user_query,
                candidates=candidates_text
            )
            
            result_text = str(result).strip()
            logger.debug("LLM reranking response received", extra={"response_preview": result_text[:200]})
            
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
            logger.warning("LLM scoring failed, falling back to BM25 scores", extra={"error": str(e)})
            # Fallback to original BM25 scores normalized to 0-100
            for candidate in candidates:
                # Normalize BM25 score (typically 0-10) to 0-100
                candidate['llm_score'] = min(100, candidate.get('score', 0) * 10)
                candidate['llm_reasoning'] = 'Fallback to BM25 score'
        
        return candidates
    
    def _apply_feedback_adjustments(
        self, 
        candidates: list[dict], 
        feedback_context: dict
    ) -> list[dict]:
        '''
        Apply feedback-based score adjustments to candidates.
        
        Args:
            candidates: List of scored candidates
            feedback_context: Feedback context with positive/negative SRM lists
            
        Returns:
            List of candidates with adjusted scores
        '''
        negative_srms = set(feedback_context.get('negative_srms', []))
        positive_srms = set(feedback_context.get('positive_srms', []))
        
        for candidate in candidates:
            srm_id = candidate.get('srm_id', '')
            
            # Apply penalties for negative feedback
            if srm_id in negative_srms:
                # Reduce score by 30% for negative feedback
                penalty = candidate['llm_score'] * 0.3
                candidate['llm_score'] = max(0, candidate['llm_score'] - penalty)
                candidate['feedback_adjusted'] = True
                candidate['adjustment_type'] = 'negative'
                logger.debug(
                    f"Applied negative feedback penalty to {candidate.get('name', 'unknown')}: "
                    f"-{penalty:.1f} points"
                )
            
            # Apply boosts for positive feedback
            if srm_id in positive_srms:
                # Increase score by 40% for positive feedback
                boost = candidate['llm_score'] * 0.4
                candidate['llm_score'] = min(100, candidate['llm_score'] + boost)
                candidate['feedback_adjusted'] = True
                candidate['adjustment_type'] = 'positive'
                logger.debug(
                    f"Applied positive feedback boost to {candidate.get('name', 'unknown')}: "
                    f"+{boost:.1f} points"
                )
        
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

