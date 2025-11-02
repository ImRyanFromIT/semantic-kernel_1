"""
QA Evaluation Script for SRM Chatbot.

This script uses QAEvaluator to measure question-answering quality through:
1. Relevance (40%): Does the response answer the question?
2. Groundedness (40%): Is the response supported by context?
3. Coherence (20%): Is the response well-structured?
4. Correctness: Was the correct SRM recommended?

Usage:
    # Basic run
    python tests/evaluation/run_qa_evaluation.py

    # Save results with a name
    python tests/evaluation/run_qa_evaluation.py --save-results --run-name "qa-baseline-v1"

    # Use specific dataset
    python tests/evaluation/run_qa_evaluation.py --dataset datasets/qa_comprehensive_set.jsonl

    # Limit test cases for quick testing
    python tests/evaluation/run_qa_evaluation.py --limit 10
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
from tests.evaluation.evaluators.qa_evaluator import QAEvaluator
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
    with open(dataset_path, "r") as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            test_cases.append(json.loads(line))
    return test_cases


async def run_evaluation(
    dataset_path: str,
    limit: int = None,
    save_results: bool = False,
    run_name: str = None,
    show_samples: int = 3,
):
    """
    Run QA evaluation on the dataset.

    Args:
        dataset_path: Path to JSONL dataset
        limit: Optional limit on test cases
        save_results: Whether to save results to file
        run_name: Name for this evaluation run
        show_samples: Number of sample results to display
    """
    print("=" * 80)
    print("QA EVALUATION FOR SRM CHATBOT")
    print("=" * 80)
    print()

    # Load environment variables
    load_dotenv()

    # Verify Azure OpenAI configuration
    required_env_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME",
    ]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        print(f"[ERROR] Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set them in your .env file.")
        return

    # Load dataset
    print(f"Loading dataset: {dataset_path}")
    test_cases = await load_dataset(dataset_path, limit)
    print(f"   Loaded {len(test_cases)} test cases")
    if limit:
        print(f"   (Limited to {limit} cases)")
    print()

    # Initialize chatbot wrapper
    print("Initializing chatbot wrapper...")
    chatbot = ChatbotWrapper()
    await chatbot.initialize()
    print()

    # Initialize QA evaluator
    print("Initializing QA evaluator...")
    model_config = {
        "azure_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
        "azure_deployment": os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
    }
    qa_evaluator = QAEvaluator(model_config=model_config)
    print(f"   Weights: Relevance={qa_evaluator.weights['relevance']:.0%}, "
          f"Groundedness={qa_evaluator.weights['groundedness']:.0%}, "
          f"Coherence={qa_evaluator.weights['coherence']:.0%}")
    print()

    # Run chatbot on all queries
    print("Running chatbot on test queries...")
    enriched_test_cases = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"   [{i}/{len(test_cases)}] {test_case['query'][:50]}...")

        chatbot_result = await chatbot.query(test_case["query"])

        enriched_test_cases.append({
            "query": test_case["query"],
            "response": chatbot_result["response"],
            "context": chatbot_result["context"],
            "expected_srm": test_case["expected_srm"],
        })
    print()

    # Run QA evaluation
    print("Running QA evaluation...")
    batch_results = qa_evaluator.evaluate_batch(enriched_test_cases)
    print()

    # Display aggregate results
    print("=" * 80)
    print("AGGREGATE METRICS")
    print("=" * 80)
    print()
    print(f"  Accuracy:             {batch_results['correct_count']}/{batch_results['total']} "
          f"({batch_results['accuracy']:.1f}%)")
    print(f"  Weighted Avg Score:   {batch_results['avg_weighted']:.2f}/5.00")
    print()
    print("  Individual Metrics:")
    print(f"    Relevance:          {batch_results['avg_relevance']:.2f}/5.00")
    print(f"    Groundedness:       {batch_results['avg_groundedness']:.2f}/5.00")
    print(f"    Coherence:          {batch_results['avg_coherence']:.2f}/5.00")
    print()

    # Display sample results
    if show_samples > 0:
        print("=" * 80)
        print(f"SAMPLE RESULTS (showing {show_samples} of {batch_results['total']})")
        print("=" * 80)
        print()

        for i, result in enumerate(batch_results["individual_results"][:show_samples], 1):
            status = "[CORRECT]" if result["is_correct"] else "[INCORRECT]"
            print(f"Sample {i}: {status}")
            print(f"  Query: {enriched_test_cases[i-1]['query'][:60]}...")
            print(f"  Expected: {result['expected_srm']}")
            print(f"  Recommended: {result['recommended_srm']}")
            print(f"  Scores: R={result['relevance']:.1f}, G={result['groundedness']:.1f}, "
                  f"C={result['coherence']:.1f}, Avg={result['weighted_average']:.2f}")
            print(f"  {result['correctness_reasoning']}")
            print()

    # Save results if requested
    if save_results:
        print("=" * 80)
        print("SAVING RESULTS")
        print("=" * 80)
        print()

        results_manager = ResultsManager()

        # Prepare results data
        results_data = {
            "run_name": run_name or "qa_evaluation",
            "dataset": dataset_path,
            "test_cases_count": len(test_cases),
            "metrics": {
                "accuracy": batch_results["accuracy"],
                "correct_count": batch_results["correct_count"],
                "incorrect_count": batch_results["incorrect_count"],
                "avg_weighted": batch_results["avg_weighted"],
                "avg_relevance": batch_results["avg_relevance"],
                "avg_groundedness": batch_results["avg_groundedness"],
                "avg_coherence": batch_results["avg_coherence"],
            },
            "individual_results": batch_results["individual_results"],
        }

        filename = results_manager.save_results(results_data, run_name or "qa_evaluation")
        print(f"Results saved to: {filename}")
        print()

    print("=" * 80)
    print("EVALUATION COMPLETE")
    print("=" * 80)


def main():
    """Parse arguments and run evaluation."""
    parser = argparse.ArgumentParser(
        description="Run QA evaluation on SRM chatbot"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="tests/evaluation/datasets/qa_comprehensive_set.jsonl",
        help="Path to dataset JSONL file",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of test cases (for quick testing)",
    )
    parser.add_argument(
        "--save-results",
        action="store_true",
        help="Save results to file",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Name for this evaluation run",
    )
    parser.add_argument(
        "--show-samples",
        type=int,
        default=3,
        help="Number of sample results to display",
    )

    args = parser.parse_args()

    asyncio.run(
        run_evaluation(
            dataset_path=args.dataset,
            limit=args.limit,
            save_results=args.save_results,
            run_name=args.run_name,
            show_samples=args.show_samples,
        )
    )


if __name__ == "__main__":
    main()
