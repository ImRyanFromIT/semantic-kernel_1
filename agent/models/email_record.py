"""
Email record model for tracking email processing state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import uuid4


class EmailStatus(Enum):
    """Status of email processing."""
    CLASSIFIED = "classified"
    ROUTED_TO_SRM_HELP = "routed_to_srm_help"
    RESPONDING_DONT_HELP = "responding_dont_help"
    ESCALATING = "escalating"
    IN_PROGRESS = "in_progress"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    AWAITING_RESPONSE = "awaiting_response"
    DATA_EXTRACTED = "data_extracted"
    UPDATE_PREPARED = "update_prepared"
    INDEX_UPDATED = "index_updated"
    COMPLETED_SUCCESS = "completed_success"
    COMPLETED_DONT_HELP = "completed_dont_help"
    ESCALATED = "escalated"
    SEARCH_ERROR = "search_error"


@dataclass
class EmailRecord:
    """
    Model to track email processing state in agent_state.jsonl.
    
    Maps to the email tracking requirements from the agent plan.
    """
    
    # Core email identification
    email_id: str
    sender: str
    subject: str
    body: str
    received_datetime: str
    conversation_id: Optional[str] = None
    
    # Classification results
    classification: Optional[str] = None  # 'help', 'dont_help', 'escalate'
    confidence: Optional[float] = None
    reason: Optional[str] = None
    
    # Processing state
    status: EmailStatus = EmailStatus.CLASSIFIED
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # Extracted data (for SRM help requests)
    extracted_data: Optional[Dict[str, Any]] = None
    
    # Update tracking
    update_payload: Optional[Dict[str, Any]] = None
    update_result: Optional[Dict[str, Any]] = None
    
    # Response tracking
    response_sent_datetime: Optional[str] = None
    clarification_sent_datetime: Optional[str] = None
    escalation_sent_datetime: Optional[str] = None
    confirmation_sent_datetime: Optional[str] = None
    
    # Metadata
    processing_attempts: int = 0
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert email record to dictionary for JSONL storage."""
        return {
            'email_id': self.email_id,
            'sender': self.sender,
            'subject': self.subject,
            'body': self.body,
            'received_datetime': self.received_datetime,
            'conversation_id': self.conversation_id,
            'classification': self.classification,
            'confidence': self.confidence,
            'reason': self.reason,
            'status': self.status.value,
            'timestamp': self.timestamp,
            'extracted_data': self.extracted_data,
            'update_payload': self.update_payload,
            'update_result': self.update_result,
            'response_sent_datetime': self.response_sent_datetime,
            'clarification_sent_datetime': self.clarification_sent_datetime,
            'escalation_sent_datetime': self.escalation_sent_datetime,
            'confirmation_sent_datetime': self.confirmation_sent_datetime,
            'processing_attempts': self.processing_attempts,
            'last_error': self.last_error,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmailRecord':
        """Create email record from dictionary loaded from JSONL."""
        # Convert status string back to enum
        status = EmailStatus(data.get('status', 'classified'))
        
        return cls(
            email_id=data['email_id'],
            sender=data['sender'],
            subject=data['subject'],
            body=data['body'],
            received_datetime=data['received_datetime'],
            conversation_id=data.get('conversation_id'),
            classification=data.get('classification'),
            confidence=data.get('confidence'),
            reason=data.get('reason'),
            status=status,
            timestamp=data.get('timestamp', datetime.utcnow().isoformat()),
            extracted_data=data.get('extracted_data'),
            update_payload=data.get('update_payload'),
            update_result=data.get('update_result'),
            response_sent_datetime=data.get('response_sent_datetime'),
            clarification_sent_datetime=data.get('clarification_sent_datetime'),
            escalation_sent_datetime=data.get('escalation_sent_datetime'),
            confirmation_sent_datetime=data.get('confirmation_sent_datetime'),
            processing_attempts=data.get('processing_attempts', 0),
            last_error=data.get('last_error'),
        )
    
    def is_stale(self, hours: int = 48) -> bool:
        """Check if email has been stale for more than specified hours."""
        try:
            last_update = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
            now = datetime.utcnow()
            return (now - last_update).total_seconds() > (hours * 3600)
        except (ValueError, AttributeError):
            return True  # Assume stale if timestamp is invalid
    
    def update_status(self, new_status: EmailStatus, error: Optional[str] = None) -> None:
        """Update status and timestamp."""
        self.status = new_status
        self.timestamp = datetime.utcnow().isoformat()
        self.processing_attempts += 1
        if error:
            self.last_error = error
