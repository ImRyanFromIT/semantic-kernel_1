'''Fuzzy text matching utilities for hybrid search.'''

from difflib import SequenceMatcher
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.srm_record import SRMRecord


def extract_tokens(text: str) -> list[str]:
    '''
    Extract lowercase tokens from text.

    Args:
        text: Input text to tokenize

    Returns:
        List of lowercase tokens with punctuation removed
    '''
    # Remove punctuation and split on whitespace
    cleaned = re.sub(r'[^\w\s]', ' ', text)
    tokens = cleaned.lower().split()
    return tokens


def fuzzy_match_score(query: str, target: str) -> float:
    '''
    Calculate fuzzy similarity score between two strings.

    Uses SequenceMatcher for fuzzy matching that handles typos
    and partial matches.

    Args:
        query: Query string
        target: Target string to match against

    Returns:
        Similarity score from 0.0 to 1.0
    '''
    # Case-insensitive comparison
    query_lower = query.lower()
    target_lower = target.lower()

    # Use SequenceMatcher for fuzzy similarity
    matcher = SequenceMatcher(None, query_lower, target_lower)
    return matcher.ratio()


def search_record_fields(
    query: str,
    record: 'SRMRecord',
    field_weights: dict[str, float] | None = None
) -> float:
    '''
    Search multiple fields in a record using fuzzy matching.

    Computes weighted fuzzy match scores across multiple text fields
    and returns the maximum score found.

    Args:
        query: Query string
        record: SRMRecord to search
        field_weights: Optional field weights (default: name=1.0, category=0.7, use_case=1.0)

    Returns:
        Maximum weighted fuzzy match score across all fields
    '''
    if field_weights is None:
        field_weights = {
            'name': 1.0,
            'category': 0.7,
            'use_case': 1.0
        }

    # Extract tokens from query
    query_tokens = extract_tokens(query)

    max_score = 0.0

    # Check each weighted field
    for field_name, weight in field_weights.items():
        if not hasattr(record, field_name):
            continue

        field_value = getattr(record, field_name)
        if not field_value:
            continue

        # Get best fuzzy match for any query token against this field
        field_tokens = extract_tokens(field_value)

        # Try matching full query against full field
        full_match_score = fuzzy_match_score(query, field_value) * weight
        max_score = max(max_score, full_match_score)

        # Try matching individual query tokens against field tokens
        for q_token in query_tokens:
            for f_token in field_tokens:
                token_score = fuzzy_match_score(q_token, f_token) * weight
                max_score = max(max_score, token_score)

    return max_score
