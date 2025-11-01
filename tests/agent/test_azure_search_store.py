"""
Azure Search Store Integration Tests

Purpose: Comprehensive testing of AzureAISearchStore class for Azure Cognitive Search integration.

Type: Integration (mocked Azure Search client)
Test Count: 20

Key Test Areas:
1. Initialization & Configuration
   - Store creation with valid/invalid config
   - Environment variable loading
   - Authentication setup
   - Index name handling

2. Search Operations
   - Basic text search (BM25)
   - Filter expressions
   - Empty result handling
   - Field mapping
   - Score parsing
   - Async iteration

3. Update Operations
   - Upsert single record
   - Upsert batch records
   - Document serialization
   - None value handling

4. Get by ID Operations
   - Successful retrieval
   - Document not found
   - Error handling

5. Feedback Score Updates
   - Positive feedback
   - Negative feedback
   - Feedback reset
   - Document key strategies
   - Error handling

6. Error Handling
   - Missing configuration
   - Search client failures
   - Network errors
   - Invalid documents

Dependencies:
- unittest.mock for Azure Search client mocking
- pytest-asyncio for async test support

Note: Tests use mocked SearchClient to avoid real Azure API calls.
"""

import os
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any

# Import the class under test
from src.memory.azure_search_store import AzureAISearchStore, SearchResult


class TestAzureSearchStoreInitialization:
    """Test Azure Search Store initialization and configuration."""

    def test_initialization_with_parameters(self):
        """Test store initialization with explicit parameters."""
        endpoint = "https://test-search.search.windows.net"
        api_key = "test-key-123"
        index_name = "test-index"

        with patch('src.memory.azure_search_store.SearchClient') as mock_client:
            store = AzureAISearchStore(
                endpoint=endpoint,
                api_key=api_key,
                index_name=index_name
            )

            assert store.endpoint == endpoint
            assert store.api_key == api_key
            assert store.index_name == index_name
            mock_client.assert_called_once()

    def test_initialization_with_environment_variables(self):
        """Test store initialization using environment variables."""
        test_endpoint = "https://env-search.search.windows.net"
        test_api_key = "env-key-456"
        test_index = "env-index"

        with patch.dict(os.environ, {
            'AZURE_AI_SEARCH_ENDPOINT': test_endpoint,
            'AZURE_AI_SEARCH_API_KEY': test_api_key,
            'AZURE_AI_SEARCH_INDEX_NAME': test_index
        }):
            with patch('src.memory.azure_search_store.SearchClient'):
                store = AzureAISearchStore()

                assert store.endpoint == test_endpoint
                assert store.api_key == test_api_key
                assert store.index_name == test_index

    def test_initialization_missing_endpoint_raises_error(self):
        """Test that missing endpoint raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Azure AI Search endpoint must be provided"):
                AzureAISearchStore(api_key="test-key")

    def test_initialization_missing_api_key_raises_error(self):
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Azure AI Search API key must be provided"):
                AzureAISearchStore(endpoint="https://test.search.windows.net")

    def test_initialization_default_index_name(self):
        """Test that default index name is used when not provided."""
        with patch.dict(os.environ, {
            'AZURE_AI_SEARCH_ENDPOINT': 'https://test.search.windows.net',
            'AZURE_AI_SEARCH_API_KEY': 'test-key'
        }, clear=True):
            with patch('src.memory.azure_search_store.SearchClient'):
                store = AzureAISearchStore()

                # Default index name from the code
                assert store.index_name == 'search-semantics'

    def test_search_client_created_with_correct_credentials(self):
        """Test that SearchClient is created with correct Azure credentials."""
        endpoint = "https://test-search.search.windows.net"
        api_key = "test-key-123"
        index_name = "test-index"

        with patch('src.memory.azure_search_store.SearchClient') as mock_client_class:
            with patch('src.memory.azure_search_store.AzureKeyCredential') as mock_credential_class:
                store = AzureAISearchStore(
                    endpoint=endpoint,
                    api_key=api_key,
                    index_name=index_name
                )

                # Verify AzureKeyCredential created with api_key
                mock_credential_class.assert_called_once_with(api_key)

                # Verify SearchClient created with correct parameters
                mock_client_class.assert_called_once_with(
                    endpoint=endpoint,
                    index_name=index_name,
                    credential=mock_credential_class.return_value
                )


class TestAzureSearchStoreEnsureCollection:
    """Test ensure_collection_exists method."""

    @pytest.mark.asyncio
    async def test_ensure_collection_exists_is_noop(self):
        """Test that ensure_collection_exists is a no-op (Azure manages index externally)."""
        with patch('src.memory.azure_search_store.SearchClient'):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            # Should complete without error and do nothing
            result = await store.ensure_collection_exists()
            assert result is None


class TestAzureSearchStoreSearch:
    """Test search operations."""

    @pytest.mark.asyncio
    async def test_search_successful_with_results(self):
        """Test successful search returning multiple results."""
        mock_search_client = Mock()

        # Mock search results
        mock_results = [
            {
                'id': '1',
                'SRM_ID': 'SRM-051',
                'Name': 'Storage Expansion Request',
                'Description': 'Expand storage capacity for data retention',
                'URL_Link': 'https://example.com/srm-051',
                'Team': 'Storage Team',
                'Type': 'Storage',
                'owner_notes': 'Configuration steps for expansion',
                'hidden_notes': 'Internal recommendation logic',
                '@search.score': 0.95
            },
            {
                'id': '2',
                'SRM_ID': 'SRM-052',
                'Name': 'Storage Migration Request',
                'Description': 'Migrate data to new storage system',
                'URL_Link': 'https://example.com/srm-052',
                'Team': 'Storage Team',
                'Type': 'Storage',
                'owner_notes': 'Migration guide',
                'hidden_notes': '',
                '@search.score': 0.85
            }
        ]

        mock_search_client.search = Mock(return_value=iter(mock_results))

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            # Execute search
            result_iterator = await store.search(query="Storage Expansion", top_k=5)

            # Collect results
            results = []
            async for result in result_iterator:
                results.append(result)

            # Verify results
            assert len(results) == 2
            assert isinstance(results[0], SearchResult)
            assert results[0].score == 0.95
            assert results[0].record.srm_id == 'SRM-051'
            assert results[0].record.name == 'Storage Expansion Request'
            assert results[0].record.content == 'Expand storage capacity for data retention'
            assert results[0].record.owner_notes == 'Configuration steps for expansion'

            assert results[1].score == 0.85
            assert results[1].record.srm_id == 'SRM-052'

            # Verify search was called with correct parameters
            mock_search_client.search.assert_called_once()
            call_kwargs = mock_search_client.search.call_args[1]
            assert call_kwargs['search_text'] == "Storage Expansion"
            assert call_kwargs['top'] == 5
            assert call_kwargs['query_type'] == "full"

    @pytest.mark.asyncio
    async def test_search_with_filters(self):
        """Test search with filter expressions."""
        mock_search_client = Mock()
        mock_search_client.search = Mock(return_value=iter([]))

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            # Execute search with filters
            filters = {"Team": "Storage Team", "Type": "Storage"}
            result_iterator = await store.search(
                query="Storage",
                top_k=10,
                filters=filters
            )

            # Consume iterator
            results = [r async for r in result_iterator]

            # Verify filter string construction
            mock_search_client.search.assert_called_once()
            call_kwargs = mock_search_client.search.call_args[1]
            filter_str = call_kwargs['filter']

            # Filter should contain both conditions joined by "and"
            assert "Team eq 'Storage Team'" in filter_str
            assert "Type eq 'Storage'" in filter_str
            assert " and " in filter_str

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """Test search returning no results."""
        mock_search_client = Mock()
        mock_search_client.search = Mock(return_value=iter([]))

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            result_iterator = await store.search(query="NonexistentQuery", top_k=5)

            results = []
            async for result in result_iterator:
                results.append(result)

            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_field_mapping(self):
        """Test that Azure Search fields are correctly mapped to internal format."""
        mock_search_client = Mock()

        mock_result = {
            'id': 'test-id-123',
            'SRM_ID': 'SRM-099',
            'Name': 'Test SRM',
            'Description': 'Test description content',
            'URL_Link': 'https://example.com/test',
            'Team': 'Test Team',
            'Type': 'TestType',
            'owner_notes': 'Owner notes content',
            'hidden_notes': 'Hidden notes content',
            '@search.score': 0.75
        }

        mock_search_client.search = Mock(return_value=iter([mock_result]))

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            result_iterator = await store.search(query="Test", top_k=1)
            results = [r async for r in result_iterator]

            record = results[0].record

            # Verify field mappings
            assert record.id == 'test-id-123'
            assert record.srm_id == 'SRM-099'
            assert record.name == 'Test SRM'
            assert record.content == 'Test description content'
            assert record.use_case == 'Test description content'  # Mapped from Description
            assert record.category == 'TestType'
            assert record.kind == 'TestType'
            assert record.owning_team == 'Test Team'
            assert record.team == 'Test Team'
            assert record.url == 'https://example.com/test'
            assert record.owner_notes == 'Owner notes content'
            assert record.hidden_notes == 'Hidden notes content'

    @pytest.mark.asyncio
    async def test_search_missing_optional_fields(self):
        """Test search handles missing optional fields gracefully."""
        mock_search_client = Mock()

        # Result with minimal fields
        mock_result = {
            'id': 'min-id',
            'SRM_ID': 'SRM-100',
            'Name': 'Minimal SRM',
            'Description': 'Minimal description',
            '@search.score': 0.5
        }

        mock_search_client.search = Mock(return_value=iter([mock_result]))

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            result_iterator = await store.search(query="Test", top_k=1)
            results = [r async for r in result_iterator]

            record = results[0].record

            # Verify defaults for missing fields
            assert record.url == ''
            assert record.team == ''
            assert record.owner_notes == ''
            assert record.hidden_notes == ''


class TestAzureSearchStoreUpsert:
    """Test upsert operations."""

    @pytest.mark.asyncio
    async def test_upsert_single_record(self):
        """Test upserting a single record."""
        mock_search_client = Mock()
        mock_search_client.upload_documents = Mock(return_value=[Mock(succeeded=True)])

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            # Create test record with INSTANCE attributes (not class attributes)
            test_record = type('Record', (), {})()
            test_record.id = 'test-001'
            test_record.SRM_ID = 'SRM-051'
            test_record.Name = 'Test SRM'
            test_record.Description = 'Test description'
            test_record.owner_notes = 'Test notes'

            await store.upsert([test_record])

            # Verify upload_documents called
            mock_search_client.upload_documents.assert_called_once()
            call_args = mock_search_client.upload_documents.call_args

            # Verify document structure
            documents = call_args[1]['documents']
            assert len(documents) == 1
            assert documents[0]['id'] == 'test-001'
            assert documents[0]['SRM_ID'] == 'SRM-051'
            assert documents[0]['owner_notes'] == 'Test notes'

    @pytest.mark.asyncio
    async def test_upsert_batch_records(self):
        """Test upserting multiple records in batch."""
        mock_search_client = Mock()
        mock_search_client.upload_documents = Mock(return_value=[
            Mock(succeeded=True),
            Mock(succeeded=True),
            Mock(succeeded=True)
        ])

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            # Create multiple test records with instance attributes
            records = []
            for i in range(3):
                record = type('Record', (), {})()
                record.id = f'test-{i:03d}'
                record.SRM_ID = f'SRM-{i:03d}'
                record.Name = f'Test SRM {i}'
                record.Description = f'Description {i}'
                records.append(record)

            await store.upsert(records)

            # Verify batch upload
            mock_search_client.upload_documents.assert_called_once()
            documents = mock_search_client.upload_documents.call_args[1]['documents']
            assert len(documents) == 3

    @pytest.mark.asyncio
    async def test_upsert_filters_none_values(self):
        """Test that upsert filters out None values from documents."""
        mock_search_client = Mock()
        mock_search_client.upload_documents = Mock(return_value=[Mock(succeeded=True)])

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            # Create record with None values (instance attributes)
            test_record = type('Record', (), {})()
            test_record.id = 'test-001'
            test_record.SRM_ID = 'SRM-051'
            test_record.Name = 'Test SRM'
            test_record.Description = None  # None value
            test_record.owner_notes = 'Test notes'
            test_record.hidden_notes = None  # None value

            await store.upsert([test_record])

            # Verify None values filtered out
            documents = mock_search_client.upload_documents.call_args[1]['documents']
            doc = documents[0]

            assert 'id' in doc
            assert 'owner_notes' in doc
            assert 'Description' not in doc  # None value filtered
            assert 'hidden_notes' not in doc  # None value filtered

    @pytest.mark.asyncio
    async def test_upsert_empty_list(self):
        """Test that upserting empty list does not call upload."""
        mock_search_client = Mock()
        mock_search_client.upload_documents = Mock()

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            await store.upsert([])

            # Verify upload NOT called for empty list
            mock_search_client.upload_documents.assert_not_called()


class TestAzureSearchStoreGetById:
    """Test get_by_id operations."""

    @pytest.mark.asyncio
    async def test_get_by_id_successful(self):
        """Test successfully retrieving a document by ID."""
        mock_search_client = Mock()

        mock_document = {
            'id': 'test-id-123',
            'SRM_ID': 'SRM-051',
            'Name': 'Storage SRM',
            'Description': 'Storage description',
            'URL_Link': 'https://example.com/srm-051',
            'Team': 'Storage Team',
            'Type': 'Storage',
            'owner_notes': 'Owner notes',
            'hidden_notes': 'Hidden notes'
        }

        mock_search_client.get_document = Mock(return_value=mock_document)

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            result = await store.get_by_id('test-id-123')

            # Verify result
            assert result is not None
            assert result.id == 'test-id-123'
            assert result.srm_id == 'SRM-051'
            assert result.name == 'Storage SRM'
            assert result.content == 'Storage description'

            # Verify get_document called with correct key
            mock_search_client.get_document.assert_called_once_with(key='test-id-123')

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        """Test get_by_id when document doesn't exist."""
        mock_search_client = Mock()
        mock_search_client.get_document = Mock(side_effect=Exception("Document not found"))

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            result = await store.get_by_id('nonexistent-id')

            # Should return None on error
            assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_for_empty_result(self):
        """Test get_by_id returns None when result is falsy."""
        mock_search_client = Mock()
        mock_search_client.get_document = Mock(return_value=None)

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            result = await store.get_by_id('test-id')

            assert result is None


class TestAzureSearchStoreFeedbackUpdates:
    """Test update_feedback_scores operations."""

    @pytest.mark.asyncio
    async def test_update_feedback_scores_positive(self):
        """Test adding positive feedback to a document."""
        mock_search_client = Mock()

        # Mock search to find document by SRM_ID
        mock_search_results = [
            {'id': 'doc-id-123', 'SRM_ID': 'SRM-051', 'Name': 'Test SRM'}
        ]
        mock_search_client.search = Mock(return_value=iter(mock_search_results))

        # Mock get_document to return existing document
        existing_doc = {
            'id': 'doc-id-123',
            'SRM_ID': 'SRM-051',
            'Name': 'Test SRM',
            'negative_feedback_queries': [],
            'positive_feedback_queries': [],
            'feedback_score_adjustment': 0.0
        }
        mock_search_client.get_document = Mock(return_value=existing_doc)

        # Mock merge_or_upload_documents
        mock_search_client.merge_or_upload_documents = Mock(return_value=[Mock(succeeded=True)])

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            await store.update_feedback_scores(
                srm_id='SRM-051',
                query='storage expansion',
                feedback_type='positive'
            )

            # Verify search called to find document
            mock_search_client.search.assert_called_once()

            # Verify merge_or_upload called
            mock_search_client.merge_or_upload_documents.assert_called_once()

            # Verify document updated correctly
            updated_doc = mock_search_client.merge_or_upload_documents.call_args[1]['documents'][0]
            assert 'storage expansion' in updated_doc['positive_feedback_queries']
            assert updated_doc['feedback_score_adjustment'] == 0.2  # +0.2 for positive

    @pytest.mark.asyncio
    async def test_update_feedback_scores_negative(self):
        """Test adding negative feedback to a document."""
        mock_search_client = Mock()

        mock_search_results = [
            {'id': 'doc-id-456', 'SRM_ID': 'SRM-052'}
        ]
        mock_search_client.search = Mock(return_value=iter(mock_search_results))

        existing_doc = {
            'id': 'doc-id-456',
            'SRM_ID': 'SRM-052',
            'negative_feedback_queries': [],
            'positive_feedback_queries': [],
            'feedback_score_adjustment': 0.0
        }
        mock_search_client.get_document = Mock(return_value=existing_doc)
        mock_search_client.merge_or_upload_documents = Mock(return_value=[Mock(succeeded=True)])

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            await store.update_feedback_scores(
                srm_id='SRM-052',
                query='irrelevant query',
                feedback_type='negative'
            )

            # Verify document updated correctly
            updated_doc = mock_search_client.merge_or_upload_documents.call_args[1]['documents'][0]
            assert 'irrelevant query' in updated_doc['negative_feedback_queries']
            assert updated_doc['feedback_score_adjustment'] == -0.1  # -0.1 for negative

    @pytest.mark.asyncio
    async def test_update_feedback_scores_reset(self):
        """Test resetting feedback scores."""
        mock_search_client = Mock()

        mock_search_results = [{'id': 'doc-id-789', 'SRM_ID': 'SRM-053'}]
        mock_search_client.search = Mock(return_value=iter(mock_search_results))

        existing_doc = {
            'id': 'doc-id-789',
            'SRM_ID': 'SRM-053',
            'negative_feedback_queries': ['query1', 'query2'],
            'positive_feedback_queries': ['query3'],
            'feedback_score_adjustment': 0.5
        }
        mock_search_client.get_document = Mock(return_value=existing_doc)
        mock_search_client.merge_or_upload_documents = Mock(return_value=[Mock(succeeded=True)])

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            await store.update_feedback_scores(
                srm_id='SRM-053',
                query='',
                feedback_type='reset'
            )

            # Verify feedback reset
            updated_doc = mock_search_client.merge_or_upload_documents.call_args[1]['documents'][0]
            assert updated_doc['negative_feedback_queries'] == []
            assert updated_doc['positive_feedback_queries'] == []
            assert updated_doc['feedback_score_adjustment'] == 0.0

    @pytest.mark.asyncio
    async def test_update_feedback_scores_document_not_found(self):
        """Test feedback update when document not found."""
        mock_search_client = Mock()

        # Search returns no results
        mock_search_client.search = Mock(return_value=iter([]))

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            # Should not raise exception
            await store.update_feedback_scores(
                srm_id='SRM-999',
                query='test query',
                feedback_type='positive'
            )

            # Verify search called but no update
            mock_search_client.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_feedback_scores_handles_none_fields(self):
        """Test feedback update initializes None fields correctly."""
        mock_search_client = Mock()

        mock_search_results = [{'id': 'doc-id-111', 'SRM_ID': 'SRM-111'}]
        mock_search_client.search = Mock(return_value=iter(mock_search_results))

        # Document with None feedback fields
        existing_doc = {
            'id': 'doc-id-111',
            'SRM_ID': 'SRM-111',
            'negative_feedback_queries': None,
            'positive_feedback_queries': None,
            'feedback_score_adjustment': None
        }
        mock_search_client.get_document = Mock(return_value=existing_doc)
        mock_search_client.merge_or_upload_documents = Mock(return_value=[Mock(succeeded=True)])

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            await store.update_feedback_scores(
                srm_id='SRM-111',
                query='test query',
                feedback_type='positive'
            )

            # Verify None fields initialized before update
            updated_doc = mock_search_client.merge_or_upload_documents.call_args[1]['documents'][0]
            assert isinstance(updated_doc['positive_feedback_queries'], list)
            assert 'test query' in updated_doc['positive_feedback_queries']
            assert updated_doc['feedback_score_adjustment'] == 0.2

    @pytest.mark.asyncio
    async def test_update_feedback_scores_tries_multiple_key_strategies(self):
        """Test that feedback update tries multiple document key strategies."""
        mock_search_client = Mock()

        # Search finds document with specific fields
        mock_search_results = [{
            'id': 'base64-encoded-id',
            'SRM_ID': 'SRM-055',
            'AzureSearch_DocumentKey': 'composite;key;123'
        }]
        mock_search_client.search = Mock(return_value=iter(mock_search_results))

        # First get_document call fails, second succeeds
        existing_doc = {
            'id': 'base64-encoded-id',
            'SRM_ID': 'SRM-055',
            'negative_feedback_queries': [],
            'positive_feedback_queries': [],
            'feedback_score_adjustment': 0.0
        }

        # Mock get_document to fail on first call, succeed on second
        mock_search_client.get_document = Mock(side_effect=[
            Exception("First key failed"),  # SRM_ID strategy fails
            existing_doc  # id strategy succeeds
        ])

        mock_search_client.merge_or_upload_documents = Mock(return_value=[Mock(succeeded=True)])

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            await store.update_feedback_scores(
                srm_id='SRM-055',
                query='test query',
                feedback_type='positive'
            )

            # Verify multiple get_document calls (trying different keys)
            assert mock_search_client.get_document.call_count >= 2

            # Verify update succeeded
            mock_search_client.merge_or_upload_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_feedback_scores_error_handling(self):
        """Test that feedback update errors are caught and logged."""
        mock_search_client = Mock()

        # Mock search to raise exception
        mock_search_client.search = Mock(side_effect=Exception("Search service unavailable"))

        with patch('src.memory.azure_search_store.SearchClient', return_value=mock_search_client):
            store = AzureAISearchStore(
                endpoint="https://test.search.windows.net",
                api_key="test-key",
                index_name="test-index"
            )

            # Should not raise exception - errors are caught
            await store.update_feedback_scores(
                srm_id='SRM-999',
                query='test query',
                feedback_type='positive'
            )

            # Verify search was attempted
            mock_search_client.search.assert_called_once()


class TestSearchResultWrapper:
    """Test SearchResult wrapper class."""

    def test_search_result_initialization(self):
        """Test SearchResult wrapper stores record and score."""
        mock_record = type('Record', (), {})()
        mock_record.id = 'test-001'
        mock_record.name = 'Test Record'

        result = SearchResult(record=mock_record, score=0.85)

        assert result.record.id == 'test-001'
        assert result.record.name == 'Test Record'
        assert result.score == 0.85


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
