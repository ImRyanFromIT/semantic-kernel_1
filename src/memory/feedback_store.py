'''
Feedback storage for persisting and querying user feedback.
'''

import json
import logging
from pathlib import Path
from typing import Optional

from src.models.feedback_record import FeedbackRecord, FeedbackType


logger = logging.getLogger(__name__)


class FeedbackStore:
    '''
    Store for persisting user feedback to JSONL file.
    
    Provides methods to add, query, and update feedback records.
    '''
    
    def __init__(self, feedback_file: str = "logs/feedback.jsonl"):
        '''
        Initialize the feedback store.
        
        Args:
            feedback_file: Path to the JSONL file for storing feedback
        '''
        self.feedback_file = Path(feedback_file)
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache for fast lookups
        self.feedback_cache: dict[str, FeedbackRecord] = {}
        
        # Load existing feedback
        self._load_feedback()
    
    def _load_feedback(self) -> None:
        '''Load feedback from JSONL file into memory cache.'''
        if not self.feedback_file.exists():
            logger.info(f"No existing feedback file at {self.feedback_file}")
            return
        
        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        feedback = FeedbackRecord.from_dict(data)
                        self.feedback_cache[feedback.id] = feedback
            
            logger.info(f"Loaded {len(self.feedback_cache)} feedback records from {self.feedback_file}")
        except Exception as e:
            logger.error(f"Error loading feedback: {e}")
    
    def add_feedback(self, feedback: FeedbackRecord) -> None:
        '''
        Add new feedback record to store.
        
        Args:
            feedback: FeedbackRecord to store
        '''
        # Add to cache
        self.feedback_cache[feedback.id] = feedback
        
        # Persist to file
        try:
            with open(self.feedback_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(feedback.to_dict()) + '\n')
            logger.info(f"Stored feedback {feedback.id} for session {feedback.session_id}")
        except Exception as e:
            logger.error(f"Error storing feedback: {e}")
    
    def update_feedback(self, feedback: FeedbackRecord) -> None:
        '''
        Update existing feedback record (e.g., mark as applied to index).
        
        Args:
            feedback: Updated FeedbackRecord
        '''
        # Update cache
        self.feedback_cache[feedback.id] = feedback
        
        # Rewrite entire file (JSONL doesn't support in-place updates)
        self._rewrite_feedback_file()
    
    def _rewrite_feedback_file(self) -> None:
        '''Rewrite the entire feedback file with current cache state.'''
        try:
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                for feedback in self.feedback_cache.values():
                    f.write(json.dumps(feedback.to_dict()) + '\n')
            logger.debug("Feedback file rewritten successfully")
        except Exception as e:
            logger.error(f"Error rewriting feedback file: {e}")
    
    def get_feedback_by_id(self, feedback_id: str) -> Optional[FeedbackRecord]:
        '''
        Get feedback record by ID.
        
        Args:
            feedback_id: Feedback ID to look up
            
        Returns:
            FeedbackRecord if found, None otherwise
        '''
        return self.feedback_cache.get(feedback_id)
    
    def get_feedback_by_session(self, session_id: str) -> list[FeedbackRecord]:
        '''
        Get all feedback for a specific session.
        
        Args:
            session_id: Session ID to filter by
            
        Returns:
            List of FeedbackRecord objects
        '''
        return [
            fb for fb in self.feedback_cache.values()
            if fb.session_id == session_id
        ]
    
    def get_feedback_by_user(self, user_id: str) -> list[FeedbackRecord]:
        '''
        Get all feedback from a specific user.
        
        Args:
            user_id: User ID to filter by
            
        Returns:
            List of FeedbackRecord objects
        '''
        return [
            fb for fb in self.feedback_cache.values()
            if fb.user_id == user_id
        ]
    
    def get_feedback_by_srm(
        self, 
        srm_id: str, 
        feedback_type: Optional[FeedbackType] = None
    ) -> list[FeedbackRecord]:
        '''
        Get all feedback related to a specific SRM.
        
        Args:
            srm_id: SRM ID to filter by
            feedback_type: Optional filter by feedback type
            
        Returns:
            List of FeedbackRecord objects
        '''
        results = []
        for fb in self.feedback_cache.values():
            # Check if this SRM appears as incorrect or correct
            if fb.incorrect_srm_id == srm_id or fb.correct_srm_id == srm_id:
                if feedback_type is None or fb.feedback_type == feedback_type:
                    results.append(fb)
        return results
    
    def get_feedback_for_query(self, query: str, similarity_threshold: float = 0.8) -> list[FeedbackRecord]:
        '''
        Get feedback for similar queries.
        
        Args:
            query: Query string to match
            similarity_threshold: Threshold for query similarity (0-1)
            
        Returns:
            List of FeedbackRecord objects with similar queries
        '''
        # Simple case-insensitive substring matching
        # In production, you might use semantic similarity
        query_lower = query.lower()
        results = []
        
        for fb in self.feedback_cache.values():
            fb_query_lower = fb.query.lower()
            # Exact or substring match
            if query_lower in fb_query_lower or fb_query_lower in query_lower:
                results.append(fb)
        
        return results
    
    def get_unapplied_feedback(self) -> list[FeedbackRecord]:
        '''
        Get all feedback that hasn't been applied to the index yet.
        
        Returns:
            List of unapplied FeedbackRecord objects
        '''
        return [
            fb for fb in self.feedback_cache.values()
            if not fb.applied_to_index
        ]
    
    def get_all_feedback(self) -> list[FeedbackRecord]:
        '''
        Get all feedback records.
        
        Returns:
            List of all FeedbackRecord objects
        '''
        return list(self.feedback_cache.values())
    
    def mark_as_applied(self, feedback_id: str) -> None:
        '''
        Mark feedback as applied to the index.
        
        Args:
            feedback_id: ID of feedback to mark as applied
        '''
        feedback = self.feedback_cache.get(feedback_id)
        if feedback:
            feedback.applied_to_index = True
            self.update_feedback(feedback)
            logger.info(f"Marked feedback {feedback_id} as applied to index")

