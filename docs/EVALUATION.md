# SRM Chatbot Evaluation System

## Overview

This evaluation framework assesses the quality of question-answering interactions between users and the SRM (Service Request Model) chatbot. The system measures whether responses are relevant, factually grounded, coherent, and whether the correct service request model is recommended.

## Purpose

The evaluation system was developed to quantify chatbot performance across different user personas and use cases. By running queries through the chatbot and measuring the quality of responses against known correct answers, gaps in service coverage, retrieval accuracy, and response quality can be identified and addressed.

## What It Does

### Query Evaluation

Test queries are processed through the chatbot exactly as a real user would experience them. For each query, the system:

1. Captures the chatbot's response and the context it retrieved
2. Evaluates the response quality using Azure AI evaluation metrics
3. Compares the recommended SRM against the expected correct answer
4. Generates detailed scoring across multiple quality dimensions

### Quality Measurement

Responses are scored on three primary dimensions:

**Relevance (40% weight)** - Whether the response actually addresses what was asked. High scores indicate the chatbot understood the question and provided an appropriate answer.

**Groundedness (40% weight)** - Whether statements in the response are supported by the retrieved context documents. High scores indicate the chatbot is not hallucinating or making unsupported claims.

**Coherence (20% weight)** - Whether the response is well-structured, logical, and easy to understand. High scores indicate clear communication without contradictions or confusion.

These three scores are combined into a weighted average that represents overall response quality on a 1-5 scale.

### Correctness Validation

Beyond quality scoring, the system validates whether the correct Service Request Model was recommended. This is measured by extracting the SRM ID from the response (e.g., "SRM-013") and comparing it to the expected answer from the test dataset. Accuracy is calculated as the percentage of queries where the correct SRM was identified.

### Result Aggregation

Individual query results are aggregated to produce:

- Overall accuracy rate (% of correct SRM recommendations)
- Average scores for each quality dimension
- Identification of systematically failing query types
- Examples of both successful and problematic responses

## How It Works

### Dataset Structure

Test cases are stored in JSONL format with each line containing a query and its expected SRM:

```jsonl
{"query": "I need database backup help", "expected_srm": "SRM-013"}
{"query": "How do I set up monitoring?", "expected_srm": "SRM-001"}
```

These datasets can be crafted to test specific scenarios, user personas, or service categories.

### Evaluation Process

When evaluation is run:

1. Each query from the dataset is sent to the chatbot
2. The chatbot processes the query using its normal retrieval and response generation
3. The response, along with retrieved context, is sent to Azure AI evaluation services
4. Quality scores are computed by GPT-4 based evaluation models
5. The recommended SRM is extracted and compared to the expected answer
6. Results are aggregated and optionally saved to JSON files

### Interpreting Results

A typical evaluation produces output like:

```
Accuracy:             22/50 (44.0%)
Weighted Avg Score:   4.20/5.00

Individual Metrics:
  Relevance:          3.68/5.00
  Groundedness:       4.88/5.00
  Coherence:          3.90/5.00
```

This indicates the system is providing high-quality responses (4.20/5.00) with excellent groundedness (no hallucinations), but is only recommending the correct SRM 44% of the time. The lower relevance score (3.68) suggests responses may not fully address what users are asking.

Such patterns help identify whether issues are with response generation quality, retrieval accuracy, or both.

## Usage

### Basic Evaluation

Evaluations are run from the command line:

```bash
# Test with a small sample
python tests/evaluation/run_qa_evaluation.py --limit 3

# Full evaluation with saved results
python tests/evaluation/run_qa_evaluation.py \
  --dataset tests/evaluation/datasets/qa_lost_end_user.jsonl \
  --save-results \
  --run-name "baseline-v1"
```

### Prerequisites

Azure OpenAI credentials must be configured in `.env`:

```bash
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4
```

These are required because the evaluation metrics themselves are computed using GPT-4 to assess response quality.

### Result Storage

When `--save-results` is specified, evaluation data is written to:

- `tests/evaluation/utils/results/*.json` - Machine-readable metrics and individual results
- `tests/evaluation/results/*.md` - Human-readable analysis reports (when generated separately)

Results can be compared across runs to measure the impact of system changes.

## Use Cases

### Regression Testing

The evaluation system can be integrated into CI/CD pipelines to ensure changes don't degrade performance:

```bash
# Before merging changes
pytest tests/evaluation/evaluators/ -v
python tests/evaluation/run_qa_evaluation.py --limit 10
```

### Persona-Based Analysis

Different datasets targeting specific user types (technical experts, end users, managers) reveal whether the chatbot serves all audiences equally well. Systematic failures with one persona indicate gaps in how the system handles that communication style.

### Service Coverage Validation

By creating comprehensive datasets covering all SRM categories, gaps in the chatbot's knowledge or retrieval capability become apparent. Services with consistently low accuracy need improved descriptions, keywords, or use case examples.

### Impact Measurement

Before and after evaluations quantify whether changes improved the system:

```bash
# Before changes
python tests/evaluation/run_qa_evaluation.py --save-results --run-name "before-fix"

# After changes
python tests/evaluation/run_qa_evaluation.py --save-results --run-name "after-fix"
```

Comparing the saved results shows whether accuracy, relevance, or other metrics improved.

## Architecture

The system is organized into modules with distinct responsibilities:

**Evaluators** (`tests/evaluation/evaluators/`) - Implement metric calculation logic. The `qa_evaluator.py` module wraps Azure AI evaluation services and combines scores according to configured weights.

**Harness** (`tests/evaluation/harness/`) - Provides a test interface to the chatbot that simulates real user interactions while capturing internal data needed for evaluation.

**Utilities** (`tests/evaluation/utils/`) - Handle result persistence, dataset loading, and helper functions.

**Datasets** (`tests/evaluation/datasets/`) - Store test cases in JSONL format.

**Results** (`tests/evaluation/results/`) - Archive evaluation outputs for analysis and comparison.

## Development

### Testing

The evaluation system itself has unit tests to ensure metric calculations and result processing work correctly:

```bash
pytest tests/evaluation/evaluators/test_qa_evaluator.py -v
```

### Extension

New evaluators can be added by:

1. Implementing an evaluator class in `tests/evaluation/evaluators/`
2. Adding corresponding tests
3. Creating a runner script similar to `run_qa_evaluation.py`

Custom metrics or weights can be configured when instantiating evaluators.

## Limitations

**Evaluation Accuracy** - Quality metrics are themselves computed by LLMs and may not perfectly align with human judgment.

**Cost** - Each evaluation makes multiple API calls to Azure OpenAI for metric computation, incurring costs proportional to the dataset size.

**Coverage** - The system only measures what is included in test datasets. Uncovered scenarios won't surface issues.

**Temporal Sensitivity** - Evaluation results reflect the state of SRM data, retrieval indices, and system configuration at evaluation time.

## Related Documentation

Implementation details and development history:
- `tests/evaluation/results/lost_end_user_evaluation_report.md` - Example analysis report

System context:
- `docs/cli_concierge_usage.md` - How the chatbot being evaluated works

---
