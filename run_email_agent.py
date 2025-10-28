#!/usr/bin/env python3
"""
Email Monitoring Agent Service

Standalone service for the SRM Archivist email monitoring agent.
Continuously monitors email inbox for SRM change requests and processes them.

Usage:
    python run_email_agent.py
    python run_email_agent.py --config config/agent_config.yaml
    python run_email_agent.py --test  # Test mode with file-based emails
"""

import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from semantic_kernel.processes.kernel_process import KernelProcessEvent
from semantic_kernel.processes.local_runtime.local_kernel_process import start

from src.utils.kernel_builder import create_kernel
from src.utils.config import load_agent_config
from src.utils.state_manager import StateManager
from src.utils.graph_client import GraphClient
from src.utils.response_handler import ResponseHandler
from src.utils.telemetry import TelemetryLogger
from src.utils.store_factory import create_vector_store
from src.processes.agent.email_intake_process import EmailIntakeProcess
from src.processes.agent.srm_help_process import SrmHelpProcess


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/email_agent.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Reduce verbose logging from Semantic Kernel process framework
logging.getLogger('semantic_kernel.processes').setLevel(logging.WARNING)
logging.getLogger('semantic_kernel.processes.local_runtime').setLevel(logging.WARNING)


class EmailAgentService:
    """Email Monitoring Agent Service."""

    def __init__(self, config_path: str = "config/agent_config.yaml", test_mode: bool = False):
        """
        Initialize the email agent service.

        Args:
            config_path: Path to agent configuration file
            test_mode: If True, use file-based email reader instead of Graph API
        """
        self.config_path = config_path
        self.test_mode = test_mode
        self.config = None
        self.kernel = None
        self.state_manager = None
        self.graph_client = None
        self.response_handler = None
        self.telemetry = None
        self.vector_store = None
        self.email_intake_process = None
        self.srm_help_process = None

    async def initialize(self) -> bool:
        """
        Initialize all components.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("=" * 80)
            logger.info("SRM ARCHIVIST EMAIL MONITORING AGENT")
            logger.info("=" * 80)

            # Load configuration
            logger.info(f"Loading configuration from {self.config_path}")
            self.config = load_agent_config(self.config_path)
            logger.info(f"✓ Configuration loaded: {self.config.agent_name}")

            # Create kernel
            logger.info("Initializing Semantic Kernel...")
            self.kernel = create_kernel()
            logger.info("✓ Kernel initialized")

            # Initialize state manager (needed by plugins)
            logger.info("Initializing state manager...")
            state_file = Path(self.config.state_file)
            state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_manager = StateManager(str(state_file))
            records = self.state_manager.read_state()
            logger.info(f"✓ State manager initialized ({len(records)} existing records)")

            # Initialize Graph client (or file reader for testing)
            if self.test_mode:
                logger.info("Initializing file-based email reader (TEST MODE)...")
                # FileEmailReader is wrapped in GraphClient for test mode
                self.graph_client = GraphClient(
                    tenant_id="test",
                    client_id="test",
                    client_secret="test",
                    mailbox="test@test.com",
                    test_mode=True
                )
                # Authenticate (will succeed in test mode)
                self.graph_client.authenticate()
                logger.info("✓ File-based email reader initialized (test mode)")
            else:
                logger.info("Initializing Microsoft Graph API client...")
                if not self.config.graph_api:
                    logger.error("Graph API configuration not found")
                    return False

                self.graph_client = GraphClient(
                    tenant_id=self.config.graph_api.tenant_id,
                    client_id=self.config.graph_api.client_id,
                    client_secret=self.config.graph_api.client_secret,
                    mailbox=self.config.graph_api.mailbox
                )
                # Authenticate with Microsoft Graph API
                if not self.graph_client.authenticate():
                    logger.error("Failed to authenticate with Graph API")
                    return False
                logger.info("✓ Graph API client initialized and authenticated")

            # Initialize response handler
            logger.info("Initializing response handler...")
            # Get support team email from environment or config
            support_team_email = os.getenv('SUPPORT_TEAM_EMAIL', 'support@example.com')
            self.response_handler = ResponseHandler(
                graph_client=self.graph_client,
                state_manager=self.state_manager,
                support_team_email=support_team_email
            )
            logger.info("✓ Response handler initialized")

            # Initialize telemetry
            logger.info("Initializing telemetry...")
            self.telemetry = TelemetryLogger()
            logger.info("✓ Telemetry initialized")

            # Initialize vector store (for SRM search)
            logger.info("Initializing vector store...")
            embedding_service = self.kernel.get_service("embedding")
            self.vector_store = create_vector_store(embedding_service)

            # Ensure collection exists
            await self.vector_store.ensure_collection_exists()
            logger.info("✓ Vector store initialized")

            # Load plugins (after all dependencies are ready)
            logger.info("Loading agent plugins...")
            self._load_plugins()
            logger.info("✓ Plugins loaded")

            # Build processes
            logger.info("Building email intake process...")
            email_intake_builder = EmailIntakeProcess.create_process()
            self.email_intake_process = email_intake_builder.build()
            logger.info("✓ Email intake process built")

            logger.info("Building SRM help process...")
            srm_help_builder = SrmHelpProcess.create_process()
            self.srm_help_process = srm_help_builder.build()
            logger.info("✓ SRM help process built")

            logger.info("=" * 80)
            logger.info("INITIALIZATION COMPLETE")
            logger.info("=" * 80)

            return True

        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}", exc_info=True)
            return False

    def _load_plugins(self):
        """Load all agent plugins into the kernel."""
        from src.plugins.agent.classification_plugin import ClassificationPlugin
        from src.plugins.agent.extraction_plugin import ExtractionPlugin
        from src.plugins.agent.search_plugin import SearchPlugin
        from src.plugins.agent.clarification_plugin import ClarificationPlugin
        from src.plugins.agent.state_plugin import StatePlugin
        from src.utils.error_handler import ErrorHandler

        # Create error handler for plugins
        error_handler = ErrorHandler()

        # Instantiate and register class-based plugins
        try:
            classification_plugin = ClassificationPlugin(
                kernel=self.kernel,
                error_handler=error_handler
            )
            self.kernel.add_plugin(classification_plugin, plugin_name="classification")
            logger.info("✓ Loaded classification plugin")
        except Exception as e:
            logger.error(f"Failed to load classification plugin: {e}", exc_info=True)

        try:
            extraction_plugin = ExtractionPlugin(
                kernel=self.kernel,
                error_handler=error_handler
            )
            self.kernel.add_plugin(extraction_plugin, plugin_name="extraction")
            logger.info("✓ Loaded extraction plugin")
        except Exception as e:
            logger.error(f"Failed to load extraction plugin: {e}", exc_info=True)

        try:
            # Get Azure Search config from environment
            import os
            search_endpoint = os.getenv('AZURE_AI_SEARCH_ENDPOINT', '')
            index_name = os.getenv('AZURE_AI_SEARCH_INDEX_NAME', 'srm-catalog')
            api_key = os.getenv('AZURE_AI_SEARCH_API_KEY', '')

            search_plugin = SearchPlugin(
                search_endpoint=search_endpoint,
                index_name=index_name,
                api_key=api_key,
                error_handler=error_handler,
                mock_updates=False  # Actually update the index
            )
            self.kernel.add_plugin(search_plugin, plugin_name="search")
            logger.info("✓ Loaded search plugin")
        except Exception as e:
            logger.error(f"Failed to load search plugin: {e}", exc_info=True)

        try:
            clarification_plugin = ClarificationPlugin(
                response_handler=self.response_handler,
                state_manager=self.state_manager,
                graph_client=self.graph_client
            )
            self.kernel.add_plugin(clarification_plugin, plugin_name="clarification")
            logger.info("✓ Loaded clarification plugin")
        except Exception as e:
            logger.error(f"Failed to load clarification plugin: {e}", exc_info=True)

        try:
            state_plugin = StatePlugin(
                state_manager=self.state_manager,
                error_handler=error_handler
            )
            self.kernel.add_plugin(state_plugin, plugin_name="state")
            logger.info("✓ Loaded state plugin")
        except Exception as e:
            logger.error(f"Failed to load state plugin: {e}", exc_info=True)

    async def run_once(self) -> Dict[str, Any]:
        """
        Run one cycle of email processing.

        Returns:
            Dictionary with processing results
        """
        try:
            logger.info("\n" + "=" * 80)
            logger.info(f"EMAIL PROCESSING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 80)

            # Prepare initial event data with all dependencies
            initial_data = {
                "kernel": self.kernel,
                "state_manager": self.state_manager,
                "graph_client": self.graph_client,
                "response_handler": self.response_handler,
                "config": self.config,
                "vector_store": self.vector_store,
                "srm_help_process": self.srm_help_process,
            }

            # Start the email intake process
            async with await start(
                process=self.email_intake_process,
                kernel=self.kernel,
                initial_event=KernelProcessEvent(
                    id=EmailIntakeProcess.ProcessEvents.StartProcess.value,
                    data=initial_data
                ),
                max_supersteps=100,
            ) as process_context:
                # Process executes automatically
                final_state = await process_context.get_state()

                logger.info("Email processing cycle completed")
                logger.info("=" * 80 + "\n")

                return {"status": "completed", "state": final_state}

        except Exception as e:
            logger.error(f"Error in processing cycle: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    async def run_continuous(self, scan_interval: int = None):
        """
        Run continuous email monitoring.

        Args:
            scan_interval: Seconds between scans (from config if not specified)
        """
        if scan_interval is None:
            scan_interval = self.config.email_scan_interval_seconds

        logger.info(f"Starting continuous monitoring (scan interval: {scan_interval}s)")
        logger.info("Press Ctrl+C to stop\n")

        cycle_count = 0

        try:
            while True:
                cycle_count += 1

                # Run one processing cycle
                await self.run_once()

                # Wait before next cycle
                logger.info(f"Waiting {scan_interval} seconds before next scan...")
                logger.info(f"(Completed {cycle_count} cycles so far)\n")
                await asyncio.sleep(scan_interval)

        except KeyboardInterrupt:
            logger.info("\n\nReceived interrupt signal. Shutting down gracefully...")
            logger.info(f"Total cycles completed: {cycle_count}")
        except Exception as e:
            logger.error(f"Fatal error in continuous monitoring: {e}", exc_info=True)
            raise


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SRM Archivist Email Monitoring Agent"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/agent_config.yaml",
        help="Path to agent configuration file"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode (use file-based email reader)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one cycle only (don't run continuously)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        help="Scan interval in seconds (overrides config)"
    )

    args = parser.parse_args()

    # Create logs directory
    Path("logs").mkdir(exist_ok=True)

    # Initialize service
    service = EmailAgentService(
        config_path=args.config,
        test_mode=args.test
    )

    # Initialize components
    if not await service.initialize():
        logger.error("Failed to initialize service. Exiting.")
        sys.exit(1)

    # Run service
    if args.once:
        logger.info("Running single processing cycle...")
        result = await service.run_once()
        logger.info(f"Result: {result['status']}")
    else:
        await service.run_continuous(scan_interval=args.interval)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nShutdown complete.")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
