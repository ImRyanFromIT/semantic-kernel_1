#!/usr/bin/env python3
'''
Feedback Wipe Utility

This utility cleans feedback data from:
1. JSONL feedback file (logs/feedback.jsonl)
2. Azure Search index feedback fields

Usage:
    python feedback_wipe.py --jsonl-only
    python feedback_wipe.py --azure-only
'''

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv
load_dotenv()

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.memory.azure_search_store import AzureAISearchStore
from src.memory.feedback_store import FeedbackStore


class FeedbackWiper:
    '''Utility to wipe feedback data from various sources.'''
    
    def __init__(self):
        '''Initialize the feedback wiper.'''
        self.feedback_store = None
        self.azure_store = None
    
    def wipe_jsonl_feedback(self, feedback_file: str = "logs/feedback.jsonl") -> int:
        '''
        Wipe feedback from JSONL file.
        
        Args:
            feedback_file: Path to feedback JSONL file
            
        Returns:
            Number of feedback records removed
        '''
        feedback_path = Path(feedback_file)
        
        if not feedback_path.exists():
            print(f"[INFO] Feedback file {feedback_file} does not exist - nothing to wipe")
            return 0
        
        # Count existing records
        record_count = 0
        try:
            with open(feedback_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        record_count += 1
        except Exception as e:
            print(f"[ERROR] Failed to read feedback file: {e}")
            return 0
        
        if record_count == 0:
            print(f"[INFO] Feedback file {feedback_file} is already empty")
            return 0
        
        print(f"[ACTION] Wiping {record_count} feedback records from {feedback_file}")
        
        try:
            # Truncate the file
            with open(feedback_path, 'w', encoding='utf-8') as f:
                pass  # Empty file
            print(f"[SUCCESS] Wiped {record_count} feedback records from {feedback_file}")
        except Exception as e:
            print(f"[ERROR] Failed to wipe feedback file: {e}")
            return 0
        
        return record_count
    
    async def wipe_azure_feedback(self) -> int:
        '''
        Wipe feedback fields from Azure Search index.
        
        Returns:
            Number of documents updated
        '''
        try:
            # Initialize Azure Search store
            self.azure_store = AzureAISearchStore()
            
            # Search for all documents that have feedback data
            print("[INFO] Searching for documents with feedback data...")
            
            search_results = self.azure_store.search_client.search(
                search_text="*",
                select=["SRM_ID", "Name", "negative_feedback_queries", "positive_feedback_queries", "feedback_score_adjustment"],
                top=1000  # Adjust if you have more documents
            )
            
            documents_to_update = []
            
            for result in search_results:
                srm_id = result.get('SRM_ID', 'Unknown')
                name = result.get('Name', 'Unknown')
                
                # Check if document has any feedback data
                has_feedback = (
                    (result.get('negative_feedback_queries') and len(result.get('negative_feedback_queries', [])) > 0) or
                    (result.get('positive_feedback_queries') and len(result.get('positive_feedback_queries', [])) > 0) or
                    (result.get('feedback_score_adjustment') is not None and result.get('feedback_score_adjustment') != 0.0)
                )
                
                if has_feedback:
                    documents_to_update.append({
                        'SRM_ID': srm_id,
                        'Name': name,
                        'negative_queries': result.get('negative_feedback_queries', []),
                        'positive_queries': result.get('positive_feedback_queries', []),
                        'score_adjustment': result.get('feedback_score_adjustment', 0.0)
                    })
            
            if not documents_to_update:
                print("[INFO] No documents found with feedback data")
                return 0
            
            print(f"[ACTION] Wiping feedback data from {len(documents_to_update)} Azure Search documents")
            
            # Show details of what will be wiped
            for doc in documents_to_update[:5]:  # Show first 5
                neg_count = len(doc['negative_queries']) if doc['negative_queries'] else 0
                pos_count = len(doc['positive_queries']) if doc['positive_queries'] else 0
                score_adj = doc['score_adjustment'] or 0.0
                
                print(f"         {doc['SRM_ID']} ({doc['Name'][:50]}...) - Neg: {neg_count}, Pos: {pos_count}, Score: {score_adj}")
            
            if len(documents_to_update) > 5:
                print(f"         ... and {len(documents_to_update) - 5} more documents")
            
            # Update documents to clear feedback fields
            updated_count = 0
            
            for doc_info in documents_to_update:
                try:
                    await self.azure_store.update_feedback_scores(
                        srm_id=doc_info['SRM_ID'],
                        query="WIPE_RESET",  # Special marker
                        feedback_type="reset",
                        user_id="system"
                    )
                    updated_count += 1
                except Exception as e:
                    print(f"[WARNING] Failed to update {doc_info['SRM_ID']}: {e}")
            
            print(f"[SUCCESS] Wiped feedback data from {updated_count} documents")
            return updated_count
            
        except Exception as e:
            print(f"[ERROR] Failed to wipe Azure feedback: {e}")
            return 0
    
async def main():
    '''Main entry point for the feedback wipe utility.'''
    parser = argparse.ArgumentParser(description="Wipe feedback data from JSONL file or Azure Search index")
    
    parser.add_argument(
        '--jsonl-only', 
        action='store_true',
        help='Wipe feedback only from JSONL file'
    )
    parser.add_argument(
        '--azure-only', 
        action='store_true',
        help='Wipe feedback only from Azure Search index'
    )
    parser.add_argument(
        '--file', 
        default='logs/feedback.jsonl',
        help='Path to feedback JSONL file (default: logs/feedback.jsonl)'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not (args.jsonl_only or args.azure_only):
        parser.error("Must specify either --jsonl-only or --azure-only")
    
    if args.jsonl_only and args.azure_only:
        parser.error("Can only specify one wipe mode at a time")
    
    # Initialize wiper
    wiper = FeedbackWiper()
    
    try:
        # Execute wipe based on mode
        if args.jsonl_only:
            count = wiper.wipe_jsonl_feedback(args.file)
            print(f"\n[COMPLETE] Wiped {count} feedback records from JSONL")
        elif args.azure_only:
            count = await wiper.wipe_azure_feedback()
            print(f"\n[COMPLETE] Wiped feedback from {count} Azure Search documents")
            
    except KeyboardInterrupt:
        print("\n[CANCELLED] Operation interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
