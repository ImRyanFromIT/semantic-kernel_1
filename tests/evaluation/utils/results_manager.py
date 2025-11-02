"""
Results Manager for Evaluation Runs.

This module handles saving, loading, and managing evaluation results.
Results are stored as JSON files with timestamps for easy comparison.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ResultsManager:
    """
    Manager for evaluation results storage and retrieval.

    Results are stored in the results/ directory with filenames:
    {timestamp}_{run_name}.json

    Each result file contains:
    - metadata: Run information (timestamp, dataset, config)
    - aggregate_metrics: Summary statistics
    - detailed_results: Individual test case results
    """

    def __init__(self, results_dir: Optional[Path] = None):
        """
        Initialize results manager.

        Args:
            results_dir: Optional custom results directory path
        """
        if results_dir:
            self.results_dir = Path(results_dir)
        else:
            # Default to tests/evaluation/results
            self.results_dir = Path(__file__).parent / "results"

        # Ensure directory exists
        self.results_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ResultsManager initialized with directory: {self.results_dir}")

    def save_results(
        self,
        aggregate_metrics: Dict,
        detailed_results: List[Dict],
        run_name: Optional[str] = None,
        dataset_name: Optional[str] = None,
        config: Optional[Dict] = None,
    ) -> Path:
        """
        Save evaluation results to a JSON file.

        Args:
            aggregate_metrics: Summary metrics across all test cases
            detailed_results: Individual test case results
            run_name: Optional name for this run (e.g., "baseline-v1")
            dataset_name: Name of the dataset used
            config: Configuration used for this run

        Returns:
            Path to the saved results file
        """
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Build filename
        if run_name:
            filename = f"{timestamp}_{run_name}.json"
        else:
            filename = f"{timestamp}_eval_run.json"

        filepath = self.results_dir / filename

        # Build results structure
        results = {
            "metadata": {
                "timestamp": timestamp,
                "datetime": datetime.now().isoformat(),
                "run_name": run_name or "unnamed",
                "dataset_name": dataset_name or "unknown",
                "config": config or {},
            },
            "aggregate_metrics": aggregate_metrics,
            "detailed_results": detailed_results,
        }

        # Save to file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        logger.info(f"Results saved to: {filepath}")
        print(f"\n[+] Results saved to: {filepath}")

        return filepath

    def load_results(self, filepath: Path) -> Dict:
        """
        Load results from a JSON file.

        Args:
            filepath: Path to results file

        Returns:
            Dictionary with metadata, aggregate_metrics, and detailed_results
        """
        with open(filepath, "r", encoding="utf-8") as f:
            results = json.load(f)

        logger.info(f"Results loaded from: {filepath}")
        return results

    def list_results(self, pattern: str = "*.json") -> List[Path]:
        """
        List all results files in the results directory.

        Args:
            pattern: Glob pattern for filtering files

        Returns:
            List of result file paths, sorted by timestamp (newest first)
        """
        files = sorted(
            self.results_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return files

    def get_latest_result(self, run_name: Optional[str] = None) -> Optional[Path]:
        """
        Get the most recent results file.

        Args:
            run_name: Optional filter by run name

        Returns:
            Path to the latest results file, or None if no results exist
        """
        if run_name:
            pattern = f"*_{run_name}.json"
        else:
            pattern = "*.json"

        files = self.list_results(pattern)
        return files[0] if files else None

    def delete_result(self, filepath: Path) -> bool:
        """
        Delete a results file.

        Args:
            filepath: Path to results file

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            filepath.unlink()
            logger.info(f"Deleted results file: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {filepath}: {e}")
            return False

    def print_summary(self, filepath: Path):
        """
        Print a summary of results from a file.

        Args:
            filepath: Path to results file
        """
        results = self.load_results(filepath)

        metadata = results["metadata"]
        metrics = results["aggregate_metrics"]

        print("\n" + "=" * 80)
        print("EVALUATION RESULTS SUMMARY")
        print("=" * 80)
        print(f"\nRun Name: {metadata['run_name']}")
        print(f"Timestamp: {metadata['datetime']}")
        print(f"Dataset: {metadata['dataset_name']}")
        print(f"Test Cases: {metrics['num_evaluated']}")

        print("\n" + "-" * 80)
        print("AGGREGATE METRICS")
        print("-" * 80)

        print(f"  Composite Score: {metrics.get('average_composite_score', 0):.2f}/5")
        print(f"  Groundedness:    {metrics.get('average_groundedness', 0):.2f}/5")
        print(f"  Relevance:       {metrics.get('average_relevance', 0):.2f}/5")
        print(f"  Coherence:       {metrics.get('average_coherence', 0):.2f}/5")
        print(f"  Fluency:         {metrics.get('average_fluency', 0):.2f}/5")
        print(f"  Behavior Correct: {metrics.get('average_behavior_correct', 0):.2f} (0-1)")

        print("\n" + "=" * 80)
