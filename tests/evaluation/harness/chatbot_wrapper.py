"""
Chatbot wrapper for evaluation.

This module provides a simple interface to run queries against the chatbot
without starting the full FastAPI server.
"""

import asyncio
import uuid
from typing import Dict, Any

from semantic_kernel.processes.kernel_process import KernelProcessEvent
from semantic_kernel.processes.local_runtime.local_kernel_process import start

from src.utils.kernel_builder import create_kernel
from src.utils.telemetry import TelemetryLogger
from src.utils.store_factory import create_vector_store
from src.data.data_loader import SRMDataLoader
from src.processes.discovery.srm_discovery_process import SRMDiscoveryProcess


class ChatbotWrapper:
    """
    Wrapper for the SRM chatbot to use in evaluations.
    """

    def __init__(self):
        """Initialize the chatbot wrapper."""
        self.kernel = None
        self.vector_store = None
        self.srm_process = None
        self.telemetry = None
        self._initialized = False

    async def initialize(self):
        """
        Initialize the kernel, vector store, and process.
        Call this once before running queries.
        """
        if self._initialized:
            return

        print("[*] Initializing chatbot for evaluation...")

        # Create kernel
        self.kernel = create_kernel()

        # Get embedding service
        embedding_service = self.kernel.get_service("embedding")

        # Create vector store
        self.vector_store = create_vector_store(embedding_service)

        # Load data if using in-memory store
        import os
        store_type = os.getenv('VECTOR_STORE_TYPE', 'azure_search').lower()

        if store_type == 'in_memory':
            data_loader = SRMDataLoader(self.vector_store)
            await data_loader.load_and_index("data/srm_catalog.csv")
        else:
            # Azure AI Search - ensure collection exists
            await self.vector_store.ensure_collection_exists()

        # Build process definition
        srm_process_builder = SRMDiscoveryProcess.create_process()
        self.srm_process = srm_process_builder.build()

        # Initialize telemetry
        self.telemetry = TelemetryLogger()

        self._initialized = True
        print("[+] Chatbot initialized for evaluation")

    async def query(self, user_query: str) -> str:
        """
        Run a single query through the chatbot.

        Args:
            user_query: The user's question

        Returns:
            The chatbot's response
        """
        if not self._initialized:
            await self.initialize()

        # Generate session ID
        session_id = str(uuid.uuid4())[:8]

        # Create result container
        result_container = {}
        initial_data = {
            "user_query": user_query,
            "vector_store": self.vector_store,
            "session_id": session_id,
            "kernel": self.kernel,
            "result_container": result_container,
            "feedback_processor": None,  # Not needed for evaluation
        }

        try:
            # Start process
            async with await start(
                process=self.srm_process,
                kernel=self.kernel,
                initial_event=KernelProcessEvent(
                    id=SRMDiscoveryProcess.ProcessEvents.StartProcess.value,
                    data=initial_data
                ),
                max_supersteps=50,
            ) as process_context:
                # Get final state
                await process_context.get_state()

                # Extract result
                result_data = result_container

                if result_data:
                    if 'rejection_message' in result_data:
                        return f"[!] {result_data['rejection_message']}"
                    elif 'clarification' in result_data:
                        return f"[?] {result_data['clarification']}"
                    elif 'final_answer' in result_data:
                        return result_data['final_answer']

                return "Process completed but no result was generated."

        except Exception as e:
            return f"[!] An error occurred: {str(e)}"

    def query_sync(self, user_query: str) -> str:
        """
        Synchronous wrapper for query.

        Args:
            user_query: The user's question

        Returns:
            The chatbot's response
        """
        return asyncio.run(self.query(user_query))
