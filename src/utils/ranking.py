'''Ranking and fusion utilities for hybrid search.'''

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.srm_record import SRMRecord


def reciprocal_rank_fusion(
    vector_results: list['SRMRecord'],
    keyword_results: list['SRMRecord'],
    k: int = 60
) -> list[tuple[str, float]]:
    '''
    Combine ranked lists using Reciprocal Rank Fusion.

    RRF formula: score(record) = Σ(1 / (k + rank_i))
    where rank_i is the rank of the record in list i.

    This is a standard industry algorithm for merging multiple ranked
    lists without requiring score normalization.

    Args:
        vector_results: Ranked list from vector search
        keyword_results: Ranked list from keyword search
        k: Constant to reduce impact of high ranks (default: 60)

    Returns:
        List of (record_id, rrf_score) tuples sorted by score descending
    '''
    rrf_scores: dict[str, float] = {}

    # Process vector results
    for rank, record in enumerate(vector_results, start=1):
        rrf_scores[record.id] = 1.0 / (k + rank)

    # Process keyword results
    for rank, record in enumerate(keyword_results, start=1):
        score = 1.0 / (k + rank)
        if record.id in rrf_scores:
            rrf_scores[record.id] += score
        else:
            rrf_scores[record.id] = score

    # Sort by RRF score descending
    sorted_results = sorted(
        rrf_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return sorted_results
