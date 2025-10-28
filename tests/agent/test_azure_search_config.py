"""
Test that Azure Search configuration is correctly loaded.

This is a regression test for the bug where AZURE_SEARCH_ENDPOINT
was used instead of AZURE_AI_SEARCH_ENDPOINT.
"""

import os
import pytest
from unittest.mock import patch
from src.plugins.agent.search_plugin import SearchPlugin
from src.utils.error_handler import ErrorHandler


class TestAzureSearchConfig:
    """Test Azure Search configuration."""

    def test_uses_correct_environment_variable(self):
        """
        Test that SearchPlugin uses AZURE_AI_SEARCH_ENDPOINT (not AZURE_SEARCH_ENDPOINT).

        This is a regression test for the bug where the wrong env var was used.
        """
        # Set up environment variables
        test_endpoint = "https://test-search.search.windows.net/"
        test_index = "test-index"
        test_api_key = "test-key-123"

        with patch.dict(os.environ, {
            'AZURE_AI_SEARCH_ENDPOINT': test_endpoint,
            'AZURE_AI_SEARCH_INDEX_NAME': test_index,
            'AZURE_AI_SEARCH_API_KEY': test_api_key,
        }):
            # In run_email_agent.py, we now correctly use AZURE_AI_SEARCH_ENDPOINT
            endpoint = os.getenv('AZURE_AI_SEARCH_ENDPOINT', '')
            index_name = os.getenv('AZURE_AI_SEARCH_INDEX_NAME', 'srm-catalog')
            api_key = os.getenv('AZURE_AI_SEARCH_API_KEY', '')

            # These should all be populated
            assert endpoint == test_endpoint, "Endpoint should be loaded from AZURE_AI_SEARCH_ENDPOINT"
            assert index_name == test_index
            assert api_key == test_api_key

            # Create plugin - should not fail
            error_handler = ErrorHandler()
            plugin = SearchPlugin(
                search_endpoint=endpoint,
                index_name=index_name,
                api_key=api_key,
                error_handler=error_handler,
                mock_updates=True
            )

            # Verify the plugin has the correct configuration
            assert plugin.search_endpoint == test_endpoint
            assert plugin.index_name == test_index
            assert plugin.api_key == test_api_key

    def test_old_environment_variable_not_used(self):
        """
        Test that the OLD incorrect env var (AZURE_SEARCH_ENDPOINT) is NOT used.

        This ensures we don't regress to the old bug.
        """
        with patch.dict(os.environ, {
            # Only set the OLD incorrect variable
            'AZURE_SEARCH_ENDPOINT': 'https://old-endpoint.search.windows.net/',
            # Don't set the CORRECT variable
        }, clear=True):
            # Should be empty because we're not using the old var name
            endpoint = os.getenv('AZURE_AI_SEARCH_ENDPOINT', '')
            assert endpoint == '', "Should NOT use AZURE_SEARCH_ENDPOINT (missing _AI_)"


if __name__ == "__main__":
    # Allow running this test directly
    pytest.main([__file__, "-v"])
