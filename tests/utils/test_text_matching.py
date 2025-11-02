'''Tests for fuzzy text matching utilities.'''

import pytest
from src.utils.text_matching import fuzzy_match_score, extract_tokens
from src.models.srm_record import SRMRecord


def test_extract_tokens_basic():
    '''Test basic token extraction.'''
    tokens = extract_tokens("Hello World")
    assert tokens == ["hello", "world"]


def test_extract_tokens_with_punctuation():
    '''Test token extraction with punctuation.'''
    tokens = extract_tokens("provision, restore & change")
    assert tokens == ["provision", "restore", "change"]


def test_fuzzy_match_exact():
    '''Test exact match returns 1.0.'''
    score = fuzzy_match_score("provisioning", "provisioning")
    assert score == 1.0


def test_fuzzy_match_typo():
    '''Test fuzzy match catches typos.'''
    score = fuzzy_match_score("provisioning", "provisionng")
    assert score >= 0.8


def test_fuzzy_match_partial():
    '''Test partial matches score lower.'''
    score = fuzzy_match_score("provisioning", "provision")
    assert 0.7 <= score < 1.0


def test_fuzzy_match_no_match():
    '''Test completely different strings score low.'''
    score = fuzzy_match_score("provisioning", "database")
    assert score < 0.5


def test_fuzzy_match_case_insensitive():
    '''Test case insensitivity.'''
    score1 = fuzzy_match_score("Provisioning", "provisioning")
    score2 = fuzzy_match_score("PROVISIONING", "provisioning")
    assert score1 == 1.0
    assert score2 == 1.0


def test_search_record_fields_exact_name():
    '''Test exact name match scores highest.'''
    record = SRMRecord(
        name="VM Provisioning",
        category="Provisioning",
        owning_team="Cloud Team",
        use_case="Use when you need to provision a new VM",
        text=""
    )

    # Import the function we're about to create
    from src.utils.text_matching import search_record_fields

    score = search_record_fields("VM Provisioning", record)
    assert score >= 0.9  # Should be very high for exact match


def test_search_record_fields_category_match():
    '''Test category match with fuzzy matching.'''
    record = SRMRecord(
        name="Create VM",
        category="Provisioning",
        owning_team="Cloud Team",
        use_case="Use to create virtual machines",
        text=""
    )

    from src.utils.text_matching import search_record_fields

    score = search_record_fields("provisionng", record)  # Typo
    assert score >= 0.5  # Should catch fuzzy match in category


def test_search_record_fields_use_case_match():
    '''Test use_case field matching.'''
    record = SRMRecord(
        name="DB Restore",
        category="Restore",
        owning_team="Data Team",
        use_case="Use when you need to restore database backups",
        text=""
    )

    from src.utils.text_matching import search_record_fields

    score = search_record_fields("database", record)
    assert score >= 0.5  # Should match "database" in use_case


def test_search_record_fields_no_match():
    '''Test no match returns low score.'''
    record = SRMRecord(
        name="VM Provisioning",
        category="Provisioning",
        owning_team="Cloud Team",
        use_case="Create virtual machines",
        text=""
    )

    from src.utils.text_matching import search_record_fields

    score = search_record_fields("database restore", record)
    assert score < 0.7  # Should be lower than good matches (fuzzy allows some incidental overlap)
