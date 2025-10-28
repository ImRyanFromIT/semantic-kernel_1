"""
Pydantic models for LLM structured outputs.

These models provide type-safe, validated outputs from LLM operations,
replacing manual JSON parsing with automatic validation.
"""

from pydantic import BaseModel, Field
from typing import Literal, List, Optional


class EmailClassification(BaseModel):
    """Structured output for email classification."""
    classification: Literal["help", "dont_help", "escalate"] = Field(
        description="Classification category"
    )
    confidence: int = Field(
        ge=0, le=100,
        description="Confidence score 0-100"
    )
    reason: str = Field(
        description="Explanation for classification decision"
    )


class ExtractedData(BaseModel):
    """Structured output for SRM data extraction."""
    srm_title: Optional[str] = Field(None, description="SRM title or description")
    new_owner_notes_content: Optional[str] = Field(None, description="Owner notes to update")
    recommendation_logic: Optional[str] = Field(None, description="Recommendation logic for hidden notes")
    exclusion_criteria: Optional[str] = Field(None, description="Exclusion criteria for hidden notes")
    reason_for_change: Optional[str] = Field(None, description="Reason for the change")
    changed_by: Optional[str] = Field(None, description="Person requesting the change")


class ValidationResult(BaseModel):
    """Structured output for validation checks."""
    is_complete: bool = Field(description="Whether all required fields are present")
    missing_fields: List[str] = Field(default_factory=list, description="List of missing required fields")


class ConflictDetection(BaseModel):
    """Structured output for conflict detection."""
    has_conflicts: bool = Field(description="Whether conflicts were detected")
    safe_to_proceed: bool = Field(description="Whether it's safe to proceed with the update")
    severity: Optional[str] = Field(None, description="Conflict severity (low, medium, high)")
    conflict_details: Optional[str] = Field(None, description="Detailed explanation of conflicts")
    conflicts: List[str] = Field(default_factory=list, description="List of specific conflicts")
