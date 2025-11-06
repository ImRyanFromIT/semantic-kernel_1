"""
Compare Evaluation Runs.

This script compares two evaluation runs and shows the differences in metrics.
Useful for before/after comparisons when making changes to the system.

Usage:
    python tests/evaluation/compare_runs.py --baseline results/run1.json --current results/run2.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict


def load_results(filepath: str) -> Dict:
    """Load results from JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def compare_metrics(baseline: Dict, current: Dict) -> Dict:
    """
    Compare aggregate metrics between two runs.

    Args:
        baseline: Baseline results
        current: Current results

    Returns:
        Dictionary with metric comparisons
    """
    baseline_metrics = baseline["aggregate_metrics"]
    current_metrics = current["aggregate_metrics"]

    comparisons = {}

    metrics_to_compare = [
        ("average_composite_score", "Composite Score"),
        ("average_groundedness", "Groundedness"),
        ("average_relevance", "Relevance"),
        ("average_coherence", "Coherence"),
        ("average_fluency", "Fluency"),
        ("average_behavior_correct", "Behavior Correct"),
    ]

    for metric_key, display_name in metrics_to_compare:
        baseline_val = baseline_metrics.get(metric_key, 0)
        current_val = current_metrics.get(metric_key, 0)
        delta = current_val - baseline_val
        delta_pct = (delta / baseline_val * 100) if baseline_val > 0 else 0

        comparisons[metric_key] = {
            "display_name": display_name,
            "baseline": baseline_val,
            "current": current_val,
            "delta": delta,
            "delta_pct": delta_pct,
            "improved": delta > 0,
            "regressed": delta < 0,
        }

    return comparisons


def print_comparison(baseline: Dict, current: Dict, comparisons: Dict):
    """Print comparison results in a formatted table."""
    print("\n" + "=" * 100)
    print("EVALUATION COMPARISON")
    print("=" * 100)

    # Metadata
    print(f"\nBaseline: {baseline['metadata']['run_name']} ({baseline['metadata']['datetime']})")
    print(f"Current:  {current['metadata']['run_name']} ({current['metadata']['datetime']})")

    print("\n" + "-" * 100)
    print(f"{'Metric':<25} {'Baseline':>12} {'Current':>12} {'Delta':>12} {'% Change':>12} {'Status':>15}")
    print("-" * 100)

    for metric_key, comp in comparisons.items():
        # Format values based on scale
        if "behavior" in metric_key.lower():
            # 0-1 scale
            baseline_str = f"{comp['baseline']:.3f}"
            current_str = f"{comp['current']:.3f}"
            delta_str = f"{comp['delta']:+.3f}"
        else:
            # 0-5 scale
            baseline_str = f"{comp['baseline']:.2f}"
            current_str = f"{comp['current']:.2f}"
            delta_str = f"{comp['delta']:+.2f}"

        pct_str = f"{comp['delta_pct']:+.1f}%"

        # Status indicator
        if comp['improved']:
            status = "✓ IMPROVED"
        elif comp['regressed']:
            status = "✗ REGRESSED"
        else:
            status = "= NO CHANGE"

        print(f"{comp['display_name']:<25} {baseline_str:>12} {current_str:>12} {delta_str:>12} {pct_str:>12} {status:>15}")

    print("-" * 100)

    # Summary
    improved_count = sum(1 for c in comparisons.values() if c['improved'])
    regressed_count = sum(1 for c in comparisons.values() if c['regressed'])
    unchanged_count = len(comparisons) - improved_count - regressed_count

    print(f"\nSummary: {improved_count} improved, {regressed_count} regressed, {unchanged_count} unchanged")

    # Overall assessment
    if improved_count > regressed_count:
        print("\n✓ Overall: Changes appear to have IMPROVED the system")
    elif regressed_count > improved_count:
        print("\n✗ Overall: Changes appear to have REGRESSED the system")
    else:
        print("\n= Overall: Mixed results or no significant change")

    print("\n" + "=" * 100)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Compare two evaluation runs and show metric differences"
    )
    parser.add_argument(
        "--baseline",
        type=str,
        required=True,
        help="Path to baseline results JSON file"
    )
    parser.add_argument(
        "--current",
        type=str,
        required=True,
        help="Path to current results JSON file"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed per-query comparison (not implemented yet)"
    )

    args = parser.parse_args()

    # Validate files exist
    baseline_path = Path(args.baseline)
    current_path = Path(args.current)

    if not baseline_path.exists():
        print(f"Error: Baseline file not found: {baseline_path}")
        sys.exit(1)

    if not current_path.exists():
        print(f"Error: Current file not found: {current_path}")
        sys.exit(1)

    # Load results
    print(f"Loading baseline: {baseline_path}")
    baseline = load_results(baseline_path)

    print(f"Loading current:  {current_path}")
    current = load_results(current_path)

    # Compare
    comparisons = compare_metrics(baseline, current)

    # Print results
    print_comparison(baseline, current, comparisons)

    # TODO: If --detailed, compare individual query results


if __name__ == "__main__":
    main()
