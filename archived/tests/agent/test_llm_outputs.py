"""
LLM Output Models Tests

Purpose: Test Pydantic models used for structured LLM outputs,
         including validation rules and field constraints.

Type: Unit
Test Count: 7

Key Test Areas:
- ChangeRequest model validation
- Classification model validation
- Field validation and constraints
- Required vs optional fields
- Pydantic error handling

Dependencies:
- Pydantic ValidationError handling
"""

import pytest
from pydantic import ValidationError

from src.models.llm_outputs import (
    EmailClassification,
    ExtractedData,
    ValidationResult,
    ConflictDetection,
)


class TestEmailClassification:
    """Tests for EmailClassification model validation."""

    def test_should_validate_email_classification_when_valid(self):
        """
        Verify EmailClassification accepts valid data with all fields.

        Tests that a properly formatted classification with valid type,
        confidence, and reason is accepted by the model.
        """
        # Arrange & Act
        classification = EmailClassification(
            classification="help",
            confidence=85,
            reason="User is requesting SRM update",
        )

        # Assert
        assert classification.classification == "help"
        assert classification.confidence == 85
        assert classification.reason == "User is requesting SRM update"

    def test_should_reject_invalid_classification_type(self):
        """
        Verify Pydantic validation rejects invalid classification types.

        Tests that the model rejects classification values that are not
        in the allowed set: 'help', 'dont_help', 'escalate'.
        """
        # Arrange & Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            EmailClassification(
                classification="invalid_type",
                confidence=85,
                reason="Some reason",
            )

        # Verify the validation error mentions the field
        assert "classification" in str(exc_info.value)

    def test_should_reject_confidence_out_of_range(self):
        """
        Verify confidence must be within 0-100 range.

        Tests that the model enforces the confidence constraint (0-100)
        and rejects values outside this range.
        """
        # Test confidence > 100
        with pytest.raises(ValidationError) as exc_info:
            EmailClassification(
                classification="help",
                confidence=150,
                reason="Reason",
            )
        assert "confidence" in str(exc_info.value)

        # Test confidence < 0
        with pytest.raises(ValidationError) as exc_info:
            EmailClassification(
                classification="help",
                confidence=-10,
                reason="Reason",
            )
        assert "confidence" in str(exc_info.value)


class TestExtractedData:
    """Tests for ExtractedData model validation."""

    def test_should_validate_extracted_data_when_complete(self):
        """
        Verify ExtractedData accepts data with all fields populated.

        Tests that a fully populated ExtractedData model with all
        optional fields is accepted.
        """
        # Arrange & Act
        data = ExtractedData(
            srm_title="Test SRM Title",
            new_owner_notes_content="New owner notes",
            recommendation_logic="Updated recommendation logic",
            exclusion_criteria="Updated exclusion criteria",
            reason_for_change="Correction needed",
            changed_by="user@example.com",
        )

        # Assert
        assert data.srm_title == "Test SRM Title"
        assert data.new_owner_notes_content == "New owner notes"
        assert data.recommendation_logic == "Updated recommendation logic"
        assert data.exclusion_criteria == "Updated exclusion criteria"
        assert data.reason_for_change == "Correction needed"
        assert data.changed_by == "user@example.com"

    def test_should_allow_optional_fields_none(self):
        """
        Verify ExtractedData allows optional fields to be None.

        Tests that the model accepts an instance with all fields set to None
        since all fields are optional.
        """
        # Arrange & Act
        data = ExtractedData()

        # Assert
        assert data.srm_title is None
        assert data.new_owner_notes_content is None
        assert data.recommendation_logic is None
        assert data.exclusion_criteria is None
        assert data.reason_for_change is None
        assert data.changed_by is None


class TestValidationResult:
    """Tests for ValidationResult model validation."""

    def test_should_validate_validation_result_structure(self):
        """
        Verify ValidationResult model structure and field validation.

        Tests that the ValidationResult model correctly stores completeness
        status and missing field information.
        """
        # Arrange & Act - Complete result
        complete = ValidationResult(
            is_complete=True,
            missing_fields=[],
        )

        # Assert
        assert complete.is_complete is True
        assert complete.missing_fields == []

        # Arrange & Act - Incomplete result
        incomplete = ValidationResult(
            is_complete=False,
            missing_fields=["srm_title", "reason_for_change"],
        )

        # Assert
        assert incomplete.is_complete is False
        assert "srm_title" in incomplete.missing_fields
        assert "reason_for_change" in incomplete.missing_fields
        assert len(incomplete.missing_fields) == 2


class TestConflictDetection:
    """Tests for ConflictDetection model validation."""

    def test_should_validate_conflict_detection_structure(self):
        """
        Verify ConflictDetection model structure with all fields.

        Tests that the ConflictDetection model correctly stores conflict
        information including flags, severity, and details.
        """
        # Arrange & Act - Conflict detected
        conflict = ConflictDetection(
            has_conflicts=True,
            safe_to_proceed=False,
            severity="high",
            conflict_details="Contradictory information about SRM owner",
            conflicts=["Owner field contradicts prior email", "Ambiguous date"],
        )

        # Assert
        assert conflict.has_conflicts is True
        assert conflict.safe_to_proceed is False
        assert conflict.severity == "high"
        assert conflict.conflict_details == "Contradictory information about SRM owner"
        assert len(conflict.conflicts) == 2
        assert "Owner field contradicts prior email" in conflict.conflicts

        # Arrange & Act - No conflict
        no_conflict = ConflictDetection(
            has_conflicts=False,
            safe_to_proceed=True,
            severity=None,
            conflict_details=None,
            conflicts=[],
        )

        # Assert
        assert no_conflict.has_conflicts is False
        assert no_conflict.safe_to_proceed is True
        assert no_conflict.severity is None
        assert no_conflict.conflict_details is None
        assert no_conflict.conflicts == []
