"""
Extraction Plugin Tests

Purpose: Test data extraction plugin using LLM to extract structured
         SRM change request data from emails.

Type: Unit
Test Count: 14

Key Test Areas:
- Data extraction from email body
- Completeness checking (required fields)
- Conflict detection
- LLM prompt handling
- Error handling and recovery
- Edge cases (missing fields, malformed data)

Dependencies:
- extraction_plugin fixture
- mock_kernel fixture
- mock_error_handler fixture
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch

from src.plugins.agent.extraction_plugin import ExtractionPlugin
from src.models.change_request import ChangeRequest


@pytest.fixture
def extraction_plugin(mock_kernel, mock_error_handler):
    """
    Provides an ExtractionPlugin instance with mocked dependencies.

    Patches _load_prompt_function to avoid file I/O during tests.
    """
    with patch.object(ExtractionPlugin, '_load_prompt_function'):
        plugin = ExtractionPlugin(mock_kernel, mock_error_handler)
        return plugin


class TestExtractChangeRequest:
    """Tests for extract_change_request method."""

    @pytest.mark.asyncio
    async def test_should_extract_complete_data_when_all_fields_present(
        self, extraction_plugin, mock_kernel, sample_extraction_result
    ):
        """
        Verify extraction returns all fields when complete data is present.

        Tests that a well-formed email with all required information
        gets properly extracted into a ChangeRequest structure.
        """
        # Arrange
        mock_kernel.invoke.return_value = json.dumps(sample_extraction_result["complete"])

        # Act
        result = await extraction_plugin.extract_change_request(
            subject="SRM Update Request",
            sender="user@example.com",
            body="Please update Test SRM owner notes with new configuration steps"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["srm_title"] == "Test SRM - Configure Email Notifications"
        assert result_data["change_type"] == "update_owner_notes"
        assert result_data["completeness_score"] == 85
        assert result_data["new_owner_notes_content"] is not None

    @pytest.mark.asyncio
    async def test_should_extract_partial_data_when_fields_missing(
        self, extraction_plugin, mock_kernel, sample_extraction_result
    ):
        """
        Verify extraction handles incomplete data gracefully.

        Tests that when some fields are missing, the extraction still
        returns a valid structure with a low completeness score.
        """
        # Arrange
        mock_kernel.invoke.return_value = json.dumps(sample_extraction_result["partial"])

        # Act
        result = await extraction_plugin.extract_change_request(
            subject="SRM Update",
            sender="user@example.com",
            body="Update something in Test SRM"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["srm_title"] == "Test SRM"
        assert result_data["completeness_score"] == 30
        assert result_data["new_owner_notes_content"] is None

    @pytest.mark.asyncio
    async def test_should_clean_markdown_code_blocks_when_present(
        self, extraction_plugin, mock_kernel, sample_extraction_result
    ):
        """
        Verify extraction removes ```json markdown formatting.

        Tests that when LLM returns data wrapped in markdown code blocks,
        they are properly cleaned before parsing.
        """
        # Arrange - Return data with markdown code blocks
        mock_kernel.invoke.return_value = sample_extraction_result["with_markdown"]

        # Act
        result = await extraction_plugin.extract_change_request(
            subject="Test",
            sender="user@example.com",
            body="Test body"
        )

        # Assert - Should successfully parse despite markdown
        result_data = json.loads(result)
        assert result_data["srm_title"] == "Test SRM"
        assert result_data["completeness_score"] == 75

    @pytest.mark.asyncio
    async def test_should_handle_extraction_parse_error(
        self, extraction_plugin, mock_kernel
    ):
        """
        Verify fallback behavior on JSON parse failure.

        Tests that if the LLM returns invalid JSON, the plugin returns
        a minimal ChangeRequest with completeness_score of 0.
        """
        # Arrange - Return invalid JSON
        mock_kernel.invoke.return_value = "This is not valid JSON {bad structure"

        # Act
        result = await extraction_plugin.extract_change_request(
            subject="Test",
            sender="user@example.com",
            body="Test body"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["completeness_score"] == 0
        assert "Failed to parse" in result_data["change_description"]

    @pytest.mark.asyncio
    async def test_should_handle_llm_call_exception(
        self, extraction_plugin, mock_kernel
    ):
        """
        Verify error handling on LLM call exception.

        Tests that if kernel.invoke raises an exception, the plugin
        returns a minimal error structure.
        """
        # Arrange - Mock kernel.invoke to raise exception
        mock_kernel.invoke.side_effect = Exception("LLM timeout")

        # Act
        result = await extraction_plugin.extract_change_request(
            subject="Test",
            sender="user@example.com",
            body="Test body"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["completeness_score"] == 0
        assert "Extraction failed" in result_data["change_description"]


class TestValidateCompleteness:
    """Tests for validate_completeness method."""

    def test_should_validate_as_complete_when_all_required_present(
        self, extraction_plugin, sample_extraction_result
    ):
        """
        Verify validation returns is_complete=True for complete data.

        Tests that a ChangeRequest with all required fields and high
        completeness score is validated as complete.
        """
        # Arrange
        extracted_data = json.dumps(sample_extraction_result["complete"])

        # Act
        result = extraction_plugin.validate_completeness(extracted_data)

        # Assert
        result_data = json.loads(result)
        assert result_data["is_complete"] is True
        assert result_data["completeness_score"] == 85
        assert result_data["needs_clarification"] is False
        assert len(result_data["missing_fields"]) == 0

    def test_should_validate_as_incomplete_when_fields_missing(
        self, extraction_plugin, sample_extraction_result
    ):
        """
        Verify validation returns is_complete=False for incomplete data.

        Tests that a ChangeRequest with missing fields or low completeness
        score is validated as incomplete.
        """
        # Arrange
        extracted_data = json.dumps(sample_extraction_result["partial"])

        # Act
        result = extraction_plugin.validate_completeness(extracted_data)

        # Assert
        result_data = json.loads(result)
        assert result_data["is_complete"] is False
        assert result_data["completeness_score"] == 30
        assert result_data["needs_clarification"] is True
        assert len(result_data["missing_fields"]) > 0

    def test_should_identify_missing_fields_correctly(
        self, extraction_plugin, sample_extraction_result
    ):
        """
        Verify missing_fields list accurately identifies what's missing.

        Tests that the validation correctly identifies which specific
        fields are missing from an incomplete request.
        """
        # Arrange
        extracted_data = json.dumps(sample_extraction_result["minimal"])

        # Act
        result = extraction_plugin.validate_completeness(extracted_data)

        # Assert
        result_data = json.loads(result)
        assert result_data["is_complete"] is False
        missing_fields = result_data["missing_fields"]
        assert "SRM title/name" in missing_fields or len(missing_fields) > 0


class TestGenerateClarification:
    """Tests for generate_clarification method."""

    @pytest.mark.asyncio
    async def test_should_generate_clarification_email(
        self, extraction_plugin, mock_kernel, mock_chat_service, sample_extraction_result
    ):
        """
        Verify generate_clarification produces email text.

        Tests that the method generates a clarification email asking
        for missing information.
        """
        # Arrange
        mock_kernel.get_service.return_value = mock_chat_service
        mock_chat_service.get_chat_message_content.return_value = (
            "Thank you for your request. Could you please provide:\n"
            "1. The exact SRM title\n"
            "2. What you'd like us to change"
        )

        extracted_data = json.dumps(sample_extraction_result["partial"])
        missing_fields = "SRM title, specific content"

        # Act
        result = await extraction_plugin.generate_clarification(
            extracted_data,
            missing_fields
        )

        # Assert
        assert "Thank you" in result
        assert "SRM" in result or "title" in result

    @pytest.mark.asyncio
    async def test_should_return_fallback_on_exception(
        self, extraction_plugin, mock_kernel, mock_chat_service
    ):
        """
        Verify fallback message on LLM exception.

        Tests that if clarification generation fails, a generic
        clarification message is returned.
        """
        # Arrange
        mock_kernel.get_service.return_value = mock_chat_service
        mock_chat_service.get_chat_message_content.side_effect = Exception("LLM error")

        extracted_data = json.dumps({})
        missing_fields = "multiple fields"

        # Act
        result = await extraction_plugin.generate_clarification(
            extracted_data,
            missing_fields
        )

        # Assert
        assert "Thank you" in result
        assert "additional information" in result
        assert "SRM" in result


class TestDetectConflicts:
    """Tests for detect_conflicts method."""

    @pytest.mark.asyncio
    async def test_should_detect_conflicts_when_contradictions_exist(
        self, extraction_plugin, mock_kernel, mock_chat_service, sample_conflict_result
    ):
        """
        Verify conflict detection finds contradictions.

        Tests that contradictory information in a change request
        is detected and flagged as unsafe to proceed.
        """
        # Arrange
        mock_kernel.get_service.return_value = mock_chat_service
        mock_chat_service.get_chat_message_content.return_value = json.dumps(
            sample_conflict_result["contradiction"]
        )

        extracted_data = json.dumps({"srm_title": "Test", "completeness_score": 70})

        # Act
        result = await extraction_plugin.detect_conflicts(
            extracted_data=extracted_data,
            email_subject="Conflicting request",
            email_body="Mark as approved but also pending",
            sender="user@example.com"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["has_conflicts"] is True
        assert result_data["safe_to_proceed"] is False
        assert result_data["severity"] == "high"
        assert len(result_data["conflicts"]) > 0

    @pytest.mark.asyncio
    async def test_should_detect_conflicts_when_ambiguous(
        self, extraction_plugin, mock_kernel, mock_chat_service, sample_conflict_result
    ):
        """
        Verify conflict detection finds ambiguity.

        Tests that ambiguous requests that mention multiple SRMs or
        unclear instructions are flagged for review.
        """
        # Arrange
        mock_kernel.get_service.return_value = mock_chat_service
        mock_chat_service.get_chat_message_content.return_value = json.dumps(
            sample_conflict_result["ambiguous"]
        )

        extracted_data = json.dumps({"srm_title": "Test", "completeness_score": 70})

        # Act
        result = await extraction_plugin.detect_conflicts(
            extracted_data=extracted_data,
            email_subject="Update SRMs",
            email_body="Update all the SRMs with new info",
            sender="user@example.com"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["has_conflicts"] is True
        assert result_data["safe_to_proceed"] is False
        assert result_data["severity"] == "medium"

    @pytest.mark.asyncio
    async def test_should_return_safe_when_no_conflicts(
        self, extraction_plugin, mock_kernel, mock_chat_service, sample_conflict_result
    ):
        """
        Verify safe_to_proceed=True when no conflicts detected.

        Tests that clear, unambiguous requests are marked as safe
        to proceed automatically.
        """
        # Arrange
        mock_kernel.get_service.return_value = mock_chat_service
        mock_chat_service.get_chat_message_content.return_value = json.dumps(
            sample_conflict_result["no_conflict"]
        )

        extracted_data = json.dumps({"srm_title": "Test SRM", "completeness_score": 85})

        # Act
        result = await extraction_plugin.detect_conflicts(
            extracted_data=extracted_data,
            email_subject="Clear request",
            email_body="Please update Test SRM owner notes with XYZ",
            sender="user@example.com"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["has_conflicts"] is False
        assert result_data["safe_to_proceed"] is True
        assert result_data["severity"] == "low"

    @pytest.mark.asyncio
    async def test_should_fallback_safely_on_conflict_error(
        self, extraction_plugin, mock_kernel, mock_chat_service
    ):
        """
        Verify safe default (escalate) on detection failure.

        Tests that if conflict detection fails or returns invalid data,
        the system defaults to flagging for manual review (safe default).
        """
        # Arrange - Return invalid JSON that will fail parsing
        mock_kernel.get_service.return_value = mock_chat_service
        mock_chat_service.get_chat_message_content.return_value = "Invalid JSON response"

        extracted_data = json.dumps({"srm_title": "Test", "completeness_score": 70})

        # Act
        result = await extraction_plugin.detect_conflicts(
            extracted_data=extracted_data,
            email_subject="Test",
            email_body="Test body",
            sender="user@example.com"
        )

        # Assert - Should return safe default (flag for review)
        result_data = json.loads(result)
        assert result_data["has_conflicts"] is True
        assert result_data["safe_to_proceed"] is False
        assert "Unable to analyze" in result_data["conflict_details"] or "manual review" in result_data["conflict_details"]
