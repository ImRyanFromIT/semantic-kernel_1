"""
SRM matching utilities for intelligent search result selection.

Implements exact and fuzzy matching logic to safely identify SRMs.
"""

from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher


class SrmMatcher:
    """
    Intelligent SRM matching to prevent incorrect updates.
    
    Matching strategy:
    1. Exact match (case-insensitive) - confidence 100%
    2. Very close fuzzy match (>90% similarity) - confidence 95%
    3. Close fuzzy match (80-90% similarity) - confidence 80%
    4. Multiple ambiguous matches - escalate
    5. No good match (<80% similarity) - escalate
    """
    
    # Thresholds
    EXACT_MATCH_THRESHOLD = 0.99  # Essentially exact
    HIGH_CONFIDENCE_THRESHOLD = 0.90  # Very close match
    MEDIUM_CONFIDENCE_THRESHOLD = 0.80  # Decent match but verify
    
    # Common suffixes to strip during normalization
    COMMON_SUFFIXES = ["SRM", "Service", "Request", "SR"]
    
    @staticmethod
    def normalize_srm_name(name: str) -> str:
        """
        Normalize SRM name by removing common suffixes.
        
        LLMs often add "SRM" or "Service" to the end of SRM names.
        This helps improve matching accuracy.
        
        Args:
            name: SRM name to normalize
            
        Returns:
            Normalized name with common suffixes removed
        """
        normalized = name.strip()
        
        # Remove common suffixes (case-insensitive)
        for suffix in SrmMatcher.COMMON_SUFFIXES:
            # Check if name ends with the suffix (as a separate word)
            if normalized.lower().endswith(f" {suffix.lower()}"):
                normalized = normalized[:-(len(suffix) + 1)].strip()
                break  # Only remove one suffix
        
        return normalized
    
    @staticmethod
    def calculate_similarity(str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Normalize: lowercase and strip whitespace
        s1 = str1.lower().strip()
        s2 = str2.lower().strip()
        
        # Use SequenceMatcher for fuzzy matching
        return SequenceMatcher(None, s1, s2).ratio()
    
    @classmethod
    def find_best_match(
        cls, 
        requested_name: str, 
        search_results: List[Dict[str, Any]],
        name_field: str = "Name"
    ) -> Tuple[Optional[Dict[str, Any]], str, float]:
        """
        Find the best matching SRM from search results.
        
        Args:
            requested_name: SRM name requested by user
            search_results: List of search results from Azure Search
            name_field: Field name containing the SRM name
            
        Returns:
            Tuple of (matched_srm, match_type, confidence_score)
            - matched_srm: Best matching result or None
            - match_type: "exact", "high_confidence", "medium_confidence", "ambiguous", "no_match"
            - confidence_score: Similarity score 0.0-1.0
        """
        if not search_results:
            return None, "no_match", 0.0
        
        # Normalize the requested name (remove common suffixes like "SRM")
        normalized_requested = cls.normalize_srm_name(requested_name)
        
        # Calculate similarity for each result
        matches = []
        for result in search_results:
            srm_name = result.get(name_field, "")
            if not srm_name:
                continue
            
            # Try matching with both original and normalized names
            # Use the better of the two scores
            similarity_original = cls.calculate_similarity(requested_name, srm_name)
            similarity_normalized = cls.calculate_similarity(normalized_requested, srm_name)
            similarity = max(similarity_original, similarity_normalized)
            
            matches.append({
                "result": result,
                "similarity": similarity,
                "name": srm_name
            })
        
        if not matches:
            return None, "no_match", 0.0
        
        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        
        best_match = matches[0]
        best_similarity = best_match["similarity"]
        
        # Check for exact match
        if best_similarity >= cls.EXACT_MATCH_THRESHOLD:
            return best_match["result"], "exact", best_similarity
        
        # Check for high confidence match
        if best_similarity >= cls.HIGH_CONFIDENCE_THRESHOLD:
            # Make sure there's not another very similar match (ambiguity)
            if len(matches) > 1 and matches[1]["similarity"] >= cls.HIGH_CONFIDENCE_THRESHOLD:
                # Multiple high-confidence matches - ambiguous
                return None, "ambiguous", best_similarity
            
            return best_match["result"], "high_confidence", best_similarity
        
        # Check for medium confidence match
        if best_similarity >= cls.MEDIUM_CONFIDENCE_THRESHOLD:
            # Make sure there's not another close match (ambiguity)
            if len(matches) > 1 and matches[1]["similarity"] >= cls.MEDIUM_CONFIDENCE_THRESHOLD:
                # Multiple medium-confidence matches - ambiguous
                return None, "ambiguous", best_similarity
            
            return best_match["result"], "medium_confidence", best_similarity
        
        # No good match
        return None, "no_match", best_similarity
    
    @classmethod
    def get_match_explanation(
        cls,
        match_type: str,
        requested_name: str,
        matched_name: Optional[str],
        confidence: float,
        search_results: List[Dict[str, Any]],
        name_field: str = "Name"
    ) -> str:
        """
        Generate human-readable explanation of the match result.
        
        Args:
            match_type: Type of match found
            requested_name: Name requested by user
            matched_name: Name of matched SRM (if any)
            confidence: Confidence score
            search_results: All search results for context
            name_field: Field containing SRM name
            
        Returns:
            Explanation string
        """
        if match_type == "exact":
            return (
                f"Exact match found for '{requested_name}'\n"
                f"Matched SRM: '{matched_name}' (confidence: {confidence:.1%})"
            )
        
        elif match_type == "high_confidence":
            return (
                f"High-confidence fuzzy match for '{requested_name}'\n"
                f"Matched SRM: '{matched_name}' (confidence: {confidence:.1%})\n"
                f"Note: Names are very similar but not identical. Likely correct match."
            )
        
        elif match_type == "medium_confidence":
            return (
                f"Medium-confidence fuzzy match for '{requested_name}'\n"
                f"Matched SRM: '{matched_name}' (confidence: {confidence:.1%})\n"
                f"WARNING: Names differ somewhat. Verify this is the correct SRM."
            )
        
        elif match_type == "ambiguous":
            # List the ambiguous matches
            top_matches = []
            for result in search_results[:3]:
                name = result.get(name_field, "")
                similarity = cls.calculate_similarity(requested_name, name)
                if similarity >= cls.MEDIUM_CONFIDENCE_THRESHOLD:
                    top_matches.append(f"  - {name} ({similarity:.1%} match)")
            
            return (
                f"Ambiguous match for '{requested_name}'\n"
                f"Multiple SRMs have similar names:\n" +
                "\n".join(top_matches) +
                "\n\nCannot determine which SRM to update. Please specify more precisely."
            )
        
        else:  # no_match
            # Show what we found
            if search_results:
                top_results = [
                    f"  - {result.get(name_field, 'Unknown')} ({cls.calculate_similarity(requested_name, result.get(name_field, '')):.1%} match)"
                    for result in search_results[:3]
                ]
                return (
                    f"No matching SRM found for '{requested_name}'\n"
                    f"Closest matches from search:\n" +
                    "\n".join(top_results) +
                    f"\n\nHighest similarity: {confidence:.1%} (threshold: {cls.MEDIUM_CONFIDENCE_THRESHOLD:.1%})"
                )
            else:
                return f"No SRM found matching '{requested_name}'. No search results returned."
    
    @classmethod
    def should_proceed_with_update(cls, match_type: str) -> bool:
        """
        Determine if we should proceed with update based on match type.
        
        Args:
            match_type: Type of match found
            
        Returns:
            True if safe to proceed, False if should escalate
        """
        # Only proceed with exact or high-confidence matches
        return match_type in ["exact", "high_confidence"]

