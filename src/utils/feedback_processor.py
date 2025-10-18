'''
Feedback processor for applying user feedback to improve search results.
'''

import logging
from typing import Optional

from src.models.feedback_record import FeedbackRecord, FeedbackType
from src.memory.feedback_store import FeedbackStore
from src.memory.vector_store_base import VectorStoreBase


logger = logging.getLogger(__name__)


class FeedbackProcessor:
    '''
    Processes user feedback to update search index scoring.
    
    Implements three-part strategy:
    1. Lower relevance of incorrectly recommended SRMs
    2. Add negative examples to prevent future incorrect matches
    3. Boost correct SRMs for similar queries
    '''
    
    def __init__(
        self, 
        feedback_store: FeedbackStore, 
        vector_store: VectorStoreBase
    ):
        '''
        Initialize the feedback processor.
        
        Args:
            feedback_store: Store for persisting feedback
            vector_store: Vector store to update with feedback
        '''
        self.feedback_store = feedback_store
        self.vector_store = vector_store
    
    async def process_feedback(self, feedback: FeedbackRecord) -> bool:
        '''
        Process feedback and update search index accordingly.
        
        Implements the 3-part strategy:
        - Lower relevance of incorrect SRM
        - Add negative example association
        - Boost correct SRM (if provided)
        
        Args:
            feedback: FeedbackRecord to process
            
        Returns:
            True if successfully processed, False otherwise
        '''
        try:
            logger.info(
                f"Processing feedback {feedback.id} for session {feedback.session_id}"
            )
            
            # Part 1 & 2: Lower relevance and add negative example for incorrect SRM
            if feedback.incorrect_srm_id:
                await self._apply_negative_feedback(
                    srm_id=feedback.incorrect_srm_id,
                    query=feedback.query,
                    user_id=feedback.user_id
                )
            
            # Part 3: Boost correct SRM if provided
            if feedback.correct_srm_id and feedback.feedback_type == FeedbackType.CORRECTION:
                await self._apply_positive_feedback(
                    srm_id=feedback.correct_srm_id,
                    query=feedback.query,
                    user_id=feedback.user_id
                )
            
            # Mark feedback as applied
            self.feedback_store.mark_as_applied(feedback.id)
            
            logger.info(f"Successfully processed feedback {feedback.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing feedback {feedback.id}: {e}")
            return False
    
    async def _apply_negative_feedback(
        self, 
        srm_id: str, 
        query: str, 
        user_id: Optional[str] = None
    ) -> None:
        '''
        Apply negative feedback to lower relevance of incorrect SRM.
        
        Args:
            srm_id: ID of the incorrectly recommended SRM
            query: Original query that led to incorrect recommendation
            user_id: Optional user ID for personalized adjustments
        '''
        logger.debug(f"Applying negative feedback for SRM {srm_id}")
        
        # Update vector store with negative signal
        await self.vector_store.update_feedback_scores(
            srm_id=srm_id,
            query=query,
            feedback_type="negative",
            user_id=user_id
        )
    
    async def _apply_positive_feedback(
        self, 
        srm_id: str, 
        query: str, 
        user_id: Optional[str] = None
    ) -> None:
        '''
        Apply positive feedback to boost relevance of correct SRM.
        
        Args:
            srm_id: ID of the correct SRM
            query: Original query that should match this SRM
            user_id: Optional user ID for personalized adjustments
        '''
        logger.debug(f"Applying positive feedback for SRM {srm_id}")
        
        # Update vector store with positive signal
        await self.vector_store.update_feedback_scores(
            srm_id=srm_id,
            query=query,
            feedback_type="positive",
            user_id=user_id
        )
    
    async def process_pending_feedback(self) -> int:
        '''
        Process all pending feedback that hasn't been applied yet.
        
        Returns:
            Number of feedback records processed
        '''
        pending = self.feedback_store.get_unapplied_feedback()
        
        if not pending:
            logger.info("No pending feedback to process")
            return 0
        
        logger.info(f"Processing {len(pending)} pending feedback records")
        
        processed_count = 0
        for feedback in pending:
            success = await self.process_feedback(feedback)
            if success:
                processed_count += 1
        
        logger.info(f"Processed {processed_count}/{len(pending)} feedback records")
        return processed_count
    
    def get_feedback_summary_for_srm(self, srm_id: str) -> dict:
        '''
        Get summary of feedback for a specific SRM.
        
        Args:
            srm_id: SRM ID to get feedback for
            
        Returns:
            Dictionary with feedback statistics
        '''
        feedback_list = self.feedback_store.get_feedback_by_srm(srm_id)
        
        positive_count = sum(
            1 for fb in feedback_list 
            if fb.feedback_type == FeedbackType.POSITIVE and fb.correct_srm_id == srm_id
        )
        negative_count = sum(
            1 for fb in feedback_list 
            if fb.feedback_type in [FeedbackType.NEGATIVE, FeedbackType.CORRECTION] 
            and fb.incorrect_srm_id == srm_id
        )
        
        return {
            'srm_id': srm_id,
            'total_feedback': len(feedback_list),
            'positive': positive_count,
            'negative': negative_count,
            'net_score': positive_count - negative_count
        }
    
    def get_feedback_for_query_context(self, query: str) -> dict:
        '''
        Get feedback context for a query to inform reranking.
        
        Args:
            query: User query
            
        Returns:
            Dictionary with feedback context for reranking
        '''
        similar_feedback = self.feedback_store.get_feedback_for_query(query)
        
        # Build lists of SRMs with positive/negative signals
        negative_srms = set()
        positive_srms = set()
        
        for fb in similar_feedback:
            if fb.incorrect_srm_id:
                negative_srms.add(fb.incorrect_srm_id)
            if fb.correct_srm_id and fb.feedback_type == FeedbackType.CORRECTION:
                positive_srms.add(fb.correct_srm_id)
        
        return {
            'has_feedback': len(similar_feedback) > 0,
            'negative_srms': list(negative_srms),
            'positive_srms': list(positive_srms),
            'feedback_count': len(similar_feedback)
        }

