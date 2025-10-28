"""
SRM change request model for structured data extraction.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ChangeType(Enum):
    """Types of SRM changes that can be requested."""
    UPDATE_OWNER_NOTES = "update_owner_notes"
    UPDATE_HIDDEN_NOTES = "update_hidden_notes"
    BOTH = "both"


@dataclass
class ChangeRequest:
    """
    Structured SRM change request data extracted from emails.
    
    Maps to the extraction requirements from the agent plan.
    """
    
    # Required fields
    srm_title: Optional[str] = None
    change_type: Optional[ChangeType] = None
    change_description: Optional[str] = None
    
    # Owner notes changes
    new_owner_notes_content: Optional[str] = None
    
    # Hidden notes changes  
    recommendation_logic: Optional[str] = None
    exclusion_criteria: Optional[str] = None
    
    # Additional context
    requester_team: Optional[str] = None
    reason_for_change: Optional[str] = None
    
    # Completeness assessment
    completeness_score: int = 0
    
    def is_complete(self) -> bool:
        """
        Check if change request has minimum required information.
        
        Returns:
            True if request is complete enough to process
        """
        # Must have SRM title
        if not self.srm_title:
            return False
            
        # Must have at least one change specified
        has_owner_notes_change = self.new_owner_notes_content is not None
        has_hidden_notes_change = (
            self.recommendation_logic is not None or 
            self.exclusion_criteria is not None
        )
        
        if not (has_owner_notes_change or has_hidden_notes_change):
            return False
            
        # Must have reasonable completeness score
        return self.completeness_score >= 60
    
    def get_missing_fields(self) -> list[str]:
        """Get list of missing required fields."""
        missing = []
        
        if not self.srm_title:
            missing.append("SRM title/name")
            
        if not self.change_description:
            missing.append("description of what needs to change")
            
        if not self.reason_for_change:
            missing.append("reason for the change")
            
        # Check if we have any actual change content
        has_owner_notes_change = self.new_owner_notes_content is not None
        has_hidden_notes_change = (
            self.recommendation_logic is not None or 
            self.exclusion_criteria is not None
        )
        
        if not (has_owner_notes_change or has_hidden_notes_change):
            missing.append("specific content to update (owner notes or hidden notes)")
            
        return missing
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            'srm_title': self.srm_title,
            'change_type': self.change_type.value if self.change_type else None,
            'change_description': self.change_description,
            'new_owner_notes_content': self.new_owner_notes_content,
            'recommendation_logic': self.recommendation_logic,
            'exclusion_criteria': self.exclusion_criteria,
            'requester_team': self.requester_team,
            'reason_for_change': self.reason_for_change,
            'completeness_score': self.completeness_score,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ChangeRequest':
        """Create from dictionary."""
        change_type = None
        if data.get('change_type'):
            change_type = ChangeType(data['change_type'])
            
        return cls(
            srm_title=data.get('srm_title'),
            change_type=change_type,
            change_description=data.get('change_description'),
            new_owner_notes_content=data.get('new_owner_notes_content'),
            recommendation_logic=data.get('recommendation_logic'),
            exclusion_criteria=data.get('exclusion_criteria'),
            requester_team=data.get('requester_team'),
            reason_for_change=data.get('reason_for_change'),
            completeness_score=data.get('completeness_score', 0),
        )
