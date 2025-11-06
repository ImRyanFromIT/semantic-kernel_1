"""
Built-in Azure AI Evaluators.

This module wraps Azure AI Evaluation SDK's built-in evaluators:
- GroundednessEvaluator: Measures if response is grounded in provided context
- RelevanceEvaluator: Measures if response answers the query
- CoherenceEvaluator: Measures logical flow and structure
- FluencyEvaluator: Measures language quality and readability

Each evaluator uses an LLM to score responses on a scale (typically 1-5).
"""

import logging
from typing import Dict, List, Optional
from azure.ai.evaluation import (
    GroundednessEvaluator,
    RelevanceEvaluator,
    CoherenceEvaluator,
    FluencyEvaluator,
)

logger = logging.getLogger(__name__)


class BuiltInEvaluators:
    """
    Wrapper for Azure AI Evaluation SDK built-in evaluators.

    This class initializes and manages the four core quality evaluators.
    """

    def __init__(self, model_config: Dict[str, str]):
        """
        Initialize built-in evaluators.

        Args:
            model_config: Configuration for Azure OpenAI including:
                - azure_endpoint: Azure OpenAI endpoint URL
                - api_key: Azure OpenAI API key
                - azure_deployment: Deployment name for chat model
        """
        self.model_config = model_config

        logger.info("Initializing built-in evaluators")

        # Initialize evaluators
        try:
            self.groundedness_eval = GroundednessEvaluator(model_config=model_config)
            self.relevance_eval = RelevanceEvaluator(model_config=model_config)
            self.coherence_eval = CoherenceEvaluator(model_config=model_config)
            self.fluency_eval = FluencyEvaluator(model_config=model_config)
            logger.info("Built-in evaluators initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize evaluators: {e}")
            raise

    def evaluate_groundedness(
        self, query: str, response: str, context: List[str]
    ) -> Dict:
        """
        Evaluate if the response is grounded in the provided context.

        Groundedness measures whether the claims made in the response
        are supported by the retrieved context documents.

        Args:
            query: User's question
            response: Chatbot's answer
            context: Retrieved documents/SRMs

        Returns:
            Dictionary with score and reasoning
        """
        if not context:
            # No context provided - can't evaluate groundedness
            return {
                "groundedness": 0,
                "reasoning": "No context provided for groundedness evaluation",
            }

        try:
            result = self.groundedness_eval(
                query=query, response=response, context="\n\n".join(context)
            )
            return {
                "groundedness": result.get("groundedness", result.get("score", 0)),
                "reasoning": result.get("reasoning", ""),
            }
        except Exception as e:
            logger.error(f"Groundedness evaluation failed: {e}")
            return {"groundedness": 0, "error": str(e)}

    def evaluate_relevance(self, query: str, response: str, context: Optional[List[str]] = None) -> Dict:
        """
        Evaluate if the response answers the user's query.

        Relevance measures whether the response addresses what the user
        asked for, regardless of whether it's grounded in context.

        Args:
            query: User's question
            response: Chatbot's answer
            context: Optional retrieved documents (some evaluators use this)

        Returns:
            Dictionary with score and reasoning
        """
        try:
            # RelevanceEvaluator can optionally use context
            eval_input = {"query": query, "response": response}
            if context:
                eval_input["context"] = "\n\n".join(context)

            result = self.relevance_eval(**eval_input)
            return {
                "relevance": result.get("relevance", result.get("score", 0)),
                "reasoning": result.get("reasoning", ""),
            }
        except Exception as e:
            logger.error(f"Relevance evaluation failed: {e}")
            return {"relevance": 0, "error": str(e)}

    def evaluate_coherence(self, query: str, response: str) -> Dict:
        """
        Evaluate the logical structure and flow of the response.

        Coherence measures whether the response is well-organized,
        logically structured, and easy to follow.

        Args:
            query: User's question
            response: Chatbot's answer

        Returns:
            Dictionary with score and reasoning
        """
        try:
            result = self.coherence_eval(query=query, response=response)
            return {
                "coherence": result.get("coherence", result.get("score", 0)),
                "reasoning": result.get("reasoning", ""),
            }
        except Exception as e:
            logger.error(f"Coherence evaluation failed: {e}")
            return {"coherence": 0, "error": str(e)}

    def evaluate_fluency(self, query: str, response: str) -> Dict:
        """
        Evaluate the language quality and readability of the response.

        Fluency measures grammar, spelling, word choice, and overall
        readability of the response.

        Args:
            query: User's question
            response: Chatbot's answer

        Returns:
            Dictionary with score and reasoning
        """
        try:
            result = self.fluency_eval(query=query, response=response)
            return {
                "fluency": result.get("fluency", result.get("score", 0)),
                "reasoning": result.get("reasoning", ""),
            }
        except Exception as e:
            logger.error(f"Fluency evaluation failed: {e}")
            return {"fluency": 0, "error": str(e)}

    def evaluate_all(
        self, query: str, response: str, context: List[str]
    ) -> Dict:
        """
        Run all built-in evaluators and return combined results.

        Args:
            query: User's question
            response: Chatbot's answer
            context: Retrieved documents/SRMs

        Returns:
            Dictionary with all evaluation scores
        """
        results = {}

        # Groundedness (requires context)
        groundedness_result = self.evaluate_groundedness(query, response, context)
        results["groundedness"] = groundedness_result.get("groundedness", 0)
        results["groundedness_reasoning"] = groundedness_result.get("reasoning", "")
        if "error" in groundedness_result:
            results["groundedness_error"] = groundedness_result["error"]

        # Relevance
        relevance_result = self.evaluate_relevance(query, response, context)
        results["relevance"] = relevance_result.get("relevance", 0)
        results["relevance_reasoning"] = relevance_result.get("reasoning", "")
        if "error" in relevance_result:
            results["relevance_error"] = relevance_result["error"]

        # Coherence
        coherence_result = self.evaluate_coherence(query, response)
        results["coherence"] = coherence_result.get("coherence", 0)
        results["coherence_reasoning"] = coherence_result.get("reasoning", "")
        if "error" in coherence_result:
            results["coherence_error"] = coherence_result["error"]

        # Fluency
        fluency_result = self.evaluate_fluency(query, response)
        results["fluency"] = fluency_result.get("fluency", 0)
        results["fluency_reasoning"] = fluency_result.get("reasoning", "")
        if "error" in fluency_result:
            results["fluency_error"] = fluency_result["error"]

        return results
