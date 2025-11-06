"""
Search Plugin Tests

Purpose: Test Azure AI Search plugin for SRM document search,
         retrieval, and updates.

Type: Unit
Test Count: 14

Key Test Areas:
- SRM document search with filters
- Top-k result limiting
- Document retrieval by ID
- Document updates with before/after capture
- Mock vs live mode handling
- Error handling

Dependencies:
- search_plugin fixture
- mock_search_client fixture
"""

import pytest
import json
from unittest.mock import Mock, patch

from src.plugins.agent.search_plugin import SearchPlugin


@pytest.fixture
def search_plugin(mock_error_handler, mock_search_client):
    """
    Provides a SearchPlugin instance with mocked dependencies.

    Uses mock_updates=True by default for safe testing.
    """
    plugin = SearchPlugin(
        search_endpoint="https://test.search.windows.net",
        index_name="test-index",
        api_key="test-key",
        error_handler=mock_error_handler,
        mock_updates=True
    )
    # Inject mock client to avoid initialization
    plugin._client = mock_search_client
    return plugin


@pytest.fixture
def search_plugin_live_mode(mock_error_handler, mock_search_client):
    """
    Provides a SearchPlugin instance in live mode (mock_updates=False).

    Used for testing actual update operations.
    """
    plugin = SearchPlugin(
        search_endpoint="https://test.search.windows.net",
        index_name="test-index",
        api_key="test-key",
        error_handler=mock_error_handler,
        mock_updates=False
    )
    plugin._client = mock_search_client
    return plugin


class TestSearchSRM:
    """Tests for search_srm method."""

    @pytest.mark.asyncio
    async def test_should_search_and_return_results_when_found(
        self, search_plugin, mock_search_client, sample_srm_documents
    ):
        """
        Verify search_srm returns matching SRM documents.

        Tests that a search query returns properly formatted results
        with all document fields.
        """
        # Arrange
        mock_search_client.search.return_value = sample_srm_documents["single_match"]

        # Act
        result = await search_plugin.search_srm(
            query="Storage Expansion",
            top_k=10
        )

        # Assert
        results_data = json.loads(result)
        assert isinstance(results_data, list)
        assert len(results_data) == 1
        assert results_data[0]["SRM_ID"] == "SRM-051"
        assert results_data[0]["SRM_Title"] == "Storage Expansion Request"
        assert results_data[0]["@search.score"] == 0.95

    @pytest.mark.asyncio
    async def test_should_return_empty_when_no_matches(
        self, search_plugin, mock_search_client
    ):
        """
        Verify search_srm returns empty array when no matches found.

        Tests that searches with no results return an empty JSON array
        rather than an error.
        """
        # Arrange
        mock_search_client.search.return_value = []

        # Act
        result = await search_plugin.search_srm(
            query="Nonexistent SRM",
            top_k=10
        )

        # Assert
        results_data = json.loads(result)
        assert isinstance(results_data, list)
        assert len(results_data) == 0

    @pytest.mark.asyncio
    async def test_should_respect_top_k_parameter(
        self, search_plugin, mock_search_client, sample_srm_documents
    ):
        """
        Verify search_srm respects top_k parameter for result limiting.

        Tests that the top_k parameter is passed correctly to the
        search client to limit results.
        """
        # Arrange
        mock_search_client.search.return_value = sample_srm_documents["multiple_matches"]

        # Act
        result = await search_plugin.search_srm(
            query="Storage",
            top_k=5
        )

        # Assert
        mock_search_client.search.assert_called_once()
        call_kwargs = mock_search_client.search.call_args.kwargs
        assert call_kwargs["top"] == 5


class TestGetSRMDocument:
    """Tests for get_srm_document method."""

    @pytest.mark.asyncio
    async def test_should_get_document_by_id_when_exists(
        self, search_plugin, mock_search_client, sample_srm_documents
    ):
        """
        Verify get_srm_document retrieves document by ID.

        Tests that requesting a document by ID returns the complete
        document data.
        """
        # Arrange
        mock_search_client.get_document.return_value = sample_srm_documents["document_detail"]

        # Act
        result = await search_plugin.get_srm_document(document_id="SRM-051")

        # Assert
        document_data = json.loads(result)
        assert document_data["SRM_ID"] == "SRM-051"
        assert document_data["SRM_Title"] == "Storage Expansion Request"
        assert document_data["owner_notes"] == "Original owner notes content"

    @pytest.mark.asyncio
    async def test_should_return_error_when_document_not_found(
        self, search_plugin, mock_search_client
    ):
        """
        Verify get_srm_document handles document not found error.

        Tests that requesting a non-existent document ID returns
        an appropriate error message.
        """
        # Arrange
        mock_search_client.get_document.side_effect = Exception("Document not found")

        # Act
        result = await search_plugin.get_srm_document(document_id="SRM-999")

        # Assert
        assert "Document retrieval failed" in result


class TestUpdateSRMDocument:
    """Tests for update_srm_document method."""

    @pytest.mark.asyncio
    async def test_should_update_document_with_owner_notes(
        self, search_plugin, mock_search_client, sample_srm_documents
    ):
        """
        Verify update_srm_document updates owner_notes field.

        Tests that updating owner_notes field works correctly
        in mock mode.
        """
        # Arrange
        mock_search_client.get_document.return_value = sample_srm_documents["document_detail"]
        updates = json.dumps({"owner_notes": "Updated owner notes content"})

        # Act
        result = await search_plugin.update_srm_document(
            document_id="SRM-051",
            updates=updates
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["srm_id"] == "SRM-051"
        assert result_data["mocked"] is True

    @pytest.mark.asyncio
    async def test_should_update_document_with_hidden_notes(
        self, search_plugin, mock_search_client, sample_srm_documents
    ):
        """
        Verify update_srm_document updates hidden_notes field.

        Tests that updating hidden_notes field works correctly.
        """
        # Arrange
        mock_search_client.get_document.return_value = sample_srm_documents["document_detail"]
        updates = json.dumps({"hidden_notes": "Updated hidden notes content"})

        # Act
        result = await search_plugin.update_srm_document(
            document_id="SRM-051",
            updates=updates
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["success"] is True
        assert len(result_data["changes"]) == 1
        assert result_data["changes"][0]["field"] == "hidden_notes"

    @pytest.mark.asyncio
    async def test_should_map_field_names_correctly(
        self, search_plugin_live_mode, mock_search_client, sample_srm_documents
    ):
        """
        Verify update_srm_document maps Owner_Notes to owner_notes.

        Tests that field name normalization works correctly, mapping
        Pascal case to snake case field names.
        """
        # Arrange
        mock_search_client.get_document.return_value = sample_srm_documents["document_detail"]
        updates = json.dumps({"Owner_Notes": "Updated content"})

        # Act
        result = await search_plugin_live_mode.update_srm_document(
            document_id="SRM-051",
            updates=updates
        )

        # Assert
        # Verify upload_documents was called with mapped field name
        upload_call = mock_search_client.upload_documents.call_args
        assert upload_call is not None
        uploaded_doc = upload_call[1]["documents"][0]
        assert "owner_notes" in uploaded_doc

    @pytest.mark.asyncio
    async def test_should_capture_before_state_when_updating(
        self, search_plugin_live_mode, mock_search_client, sample_srm_documents
    ):
        """
        Verify update_srm_document captures before state.

        Tests that the plugin retrieves current document state before
        updating to provide before/after comparison.
        """
        # Arrange
        mock_search_client.get_document.return_value = sample_srm_documents["document_detail"]
        updates = json.dumps({"owner_notes": "New content"})

        # Act
        result = await search_plugin_live_mode.update_srm_document(
            document_id="SRM-051",
            updates=updates
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["success"] is True
        assert len(result_data["changes"]) == 1
        change = result_data["changes"][0]
        assert change["field"] == "owner_notes"
        assert change["before"] == "Original owner notes content"
        assert change["after"] == "New content"

    @pytest.mark.asyncio
    async def test_should_return_changes_with_before_after(
        self, search_plugin, mock_search_client, sample_srm_documents
    ):
        """
        Verify update response includes before/after values.

        Tests that the update response includes detailed change
        information with before and after values for each field.
        """
        # Arrange
        mock_search_client.get_document.return_value = sample_srm_documents["document_detail"]
        updates = json.dumps({
            "owner_notes": "New owner notes",
            "hidden_notes": "New hidden notes"
        })

        # Act
        result = await search_plugin.update_srm_document(
            document_id="SRM-051",
            updates=updates
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["success"] is True
        assert len(result_data["changes"]) == 2

        # Verify structure of changes array
        for change in result_data["changes"]:
            assert "field" in change
            assert "before" in change
            assert "after" in change

    @pytest.mark.asyncio
    async def test_should_handle_mock_mode_correctly(
        self, search_plugin, mock_search_client
    ):
        """
        Verify update_srm_document respects mock_updates flag.

        Tests that when mock_updates=True, no actual updates are
        performed to Azure Search.
        """
        # Arrange
        updates = json.dumps({"owner_notes": "Test update"})

        # Act
        result = await search_plugin.update_srm_document(
            document_id="SRM-051",
            updates=updates
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["mocked"] is True

        # Verify upload_documents was NOT called in mock mode
        mock_search_client.upload_documents.assert_not_called()

    @pytest.mark.asyncio
    async def test_should_handle_update_failure_gracefully(
        self, search_plugin_live_mode, mock_search_client, sample_srm_documents
    ):
        """
        Verify update_srm_document handles Azure Search errors.

        Tests that failures during upload are caught and returned
        as error responses rather than raising exceptions.
        """
        # Arrange
        mock_search_client.get_document.return_value = sample_srm_documents["document_detail"]

        # Mock upload failure
        upload_result = Mock()
        upload_result.succeeded = False
        upload_result.error_message = "Index update failed"
        mock_search_client.upload_documents.return_value = [upload_result]

        updates = json.dumps({"owner_notes": "Test update"})

        # Act
        result = await search_plugin_live_mode.update_srm_document(
            document_id="SRM-051",
            updates=updates
        )

        # Assert
        result_data = json.loads(result)
        assert result_data["success"] is False
        assert "error" in result_data

    @pytest.mark.asyncio
    async def test_should_use_srm_id_as_key_field(
        self, search_plugin_live_mode, mock_search_client, sample_srm_documents
    ):
        """
        Verify update_srm_document uses SRM_ID as document key.

        Tests that the update document includes SRM_ID as the key field
        for Azure Search merge operations.
        """
        # Arrange
        mock_search_client.get_document.return_value = sample_srm_documents["document_detail"]
        updates = json.dumps({"owner_notes": "Updated content"})

        # Act
        result = await search_plugin_live_mode.update_srm_document(
            document_id="SRM-051",
            updates=updates
        )

        # Assert
        upload_call = mock_search_client.upload_documents.call_args
        uploaded_doc = upload_call[1]["documents"][0]
        assert uploaded_doc["SRM_ID"] == "SRM-051"
        assert uploaded_doc["@search.action"] == "merge"


class TestFindSimilarSRMs:
    """Tests for find_similar_srms method."""

    @pytest.mark.asyncio
    async def test_should_filter_by_similarity_threshold(
        self, search_plugin
    ):
        """
        Verify find_similar_srms filters by similarity threshold.

        Tests that only documents with similarity scores above
        the threshold are returned.
        """
        # Act
        result = await search_plugin.find_similar_srms(
            query="Application Server",
            similarity_threshold=0.8
        )

        # Assert
        results_data = json.loads(result)
        assert isinstance(results_data, list)

        # All results should be above threshold
        for doc in results_data:
            assert doc["similarity_score"] >= 0.8
