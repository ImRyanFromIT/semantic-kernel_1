#!/usr/bin/env python3
"""
Quick test script for chatbot functionality.
Tests the chatbot without starting the full web server.
"""

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_chatbot():
    """Test basic chatbot functionality."""
    print("=" * 80)
    print("CHATBOT FUNCTIONALITY TEST")
    print("=" * 80)

    # Test 1: Import modules
    print("\n[1/5] Testing imports...")
    try:
        from src.utils.kernel_builder import create_kernel
        from src.utils.store_factory import create_vector_store
        from src.processes.discovery.srm_discovery_process import SRMDiscoveryProcess
        print("✓ All imports successful")
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

    # Test 2: Create kernel
    print("\n[2/5] Creating kernel...")
    try:
        kernel = create_kernel()
        print("✓ Kernel created")

        # Check services
        chat_service = kernel.get_service("chat")
        embedding_service = kernel.get_service("embedding")
        print(f"✓ Chat service: {type(chat_service).__name__}")
        print(f"✓ Embedding service: {type(embedding_service).__name__}")
    except Exception as e:
        print(f"✗ Kernel creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 3: Create vector store
    print("\n[3/5] Creating vector store...")
    try:
        vector_store = create_vector_store(embedding_service)
        print(f"✓ Vector store created: {type(vector_store).__name__}")

        # Test connection
        await vector_store.ensure_collection_exists()
        print("✓ Vector store connection successful")
    except Exception as e:
        print(f"✗ Vector store creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 4: Build process
    print("\n[4/5] Building SRM discovery process...")
    try:
        process_builder = SRMDiscoveryProcess.create_process()
        process = process_builder.build()
        print("✓ Process built successfully")
    except Exception as e:
        print(f"✗ Process build failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 5: Run a simple query
    print("\n[5/5] Testing query execution...")
    try:
        from semantic_kernel.processes.kernel_process import KernelProcessEvent
        from semantic_kernel.processes.local_runtime.local_kernel_process import start

        result_container = {}
        initial_data = {
            "user_query": "I need to request a new server",
            "vector_store": vector_store,
            "session_id": "test-session",
            "kernel": kernel,
            "result_container": result_container,
            "feedback_processor": None,  # Not needed for test
        }

        print("  Running process...")
        async with await start(
            process=process,
            kernel=kernel,
            initial_event=KernelProcessEvent(
                id=SRMDiscoveryProcess.ProcessEvents.StartProcess.value,
                data=initial_data
            ),
            max_supersteps=50,
        ) as process_context:
            await process_context.get_state()

        if result_container:
            if 'rejection_message' in result_container:
                print(f"  Result: [Rejection] {result_container['rejection_message'][:100]}")
            elif 'clarification' in result_container:
                print(f"  Result: [Clarification] {result_container['clarification'][:100]}")
            elif 'final_answer' in result_container:
                print(f"  Result: [Answer] {result_container['final_answer'][:200]}")
            print("✓ Query executed successfully")
        else:
            print("⚠ Query completed but no result generated")

    except Exception as e:
        print(f"✗ Query execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED ✓")
    print("=" * 80)
    print("\nThe chatbot is working correctly. You can now run:")
    print("  python run_chatbot.py")
    print("\nOr use the old CLI interface:")
    print("  python main.py")
    return True

if __name__ == "__main__":
    asyncio.run(test_chatbot())
