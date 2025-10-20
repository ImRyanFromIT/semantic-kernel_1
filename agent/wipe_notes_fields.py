#!/usr/bin/env python3
"""
Utility to wipe OwnerNotes and HiddenNotes fields from Azure AI Search index.

Use this after testing to clean up the index and return fields to null/empty state.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent  # Now at agent/, so only need .parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(project_root / '.env')


def wipe_notes_fields(
    endpoint: str,
    index_name: str,
    api_key: str,
    dry_run: bool = True,
    batch_size: int = 100
) -> None:
    """
    Wipe OwnerNotes and HiddenNotes fields from all documents in the index.
    
    Args:
        endpoint: Azure Search service endpoint
        index_name: Name of the index
        api_key: API key for authentication
        dry_run: If True, only show what would be changed without actually updating
        batch_size: Number of documents to process in each batch
    """
    try:
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential
    except ImportError:
        print("ERROR: azure-search-documents not installed.")
        print("Install with: pip install azure-search-documents")
        sys.exit(1)
    
    print(f"\n{'='*80}")
    print(f"Azure AI Search Notes Field Wiper")
    print(f"{'='*80}")
    print(f"Endpoint: {endpoint}")
    print(f"Index: {index_name}")
    print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE (will update index)'}")
    print(f"{'='*80}\n")
    
    # Create search client
    credential = AzureKeyCredential(api_key)
    client = SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=credential
    )
    
    print("Fetching all documents from index...")
    
    # Get all documents
    try:
        results = client.search(
            search_text="*",
            select=["SRM_ID", "Name", "owner_notes", "hidden_notes"],
            top=1000  # Adjust if you have more than 1000 SRMs
        )
        
        documents_to_update = []
        documents_with_notes = []
        
        for result in results:
            srm_id = result.get('SRM_ID', 'Unknown')
            name = result.get('Name', 'Unknown')
            owner_notes = result.get('owner_notes')
            hidden_notes = result.get('hidden_notes')
            
            # Check if document has any notes
            has_notes = bool(owner_notes or hidden_notes)
            
            if has_notes:
                documents_with_notes.append({
                    'SRM_ID': srm_id,
                    'Name': name,
                    'owner_notes': owner_notes,
                    'hidden_notes': hidden_notes
                })
                
                # Prepare update document
                documents_to_update.append({
                    'SRM_ID': srm_id,
                    'owner_notes': None,
                    'hidden_notes': None,
                    '@search.action': 'merge'
                })
        
        print(f"\nTotal documents in index: {len(list(results))}")
        print(f"Documents with notes to wipe: {len(documents_with_notes)}")
        
        if documents_with_notes:
            print(f"\n{'='*80}")
            print("Documents that will be modified:")
            print(f"{'='*80}")
            
            for doc in documents_with_notes:
                print(f"\n  {doc['SRM_ID']}: {doc['Name']}")
                if doc.get('owner_notes'):
                    preview = doc['owner_notes'][:100] + "..." if len(doc['owner_notes']) > 100 else doc['owner_notes']
                    print(f"    owner_notes: {preview}")
                if doc.get('hidden_notes'):
                    preview = doc['hidden_notes'][:100] + "..." if len(doc['hidden_notes']) > 100 else doc['hidden_notes']
                    print(f"    hidden_notes: {preview}")
        else:
            print("\n[OK] No documents have notes to wipe. Index is already clean.")
            return
        
        # Perform update
        if dry_run:
            print(f"\n{'='*80}")
            print("DRY RUN MODE - No changes were made")
            print(f"{'='*80}")
            print("\nTo actually wipe the fields, run with --confirm flag:")
            print(f"  python {Path(__file__).name} --confirm")
        else:
            print(f"\n{'='*80}")
            print("UPDATING INDEX...")
            print(f"{'='*80}")
            
            # Confirm with user
            response = input("\nAre you sure you want to wipe these fields? (yes/no): ")
            if response.lower() != 'yes':
                print("\nOperation cancelled by user.")
                return
            
            # Process in batches
            for i in range(0, len(documents_to_update), batch_size):
                batch = documents_to_update[i:i + batch_size]
                result = client.upload_documents(documents=batch)
                
                succeeded = sum(1 for r in result if r.succeeded)
                failed = len(batch) - succeeded
                
                print(f"  Batch {i // batch_size + 1}: {succeeded} updated, {failed} failed")
            
            print(f"\n{'='*80}")
            print("[SUCCESS] Fields wiped successfully")
            print(f"{'='*80}")
            print(f"\nProcessed {len(documents_to_update)} documents")
            print("owner_notes and hidden_notes fields set to null")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Wipe owner_notes and hidden_notes fields from Azure AI Search index",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (see what would be changed):
  python wipe_notes_fields.py
  
  # Actually wipe the fields:
  python wipe_notes_fields.py --confirm
  
  # Specify custom endpoint and index:
  python wipe_notes_fields.py --endpoint https://my-search.search.windows.net --index my-index --confirm

Environment variables:
  AZURE_AI_SEARCH_ENDPOINT    - Azure Search service endpoint
  AZURE_AI_SEARCH_INDEX_NAME  - Index name
  AZURE_AI_SEARCH_API_KEY     - API key for authentication
        """
    )
    
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Actually perform the wipe (without this, runs in dry-run mode)'
    )
    
    parser.add_argument(
        '--endpoint',
        default=os.getenv('AZURE_AI_SEARCH_ENDPOINT'),
        help='Azure Search endpoint (default: from .env)'
    )
    
    parser.add_argument(
        '--index',
        default=os.getenv('AZURE_AI_SEARCH_INDEX_NAME'),
        help='Index name (default: from .env)'
    )
    
    parser.add_argument(
        '--api-key',
        default=os.getenv('AZURE_AI_SEARCH_API_KEY'),
        help='API key (default: from .env)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch size for updates (default: 100)'
    )
    
    args = parser.parse_args()
    
    # Validate required parameters
    if not args.endpoint:
        print("ERROR: Azure Search endpoint not provided")
        print("Set AZURE_AI_SEARCH_ENDPOINT in .env or use --endpoint")
        sys.exit(1)
    
    if not args.index:
        print("ERROR: Index name not provided")
        print("Set AZURE_AI_SEARCH_INDEX_NAME in .env or use --index")
        sys.exit(1)
    
    if not args.api_key:
        print("ERROR: API key not provided")
        print("Set AZURE_AI_SEARCH_API_KEY in .env or use --api-key")
        sys.exit(1)
    
    # Run the wipe
    wipe_notes_fields(
        endpoint=args.endpoint,
        index_name=args.index,
        api_key=args.api_key,
        dry_run=not args.confirm,
        batch_size=args.batch_size
    )


if __name__ == "__main__":
    main()

