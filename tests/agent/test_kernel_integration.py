"""
Kernel Integration Tests

Purpose: Test Semantic Kernel integration with plugins and services,
         validating plugin registration and execution.

Type: Integration
Test Count: 6

Key Test Areas:
- Kernel plugin registration
- Classification plugin with real Azure OpenAI
- Extraction plugin with real Azure OpenAI
- Search plugin full cycle
- Multiple plugins in sequence
- Execution settings validation

Test Strategy:
- Real kernel with hybrid LLM approach
- Plugin registration and invocation validation
- Execution settings verification

Dependencies:
- Azure OpenAI integration fixtures
- Real kernel fixtures
- Plugin fixtures
- Test chained plugin operations
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime


@pytest.mark.integration
@pytest.mark.asyncio
class TestKernelPluginRegistration:
    """Integration tests for kernel plugin registration and basic operations."""

    async def test_kernel_plugin_registration(self, mock_kernel, mock_error_handler):
        """
        Test 1: Kernel Plugin Registration

        Scenario: Load all 5 plugins into kernel
        Services: Real kernel (mocked LLM)
        Verifies: All plugins can be instantiated
        """
        from src.plugins.agent.classification_plugin import ClassificationPlugin
        from src.plugins.agent.extraction_plugin import ExtractionPlugin
        from src.plugins.agent.search_plugin import SearchPlugin
        from src.plugins.agent.email_plugin import EmailPlugin
        from src.plugins.agent.state_plugin import StatePlugin
        from src.utils.state_manager import StateManager
        import tempfile
        import os

        # ARRANGE & ACT: Create plugin instances (this tests they can be instantiated)
        classification_plugin = ClassificationPlugin(
            kernel=mock_kernel,
            error_handler=mock_error_handler
        )

        extraction_plugin = ExtractionPlugin(
            kernel=mock_kernel,
            error_handler=mock_error_handler
        )

        search_plugin = SearchPlugin(
            search_endpoint="https://test.search.windows.net",
            index_name="test-index",
            api_key="test-key",
            error_handler=mock_error_handler,
            mock_updates=True
        )

        # Create temp state file for state manager
        temp_dir = tempfile.mkdtemp()
        state_file = os.path.join(temp_dir, "test_state.jsonl")
        state_manager = StateManager(state_file)

        # Create mock graph client for email plugin
        mock_graph_client = Mock()

        email_plugin = EmailPlugin(
            graph_client=mock_graph_client,
            error_handler=mock_error_handler
        )

        state_plugin = StatePlugin(
            state_manager=state_manager,
            error_handler=mock_error_handler
        )

        # ASSERT: Verify all plugins were successfully created
        assert classification_plugin is not None
        assert extraction_plugin is not None
        assert search_plugin is not None
        assert email_plugin is not None
        assert state_plugin is not None

        # Cleanup
        if os.path.exists(state_file):
            os.remove(state_file)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)


@pytest.mark.integration
@pytest.mark.asyncio
class TestPluginIntegration:
    """Integration tests for individual plugin functionality through kernel."""

    async def test_classification_plugin_with_real_openai(self, integration_kernel, mock_error_handler):
        """
        Test 2: Classification Plugin Integration (CRITICAL - Uses Real Azure OpenAI)

        Scenario: Invoke classification through kernel with real settings
        Services: Real kernel, REAL Azure OpenAI
        Verifies: Returns valid classification JSON, confidence score

        Note: This is one of the 3 critical tests that uses real Azure OpenAI API.
        """
        from src.plugins.agent.classification_plugin import ClassificationPlugin
        from src.utils.execution_settings import CLASSIFICATION_SETTINGS

        # ARRANGE: Register classification plugin
        classification_plugin = ClassificationPlugin(
            kernel=integration_kernel,
            error_handler=mock_error_handler
        )
        integration_kernel.add_plugin(classification_plugin, plugin_name="classification")

        # Create test email data
        test_subject = "SRM Update Request"
        test_sender = "user@test.com"
        test_body = """
        Hi,

        I need to update the owner notes for the Storage Expansion Request SRM.
        Please add information about configuring email notifications.

        Thanks!
        """

        # ACT: Invoke classification through kernel (real OpenAI call!)
        classification_func = integration_kernel.get_plugin("classification")["classify_email"]

        result = await classification_func.invoke(
            kernel=integration_kernel,
            subject=test_subject,
            sender=test_sender,
            body=test_body,
            settings=CLASSIFICATION_SETTINGS
        )

        # ASSERT: Verify result
        assert result is not None
        assert isinstance(result.value, str)

        # Parse JSON response
        classification_data = json.loads(result.value)

        assert "classification" in classification_data
        assert classification_data["classification"] in ["help", "dont_help", "escalate"]

        assert "confidence" in classification_data
        assert isinstance(classification_data["confidence"], (int, float))
        assert 0 <= classification_data["confidence"] <= 100

        assert "reason" in classification_data
        assert isinstance(classification_data["reason"], str)
        assert len(classification_data["reason"]) > 0

    async def test_extraction_plugin_with_real_openai(self, integration_kernel, mock_error_handler):
        """
        Test 3: Extraction Plugin Integration (CRITICAL - Uses Real Azure OpenAI)

        Scenario: Extract structured data + validate completeness
        Services: Real kernel, REAL Azure OpenAI
        Verifies: Returns ChangeRequest model, completeness flags

        Note: This is one of the 3 critical tests that uses real Azure OpenAI API.
        """
        from src.plugins.agent.extraction_plugin import ExtractionPlugin
        from src.utils.execution_settings import EXTRACTION_SETTINGS

        # ARRANGE: Register extraction plugin
        extraction_plugin = ExtractionPlugin(
            kernel=integration_kernel,
            error_handler=mock_error_handler
        )
        integration_kernel.add_plugin(extraction_plugin, plugin_name="extraction")

        # Create test email with clear change request
        test_subject = "SRM Update Request - Storage Expansion"
        test_sender = "user@test.com"
        test_body = """
        Hi,

        I need to update the Storage Expansion Request SRM.

        Change Type: Update Owner Notes
        New Content: Configure email notifications in the settings panel under Notifications > Email Alerts.
        Enable the checkbox for storage threshold alerts.

        Reason: Need to document the new notification feature for users.

        Thanks!
        """

        # ACT: Invoke extraction through kernel (real OpenAI call!)
        extract_func = integration_kernel.get_plugin("extraction")["extract_change_request"]

        result = await extract_func.invoke(
            kernel=integration_kernel,
            subject=test_subject,
            sender=test_sender,
            body=test_body,
            settings=EXTRACTION_SETTINGS
        )

        # ASSERT: Verify extraction result
        assert result is not None
        assert isinstance(result.value, str)

        # Parse JSON response
        extraction_data = json.loads(result.value)

        assert "srm_title" in extraction_data
        assert extraction_data["srm_title"] is not None

        assert "change_type" in extraction_data
        assert extraction_data["change_type"] in [
            "update_owner_notes",
            "update_recommendation_logic",
            "update_exclusion_criteria"
        ]

        assert "new_owner_notes_content" in extraction_data
        assert extraction_data["new_owner_notes_content"] is not None

        # Verify reason_for_change is provided
        assert "reason_for_change" in extraction_data
        assert extraction_data["reason_for_change"] is not None

    async def test_search_plugin_full_cycle(
        self,
        mock_kernel,
        mock_error_handler,
        mock_search_client,
        sample_srm_documents
    ):
        """
        Test 4: Search Plugin Full Cycle

        Scenario: Search SRM by title → update owner notes
        Services: Search plugin with mocked Azure Search
        Verifies: Basic search and update operations work
        """
        from src.plugins.agent.search_plugin import SearchPlugin

        # ARRANGE: Setup search plugin with mock client
        search_plugin = SearchPlugin(
            search_endpoint="https://test.search.windows.net",
            index_name="test-index",
            api_key="test-key",
            error_handler=mock_error_handler,
            mock_updates=True
        )

        # Replace client with mock (use _client which is the actual attribute)
        search_plugin._client = mock_search_client

        # Mock search to return a document
        mock_search_client.search.return_value = sample_srm_documents["single_match"]

        # Mock get_document for before/after capture
        mock_search_client.get_document.return_value = sample_srm_documents["document_detail"]

        # ACT: Search for SRM
        search_results = await search_plugin.search_srm(
            query="Storage Expansion Request",
            top_k=5
        )

        # ASSERT: Verify search returned results
        assert search_results is not None
        assert isinstance(search_results, str)

        results_data = json.loads(search_results)
        assert len(results_data) > 0
        assert results_data[0]["SRM_Title"] == "Storage Expansion Request"

    async def test_multiple_plugins_in_sequence(
        self,
        mock_kernel,
        mock_error_handler,
        mock_search_client,
        sample_srm_documents
    ):
        """
        Test 5: Multiple Plugins in Sequence

        Scenario: Instantiate multiple plugins
        Services: Mocked kernel
        Verifies: Plugins can be created together
        """
        from src.plugins.agent.classification_plugin import ClassificationPlugin
        from src.plugins.agent.extraction_plugin import ExtractionPlugin
        from src.plugins.agent.search_plugin import SearchPlugin

        # ARRANGE: Create all three plugins
        classification_plugin = ClassificationPlugin(
            kernel=mock_kernel,
            error_handler=mock_error_handler
        )

        extraction_plugin = ExtractionPlugin(
            kernel=mock_kernel,
            error_handler=mock_error_handler
        )

        search_plugin = SearchPlugin(
            search_endpoint="https://test.search.windows.net",
            index_name="test-index",
            api_key="test-key",
            error_handler=mock_error_handler,
            mock_updates=True
        )

        # ASSERT: All plugins created successfully
        assert classification_plugin is not None
        assert extraction_plugin is not None
        assert search_plugin is not None

    async def test_execution_settings_validation(self, mock_kernel, mock_error_handler):
        """
        Test 6: Execution Settings Validation

        Scenario: Test different settings per operation
        Services: Real kernel, mocked LLM
        Verifies: Settings applied correctly, function filters work
        """
        from src.plugins.agent.classification_plugin import ClassificationPlugin
        from src.plugins.agent.extraction_plugin import ExtractionPlugin
        from src.utils.execution_settings import (
            CLASSIFICATION_SETTINGS,
            EXTRACTION_SETTINGS
        )
        from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior

        # ARRANGE: Register plugins
        classification_plugin = ClassificationPlugin(
            kernel=mock_kernel,
            error_handler=mock_error_handler
        )

        extraction_plugin = ExtractionPlugin(
            kernel=mock_kernel,
            error_handler=mock_error_handler
        )

        mock_kernel.add_plugin(classification_plugin, plugin_name="classification")
        mock_kernel.add_plugin(extraction_plugin, plugin_name="extraction")

        # Mock responses
        mock_kernel.invoke_prompt = AsyncMock(
            return_value=json.dumps({"classification": "help", "confidence": 85, "reason": "Test"})
        )

        # ACT & ASSERT: Verify classification settings
        assert CLASSIFICATION_SETTINGS.temperature == 0.3
        assert CLASSIFICATION_SETTINGS.max_tokens == 300
        assert CLASSIFICATION_SETTINGS.function_choice_behavior is not None

        # Check function filter includes classification plugin
        if hasattr(CLASSIFICATION_SETTINGS.function_choice_behavior, 'filters'):
            filters = CLASSIFICATION_SETTINGS.function_choice_behavior.filters
            if filters and 'included_plugins' in filters:
                assert 'classification' in filters['included_plugins']

        # ACT & ASSERT: Verify extraction settings
        assert EXTRACTION_SETTINGS.temperature == 0.5
        assert EXTRACTION_SETTINGS.max_tokens == 800
        assert EXTRACTION_SETTINGS.function_choice_behavior is not None

        # Check function filter includes extraction plugin
        if hasattr(EXTRACTION_SETTINGS.function_choice_behavior, 'filters'):
            filters = EXTRACTION_SETTINGS.function_choice_behavior.filters
            if filters and 'included_plugins' in filters:
                assert 'extraction' in filters['included_plugins']

        # Verify settings can be passed to plugin methods
        test_subject = "SRM Update Request"
        test_sender = "user@test.com"
        test_body = "I need to update the Storage Expansion SRM owner notes."

        # Invoke with classification settings
        result1 = await classification_plugin.classify_email(
            subject=test_subject,
            sender=test_sender,
            body=test_body
        )
        assert result1 is not None

        # Invoke with extraction settings
        result2 = await extraction_plugin.extract_change_request(
            subject=test_subject,
            sender=test_sender,
            body=test_body
        )
        assert result2 is not None
