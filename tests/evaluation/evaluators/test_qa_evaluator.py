"""
Tests for QAEvaluator.
"""
import pytest
from tests.evaluation.evaluators.qa_evaluator import QAEvaluator


class TestQAEvaluator:
    """Test suite for QAEvaluator."""

    @pytest.fixture
    def model_config(self):
        """Mock model config for testing."""
        return {
            "azure_endpoint": "https://test.openai.azure.com",
            "api_key": "test-key",
            "azure_deployment": "gpt-4",
        }

    @pytest.fixture
    def qa_evaluator(self, model_config):
        """Create QAEvaluator instance."""
        return QAEvaluator(model_config=model_config)

    def test_evaluator_initialization(self, qa_evaluator):
        """Test that evaluator initializes with correct weights."""
        assert qa_evaluator.weights["relevance"] == 0.40
        assert qa_evaluator.weights["groundedness"] == 0.40
        assert qa_evaluator.weights["coherence"] == 0.20
        assert sum(qa_evaluator.weights.values()) == pytest.approx(1.0)

    def test_extract_srm_from_response_with_valid_srm(self, qa_evaluator):
        """Test SRM extraction from response with valid SRM-XXX format."""
        response = "I recommend SRM-013 for database backup configuration."
        extracted = qa_evaluator._extract_srm_from_response(response)
        assert extracted == "SRM-013"

    def test_extract_srm_from_response_with_no_srm(self, qa_evaluator):
        """Test SRM extraction from response without SRM."""
        response = "I cannot help with that request."
        extracted = qa_evaluator._extract_srm_from_response(response)
        assert extracted is None

    def test_extract_srm_from_response_with_multiple_srms(self, qa_evaluator):
        """Test SRM extraction returns first SRM when multiple present."""
        response = "Consider SRM-001 or SRM-002 for this task."
        extracted = qa_evaluator._extract_srm_from_response(response)
        assert extracted == "SRM-001"

    def test_evaluate_correctness_when_correct(self, qa_evaluator):
        """Test correctness evaluation when SRM matches."""
        response = "I recommend SRM-013 for database backup."
        expected_srm = "SRM-013"

        result = qa_evaluator._evaluate_correctness(response, expected_srm)

        assert result["is_correct"] is True
        assert result["recommended_srm"] == "SRM-013"
        assert result["expected_srm"] == "SRM-013"
        assert "Correctly recommended SRM-013" in result["reasoning"]

    def test_evaluate_correctness_when_incorrect(self, qa_evaluator):
        """Test correctness evaluation when SRM doesn't match."""
        response = "I recommend SRM-005 for database backup."
        expected_srm = "SRM-013"

        result = qa_evaluator._evaluate_correctness(response, expected_srm)

        assert result["is_correct"] is False
        assert result["recommended_srm"] == "SRM-005"
        assert result["expected_srm"] == "SRM-013"
        assert "Recommended SRM-005" in result["reasoning"]
        assert "expected SRM-013" in result["reasoning"]

    def test_evaluate_correctness_when_no_srm_recommended(self, qa_evaluator):
        """Test correctness evaluation when no SRM found in response."""
        response = "I cannot help with that request."
        expected_srm = "SRM-013"

        result = qa_evaluator._evaluate_correctness(response, expected_srm)

        assert result["is_correct"] is False
        assert result["recommended_srm"] is None
        assert result["expected_srm"] == "SRM-013"
        assert "No SRM recommended" in result["reasoning"]

    @pytest.fixture
    def mock_builtin_evaluators(self, mocker):
        """Mock the builtin evaluators to avoid actual LLM calls."""
        mock = mocker.patch('tests.evaluation.evaluators.qa_evaluator.BuiltInEvaluators')

        # Mock the evaluator methods
        mock_instance = mock.return_value
        mock_instance.evaluate_relevance.return_value = {
            "relevance": 5,
            "reasoning": "Highly relevant response"
        }
        mock_instance.evaluate_groundedness.return_value = {
            "groundedness": 5,
            "reasoning": "Fully grounded in context"
        }
        mock_instance.evaluate_coherence.return_value = {
            "coherence": 4,
            "reasoning": "Well-structured response"
        }

        return mock

    def test_evaluate_complete_success(self, model_config, mock_builtin_evaluators):
        """Test complete evaluation with correct answer."""
        evaluator = QAEvaluator(model_config=model_config)

        result = evaluator.evaluate(
            query="I need database backup",
            response="I recommend SRM-013 for database backup and recovery configuration.",
            context=["SRM-013: Database Backup and Recovery Configuration..."],
            expected_srm="SRM-013"
        )

        # Check individual scores
        assert result["relevance"] == 5
        assert result["groundedness"] == 5
        assert result["coherence"] == 4

        # Check weighted average: 5*0.4 + 5*0.4 + 4*0.2 = 4.8
        assert result["weighted_average"] == pytest.approx(4.8)

        # Check correctness
        assert result["is_correct"] is True
        assert result["recommended_srm"] == "SRM-013"
        assert result["expected_srm"] == "SRM-013"

        # Check query is included
        assert result["query"] == "I need database backup"

        # Check correctness reasoning is present (but not metric reasoning)
        assert "correctness_reasoning" in result
        assert "relevance_reasoning" not in result
        assert "groundedness_reasoning" not in result
        assert "coherence_reasoning" not in result

    def test_evaluate_incorrect_srm(self, model_config, mock_builtin_evaluators):
        """Test evaluation with incorrect SRM recommendation."""
        evaluator = QAEvaluator(model_config=model_config)

        result = evaluator.evaluate(
            query="I need database backup",
            response="I recommend SRM-005 for your needs.",
            context=["SRM-005: Load Balancing Configuration..."],
            expected_srm="SRM-013"
        )

        # Scores should still be calculated
        assert "weighted_average" in result

        # But correctness should be False
        assert result["is_correct"] is False
        assert result["recommended_srm"] == "SRM-005"
        assert "Recommended" in result["correctness_reasoning"]

    def test_evaluate_batch(self, model_config, mock_builtin_evaluators):
        """Test batch evaluation with multiple test cases."""
        evaluator = QAEvaluator(model_config=model_config)

        test_cases = [
            {
                "query": "I need database backup",
                "response": "I recommend SRM-013 for database backup.",
                "context": ["SRM-013: Database Backup..."],
                "expected_srm": "SRM-013",
            },
            {
                "query": "I need load balancing",
                "response": "I recommend SRM-004 for load balancing.",
                "context": ["SRM-004: Load Balancing..."],
                "expected_srm": "SRM-004",
            },
            {
                "query": "I need monitoring",
                "response": "I recommend SRM-001 for monitoring.",
                "context": ["SRM-003: Monitoring..."],
                "expected_srm": "SRM-003",  # Wrong answer
            },
        ]

        results = evaluator.evaluate_batch(test_cases)

        # Check aggregate metrics
        assert results["total"] == 3
        assert results["correct_count"] == 2
        assert results["incorrect_count"] == 1
        assert results["accuracy"] == pytest.approx(66.67, rel=0.1)

        # Check that individual results are included
        assert len(results["individual_results"]) == 3

        # Verify first result is correct
        assert results["individual_results"][0]["is_correct"] is True

        # Verify third result is incorrect
        assert results["individual_results"][2]["is_correct"] is False
