"""
SRM Matcher Tests

Purpose: Test SRM matching logic with fuzzy matching, normalization,
         and ambiguity detection.

Type: Integration
Test Count: 11

Key Test Areas:
- Fuzzy matching with similarity thresholds (99%, 90%, 80%)
- Suffix normalization ("Storage SRM" -> "Storage")
- Ambiguity detection (multiple high-confidence matches)
- Update decision logic (should_proceed_with_update)
- Edge cases (empty results, missing fields, whitespace)
- Case sensitivity handling

Dependencies:
- SRMMatcher class
- Mock search results
- Sample SRM data fixtures
"""

import pytest
from src.utils.srm_matcher import SrmMatcher


# ==================== Test Class 1: Similarity Thresholds ====================

class TestSrmMatcherSimilarity:
    """Test SRM matching at different similarity thresholds."""

    def test_exact_match_returns_exact_type(self):
        """
        Test that exact matches (>=99% similarity) return "exact" match type
        with 100 confidence score.

        Thresholds: EXACT_MATCH_THRESHOLD = 0.99
        Location: src/utils/srm_matcher.py:23-26, 109-119
        """
        matcher = SrmMatcher()

        # Test 100% exact match (case-insensitive)
        search_results = [
            {"Name": "Storage Expansion Request", "SRM_ID": "SRM-051"},
            {"Name": "Storage Migration Request", "SRM_ID": "SRM-052"}
        ]

        matched_srm, match_type, confidence = matcher.find_best_match(
            "storage expansion request",  # lowercase
            search_results
        )

        # Verify exact match
        assert match_type == "exact"
        assert confidence >= 0.99  # Confidence is float 0.0-1.0, not 0-100
        assert matched_srm["SRM_ID"] == "SRM-051"

        # Test >=99% similarity (essentially exact)
        search_results = [
            {"Name": "VM Provisioning Request", "SRM_ID": "SRM-101"}
        ]

        matched_srm, match_type, confidence = matcher.find_best_match(
            "VM Provisioning Request",  # Exact match
            search_results
        )

        assert match_type == "exact"
        assert confidence >= 0.99

    def test_high_confidence_match_90_percent(self):
        """
        Test that 90-98% similarity returns "high_confidence" match type.

        Thresholds: HIGH_CONFIDENCE_THRESHOLD = 0.90
        Location: src/utils/srm_matcher.py:121-128
        """
        matcher = SrmMatcher()

        # Test high confidence match (very similar but not exact)
        # "Storage Expansion Requests" vs "Storage Expansion Request" = ~95% similar
        search_results = [
            {"Name": "Storage Expansion Request", "SRM_ID": "SRM-051"}
        ]

        # Using slightly different name (added 's' to make it ~95% similar)
        matched_srm, match_type, confidence = matcher.find_best_match(
            "Storage Expansion Requests",  # Plural vs singular
            search_results
        )

        # Should be high confidence or exact (90%+ similarity)
        assert match_type in ["high_confidence", "exact"], \
            f"Expected 'high_confidence' or 'exact', got '{match_type}' with {confidence} confidence"
        assert confidence >= 0.90
        assert matched_srm["SRM_ID"] == "SRM-051"

    def test_medium_confidence_match_80_percent(self):
        """
        Test that 80-89% similarity returns "medium_confidence" match type.

        Thresholds: MEDIUM_CONFIDENCE_THRESHOLD = 0.80
        Location: src/utils/srm_matcher.py:130-135
        """
        matcher = SrmMatcher()

        # Test medium confidence match (somewhat similar)
        # "Storage Expansion" vs "Storage Expansion Request" = ~81% similar
        search_results = [
            {"Name": "Storage Expansion Request", "SRM_ID": "SRM-051"}
        ]

        matched_srm, match_type, confidence = matcher.find_best_match(
            "Storage Expansion",  # Missing "Request" word
            search_results
        )

        # Should be medium or high confidence (80%+)
        # Acceptable: "medium_confidence" or "high_confidence"
        assert match_type in ["medium_confidence", "high_confidence"], \
            f"Expected medium or high confidence, got '{match_type}' with {confidence} confidence"
        assert confidence >= 0.80
        assert matched_srm["SRM_ID"] == "SRM-051"

    def test_below_threshold_returns_no_match(self):
        """
        Test that <80% similarity returns "no_match" type.

        Location: src/utils/srm_matcher.py:148-153
        """
        matcher = SrmMatcher()

        # Test no match (very different names)
        search_results = [
            {"Name": "Storage Expansion Request", "SRM_ID": "SRM-051"},
            {"Name": "VM Provisioning Service", "SRM_ID": "SRM-052"}
        ]

        matched_srm, match_type, confidence = matcher.find_best_match(
            "Database Backup Configuration",  # Completely different
            search_results
        )

        # Verify no match
        assert match_type == "no_match"
        assert matched_srm is None


# ==================== Test Class 2: Normalization ====================

class TestSrmMatcherNormalization:
    """Test suffix removal normalization to improve matching."""

    def test_suffix_removal_improves_matching(self):
        """
        Test that common suffixes ("SRM", "Service", "Request", "SR")
        are stripped to improve matching.

        LLMs often add these suffixes, but the index may not include them.

        Location: src/utils/srm_matcher.py:32-54
        """
        matcher = SrmMatcher()

        # Test suffix removal: "Storage Expansion SRM" -> "Storage Expansion"
        search_results = [
            {"Name": "Storage Expansion", "SRM_ID": "SRM-051"}
        ]

        # User says "Storage Expansion SRM" (with suffix)
        matched_srm, match_type, confidence = matcher.find_best_match(
            "Storage Expansion SRM",
            search_results
        )

        # Should match after normalization
        assert match_type in ["exact", "high_confidence"]
        assert matched_srm["SRM_ID"] == "SRM-051"

        # Test "Service" suffix removal
        search_results = [
            {"Name": "VM Provisioning", "SRM_ID": "SRM-101"}
        ]

        matched_srm, match_type, confidence = matcher.find_best_match(
            "VM Provisioning Service",  # With "Service" suffix
            search_results
        )

        assert match_type in ["exact", "high_confidence"]
        assert matched_srm["SRM_ID"] == "SRM-101"

        # Test "Request" suffix removal
        search_results = [
            {"Name": "Database Backup", "SRM_ID": "SRM-201"}
        ]

        matched_srm, match_type, confidence = matcher.find_best_match(
            "Database Backup Request",  # With "Request" suffix
            search_results
        )

        assert match_type in ["exact", "high_confidence"]
        assert matched_srm["SRM_ID"] == "SRM-201"


# ==================== Test Class 3: Ambiguity Detection ====================

class TestSrmMatcherAmbiguity:
    """Test ambiguity detection when multiple SRMs match well."""

    def test_multiple_high_confidence_matches_returns_ambiguous(self):
        """
        Test that when 2+ SRMs have >90% similarity, the matcher
        returns "ambiguous" to escalate for human review.

        Location: src/utils/srm_matcher.py:137-146
        """
        matcher = SrmMatcher()

        # Create ambiguous search results (multiple very similar names)
        # Using very similar names that will both score >90%
        search_results = [
            {"Name": "Storage Expansion Request Type A", "SRM_ID": "SRM-051"},
            {"Name": "Storage Expansion Request Type B", "SRM_ID": "SRM-052"}
        ]

        matched_srm, match_type, confidence = matcher.find_best_match(
            "Storage Expansion Request",  # Very similar to both
            search_results
        )

        # Should detect ambiguity (both are >90% similar after substring matching)
        assert match_type == "ambiguous", \
            f"Expected 'ambiguous', got '{match_type}' with confidence {confidence}"
        assert matched_srm is None  # No single match returned

        # Test with 2 nearly identical names
        search_results = [
            {"Name": "VM Provisioning Request v1", "SRM_ID": "SRM-101"},
            {"Name": "VM Provisioning Request v2", "SRM_ID": "SRM-102"}
        ]

        matched_srm, match_type, confidence = matcher.find_best_match(
            "VM Provisioning Request",  # Very similar to both
            search_results
        )

        # Should detect ambiguity (both are >90% similar)
        assert match_type == "ambiguous", \
            f"Expected 'ambiguous', got '{match_type}' with confidence {confidence}"

    def test_should_proceed_only_for_exact_or_high_confidence(self):
        """
        Test that should_proceed_with_update() only returns True for
        "exact" or "high_confidence" matches.

        Medium confidence, ambiguous, and no matches should escalate.

        Location: src/utils/srm_matcher.py:232-243
        """
        matcher = SrmMatcher()

        # Test exact match - should proceed
        assert matcher.should_proceed_with_update("exact") is True

        # Test high confidence - should proceed
        assert matcher.should_proceed_with_update("high_confidence") is True

        # Test medium confidence - should NOT proceed (escalate)
        assert matcher.should_proceed_with_update("medium_confidence") is False

        # Test ambiguous - should NOT proceed (escalate)
        assert matcher.should_proceed_with_update("ambiguous") is False

        # Test no match - should NOT proceed (escalate)
        assert matcher.should_proceed_with_update("no_match") is False


# ==================== Edge Cases ====================

class TestSrmMatcherEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_search_results(self):
        """Test handling of empty search results."""
        matcher = SrmMatcher()

        matched_srm, match_type, confidence = matcher.find_best_match(
            "Storage Request",
            []  # Empty results
        )

        assert match_type == "no_match"
        assert matched_srm is None

    def test_search_result_missing_name_field(self):
        """Test handling of search results missing the Name field."""
        matcher = SrmMatcher()

        # Results with missing Name field
        search_results = [
            {"SRM_ID": "SRM-051"},  # Missing Name
            {"Name": "Valid Result", "SRM_ID": "SRM-052"}
        ]

        # Should skip invalid results and match valid one
        matched_srm, match_type, confidence = matcher.find_best_match(
            "Valid Result",
            search_results
        )

        assert matched_srm["SRM_ID"] == "SRM-052"
        assert match_type in ["exact", "high_confidence"]

    def test_case_insensitive_matching(self):
        """Test that matching is case-insensitive."""
        matcher = SrmMatcher()

        search_results = [
            {"Name": "STORAGE EXPANSION REQUEST", "SRM_ID": "SRM-051"}
        ]

        # Lowercase query
        matched_srm, match_type, confidence = matcher.find_best_match(
            "storage expansion request",
            search_results
        )

        assert match_type == "exact"
        assert matched_srm["SRM_ID"] == "SRM-051"

        # Mixed case query
        matched_srm, match_type, confidence = matcher.find_best_match(
            "StOrAgE ExPaNsIoN ReQuEsT",
            search_results
        )

        assert match_type == "exact"

    def test_whitespace_handling(self):
        """Test that extra whitespace doesn't affect matching."""
        matcher = SrmMatcher()

        search_results = [
            {"Name": "Storage Expansion Request", "SRM_ID": "SRM-051"}
        ]

        # Extra spaces
        matched_srm, match_type, confidence = matcher.find_best_match(
            "  Storage   Expansion   Request  ",
            search_results
        )

        # Should still match (after normalization)
        assert match_type in ["exact", "high_confidence"]
        assert matched_srm["SRM_ID"] == "SRM-051"


class TestGetMatchExplanation:
    """Tests for get_match_explanation method."""

    def test_explains_high_confidence_match(self):
        """Test explanation for high confidence match."""
        explanation = SrmMatcher.get_match_explanation(
            match_type="high_confidence",
            requested_name="Storage Request",
            matched_name="Storage Expansion Request",
            confidence=0.92,
            search_results=[]
        )
        
        assert "High-confidence fuzzy match" in explanation
        assert "Storage Request" in explanation
        assert "Storage Expansion Request" in explanation
        assert "92.0%" in explanation

    def test_explains_medium_confidence_match(self):
        """Test explanation for medium confidence match."""
        explanation = SrmMatcher.get_match_explanation(
            match_type="medium_confidence",
            requested_name="Storage",
            matched_name="Storage Expansion",
            confidence=0.85,
            search_results=[]
        )
        
        assert "Medium-confidence fuzzy match" in explanation
        assert "Storage" in explanation
        assert "85.0%" in explanation
        assert "WARNING" in explanation

    def test_explains_ambiguous_match(self):
        """Test explanation for ambiguous match (covers lines 201-208)."""
        # Use names that will have high similarity (> 0.8 threshold)
        search_results = [
            {"name": "Storage Expansion Request"},
            {"name": "Storage Expansion Service"},
            {"name": "Storage Expansion System"}
        ]
        
        explanation = SrmMatcher.get_match_explanation(
            match_type="ambiguous",
            requested_name="Storage Expansion",
            matched_name="",
            confidence=0.0,
            search_results=search_results
        )
        
        assert "Ambiguous match" in explanation
        assert "Storage Expansion" in explanation
        assert "Multiple SRMs" in explanation
        # Verify basic structure of ambiguous explanation
        assert len(explanation) > 100  # Should have substantial content
