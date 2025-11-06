#!/usr/bin/env python3
"""
Reset agent state for testing.

This script clears the agent state files and processed email tracking
so you can run tests with fresh state. It can also reset owner_notes and
hidden_notes fields in the Azure Search index.

Usage:
    python reset_agent_state.py
    python reset_agent_state.py --confirm  # Skip confirmation prompt
    python reset_agent_state.py --reset-index  # Also reset Azure Search index fields
    python reset_agent_state.py --reset-index --confirm  # Reset both without prompts
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def reset_index_fields(confirm: bool = False):
    """Reset owner_notes and hidden_notes fields in Azure Search index."""
    print("\n" + "="*60)
    print("RESETTING AZURE SEARCH INDEX FIELDS")
    print("="*60)

    # Get Azure Search config
    endpoint = os.getenv('AZURE_AI_SEARCH_ENDPOINT', '')
    api_key = os.getenv('AZURE_AI_SEARCH_API_KEY', '')
    index_name = os.getenv('AZURE_AI_SEARCH_INDEX_NAME', 'srm-catalog')

    if not endpoint or not api_key:
        print("✗ Azure Search credentials not found in environment")
        print("  Please set AZURE_AI_SEARCH_ENDPOINT and AZURE_AI_SEARCH_API_KEY in .env")
        return False

    print(f"\nIndex: {index_name}")
    print(f"Endpoint: {endpoint}")

    if not confirm:
        print("\nThis will reset the following fields for ALL documents in the index:")
        print("  - owner_notes (will be set to empty string)")
        print("  - hidden_notes (will be set to empty string)")
        print()
        response = input("Continue with index reset? (yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("Skipped index reset.")
            return False

    try:
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential

        # Initialize search client
        credential = AzureKeyCredential(api_key)
        client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=credential
        )

        print("\n✓ Connected to Azure Search")
        print("  Fetching all documents...")

        # Get all documents
        results = client.search(search_text="*", select=["SRM_ID"], top=1000)

        documents_to_update = []
        for result in results:
            srm_id = result.get('SRM_ID')
            if srm_id:
                documents_to_update.append({
                    "SRM_ID": srm_id,
                    "owner_notes": "",
                    "hidden_notes": "",
                    "@search.action": "merge"
                })

        if not documents_to_update:
            print("  No documents found in index")
            return True

        print(f"  Found {len(documents_to_update)} documents to reset")
        print("  Resetting owner_notes and hidden_notes fields...")

        # Update documents in batches
        batch_size = 100
        for i in range(0, len(documents_to_update), batch_size):
            batch = documents_to_update[i:i+batch_size]
            result = client.upload_documents(documents=batch)

            # Check for errors
            failed = [r for r in result if not r.succeeded]
            if failed:
                print(f"  ⚠ Warning: {len(failed)} documents failed to update in batch {i//batch_size + 1}")

        print(f"✓ Reset complete! Updated {len(documents_to_update)} documents")
        return True

    except ImportError:
        print("✗ azure-search-documents package not installed")
        print("  Run: pip install azure-search-documents")
        return False
    except Exception as e:
        print(f"✗ Failed to reset index fields: {e}")
        import traceback
        traceback.print_exc()
        return False


def reset_state(confirm: bool = False, reset_index: bool = False):
    """Reset agent state files and optionally index fields."""

    if not confirm:
        print("This will delete the following:")
        print("  - src/state/agent_state.jsonl")
        print("  - src/state/agent_state.jsonl.backup")
        print("  - src/state/chat_history.jsonl")
        print("  - logs/email_agent.log")
        if reset_index:
            print("  - owner_notes and hidden_notes fields in Azure Search index")
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

    # Reset Azure Search index fields if requested
    if reset_index:
        index_reset_success = reset_index_fields(confirm=confirm)
        if not index_reset_success:
            print("\n⚠ Warning: Index field reset failed or was skipped")

    print(f"\n{'='*60}")
    print(f"Reset complete! Removed {removed_count} files.")
    if reset_index:
        print("Azure Search index fields have been reset.")
    print("You can now run the agent with fresh state.")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reset SRM Archivist Agent state files and optionally Azure Search index fields"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Skip confirmation prompt"
    )
    parser.add_argument(
        "--reset-index",
        action="store_true",
        help="Also reset owner_notes and hidden_notes fields in Azure Search index"
    )

    args = parser.parse_args()

    print("="*60)
    print("SRM ARCHIVIST AGENT - RESET STATE")
    print("="*60)
    print()

    reset_state(confirm=args.confirm, reset_index=args.reset_index)
