#!/bin/bash
# Convenience script to run tests

echo "=========================================="
echo "Running SRM Agent Tests"
echo "=========================================="
echo ""

# Use the venv's python
PYTHON=".venv/bin/python"

# Show usage if no arguments
if [ $# -eq 0 ]; then
    echo "Usage examples:"
    echo "  ./run_tests.sh                    # Run all tests"
    echo "  ./run_tests.sh test_plugins.py    # Run specific file"
    echo "  ./run_tests.sh -v                 # Verbose mode"
    echo "  ./run_tests.sh -k 'search'        # Run tests matching 'search'"
    echo ""
    echo "=========================================="
    echo ""
fi

# Run pytest with all arguments passed to this script
$PYTHON -m pytest "$@"
