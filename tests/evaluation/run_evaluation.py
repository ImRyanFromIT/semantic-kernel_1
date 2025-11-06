"""
Enhanced Evaluation Script for SRM Chatbot.

This script demonstrates a comprehensive evaluation pipeline using:
1. Built-in Azure AI evaluators (Groundedness, Relevance, Coherence, Fluency)
2. Custom domain-specific evaluators (Rejection/Clarification handling)
3. Composite scoring with configurable weights
4. Results storage and comparison
5. Optional Azure AI Foundry integration (Phase 2 - not yet implemented)

Usage:
    # Basic run
    python tests/evaluation/run_evaluation.py

    # Save results with a name
    python tests/evaluation/run_evaluation.py --save-results --run-name "baseline-v1"

    # Use specific dataset
    python tests/evaluation/run_evaluation.py --dataset datasets/qa_golden_set.jsonl

    # Limit test cases for quick testing
    python tests/evaluation/run_evaluation.py --limit 10
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.evaluation.harness.chatbot_wrapper import ChatbotWrapper
from tests.evaluation.evaluators.composite_evaluator import CompositeEvaluator
from tests.evaluation.utils.results_manager import ResultsManager


async def load_dataset(dataset_path: str, limit: int = None) -> list[dict]:
    """
    Load test cases from JSONL file.

    Args:
        dataset_path: Path to JSONL dataset file
        limit: Optional limit on number of test cases to load

    Returns:
        List of test case dictionaries
    """
    test_cases = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                test_cases.append(json.loads(line))
                if limit and len(test_cases) >= limit:
                    break
    return test_cases


async def run_chatbot_on_dataset(
    chatbot: ChatbotWrapper,
    test_cases: list[dict],
) -> list[dict]:
    """
    Run chatbot on all test cases.

    Args:
        chatbot: ChatbotWrapper instance
        test_cases: List of test cases

    Returns:
        List of results with query, response, and context
    """
    results = []
    total = len(test_cases)

    print("\n" + "=" * 80)
    print("RUNNING CHATBOT ON TEST CASES")
    print("=" * 80)

    for i, test_case in enumerate(test_cases, 1):
        query = test_case['query']
        print(f"\n[{i}/{total}] Query: {query[:70]}...")

        # Run query and get structured result
        result = await chatbot.query(query)

        # Store complete result with test case metadata
        results.append({
            "query": query,
            "response": result["response"],
            "context": result["context"],
            "metadata": result["metadata"],
            "expected_behavior": test_case.get("expected_behavior", "answer"),
            "expected_srm": test_case.get("expected_srm"),
            "ground_truth_context": test_case.get("ground_truth_context", ""),
        })

        # Show brief preview
        response_preview = result["response"][:100].replace("\n", " ")
        print(f"    Response: {response_preview}...")
        print(f"    Retrieved: {result['metadata']['num_retrieved']} documents")
        print(f"    Time: {result['metadata']['processing_time_ms']}ms")

    print(f"\n[+] Completed {len(results)} queries")
    return results


def evaluate_responses(
    results: list[dict],
    model_config: dict,
) -> dict:
    """
    Evaluate responses using composite evaluator.

    Args:
        results: List of query-response pairs with context
        model_config: Azure OpenAI configuration for evaluators

    Returns:
        Dictionary with aggregate_metrics and detailed_results
    """
    print("\n" + "=" * 80)
    print("EVALUATING RESPONSES")
    print("=" * 80)

    # Initialize composite evaluator
    print("[*] Initializing composite evaluator...")
    composite_eval = CompositeEvaluator(model_config=model_config)

    # Prepare test cases for batch evaluation
    test_cases = [
        {
            "query": r["query"],
            "response": r["response"],
            "context": r["context"],
            "expected_behavior": r["expected_behavior"],
        }
        for r in results
    ]

    # Progress callback
    def progress(current, total):
        print(f"[{current}/{total}] Evaluating test case {current}...")

    # Run batch evaluation
    print(f"\n[*] Evaluating {len(test_cases)} test cases...")
    eval_results = composite_eval.evaluate_batch(
        test_cases,
        progress_callback=progress,
    )

    return eval_results


def print_summary(eval_results: dict, run_name: str = None):
    """
    Print evaluation summary.

    Args:
        eval_results: Evaluation results dictionary
        run_name: Optional run name
    """
    metrics = eval_results["aggregate_metrics"]

    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    if run_name:
        print(f"Run: {run_name}")
    print("=" * 80)

    print(f"\nTest Cases Evaluated: {metrics['num_evaluated']}")

    print("\n" + "-" * 80)
    print("AGGREGATE METRICS")
    print("-" * 80)

    print(f"\n  Composite Score:     {metrics['average_composite_score']:.2f}/5.00")
    print(f"\n  Individual Metrics:")
    print(f"    Groundedness:      {metrics['average_groundedness']:.2f}/5.00")
    print(f"    Relevance:         {metrics['average_relevance']:.2f}/5.00")
    print(f"    Coherence:         {metrics['average_coherence']:.2f}/5.00")
    print(f"    Fluency:           {metrics['average_fluency']:.2f}/5.00")
    print(f"    Behavior Correct:  {metrics['average_behavior_correct']:.3f}/1.00")

    print("\n" + "-" * 80)
    print("METRIC EXPLANATIONS")
    print("-" * 80)
    print("  Groundedness:  Are responses supported by retrieved context?")
    print("  Relevance:     Do responses answer the user's query?")
    print("  Coherence:     Are responses logically structured?")
    print("  Fluency:       Are responses well-written?")
    print("  Behavior:      Did system correctly handle query type?")
    print("                 (reject out-of-scope, clarify vague, answer valid)")

    print("\n" + "=" * 80)


def print_detailed_sample(eval_results: dict, num_samples: int = 3):
    """
    Print a few detailed examples.

    Args:
        eval_results: Evaluation results
        num_samples: Number of samples to show
    """
    detailed = eval_results["detailed_results"]

    if not detailed:
        return

    print("\n" + "=" * 80)
    print(f"DETAILED SAMPLE RESULTS (showing {min(num_samples, len(detailed))} examples)")
    print("=" * 80)

    for i, result in enumerate(detailed[:num_samples], 1):
        metrics = result["metrics"]
        print(f"\n[{i}] Query: {result['query'][:70]}...")
        print(f"    Response: {result['response']}")
        print(f"\n    Scores:")
        print(f"      Composite:     {metrics.get('composite_score', 0):.2f}/5")
        print(f"      Groundedness:  {metrics.get('groundedness', 0):.2f}/5")
        print(f"      Relevance:     {metrics.get('relevance', 0):.2f}/5")
        print(f"      Coherence:     {metrics.get('coherence', 0):.2f}/5")
        print(f"      Fluency:       {metrics.get('fluency', 0):.2f}/5")
        print(f"      Behavior:      {metrics.get('detected_behavior', 'unknown')} "
              f"(expected: {metrics.get('expected_behavior', 'unknown')})")

        if i < num_samples:
            print("\n" + "-" * 80)

    print("\n" + "=" * 80)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive evaluation on SRM chatbot"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="tests/evaluation/datasets/qa_comprehensive_set.jsonl",
        help="Path to test dataset (JSONL file)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of test cases (for quick testing)",
    )
    parser.add_argument(
        "--save-results",
        action="store_true",
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        help="Name for this evaluation run (used in filename if saving)",
    )
    parser.add_argument(
        "--show-samples",
        type=int,
        default=3,
        help="Number of detailed sample results to show (default: 3)",
    )

    args = parser.parse_args()

    print("=" * 80)
    print("COMPREHENSIVE EVALUATION: SRM CHATBOT")
    print("=" * 80)

    # Load environment
    load_dotenv()

    # Validate Azure OpenAI configuration
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")

    if not all([azure_endpoint, azure_api_key, azure_deployment]):
        print("\n[!] ERROR: Missing Azure OpenAI configuration")
        print("Please set the following environment variables:")
        print("  - AZURE_OPENAI_ENDPOINT")
        print("  - AZURE_OPENAI_API_KEY")
        print("  - AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
        sys.exit(1)

    model_config = {
        "azure_endpoint": azure_endpoint,
        "api_key": azure_api_key,
        "azure_deployment": azure_deployment,
    }

    # Load dataset
    dataset_path = args.dataset
    print(f"\n[*] Loading dataset: {dataset_path}")

    if not Path(dataset_path).exists():
        print(f"[!] ERROR: Dataset not found: {dataset_path}")
        sys.exit(1)

    test_cases = await load_dataset(dataset_path, limit=args.limit)
    print(f"[+] Loaded {len(test_cases)} test cases")

    if args.limit:
        print(f"    (limited to {args.limit} for testing)")

    # Initialize chatbot
    print("\n[*] Initializing chatbot...")
    chatbot = ChatbotWrapper()
    await chatbot.initialize()

    # Run chatbot on dataset
    results = await run_chatbot_on_dataset(chatbot, test_cases)

    # Evaluate responses
    eval_results = evaluate_responses(results, model_config)

    # Print summary
    print_summary(eval_results, run_name=args.run_name)

    # Print detailed samples
    if args.show_samples > 0:
        print_detailed_sample(eval_results, num_samples=args.show_samples)

    # Save results if requested
    if args.save_results:
        print("\n" + "=" * 80)
        print("SAVING RESULTS")
        print("=" * 80)

        results_manager = ResultsManager()
        results_path = results_manager.save_results(
            aggregate_metrics=eval_results["aggregate_metrics"],
            detailed_results=eval_results["detailed_results"],
            run_name=args.run_name,
            dataset_name=Path(dataset_path).name,
            config={
                "model_config": {
                    "azure_endpoint": azure_endpoint,
                    "azure_deployment": azure_deployment,
                },
                "dataset": dataset_path,
                "num_test_cases": len(test_cases),
            },
        )

        print(f"\n[+] Results saved!")
        print(f"\nTo compare with another run:")
        print(f"  python tests/evaluation/compare_runs.py \\")
        print(f"    --baseline {results_path} \\")
        print(f"    --current <path-to-other-run>")

    print("\n[+] Evaluation complete!")


if __name__ == "__main__":
    asyncio.run(main())
