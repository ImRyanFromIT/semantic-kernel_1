"""
QA Evaluator for Question-Answering Quality Assessment.

This evaluator focuses on three core metrics:
- Relevance (40%): Does the response answer the user's question?
- Groundedness (40%): Is the response supported by retrieved context?
- Coherence (20%): Is the response well-structured and logical?

Plus answer correctness: Does the recommended SRM match the expected SRM?
"""

import logging
import re
from typing import Dict, List, Optional
from .builtin_evaluators import BuiltInEvaluators

logger = logging.getLogger(__name__)


class QAEvaluator:
    """
    Question-Answering evaluator with focused metrics and correctness checking.

    This evaluator measures response quality through relevance, groundedness,
    and coherence, then validates whether the correct SRM was recommended.
    """

    DEFAULT_WEIGHTS = {
        "relevance": 0.40,      # 40% - Does response answer the query?
        "groundedness": 0.40,   # 40% - Is response supported by context?
        "coherence": 0.20,      # 20% - Is response well-structured?
    }

    def __init__(
        self,
        model_config: Dict[str, str],
        weights: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize QA evaluator.

        Args:
            model_config: Azure OpenAI configuration for LLM evaluators
            weights: Optional custom weights for metrics (must sum to 1.0)
        """
        self.builtin_evaluators = BuiltInEvaluators(model_config)

        # Set weights
        self.weights = weights if weights else self.DEFAULT_WEIGHTS.copy()

        # Validate weights
        weight_sum = sum(self.weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            logger.warning(
                f"Weights sum to {weight_sum}, not 1.0. Normalizing..."
            )
            self.weights = {k: v / weight_sum for k, v in self.weights.items()}

        logger.info(f"QAEvaluator initialized with weights: {self.weights}")

    def _extract_srm_from_response(self, response: str) -> Optional[str]:
        """
        Extract SRM ID from response using regex pattern matching.

        Args:
            response: Chatbot's response text

        Returns:
            SRM ID (e.g., "SRM-013") or None if not found
        """
        # Pattern: SRM-XXX where XXX is 3 digits
        pattern = r'SRM-\d{3}'
        match = re.search(pattern, response)
        return match.group(0) if match else None

    def _evaluate_correctness(
        self, response: str, expected_srm: str
    ) -> Dict:
        """
        Evaluate if the response recommends the correct SRM.

        Args:
            response: Chatbot's response
            expected_srm: Expected SRM ID from dataset (e.g., "SRM-013")

        Returns:
            Dictionary with:
            - is_correct: bool
            - recommended_srm: str or None
            - expected_srm: str
            - reasoning: str
        """
        recommended_srm = self._extract_srm_from_response(response)

        if recommended_srm == expected_srm:
            return {
                "is_correct": True,
                "recommended_srm": recommended_srm,
                "expected_srm": expected_srm,
                "reasoning": f"Correctly recommended {expected_srm}",
            }
        elif recommended_srm is None:
            return {
                "is_correct": False,
                "recommended_srm": None,
                "expected_srm": expected_srm,
                "reasoning": f"No SRM recommended (expected {expected_srm})",
            }
        else:
            return {
                "is_correct": False,
                "recommended_srm": recommended_srm,
                "expected_srm": expected_srm,
                "reasoning": f"Recommended {recommended_srm} instead of expected {expected_srm}",
            }

    def evaluate(
        self,
        query: str,
        response: str,
        context: List[str],
        expected_srm: str,
    ) -> Dict:
        """
        Run complete QA evaluation with all metrics and correctness check.

        Args:
            query: User's question
            response: Chatbot's answer
            context: Retrieved documents/SRMs
            expected_srm: Expected SRM ID from dataset

        Returns:
            Dictionary with:
            - query: User's original question
            - Individual metric scores (relevance, groundedness, coherence)
            - weighted_average: Weighted average of the three metrics
            - is_correct: Whether the correct SRM was recommended
            - recommended_srm: SRM extracted from response
            - expected_srm: Expected SRM from dataset
            - correctness_reasoning: Explanation of correctness evaluation
        """
        logger.info(f"Evaluating query: {query[:50]}...")

        # Evaluate quality metrics
        relevance_result = self.builtin_evaluators.evaluate_relevance(
            query, response, context
        )
        groundedness_result = self.builtin_evaluators.evaluate_groundedness(
            query, response, context
        )
        coherence_result = self.builtin_evaluators.evaluate_coherence(
            query, response
        )

        # Extract scores
        relevance_score = relevance_result.get("relevance", 0)
        groundedness_score = groundedness_result.get("groundedness", 0)
        coherence_score = coherence_result.get("coherence", 0)

        # Calculate weighted average
        weighted_avg = (
            relevance_score * self.weights["relevance"]
            + groundedness_score * self.weights["groundedness"]
            + coherence_score * self.weights["coherence"]
        )

        # Evaluate correctness
        correctness_result = self._evaluate_correctness(response, expected_srm)

        # Build complete result
        result = {
            # Input query
            "query": query,
            # Individual scores
            "relevance": relevance_score,
            "groundedness": groundedness_score,
            "coherence": coherence_score,
            # Weighted average
            "weighted_average": weighted_avg,
            # Correctness
            "is_correct": correctness_result["is_correct"],
            "recommended_srm": correctness_result["recommended_srm"],
            "expected_srm": correctness_result["expected_srm"],
            "correctness_reasoning": correctness_result["reasoning"],
        }

        logger.info(
            f"Evaluation complete: avg={weighted_avg:.2f}, correct={result['is_correct']}"
        )

        return result

    def evaluate_batch(self, test_cases: List[Dict]) -> Dict:
        """
        Evaluate a batch of test cases.

        Args:
            test_cases: List of test cases, each containing:
                - query: str
                - response: str
                - context: List[str]
                - expected_srm: str

        Returns:
            Dictionary with:
            - total: Total number of test cases
            - correct_count: Number of correct SRM recommendations
            - incorrect_count: Number of incorrect SRM recommendations
            - accuracy: Percentage of correct recommendations
            - avg_relevance: Average relevance score
            - avg_groundedness: Average groundedness score
            - avg_coherence: Average coherence score
            - avg_weighted: Average weighted score
            - individual_results: List of individual evaluation results
        """
        logger.info(f"Starting batch evaluation of {len(test_cases)} test cases")

        individual_results = []
        correct_count = 0

        # Accumulate scores for averaging
        total_relevance = 0.0
        total_groundedness = 0.0
        total_coherence = 0.0
        total_weighted = 0.0

        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"Evaluating test case {i}/{len(test_cases)}")

            result = self.evaluate(
                query=test_case["query"],
                response=test_case["response"],
                context=test_case["context"],
                expected_srm=test_case["expected_srm"],
            )

            individual_results.append(result)

            # Track correctness
            if result["is_correct"]:
                correct_count += 1

            # Accumulate scores
            total_relevance += result["relevance"]
            total_groundedness += result["groundedness"]
            total_coherence += result["coherence"]
            total_weighted += result["weighted_average"]

        total = len(test_cases)
        incorrect_count = total - correct_count
        accuracy = (correct_count / total * 100) if total > 0 else 0

        # Calculate averages
        avg_relevance = total_relevance / total if total > 0 else 0
        avg_groundedness = total_groundedness / total if total > 0 else 0
        avg_coherence = total_coherence / total if total > 0 else 0
        avg_weighted = total_weighted / total if total > 0 else 0

        batch_results = {
            "total": total,
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "accuracy": accuracy,
            "avg_relevance": avg_relevance,
            "avg_groundedness": avg_groundedness,
            "avg_coherence": avg_coherence,
            "avg_weighted": avg_weighted,
            "individual_results": individual_results,
        }

        logger.info(
            f"Batch evaluation complete: {correct_count}/{total} correct "
            f"({accuracy:.1f}%), avg_score={avg_weighted:.2f}"
        )

        return batch_results
