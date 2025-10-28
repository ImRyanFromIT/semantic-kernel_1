"""
Tests for ClassificationPlugin.

This module tests the email classification plugin which uses LLM to route
emails to help/dont_help/escalate categories.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch

from src.plugins.agent.classification_plugin import ClassificationPlugin


@pytest.fixture
def classification_plugin(mock_kernel, mock_error_handler):
    """
    Provides a ClassificationPlugin instance with mocked dependencies.

    Patches _load_prompt_function to avoid file I/O during tests.
    """
    with patch.object(ClassificationPlugin, '_load_prompt_function'):
        plugin = ClassificationPlugin(mock_kernel, mock_error_handler)
        return plugin


class TestClassifyEmail:
    """Tests for classify_email method."""

    @pytest.mark.asyncio
    async def test_should_classify_as_help_when_clear_srm_request(
        self, classification_plugin, mock_kernel, sample_classification_result
    ):
        """
        Verify 'help' classification for clear SRM requests.

        Tests that a clear SRM update request is correctly classified as 'help'
        with high confidence.
        """
        # Arrange
        mock_kernel.invoke.return_value = json.dumps(sample_classification_result["help"])

        # Act
        result = await classification_plugin.classify_email(
            subject="SRM Update Request",
            sender="user@example.com",
            body="Please update the owner notes for SRM-12345"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["classification"] == "help"
        assert result_data["confidence"] == 85
        assert "SRM update" in result_data["reason"]

    @pytest.mark.asyncio
    async def test_should_classify_as_dont_help_when_off_topic(
        self, classification_plugin, mock_kernel, sample_classification_result
    ):
        """
        Verify 'dont_help' classification for off-topic emails.

        Tests that emails unrelated to SRM updates are classified as 'dont_help'.
        """
        # Arrange
        mock_kernel.invoke.return_value = json.dumps(sample_classification_result["dont_help"])

        # Act
        result = await classification_plugin.classify_email(
            subject="Spam: Buy our product!",
            sender="spam@example.com",
            body="Click here for amazing deals!"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["classification"] == "dont_help"
        assert result_data["confidence"] == 95
        assert "spam" in result_data["reason"].lower()

    @pytest.mark.asyncio
    async def test_should_classify_as_escalate_when_ambiguous(
        self, classification_plugin, mock_kernel, sample_classification_result
    ):
        """
        Verify 'escalate' classification for ambiguous requests.

        Tests that unclear or ambiguous requests are classified for escalation.
        """
        # Arrange
        mock_kernel.invoke.return_value = json.dumps(sample_classification_result["escalate"])

        # Act
        result = await classification_plugin.classify_email(
            subject="Question",
            sender="user@example.com",
            body="Can you help with something?"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["classification"] == "escalate"
        assert result_data["confidence"] == 40
        assert "ambiguous" in result_data["reason"].lower()

    @pytest.mark.asyncio
    async def test_should_handle_json_parse_error_gracefully(
        self, classification_plugin, mock_kernel
    ):
        """
        Verify fallback to escalate on malformed JSON response.

        Tests that if the LLM returns invalid JSON, the plugin falls back
        to escalate classification with confidence 0.
        """
        # Arrange - Return invalid JSON
        mock_kernel.invoke.return_value = "This is not valid JSON {bad}"

        # Act
        result = await classification_plugin.classify_email(
            subject="Test",
            sender="user@example.com",
            body="Test body"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["classification"] == "escalate"
        assert result_data["confidence"] == 0
        assert "Failed to parse" in result_data["reason"]

    @pytest.mark.asyncio
    async def test_should_escalate_when_missing_required_fields(
        self, classification_plugin, mock_kernel
    ):
        """
        Verify escalate on incomplete LLM response (missing fields).

        Tests that if the LLM response is missing required fields,
        the plugin falls back to escalate.
        """
        # Arrange - Return JSON missing required field
        incomplete_response = {
            "classification": "help",
            "confidence": 85
            # Missing 'reason' field
        }
        mock_kernel.invoke.return_value = json.dumps(incomplete_response)

        # Act
        result = await classification_plugin.classify_email(
            subject="Test",
            sender="user@example.com",
            body="Test body"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["classification"] == "escalate"
        assert result_data["confidence"] == 0
        assert "Failed to parse" in result_data["reason"]

    @pytest.mark.asyncio
    async def test_should_escalate_when_invalid_classification_value(
        self, classification_plugin, mock_kernel
    ):
        """
        Verify escalate on invalid classification value.

        Tests that if the LLM returns an invalid classification value
        (not help/dont_help/escalate), the plugin falls back to escalate.
        """
        # Arrange - Return invalid classification value
        invalid_response = {
            "classification": "invalid_category",
            "confidence": 85,
            "reason": "Some reason"
        }
        mock_kernel.invoke.return_value = json.dumps(invalid_response)

        # Act
        result = await classification_plugin.classify_email(
            subject="Test",
            sender="user@example.com",
            body="Test body"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["classification"] == "escalate"
        assert result_data["confidence"] == 0
        assert "Failed to parse" in result_data["reason"]

    @pytest.mark.asyncio
    async def test_should_escalate_when_confidence_out_of_range(
        self, classification_plugin, mock_kernel
    ):
        """
        Verify escalate on invalid confidence score.

        Tests that if confidence is not an integer in range 0-100,
        the plugin falls back to escalate.
        """
        # Arrange - Return confidence > 100
        invalid_response = {
            "classification": "help",
            "confidence": 150,
            "reason": "Some reason"
        }
        mock_kernel.invoke.return_value = json.dumps(invalid_response)

        # Act
        result = await classification_plugin.classify_email(
            subject="Test",
            sender="user@example.com",
            body="Test body"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["classification"] == "escalate"
        assert result_data["confidence"] == 0
        assert "Failed to parse" in result_data["reason"]

    @pytest.mark.asyncio
    async def test_should_handle_llm_call_exception(
        self, classification_plugin, mock_kernel
    ):
        """
        Verify error handling on LLM call exception.

        Tests that if the kernel.invoke raises an exception,
        the plugin returns escalate classification.
        """
        # Arrange - Mock kernel.invoke to raise exception
        mock_kernel.invoke.side_effect = Exception("LLM timeout")

        # Act
        result = await classification_plugin.classify_email(
            subject="Test",
            sender="user@example.com",
            body="Test body"
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["classification"] == "escalate"
        assert result_data["confidence"] == 0
        assert "Classification failed" in result_data["reason"]


class TestValidateClassification:
    """Tests for validate_classification method."""

    def test_should_validate_and_pass_high_confidence(
        self, classification_plugin, sample_classification_result
    ):
        """
        Verify validate_classification passes high confidence results.

        Tests that classifications with confidence >= threshold pass
        through unchanged.
        """
        # Arrange
        classification_json = json.dumps(sample_classification_result["help"])

        # Act
        result = classification_plugin.validate_classification(
            classification_json,
            confidence_threshold=70
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["classification"] == "help"
        assert result_data["confidence"] == 85

    def test_should_override_to_escalate_when_low_confidence(
        self, classification_plugin, sample_classification_result
    ):
        """
        Verify validate_classification overrides low confidence to escalate.

        Tests that classifications with confidence < threshold are
        automatically overridden to 'escalate'.
        """
        # Arrange
        classification_json = json.dumps(sample_classification_result["low_confidence"])

        # Act
        result = classification_plugin.validate_classification(
            classification_json,
            confidence_threshold=70
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["classification"] == "escalate"
        assert result_data["confidence"] == 35  # Original confidence preserved
        assert "Low confidence" in result_data["reason"]
        assert "escalating for human review" in result_data["reason"]

    def test_should_return_escalate_on_invalid_input(
        self, classification_plugin
    ):
        """
        Verify validate_classification returns escalate on invalid JSON input.

        Tests that if the input is not valid JSON or missing fields,
        the method returns escalate.
        """
        # Arrange - Invalid JSON
        invalid_json = "not valid json"

        # Act
        result = classification_plugin.validate_classification(invalid_json)

        # Assert
        result_data = json.loads(result)
        assert result_data["classification"] == "escalate"
        assert result_data["confidence"] == 0
        assert "Invalid classification result" in result_data["reason"]
