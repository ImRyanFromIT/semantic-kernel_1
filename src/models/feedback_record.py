'''
Feedback record model for user feedback on SRM recommendations.
'''

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4


class FeedbackType(Enum):
    '''Types of feedback users can provide.'''
    POSITIVE = "positive"  # User confirms recommendation is correct
    NEGATIVE = "negative"  # User indicates recommendation is wrong
    CORRECTION = "correction"  # User provides correct SRM


@dataclass
class FeedbackRecord:
    '''
    Model to store user feedback on SRM recommendations.
    
    Fields:
        id: Unique identifier for the feedback
        session_id: Session ID from the original query
        user_id: Optional user identifier for personalization
        query: Original user query that generated the recommendation
        incorrect_srm_id: ID of the SRM that was incorrectly recommended
        incorrect_srm_name: Name of the incorrect SRM (for display)
        correct_srm_id: ID of the correct SRM (if user provided)
        correct_srm_name: Name of the correct SRM (for display)
        feedback_text: Optional user explanation of the issue
        feedback_type: Type of feedback (positive/negative/correction)
        timestamp: When the feedback was submitted
        applied_to_index: Whether feedback has been applied to the search index
    '''
    
    id: str = field(default_factory=lambda: str(uuid4()))
    session_id: str = ""
    user_id: Optional[str] = None
    query: str = ""
    incorrect_srm_id: Optional[str] = None
    incorrect_srm_name: Optional[str] = None
    correct_srm_id: Optional[str] = None
    correct_srm_name: Optional[str] = None
    feedback_text: Optional[str] = None
    feedback_type: FeedbackType = FeedbackType.NEGATIVE
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    applied_to_index: bool = False
    
    def to_dict(self) -> dict:
        '''Convert feedback record to dictionary for storage.'''
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'query': self.query,
            'incorrect_srm_id': self.incorrect_srm_id,
            'incorrect_srm_name': self.incorrect_srm_name,
            'correct_srm_id': self.correct_srm_id,
            'correct_srm_name': self.correct_srm_name,
            'feedback_text': self.feedback_text,
            'feedback_type': self.feedback_type.value,
            'timestamp': self.timestamp,
            'applied_to_index': self.applied_to_index,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FeedbackRecord':
        '''Create feedback record from dictionary.'''
        # Convert feedback_type string back to enum
        feedback_type = FeedbackType(data.get('feedback_type', 'negative'))
        
        return cls(
            id=data.get('id', str(uuid4())),
            session_id=data.get('session_id', ''),
            user_id=data.get('user_id'),
            query=data.get('query', ''),
            incorrect_srm_id=data.get('incorrect_srm_id'),
            incorrect_srm_name=data.get('incorrect_srm_name'),
            correct_srm_id=data.get('correct_srm_id'),
            correct_srm_name=data.get('correct_srm_name'),
            feedback_text=data.get('feedback_text'),
            feedback_type=feedback_type,
            timestamp=data.get('timestamp', datetime.utcnow().isoformat()),
            applied_to_index=data.get('applied_to_index', False),
        )

