"""
SQLite FTS5 search store implementation.

Provides BM25 keyword search using SQLite's FTS5 extension.
Suitable for local development, testing, and small deployments (~10K documents).
"""

import sqlite3
import json
from typing import Any, AsyncIterator

from src.memory.vector_store_base import VectorStoreBase


class SearchResult:
    """Wrapper for search results to match expected interface."""

    def __init__(self, record: Any, score: float):
        """
        Initialize search result.

        Args:
            record: The record object
            score: Search relevance score (BM25)
        """
        self.record = record
        self.score = score


class SQLiteSearchStore(VectorStoreBase):
    """
    SQLite FTS5 implementation for BM25 keyword search.

    Uses SQLite's FTS5 extension for full-text search with BM25 ranking.
    Supports both in-memory (:memory:) and file-based databases.

    Schema:
        - Searchable fields: Name, Description, owner_notes, hidden_notes, TechnologiesTeamWorksWith
        - Filterable fields: SRM_ID, Team, Type, id, URL_Link
        - Feedback fields: negative_feedback_queries, positive_feedback_queries, feedback_score_adjustment

    WARNING: Thread Safety
        This store uses check_same_thread=False for SQLite connections.
        It is NOT thread-safe and must only be accessed from a single thread.
        Do not share instances across multiple threads or async tasks that
        run in different threads.
    """

    # Whitelist of allowed filter fields to prevent SQL injection
    ALLOWED_FILTER_FIELDS = {'SRM_ID', 'Team', 'Type', 'id', 'URL_Link'}

    def __init__(self, db_path: str = ":memory:"):
        """
        Initialize SQLite search store.

        Args:
            db_path: Path to SQLite database file, or ":memory:" for in-memory database
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Access columns by name

        # Create FTS5 table
        self._create_fts_table()

    def _create_fts_table(self) -> None:
        """Create FTS5 virtual table for full-text search."""
        cursor = self.conn.cursor()

        # Create FTS5 table with BM25 ranking
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS srm_fts USING fts5(
                -- Searchable fields (full-text indexed)
                Name,
                Description,
                owner_notes,
                hidden_notes,
                TechnologiesTeamWorksWith,

                -- Filterable fields (not full-text indexed)
                SRM_ID UNINDEXED,
                Team UNINDEXED,
                Type UNINDEXED,
                id UNINDEXED,
                URL_Link UNINDEXED,

                -- Feedback metadata (stored as JSON text)
                negative_feedback_queries UNINDEXED,
                positive_feedback_queries UNINDEXED,
                feedback_score_adjustment UNINDEXED,

                -- Use porter stemming and unicode tokenization
                tokenize='porter unicode61'
            )
        """)

        self.conn.commit()

    async def ensure_collection_exists(self) -> None:
        """
        Ensure the collection/table exists.

        For SQLite, table is created in __init__, so this is a no-op.
        """
        # No-op: table created in __init__
        pass

    async def upsert(self, records: list[Any]) -> None:
        """
        Insert or update records in SQLite FTS5 table.

        Args:
            records: List of record objects to upsert
        """
        if not records:
            return

        cursor = self.conn.cursor()

        for record in records:
            # Extract fields from record
            doc = {}
            if hasattr(record, '__dict__'):
                doc = record.__dict__.copy()

            # Convert feedback lists to JSON strings for storage
            if 'negative_feedback_queries' in doc and isinstance(doc['negative_feedback_queries'], list):
                doc['negative_feedback_queries'] = json.dumps(doc['negative_feedback_queries'])
            if 'positive_feedback_queries' in doc and isinstance(doc['positive_feedback_queries'], list):
                doc['positive_feedback_queries'] = json.dumps(doc['positive_feedback_queries'])

            # Ensure all required fields exist with defaults
            fields = {
                'id': doc.get('id', ''),
                'SRM_ID': doc.get('SRM_ID', ''),
                'Name': doc.get('Name', ''),
                'Description': doc.get('Description', ''),
                'URL_Link': doc.get('URL_Link', ''),
                'Team': doc.get('Team', ''),
                'Type': doc.get('Type', ''),
                'TechnologiesTeamWorksWith': doc.get('TechnologiesTeamWorksWith', ''),
                'owner_notes': doc.get('owner_notes', ''),
                'hidden_notes': doc.get('hidden_notes', ''),
                'negative_feedback_queries': doc.get('negative_feedback_queries', '[]'),
                'positive_feedback_queries': doc.get('positive_feedback_queries', '[]'),
                'feedback_score_adjustment': doc.get('feedback_score_adjustment', 0.0),
            }

            # Delete existing record with same id if exists
            cursor.execute("DELETE FROM srm_fts WHERE id = ?", (fields['id'],))

            # Insert new record
            cursor.execute("""
                INSERT INTO srm_fts (
                    id, SRM_ID, Name, Description, URL_Link, Team, Type,
                    TechnologiesTeamWorksWith, owner_notes, hidden_notes,
                    negative_feedback_queries, positive_feedback_queries,
                    feedback_score_adjustment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fields['id'], fields['SRM_ID'], fields['Name'],
                fields['Description'], fields['URL_Link'], fields['Team'],
                fields['Type'], fields['TechnologiesTeamWorksWith'],
                fields['owner_notes'], fields['hidden_notes'],
                fields['negative_feedback_queries'],
                fields['positive_feedback_queries'],
                fields['feedback_score_adjustment']
            ))

        self.conn.commit()
        print(f"[+] Upserted {len(records)} documents to SQLite FTS5")

    async def search(
        self,
        query: str,
        top_k: int = 8,
        filters: dict | None = None
    ) -> AsyncIterator[SearchResult]:
        """
        Search using FTS5 BM25 keyword search.

        Args:
            query: The search query text
            top_k: Number of top results to return
            filters: Optional filters to apply (e.g., {"Team": "Storage Team"})

        Returns:
            AsyncIterator of SearchResult objects with records and scores
        """
        cursor = self.conn.cursor()

        # Build WHERE clause for filters
        where_clauses = []
        params = []

        # Add FTS5 MATCH clause
        where_clauses.append("srm_fts MATCH ?")
        params.append(query)

        # Add filter clauses
        if filters:
            for key, value in filters.items():
                if key not in self.ALLOWED_FILTER_FIELDS:
                    raise ValueError(f"Invalid filter field: {key}. Allowed fields: {self.ALLOWED_FILTER_FIELDS}")
                where_clauses.append(f"{key} = ?")
                params.append(value)

        where_clause = " AND ".join(where_clauses)

        # Execute search with BM25 ranking
        sql = f"""
            SELECT
                id, SRM_ID, Name, Description, URL_Link, Team, Type,
                TechnologiesTeamWorksWith, owner_notes, hidden_notes,
                negative_feedback_queries, positive_feedback_queries,
                feedback_score_adjustment,
                bm25(srm_fts) as score
            FROM srm_fts
            WHERE {where_clause}
            ORDER BY bm25(srm_fts)
            LIMIT ?
        """
        params.append(top_k)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # Convert rows to SearchResult objects
        async def result_generator():
            for row in rows:
                # Parse JSON feedback fields
                negative_feedback = json.loads(row['negative_feedback_queries']) if row['negative_feedback_queries'] else []
                positive_feedback = json.loads(row['positive_feedback_queries']) if row['positive_feedback_queries'] else []

                # Create record object
                # Note: Multiple field names for backward compatibility with Azure store
                # - content/use_case both map to Description (different consumers expect different names)
                # - category/kind both map to Type (legacy naming)
                # - owning_team/team both map to Team (API compatibility)
                record = type('Record', (), {
                    'id': row['id'],
                    'srm_id': row['SRM_ID'],
                    'name': row['Name'],
                    'content': row['Description'],
                    'use_case': row['Description'],
                    'category': row['Type'],
                    'kind': row['Type'],
                    'owning_team': row['Team'],
                    'team': row['Team'],
                    'technologies': row['TechnologiesTeamWorksWith'],
                    'url': row['URL_Link'],
                    'owner_notes': row['owner_notes'],
                    'hidden_notes': row['hidden_notes'],
                    'negative_feedback_queries': negative_feedback,
                    'positive_feedback_queries': positive_feedback,
                    'feedback_score_adjustment': row['feedback_score_adjustment'],
                })()

                # BM25 scores are negative (lower is better), convert to positive
                score = abs(float(row['score']))

                yield SearchResult(record=record, score=score)

        return result_generator()

    async def get_by_id(self, record_id: str) -> Any | None:
        """
        Retrieve a specific record by ID.

        Args:
            record_id: The unique identifier of the record (id field)

        Returns:
            The record if found, None otherwise
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                id, SRM_ID, Name, Description, URL_Link, Team, Type,
                TechnologiesTeamWorksWith, owner_notes, hidden_notes,
                negative_feedback_queries, positive_feedback_queries,
                feedback_score_adjustment
            FROM srm_fts
            WHERE id = ?
        """, (record_id,))

        row = cursor.fetchone()

        if not row:
            return None

        # Parse JSON feedback fields
        negative_feedback = json.loads(row['negative_feedback_queries']) if row['negative_feedback_queries'] else []
        positive_feedback = json.loads(row['positive_feedback_queries']) if row['positive_feedback_queries'] else []

        # Create record object
        # Note: Multiple field names for backward compatibility with Azure store
        # - content/use_case both map to Description (different consumers expect different names)
        # - category/kind both map to Type (legacy naming)
        # - owning_team/team both map to Team (API compatibility)
        record = type('Record', (), {
            'id': row['id'],
            'srm_id': row['SRM_ID'],
            'name': row['Name'],
            'content': row['Description'],
            'use_case': row['Description'],
            'category': row['Type'],
            'kind': row['Type'],
            'owning_team': row['Team'],
            'team': row['Team'],
            'technologies': row['TechnologiesTeamWorksWith'],
            'url': row['URL_Link'],
            'owner_notes': row['owner_notes'],
            'hidden_notes': row['hidden_notes'],
            'negative_feedback_queries': negative_feedback,
            'positive_feedback_queries': positive_feedback,
            'feedback_score_adjustment': row['feedback_score_adjustment'],
        })()

        return record

    async def update_feedback_scores(
        self,
        srm_id: str,
        query: str,
        feedback_type: str,
        user_id: str | None = None
    ) -> None:
        """
        Update record with feedback metadata.

        Args:
            srm_id: SRM_ID from the record (e.g., "SRM-051")
            query: Query associated with the feedback
            feedback_type: Type of feedback ('positive', 'negative', or 'reset')
            user_id: Optional user ID for personalized adjustments (not used in SQLite)
        """
        cursor = self.conn.cursor()

        # Find document by SRM_ID
        cursor.execute("""
            SELECT
                id, negative_feedback_queries, positive_feedback_queries,
                feedback_score_adjustment
            FROM srm_fts
            WHERE SRM_ID = ?
        """, (srm_id,))

        row = cursor.fetchone()

        if not row:
            print(f"[!] Document with SRM_ID '{srm_id}' not found for feedback update")
            print(f"[*] Feedback is still recorded and will be used in reranking")
            return

        # Parse existing feedback
        negative_feedback = json.loads(row['negative_feedback_queries']) if row['negative_feedback_queries'] else []
        positive_feedback = json.loads(row['positive_feedback_queries']) if row['positive_feedback_queries'] else []
        score_adjustment = float(row['feedback_score_adjustment']) if row['feedback_score_adjustment'] else 0.0

        # Update based on feedback type
        if feedback_type == 'negative':
            if query not in negative_feedback:
                negative_feedback.append(query)
            score_adjustment -= 0.1  # Lower score by 0.1 for negative feedback
        elif feedback_type == 'positive':
            if query not in positive_feedback:
                positive_feedback.append(query)
            score_adjustment += 0.2  # Boost score by 0.2 for positive feedback
        elif feedback_type == 'reset':
            negative_feedback = []
            positive_feedback = []
            score_adjustment = 0.0

        # Update the record
        cursor.execute("""
            UPDATE srm_fts
            SET
                negative_feedback_queries = ?,
                positive_feedback_queries = ?,
                feedback_score_adjustment = ?
            WHERE id = ?
        """, (
            json.dumps(negative_feedback),
            json.dumps(positive_feedback),
            score_adjustment,
            row['id']
        ))

        self.conn.commit()
        print(f"[+] Updated feedback scores for SRM {srm_id} ({feedback_type})")

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def __del__(self):
        """Cleanup database connection on deletion."""
        self.close()
