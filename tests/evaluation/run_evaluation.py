"""
Minimal Example: Azure AI Evaluation for SRM Chatbot

This script demonstrates how to:
1. Load a golden dataset (JSONL)
2. Run queries through the chatbot
3. Evaluate responses using Azure AI Evaluation SDK
4. Report metrics

Usage:
    python tests/evaluation/run_evaluation.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from azure.ai.evaluation import RelevanceEvaluator
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential

from tests.evaluation.harness.chatbot_wrapper import ChatbotWrapper


async def load_dataset(dataset_path: str) -> list[dict]:
    """
    Load test cases from JSONL file.

    Args:
        dataset_path: Path to JSONL dataset file

    Returns:
        List of test case dictionaries
    """
    test_cases = []
    with open(dataset_path, 'r') as f:
        for line in f:
            test_cases.append(json.loads(line))
    return test_cases


async def run_chatbot_on_dataset(chatbot: ChatbotWrapper, test_cases: list[dict]) -> list[dict]:
    """
    Run chatbot on all test cases.

    Args:
        chatbot: ChatbotWrapper instance
        test_cases: List of test cases

    Returns:
        List of results with query and response
    """
    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] Running query: {test_case['query']}")

        # Run query
        response = await chatbot.query(test_case['query'])

        # Store result
        result = {
            "query": test_case['query'],
            "response": response,
            "expected_context": test_case.get('expected_context', ''),
            "notes": test_case.get('notes', ''),
        }
        results.append(result)

        print(f"    Response: {response[:100]}...")

    return results


def evaluate_responses(results: list[dict]) -> dict:
    """
    Evaluate responses using Azure AI Evaluation SDK.

    Args:
        results: List of query-response pairs

    Returns:
        Evaluation metrics
    """
    print("\n" + "=" * 80)
    print("EVALUATING RESPONSES")
    print("=" * 80)

    # Load Azure OpenAI configuration
    load_dotenv()
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")

    if not all([azure_endpoint, azure_api_key, azure_deployment]):
        raise ValueError(
            "Missing Azure OpenAI configuration. Please set:\n"
            "  - AZURE_OPENAI_ENDPOINT\n"
            "  - AZURE_OPENAI_API_KEY\n"
            "  - AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"
        )

    # Create evaluator
    print(f"[*] Creating RelevanceEvaluator with deployment: {azure_deployment}")

    model_config = {
        "azure_endpoint": azure_endpoint,
        "api_key": azure_api_key,
        "azure_deployment": azure_deployment,
    }

    relevance_eval = RelevanceEvaluator(model_config=model_config)

    # Evaluate each response
    scores = []
    detailed_results = []

    for i, result in enumerate(results, 1):
        print(f"\n[{i}/{len(results)}] Evaluating response for: {result['query'][:50]}...")

        try:
            # Prepare data for evaluator
            # RelevanceEvaluator expects: query, response, context (optional)
            eval_input = {
                "query": result['query'],
                "response": result['response'],
                # We don't have actual context for now, using expected_context as guidance
            }

            # Run evaluation
            score_result = relevance_eval(**eval_input)

            # Extract score
            relevance_score = score_result.get('relevance', score_result.get('score', 0))

            scores.append(relevance_score)

            detailed_result = {
                "query": result['query'],
                "response": result['response'],
                "relevance_score": relevance_score,
                "expected_context": result['expected_context'],
                "notes": result['notes'],
            }
            detailed_results.append(detailed_result)

            print(f"    Relevance Score: {relevance_score}")

        except Exception as e:
            print(f"    [!] Evaluation error: {e}")
            scores.append(0)

    # Calculate aggregate metrics
    avg_relevance = sum(scores) / len(scores) if scores else 0

    metrics = {
        "average_relevance": avg_relevance,
        "num_evaluated": len(scores),
        "detailed_results": detailed_results,
    }

    return metrics


def print_summary(metrics: dict):
    """
    Print evaluation summary.

    Args:
        metrics: Evaluation metrics dictionary
    """
    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)

    print(f"\nTest Cases Evaluated: {metrics['num_evaluated']}")
    print(f"Average Relevance Score: {metrics['average_relevance']:.2f}")

    print("\n" + "-" * 80)
    print("DETAILED RESULTS")
    print("-" * 80)

    for i, result in enumerate(metrics['detailed_results'], 1):
        print(f"\n[{i}] Query: {result['query']}")
        print(f"    Response: {result['response'][:150]}...")
        print(f"    Relevance Score: {result['relevance_score']}")
        print(f"    Expected Context: {result['expected_context']}")

    print("\n" + "=" * 80)


async def main():
    """Main entry point."""
    print("=" * 80)
    print("MINIMAL EVALUATION EXAMPLE: SRM CHATBOT")
    print("=" * 80)

    # Paths
    dataset_path = "tests/evaluation/datasets/qa_golden_set.jsonl"

    # Load dataset
    print(f"\n[*] Loading dataset: {dataset_path}")
    test_cases = await load_dataset(dataset_path)
    print(f"[+] Loaded {len(test_cases)} test cases")

    # Initialize chatbot
    print("\n[*] Initializing chatbot...")
    chatbot = ChatbotWrapper()
    await chatbot.initialize()

    # Run chatbot on dataset
    print("\n[*] Running chatbot on test cases...")
    results = await run_chatbot_on_dataset(chatbot, test_cases)
    print(f"[+] Completed {len(results)} queries")

    # Evaluate responses
    metrics = evaluate_responses(results)

    # Print summary
    print_summary(metrics)

    print("\n[+] Evaluation complete!")


if __name__ == "__main__":
    asyncio.run(main())
