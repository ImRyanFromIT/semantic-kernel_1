"""
Composite Evaluator.

This module combines multiple evaluators into a single composite score
with configurable weights for each metric.
"""

import logging
from typing import Dict, List
from .builtin_evaluators import BuiltInEvaluators
from .custom_evaluators import RejectionClarificationEvaluator

logger = logging.getLogger(__name__)


class CompositeEvaluator:
    """
    Composite evaluator that combines multiple metrics.

    This evaluator runs all built-in and custom evaluators, then combines
    their scores into a single composite quality score using configurable weights.
    """

    DEFAULT_WEIGHTS = {
        "groundedness": 0.30,  # 30% - Is response supported by context?
        "relevance": 0.30,  # 30% - Does response answer the query?
        "coherence": 0.15,  # 15% - Is response well-structured?
        "fluency": 0.10,  # 10% - Is response well-written?
        "behavior_correct": 0.15,  # 15% - Did system behave correctly?
    }

    def __init__(
        self,
        model_config: Dict[str, str],
        weights: Dict[str, float] = None,
    ):
        """
        Initialize composite evaluator.

        Args:
            model_config: Azure OpenAI configuration for LLM evaluators
            weights: Optional custom weights for each metric (must sum to 1.0)
        """
        self.builtin_evaluators = BuiltInEvaluators(model_config)
        self.rejection_clarification_eval = RejectionClarificationEvaluator()

        # Set weights
        self.weights = weights if weights else self.DEFAULT_WEIGHTS

        # Validate weights
        weight_sum = sum(self.weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            logger.warning(
                f"Weights sum to {weight_sum}, not 1.0. Normalizing..."
            )
            # Normalize weights
            self.weights = {k: v / weight_sum for k, v in self.weights.items()}

        logger.info(f"CompositeEvaluator initialized with weights: {self.weights}")

    def evaluate(
        self,
        query: str,
        response: str,
        context: List[str],
        expected_behavior: str = "answer",
    ) -> Dict:
        """
        Run all evaluators and compute composite score.

        Args:
            query: User's question
            response: Chatbot's answer
            context: Retrieved documents/SRMs
            expected_behavior: Expected system behavior ("answer", "reject", "clarify")

        Returns:
            Dictionary with:
            - Individual metric scores
            - Composite score (0-5 scale to match Azure AI evaluators)
            - Detailed results from each evaluator
        """
        results = {}

        # Run built-in evaluators
        logger.info(f"Evaluating query: {query[:50]}...")
        builtin_results = self.builtin_evaluators.evaluate_all(
            query, response, context
        )
        results.update(builtin_results)

        # Run custom behavior evaluator
        behavior_result = self.rejection_clarification_eval.evaluate(
            query, response, expected_behavior
        )
        results["behavior_correct"] = behavior_result["behavior_correct"]
        results["detected_behavior"] = behavior_result["detected_behavior"]
        results["expected_behavior"] = behavior_result["expected_behavior"]
        results["behavior_reasoning"] = behavior_result["reasoning"]

        # Compute composite score
        # Normalize all scores to 0-1 range (Azure evaluators typically use 1-5 scale)
        normalized_scores = {
            "groundedness": self._normalize_score(results.get("groundedness", 0)),
            "relevance": self._normalize_score(results.get("relevance", 0)),
            "coherence": self._normalize_score(results.get("coherence", 0)),
            "fluency": self._normalize_score(results.get("fluency", 0)),
            "behavior_correct": results.get("behavior_correct", 0),  # Already 0-1
        }

        # Weighted average
        composite_score = sum(
            normalized_scores[metric] * weight
            for metric, weight in self.weights.items()
        )

        # Scale back to 0-5 to match Azure AI scale
        composite_score_scaled = composite_score * 5

        results["composite_score"] = composite_score_scaled
        results["normalized_scores"] = normalized_scores
        results["weights_used"] = self.weights

        logger.info(f"Composite score: {composite_score_scaled:.2f}/5")

        return results

    def _normalize_score(self, score: float, min_val: float = 1, max_val: float = 5) -> float:
        """
        Normalize a score from Azure AI scale (typically 1-5) to 0-1.

        Args:
            score: Raw score from evaluator
            min_val: Minimum possible score
            max_val: Maximum possible score

        Returns:
            Normalized score (0-1)
        """
        if score <= 0:
            return 0.0
        if score >= max_val:
            return 1.0
        return (score - min_val) / (max_val - min_val)

    def evaluate_batch(
        self,
        test_cases: List[Dict],
        progress_callback=None,
    ) -> Dict:
        """
        Evaluate a batch of test cases.

        Args:
            test_cases: List of test cases, each containing:
                - query: str
                - response: str
                - context: List[str]
                - expected_behavior: str
            progress_callback: Optional callback(current, total) for progress tracking

        Returns:
            Dictionary with:
            - aggregate_metrics: Average scores across all test cases
            - detailed_results: Individual results for each test case
        """
        results = []
        total = len(test_cases)

        # Accumulators for aggregate metrics
        sum_groundedness = 0
        sum_relevance = 0
        sum_coherence = 0
        sum_fluency = 0
        sum_behavior_correct = 0
        sum_composite = 0

        for i, test_case in enumerate(test_cases, 1):
            if progress_callback:
                progress_callback(i, total)

            result = self.evaluate(
                query=test_case["query"],
                response=test_case["response"],
                context=test_case.get("context", []),
                expected_behavior=test_case.get("expected_behavior", "answer"),
            )

            results.append({
                "query": test_case["query"],
                "response": test_case["response"][:100] + "...",  # Truncate for storage
                "metrics": result,
            })

            # Accumulate for averages
            sum_groundedness += result.get("groundedness", 0)
            sum_relevance += result.get("relevance", 0)
            sum_coherence += result.get("coherence", 0)
            sum_fluency += result.get("fluency", 0)
            sum_behavior_correct += result.get("behavior_correct", 0)
            sum_composite += result.get("composite_score", 0)

        # Calculate averages
        aggregate_metrics = {
            "average_groundedness": sum_groundedness / total if total > 0 else 0,
            "average_relevance": sum_relevance / total if total > 0 else 0,
            "average_coherence": sum_coherence / total if total > 0 else 0,
            "average_fluency": sum_fluency / total if total > 0 else 0,
            "average_behavior_correct": sum_behavior_correct / total if total > 0 else 0,
            "average_composite_score": sum_composite / total if total > 0 else 0,
            "num_evaluated": total,
        }

        return {
            "aggregate_metrics": aggregate_metrics,
            "detailed_results": results,
        }
