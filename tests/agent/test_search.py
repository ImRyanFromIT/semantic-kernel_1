#!/usr/bin/env python3
"""
Test Azure Search connection directly.
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_search():
    """Test Azure Search directly."""
    print("=" * 80)
    print("AZURE SEARCH CONNECTION TEST")
    print("=" * 80)

    # Check environment variables
    print("\n[1/4] Checking environment variables...")
    endpoint = os.getenv('AZURE_AI_SEARCH_ENDPOINT')
    api_key = os.getenv('AZURE_AI_SEARCH_API_KEY')
    index_name = os.getenv('AZURE_AI_SEARCH_INDEX_NAME')

    print(f"  Endpoint: {endpoint}")
    print(f"  Index: {index_name}")
    print(f"  API Key: {'***' if api_key else 'NOT SET'}")

    if not endpoint or not api_key or not index_name:
        print("✗ Missing environment variables!")
        return False

    print("✓ Environment variables set")

    # Create vector store
    print("\n[2/4] Creating Azure Search store...")
    try:
        from src.memory.azure_search_store import AzureAISearchStore
        store = AzureAISearchStore()
        print("✓ Store created")
    except Exception as e:
        print(f"✗ Failed to create store: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test connection
    print("\n[3/4] Testing connection...")
    try:
        await store.ensure_collection_exists()
        print("✓ Connection successful")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test search
    print("\n[4/4] Testing search...")
    try:
        print("  Searching for: 'server request'")
        results = await store.search("server request", top_k=3)

        result_list = []
        async for result in results:
            result_list.append(result)

        print(f"✓ Search successful! Found {len(result_list)} results")

        if result_list:
            print("\n  Results:")
            for i, result in enumerate(result_list[:3], 1):
                record = result.record
                print(f"\n  [{i}] Score: {result.score:.2f}")

                # Try to get basic info
                if hasattr(record, 'name'):
                    print(f"      Name: {record.name}")
                if hasattr(record, 'srm_id'):
                    print(f"      SRM ID: {record.srm_id}")
                if hasattr(record, 'id'):
                    print(f"      ID: {record.id}")

                # Print all available fields
                print(f"      Available fields: {dir(record)}")
        else:
            print("⚠ No results found (index might be empty)")
            print("\n  Trying a broader search with '*'...")
            results = await store.search("*", top_k=1)
            result_list = []
            async for result in results:
                result_list.append(result)
            if result_list:
                print(f"  Found {len(result_list)} documents in index")
                record = result_list[0].record
                print(f"  Sample record fields: {[attr for attr in dir(record) if not attr.startswith('_')]}")
            else:
                print("  Index appears to be empty!")

        return True

    except Exception as e:
        print(f"✗ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_search())
    if success:
        print("\n" + "=" * 80)
        print("AZURE SEARCH IS WORKING ✓")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("AZURE SEARCH HAS ISSUES ✗")
        print("=" * 80)
        print("\nPlease check:")
        print("1. Azure Search endpoint, API key, and index name in .env")
        print("2. Index exists in Azure Portal")
        print("3. Index has documents")
        print("4. API key has read permissions")
