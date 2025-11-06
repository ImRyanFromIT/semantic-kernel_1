'''
In-memory vector store implementation using Semantic Kernel.
'''

from typing import Any, AsyncIterator

from semantic_kernel.connectors.ai.embeddings.embedding_generator_base import EmbeddingGeneratorBase
from semantic_kernel.connectors.in_memory import InMemoryStore

from src.memory.vector_store_base import VectorStoreBase
from src.models.srm_record import SRMRecord
from src.utils.text_matching import search_record_fields
from src.utils.ranking import reciprocal_rank_fusion


class SearchResult:
    '''Wrapper for search results.'''

    def __init__(self, record, score):
        '''
        Initialize search result.

        Args:
            record: The record object
            score: Search relevance score
        '''
        self.record = record
        self.score = score


class InMemoryVectorStore(VectorStoreBase):
    '''
    In-memory vector store with hybrid search capabilities.

    Combines Semantic Kernel's InMemoryStore for vector similarity
    with custom fuzzy keyword matching using Reciprocal Rank Fusion (RRF).

    Features:
    - Vector similarity search (semantic matching via embeddings)
    - Fuzzy keyword matching (handles typos, partial matches)
    - Reciprocal Rank Fusion for intelligent result merging
    - Configurable fuzzy threshold and RRF parameters

    Best for: Development, testing, prototyping. Not recommended for
    production due to lack of persistence and scalability limits.

    Example:
        >>> from src.memory.in_memory_store import InMemoryVectorStore
        >>> from src.utils.embedding_service import AzureEmbeddingService
        >>>
        >>> embedding_gen = AzureEmbeddingService()
        >>> store = InMemoryVectorStore(embedding_gen)
        >>> await store.ensure_collection_exists()
        >>>
        >>> # Upsert records
        >>> await store.upsert(records)
        >>>
        >>> # Hybrid search
        >>> results = await store.search("database backup", top_k=5)
        >>> async for result in results:
        >>>     print(f"{result.record.name}: {result.score}")
    '''
    
    def __init__(self, embedding_generator: EmbeddingGeneratorBase):
        '''
        Initialize the in-memory vector store.
        
        Args:
            embedding_generator: The embedding generator service to use
        '''
        self.embedding_generator = embedding_generator
        self.store = InMemoryStore()
        self.collection = None
    
    async def ensure_collection_exists(self) -> None:
        '''Ensure the collection exists in the store.'''
        # Don't pass embedding_generator here since we manually generate embeddings
        self.collection = self.store.get_collection(
            record_type=SRMRecord
        )
        await self.collection.ensure_collection_exists()
    
    async def upsert(self, records: list[SRMRecord]) -> None:
        '''
        Insert or update SRM records with embeddings.
        
        Args:
            records: List of SRMRecord objects to upsert
        '''
        if not self.collection:
            await self.ensure_collection_exists()
        
        # Generate embeddings for records that need them
        for record in records:
            if isinstance(record.embedding, str):
                # The embedding field contains text - generate the actual embedding
                embeddings = await self.embedding_generator.generate_embeddings([record.embedding])
                # Convert numpy array to plain Python list if needed
                embedding = embeddings[0]
                if hasattr(embedding, 'tolist'):
                    embedding = embedding.tolist()
                record.embedding = embedding
        
        # Upsert to collection
        await self.collection.upsert(records)
    
    async def search(
        self,
        query: str,
        top_k: int = 8,
        filters: dict | None = None,
        fuzzy_threshold: float = 0.8,
        rrf_k: int = 60
    ) -> AsyncIterator[Any]:
        '''
        Hybrid search combining vector similarity and fuzzy keyword matching.

        Uses Reciprocal Rank Fusion to combine:
        1. Vector similarity search (semantic matching)
        2. Fuzzy keyword search across name, category, and use_case fields

        Args:
            query: The search query text
            top_k: Number of top results to return
            filters: Optional filters (not fully implemented for InMemory)
            fuzzy_threshold: Minimum similarity score for keyword matches (0.0-1.0)
            rrf_k: RRF constant for rank fusion (default: 60)

        Returns:
            AsyncIterator of search results sorted by RRF score

        Raises:
            ValueError: If fuzzy_threshold is not in range [0.0, 1.0] or rrf_k is not positive
        '''
        # Validate parameters
        if not 0.0 <= fuzzy_threshold <= 1.0:
            raise ValueError(f"fuzzy_threshold must be in range [0.0, 1.0], got {fuzzy_threshold}")
        if rrf_k <= 0:
            raise ValueError(f"rrf_k must be positive, got {rrf_k}")

        if not self.collection:
            await self.ensure_collection_exists()

        # Skip hybrid search for empty queries - return empty results
        if not query or not query.strip():
            async def empty_iterator():
                return
                yield  # Make it a generator (unreachable but makes it async gen)
            return empty_iterator()

        # 1. Vector search (semantic similarity)
        # Generate embedding for the query
        query_embeddings = await self.embedding_generator.generate_embeddings([query])
        query_embedding = query_embeddings[0]
        if hasattr(query_embedding, 'tolist'):
            query_embedding = query_embedding.tolist()

        # Fetch more results for better RRF coverage
        vector_results = await self.collection.search(vector=query_embedding, top=top_k * 2)
        vector_records = [result.record async for result in vector_results.results]

        # 2. Keyword search (fuzzy matching)
        # Get all records and score them by keyword matching
        # NOTE: Using top=1000 as a "get all" approach has a limitation - it won't work for
        # collections with >1000 records. This is acceptable for development and testing scenarios
        # where the dataset is small. For production use with larger datasets, consider using
        # SQLite or Azure AI Search stores which handle this more efficiently.
        all_records_result = await self.collection.search(vector=query_embedding, top=1000)
        all_records = [result.record async for result in all_records_result.results]

        keyword_scored = []
        for record in all_records:
            score = search_record_fields(query, record)
            if score >= fuzzy_threshold:
                keyword_scored.append((record, score))

        # Sort by keyword score
        keyword_scored.sort(key=lambda x: x[1], reverse=True)
        keyword_records = [record for record, score in keyword_scored[:top_k * 2]]

        # 3. Reciprocal Rank Fusion
        rrf_results = reciprocal_rank_fusion(vector_records, keyword_records, k=rrf_k)

        # 4. Get top_k record IDs from RRF
        top_ids = [record_id for record_id, score in rrf_results[:top_k]]

        # 5. Fetch full records in RRF order
        final_results = []
        for record_id in top_ids:
            record = await self.collection.get(record_id)
            if record:
                # Create a result object with RRF score
                result = SearchResult(
                    record=record,
                    score=dict(rrf_results)[record_id]  # RRF score
                )
                final_results.append(result)

        # Return as async iterator
        async def result_iterator():
            for result in final_results:
                yield result

        return result_iterator()
    
    async def get_by_id(self, record_id: str) -> SRMRecord | None:
        '''
        Retrieve a specific SRM record by ID.
        
        Args:
            record_id: The unique identifier of the record
            
        Returns:
            The SRMRecord if found, None otherwise
        '''
        if not self.collection:
            await self.ensure_collection_exists()
        
        result = await self.collection.get(record_id)
        return result
    
    async def update_feedback_scores(
        self, 
        srm_id: str, 
        query: str, 
        feedback_type: str,
        user_id: str | None = None
    ) -> None:
        '''
        Update SRM record with feedback metadata.
        
        For in-memory store, we store feedback in memory and apply adjustments
        during search operations. Since we can't easily modify the embeddings,
        we'll store feedback metadata for use in reranking.
        
        Args:
            srm_id: ID of the SRM to update
            query: Query associated with the feedback
            feedback_type: Type of feedback ('positive' or 'negative')
            user_id: Optional user ID for personalized adjustments
        '''
        # For in-memory store, feedback is primarily handled through
        # the FeedbackStore and applied during reranking
        # This is a no-op as we don't modify the in-memory records directly
        # The feedback processor will use FeedbackStore to influence reranking
        print(f"[*] Feedback recorded for SRM {srm_id} ({feedback_type})")
        print(f"[*] Feedback will be applied during reranking phase")

