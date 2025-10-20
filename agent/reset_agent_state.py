#!/usr/bin/env python3
"""
Reset agent state for testing.

This script clears the agent state file and processed email tracking
so you can run tests with fresh state.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to Python path so we can import agent modules
agent_dir = Path(__file__).parent
project_root = agent_dir.parent
sys.path.insert(0, str(project_root))

def reset_state():
    """Reset agent state files."""
    # Look for state files in the state directory
    agent_dir = Path(__file__).parent
    state_dir = agent_dir / "state"
    
    files_to_remove = [
        state_dir / "agent_state.jsonl",
        state_dir / "agent_actions.log",
        state_dir / "agent_state.jsonl.backup"
    ]
    
    removed_count = 0
    
    for file_path in files_to_remove:
        if file_path.exists():
            file_path.unlink()
            print(f"Removed: {file_path}")
            removed_count += 1
    
    # Reset file reader processed files tracking
    try:
        from agent.utils.file_email_reader import FileEmailReader
        reader = FileEmailReader()
        reader.reset_processed_files()
        print("Reset file reader processed files tracking")
    except Exception as e:
        print(f"Could not reset file reader: {e}")
    
    print(f"\nReset complete! Removed {removed_count} files.")
    print("You can now run the agent tests with fresh state.")

if __name__ == "__main__":
    print("Resetting SRM Archivist Agent state...")
    reset_state()
