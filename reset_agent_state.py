#!/usr/bin/env python3
"""
Reset agent state for testing.

This script clears the agent state files and processed email tracking
so you can run tests with fresh state.

Usage:
    python reset_agent_state.py
    python reset_agent_state.py --confirm  # Skip confirmation prompt
"""

import os
import sys
import argparse
from pathlib import Path


def reset_state(confirm: bool = False):
    """Reset agent state files."""

    if not confirm:
        print("This will delete the following:")
        print("  - src/state/agent_state.jsonl")
        print("  - src/state/agent_state.jsonl.backup")
        print("  - src/state/chat_history.jsonl")
        print("  - logs/email_agent.log")
        print()
        response = input("Continue? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Aborted.")
            return

    # State files to remove
    files_to_remove = [
        Path("src/state/agent_state.jsonl"),
        Path("src/state/agent_state.jsonl.backup"),
        Path("src/state/chat_history.jsonl"),
        Path("logs/email_agent.log"),
    ]

    removed_count = 0

    for file_path in files_to_remove:
        if file_path.exists():
            file_path.unlink()
            print(f"✓ Removed: {file_path}")
            removed_count += 1
        else:
            print(f"  (not found: {file_path})")

    # Reset file reader processed files tracking (for test mode)
    try:
        from src.utils.file_email_reader import FileEmailReader
        reader = FileEmailReader()
        if hasattr(reader, 'reset_processed_files'):
            reader.reset_processed_files()
            print("✓ Reset file reader processed files tracking")
    except Exception as e:
        print(f"  (could not reset file reader: {e})")

    print(f"\n{'='*60}")
    print(f"Reset complete! Removed {removed_count} files.")
    print("You can now run the agent with fresh state.")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reset SRM Archivist Agent state files"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    print("="*60)
    print("SRM ARCHIVIST AGENT - RESET STATE")
    print("="*60)
    print()

    reset_state(confirm=args.confirm)
