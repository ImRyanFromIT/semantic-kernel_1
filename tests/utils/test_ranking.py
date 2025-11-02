'''Tests for ranking and fusion utilities.'''

import pytest
from src.utils.ranking import reciprocal_rank_fusion
from src.models.srm_record import SRMRecord


def test_rrf_single_list():
    '''Test RRF with single result list.'''
    record1 = SRMRecord(id="1", name="A", category="Cat", owning_team="Team", use_case="Use", text="A Cat Use")
    record2 = SRMRecord(id="2", name="B", category="Cat", owning_team="Team", use_case="Use", text="B Cat Use")
    record3 = SRMRecord(id="3", name="C", category="Cat", owning_team="Team", use_case="Use", text="C Cat Use")

    vector_results = [record1, record2, record3]
    keyword_results = []

    merged = reciprocal_rank_fusion(vector_results, keyword_results, k=60)

    # Should maintain order from vector results
    assert len(merged) == 3
    assert merged[0][0] == "1"
    assert merged[1][0] == "2"
    assert merged[2][0] == "3"


def test_rrf_overlapping_results():
    '''Test RRF with overlapping results gets boosted.'''
    record1 = SRMRecord(id="1", name="A", category="Cat", owning_team="Team", use_case="Use", text="A Cat Use")
    record2 = SRMRecord(id="2", name="B", category="Cat", owning_team="Team", use_case="Use", text="B Cat Use")
    record3 = SRMRecord(id="3", name="C", category="Cat", owning_team="Team", use_case="Use", text="C Cat Use")

    vector_results = [record1, record2, record3]
    keyword_results = [record2]  # record2 ranks #1 in keyword, #2 in vector

    merged = reciprocal_rank_fusion(vector_results, keyword_results, k=60)

    # record2 should be boosted to top (appears in both lists with best combined rank)
    assert merged[0][0] == "2"
    # record1 should be second (only in vector list at rank 1)
    assert merged[1][0] == "1"


def test_rrf_disjoint_results():
    '''Test RRF with completely different results.'''
    record1 = SRMRecord(id="1", name="A", category="Cat", owning_team="Team", use_case="Use", text="A Cat Use")
    record2 = SRMRecord(id="2", name="B", category="Cat", owning_team="Team", use_case="Use", text="B Cat Use")
    record3 = SRMRecord(id="3", name="C", category="Cat", owning_team="Team", use_case="Use", text="C Cat Use")
    record4 = SRMRecord(id="4", name="D", category="Cat", owning_team="Team", use_case="Use", text="D Cat Use")

    vector_results = [record1, record2]
    keyword_results = [record3, record4]

    merged = reciprocal_rank_fusion(vector_results, keyword_results, k=60)

    # Should include all 4 results
    assert len(merged) == 4
    result_ids = {item[0] for item in merged}
    assert result_ids == {"1", "2", "3", "4"}


def test_rrf_empty_lists():
    '''Test RRF handles empty input.'''
    merged = reciprocal_rank_fusion([], [], k=60)
    assert merged == []


def test_rrf_score_calculation():
    '''Test RRF score formula is correct.'''
    record1 = SRMRecord(id="1", name="A", category="Cat", owning_team="Team", use_case="Use", text="A Cat Use")

    vector_results = [record1]  # rank 1
    keyword_results = [record1]  # rank 1

    merged = reciprocal_rank_fusion(vector_results, keyword_results, k=60)

    # RRF score should be: 1/(60+1) + 1/(60+1) = 2/61
    expected_score = 2 / 61
    assert abs(merged[0][1] - expected_score) < 0.001
