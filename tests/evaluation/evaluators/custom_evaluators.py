"""
Custom Domain-Specific Evaluators.

This module contains custom evaluators specific to the SRM chatbot domain:
- RejectionClarificationEvaluator: Validates correct handling of out-of-scope
  and unclear queries
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class RejectionClarificationEvaluator:
    """
    Evaluator for rejection and clarification handling.

    This evaluator checks if the system correctly:
    1. Rejects out-of-scope queries (should have [!] prefix)
    2. Asks for clarification on vague queries (should have [?] prefix)
    3. Provides proper answers for in-scope queries

    This is a rule-based evaluator using simple pattern matching.
    """

    def evaluate(
        self, query: str, response: str, expected_behavior: str
    ) -> Dict:
        """
        Evaluate if the response matches expected behavior.

        Args:
            query: User's question
            response: Chatbot's answer
            expected_behavior: One of "answer", "reject", "clarify"

        Returns:
            Dictionary with:
            - behavior_correct: 1 if correct, 0 if incorrect
            - detected_behavior: What behavior was detected
            - expected_behavior: What was expected
            - reasoning: Explanation of the evaluation
        """
        # Detect actual behavior from response
        detected_behavior = self._detect_behavior(response)

        # Check if it matches expectation
        is_correct = detected_behavior == expected_behavior

        # Build reasoning
        reasoning = self._build_reasoning(
            query, detected_behavior, expected_behavior, is_correct
        )

        return {
            "behavior_correct": 1 if is_correct else 0,
            "detected_behavior": detected_behavior,
            "expected_behavior": expected_behavior,
            "reasoning": reasoning,
        }

    def _detect_behavior(self, response: str) -> str:
        """
        Detect the behavior from response patterns.

        Args:
            response: Chatbot's response

        Returns:
            One of "reject", "clarify", "answer", "unknown"
        """
        response_lower = response.strip()[:50].lower()  # Check first 50 chars

        # Check for rejection patterns
        if response.startswith("[!]"):
            return "reject"

        # Check for clarification patterns
        if response.startswith("[?]"):
            return "clarify"

        # Check for common rejection phrases
        rejection_phrases = [
            "cannot help with",
            "not able to assist",
            "outside my scope",
            "can't help with",
            "out of scope",
        ]
        if any(phrase in response_lower for phrase in rejection_phrases):
            return "reject"

        # Check for clarification phrases
        clarification_phrases = [
            "can you provide more",
            "could you clarify",
            "can you be more specific",
            "need more information",
            "what specifically",
        ]
        if any(phrase in response_lower for phrase in clarification_phrases):
            return "clarify"

        # Check if it's a proper answer (has SRM-related content)
        if "srm" in response_lower or "recommended" in response_lower:
            return "answer"

        # Unknown behavior
        return "unknown"

    def _build_reasoning(
        self,
        query: str,
        detected: str,
        expected: str,
        is_correct: bool,
    ) -> str:
        """
        Build human-readable reasoning for the evaluation.

        Args:
            query: User's question
            detected: Detected behavior
            expected: Expected behavior
            is_correct: Whether detection matches expectation

        Returns:
            Reasoning string
        """
        if is_correct:
            if expected == "reject":
                return (
                    f"✓ Correctly rejected out-of-scope query. "
                    f"The system recognized '{query[:50]}...' is not within its domain."
                )
            elif expected == "clarify":
                return (
                    f"✓ Correctly requested clarification. "
                    f"The query '{query[:50]}...' was too vague and needs more detail."
                )
            elif expected == "answer":
                return (
                    f"✓ Correctly provided an answer. "
                    f"The query was in-scope and received a proper SRM recommendation."
                )
            else:
                return f"✓ Behavior matched expectation: {expected}"
        else:
            return (
                f"✗ Behavior mismatch! Expected '{expected}' but detected '{detected}'. "
                f"Query: '{query[:50]}...'"
            )

    def evaluate_batch(self, test_cases: list[Dict]) -> Dict:
        """
        Evaluate a batch of test cases.

        Args:
            test_cases: List of test cases, each containing:
                - query: str
                - response: str
                - expected_behavior: str

        Returns:
            Dictionary with:
            - total: Total test cases
            - correct: Number of correct behaviors
            - incorrect: Number of incorrect behaviors
            - accuracy: Accuracy percentage
            - detailed_results: List of individual results
        """
        results = []
        correct_count = 0

        for test_case in test_cases:
            result = self.evaluate(
                query=test_case["query"],
                response=test_case["response"],
                expected_behavior=test_case["expected_behavior"],
            )

            results.append({
                "query": test_case["query"],
                "expected": test_case["expected_behavior"],
                "detected": result["detected_behavior"],
                "correct": result["behavior_correct"] == 1,
                "reasoning": result["reasoning"],
            })

            if result["behavior_correct"] == 1:
                correct_count += 1

        total = len(test_cases)
        accuracy = (correct_count / total * 100) if total > 0 else 0

        return {
            "total": total,
            "correct": correct_count,
            "incorrect": total - correct_count,
            "accuracy": accuracy,
            "detailed_results": results,
        }
