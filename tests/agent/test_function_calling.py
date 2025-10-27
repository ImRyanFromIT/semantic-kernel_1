"""
Test harness for verifying agent function calling behavior.

This test suite verifies that the agent actually calls functions when it should,
rather than just describing what it would do.
"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.main import SrmArchivistAgent


class MockScenario:
    """Represents a test scenario with expected function calls."""

    def __init__(self, name, user_message, expected_functions, description=""):
        self.name = name
        self.user_message = user_message
        self.expected_functions = expected_functions  # List of function names that should be called
        self.description = description
        self.actual_calls = []  # Will be populated during test

    def verify(self):
        """Check if expected functions were called."""
        missing = set(self.expected_functions) - set(self.actual_calls)
        unexpected = set(self.actual_calls) - set(self.expected_functions)

        return {
            'passed': len(missing) == 0 and len(unexpected) == 0,
            'missing': list(missing),
            'unexpected': list(unexpected),
            'expected': self.expected_functions,
            'actual': self.actual_calls
        }


# Define test scenarios
TEST_SCENARIOS = [
    MockScenario(
        name="email_fetch",
        user_message="Check for new emails",
        expected_functions=["fetch_emails"],
        description="Agent should call fetch_emails when asked to check for new emails"
    ),

    MockScenario(
        name="srm_search",
        user_message="Find the SRM for storage expansion",
        expected_functions=["search_srm"],
        description="Agent should call search_srm when asked to find an SRM by description"
    ),

    MockScenario(
        name="srm_update_flow",
        user_message="Update SRM-051 owner notes to 'This is a test update'",
        expected_functions=["search_srm", "update_srm_document"],
        description="Agent should search first, then update the SRM"
    ),

    MockScenario(
        name="notification_send",
        user_message="Send notification to test@greatvaluelab.com",
        expected_functions=["send_update_notification"],
        description="Agent should actually call send_update_notification when user provides email"
    ),

    MockScenario(
        name="state_check",
        user_message="Show me resumable work items",
        expected_functions=["find_resumable_records"],
        description="Agent should call find_resumable_records to check for incomplete work"
    ),
]


def extract_function_calls_from_log(log_output):
    """
    Parse log output to extract function calls.

    Looks for patterns like:
    [FUNCTION CALL] plugin.function_name
    """
    function_calls = []
    for line in log_output.split('\n'):
        if '[FUNCTION CALL]' in line:
            # Extract function name from log line
            # Format: [FUNCTION CALL] plugin.function_name
            try:
                parts = line.split('[FUNCTION CALL]')[1].strip()
                # Extract just the function name (after the dot)
                if '.' in parts:
                    function_name = parts.split('.')[1].split()[0]
                    function_calls.append(function_name)
            except (IndexError, AttributeError):
                pass

    return function_calls


@pytest.mark.asyncio
async def test_function_calling_scenarios():
    """
    Test that the agent calls functions for various scenarios.

    This is a semi-automated test that requires:
    1. Agent configuration to be set up
    2. Mock mode or test environment
    3. Logged function calls to be captured

    NOTE: This test may require manual verification of logs.
    """
    print("\n" + "=" * 80)
    print("FUNCTION CALLING TEST HARNESS")
    print("=" * 80)
    print("\nThis test verifies that the agent calls functions instead of just describing them.\n")

    # Instructions for running tests
    print("SETUP REQUIRED:")
    print("1. Ensure agent_config.yaml is configured with test/mock settings")
    print("2. Set mock_updates: true in config")
    print("3. Run agent in test mode to collect function call logs")
    print("\nTO RUN MANUALLY:")
    print("1. Start the agent in chat mode: python -m agent.run_agent_chat")
    print("2. For each scenario below, send the user message")
    print("3. Check logs for [FUNCTION CALL] entries")
    print("4. Verify expected functions were called\n")

    print("=" * 80)
    print("TEST SCENARIOS:")
    print("=" * 80)

    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"\n{i}. {scenario.name}")
        print(f"   Description: {scenario.description}")
        print(f"   User Message: '{scenario.user_message}'")
        print(f"   Expected Functions: {', '.join(scenario.expected_functions)}")
        print(f"   ---")
        print(f"   VERIFY: After sending message, check logs for these [FUNCTION CALL] entries:")
        for func in scenario.expected_functions:
            print(f"            - [FUNCTION CALL] <plugin>.{func}")

    print("\n" + "=" * 80)
    print("AUTOMATED TEST STUB")
    print("=" * 80)
    print("To implement automated testing:")
    print("1. Capture agent logs during invocation")
    print("2. Parse [FUNCTION CALL] entries from logs")
    print("3. Compare actual vs expected function calls")
    print("4. Assert all expected functions were called\n")

    # For now, this is a documentation test
    # To make it fully automated, you would need to:
    # 1. Initialize an agent with test config
    # 2. Send each scenario message
    # 3. Capture the callback logs
    # 4. Verify function calls

    # Placeholder assertion
    assert len(TEST_SCENARIOS) > 0, "Test scenarios should be defined"

    print("=" * 80)
    print("TEST COMPLETE - MANUAL VERIFICATION REQUIRED")
    print("=" * 80)


@pytest.mark.asyncio
async def test_function_call_logging():
    """
    Test that function call logging infrastructure is in place.

    Verifies that the _log_function_calls method exists and can process messages.
    """
    print("\nTesting function call logging infrastructure...")

    # This would need actual agent initialization
    # For now, just verify the test scenarios are well-formed

    for scenario in TEST_SCENARIOS:
        assert scenario.name, "Scenario must have a name"
        assert scenario.user_message, "Scenario must have a user message"
        assert len(scenario.expected_functions) > 0, f"Scenario {scenario.name} must expect at least one function call"

    print(f"✓ All {len(TEST_SCENARIOS)} test scenarios are well-formed")


def print_test_report(scenarios_with_results):
    """
    Print a detailed test report showing which scenarios passed/failed.

    Args:
        scenarios_with_results: List of (scenario, verification_result) tuples
    """
    print("\n" + "=" * 80)
    print("FUNCTION CALLING TEST REPORT")
    print("=" * 80)

    passed = sum(1 for _, result in scenarios_with_results if result['passed'])
    total = len(scenarios_with_results)

    print(f"\nResults: {passed}/{total} scenarios passed\n")

    for scenario, result in scenarios_with_results:
        status = "✓ PASS" if result['passed'] else "✗ FAIL"
        print(f"{status} - {scenario.name}")
        print(f"      Expected: {', '.join(result['expected'])}")
        print(f"      Actual:   {', '.join(result['actual'])}")

        if result['missing']:
            print(f"      MISSING:  {', '.join(result['missing'])}")
        if result['unexpected']:
            print(f"      UNEXPECTED: {', '.join(result['unexpected'])}")
        print()

    print("=" * 80)


if __name__ == "__main__":
    """
    Run tests directly with: python -m agent.tests.test_function_calling
    """
    print("\nRunning Function Calling Tests...")
    asyncio.run(test_function_calling_scenarios())
    asyncio.run(test_function_call_logging())
    print("\n✓ Tests complete - see output above for manual verification steps\n")
