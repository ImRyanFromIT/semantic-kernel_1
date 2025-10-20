"""
Main entry point for the SRM Archivist Agent.

Implements continuous email monitoring with Semantic Kernel ChatCompletionAgent.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.contents import ChatHistory

from .config import load_config, validate_config
from .models.agent_config import AgentConfig
from .utils.graph_client import GraphClient
from .utils.state_manager import StateManager
from .utils.error_handler import ErrorHandler, ErrorType
from .plugins.email_plugin import EmailPlugin
from .plugins.state_plugin import StatePlugin
from .plugins.search_plugin import SearchPlugin
from .plugins.classification_plugin import ClassificationPlugin
from .plugins.extraction_plugin import ExtractionPlugin
from .utils.response_handler import ResponseHandler


class SrmArchivistAgent:
    """
    SRM Archivist Agent - monitors email inbox and processes SRM change requests.
    
    Uses Semantic Kernel ChatCompletionAgent with continuous monitoring loop.
    """
    
    def __init__(self, config_file: str = "agent_config.yaml", test_mode: bool = False):
        """
        Initialize the SRM Archivist Agent.
        
        Args:
            config_file: Path to configuration file
            test_mode: If True, use file-based email reading from test_emails/Inbox/ directory
        """
        self.config_file = config_file
        self.test_mode = test_mode
        self.config: Optional[AgentConfig] = None
        self.kernel: Optional[Kernel] = None
        self.agent: Optional[ChatCompletionAgent] = None
        self.error_handler: Optional[ErrorHandler] = None
        self.state_manager: Optional[StateManager] = None
        self.graph_client: Optional[GraphClient] = None
        self.response_handler: Optional[ResponseHandler] = None
        
        # Plugins
        self.email_plugin: Optional[EmailPlugin] = None
        self.state_plugin: Optional[StatePlugin] = None
        self.search_plugin: Optional[SearchPlugin] = None
        self.classification_plugin: Optional[ClassificationPlugin] = None
        self.extraction_plugin: Optional[ExtractionPlugin] = None
        
        # Process workflows
        self.srm_help_process = None
        
        # Control flags
        self.running = False
        self.shutdown_requested = False
        
        # Setup logging
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        # Ensure state directory is used for logs
        agent_dir = Path(__file__).parent
        state_dir = agent_dir / 'state'
        state_dir.mkdir(exist_ok=True)
        log_file = state_dir / 'agent_actions.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(str(log_file)),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Suppress verbose logging from SK internal components
        logging.getLogger('semantic_kernel.kernel').setLevel(logging.WARNING)
        logging.getLogger('semantic_kernel.functions').setLevel(logging.WARNING)
        logging.getLogger('semantic_kernel.processes').setLevel(logging.WARNING)
        logging.getLogger('opentelemetry').setLevel(logging.WARNING)
        
        # Keep our agent logs at INFO level
        logging.getLogger('agent').setLevel(logging.INFO)
    
    async def initialize(self) -> bool:
        """
        Initialize the agent and all components.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.logger.info("Initializing SRM Archivist Agent...")
            
            # Load configuration
            self.config = load_config(self.config_file)
            
            # Log update mode
            update_mode = "MOCK (no changes will be made)" if self.config.mock_updates else "LIVE (will update index)"
            self.logger.info(f"Update mode: {update_mode}")
            
            # Validate configuration
            issues = validate_config(self.config)
            if issues:
                self.logger.error(f"Configuration validation failed: {issues}")
                return False
            
            # Initialize error handler
            self.error_handler = ErrorHandler(
                max_retries=self.config.max_retries_api_calls,
                retry_delay=self.config.retry_delay_seconds,
                logger=self.logger
            )
            
            # Initialize state manager with agent folder path
            from pathlib import Path
            agent_dir = Path(__file__).parent
            state_file_path = str(agent_dir / self.config.state_file)
            self.state_manager = StateManager(state_file_path)
            
            # Initialize Response Handler (will be fully configured after Graph client)
            
            # Initialize Graph client
            if self.config.graph_api:
                self.graph_client = GraphClient(
                    tenant_id=self.config.graph_api.tenant_id,
                    client_id=self.config.graph_api.client_id,
                    client_secret=self.config.graph_api.client_secret,
                    mailbox=self.config.graph_api.mailbox,
                    test_mode=self.test_mode
                )
                
                # Authenticate with Graph API
                auth_success = self.graph_client.authenticate()
                if not auth_success:
                    self.logger.error("Failed to authenticate with Microsoft Graph API")
                    return False
                
                # Initialize Response Handler
                self.response_handler = ResponseHandler(
                    graph_client=self.graph_client,
                    state_manager=self.state_manager,
                    support_team_email=self.config.support_team_email,
                    logger=self.logger
                )
            
            # Initialize Semantic Kernel
            await self._initialize_kernel()
            
            # Initialize ChatCompletionAgent
            await self._initialize_agent()
            
            # Initialize plugins
            await self._initialize_plugins()
            
            # Initialize processes
            self._initialize_processes()
            
            self.logger.info("SRM Archivist Agent initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize agent: {e}")
            return False
    
    async def _initialize_kernel(self) -> None:
        """Initialize Semantic Kernel with services."""
        # Import kernel builder from existing codebase
        from src.utils.kernel_builder import create_kernel
        
        self.kernel = create_kernel()
        self.logger.info("Semantic Kernel initialized")
    
    async def _initialize_agent(self) -> None:
        """Initialize ChatCompletionAgent."""
        self.agent = ChatCompletionAgent(
            kernel=self.kernel,
            name=self.config.agent_name,
            instructions=(
                f"{self.config.description}\n\n"
                "You are an intelligent email processing agent that:\n"
                "1. Monitors email inbox for SRM change requests\n"
                "2. Classifies emails appropriately\n" 
                "3. Extracts structured data from requests\n"
                "4. Updates Azure AI Search index\n"
                "5. Provides helpful responses to users\n\n"
                "Always be professional, helpful, and accurate in your responses."
            )
        )
        self.logger.info("ChatCompletionAgent initialized")
    
    async def _initialize_plugins(self) -> None:
        """Initialize all plugins and add to kernel."""
        # Initialize plugins
        self.email_plugin = EmailPlugin(self.graph_client, self.error_handler)
        self.state_plugin = StatePlugin(self.state_manager, self.error_handler)
        
        if self.config.azure_search:
            self.search_plugin = SearchPlugin(
                search_endpoint=self.config.azure_search.endpoint,
                index_name=self.config.azure_search.index_name,
                api_key=self.config.azure_search.api_key,
                error_handler=self.error_handler,
                mock_updates=self.config.mock_updates
            )
        
        self.classification_plugin = ClassificationPlugin(self.kernel, self.error_handler)
        self.extraction_plugin = ExtractionPlugin(self.kernel, self.error_handler)
        
        # Add plugins to kernel
        self.kernel.add_plugin(self.email_plugin, "email")
        self.kernel.add_plugin(self.state_plugin, "state")
        if self.search_plugin:
            self.kernel.add_plugin(self.search_plugin, "search")
        self.kernel.add_plugin(self.classification_plugin, "classification")
        self.kernel.add_plugin(self.extraction_plugin, "extraction")
        
        self.logger.info("All plugins initialized and added to kernel")
    
    def _initialize_processes(self) -> None:
        """Initialize process workflows."""
        from .processes.srm_help_process import create_srm_help_process
        
        # Build SRM Help Process
        self.srm_help_process = create_srm_help_process().build()
        
        self.logger.info("SRM Help Process initialized with SK Process framework")
    
    async def run(self) -> None:
        """
        Run the main agent monitoring loop.
        
        Continuously monitors email inbox and processes requests.
        """
        if not await self.initialize():
            self.logger.error("Failed to initialize agent. Exiting.")
            return
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.running = True
        self.logger.info(f"Starting email monitoring loop (interval: {self.config.email_scan_interval_seconds}s)")
        
        try:
            while self.running and not self.shutdown_requested:
                try:
                    # Run email intake process - this does all the work
                    await self._run_email_intake_cycle()
                    
                    # Check for shutdown before sleeping
                    if self.shutdown_requested:
                        break
                    
                    # Wait for next cycle with periodic checks for shutdown
                    for _ in range(self.config.email_scan_interval_seconds):
                        if self.shutdown_requested:
                            break
                        await asyncio.sleep(1)
                    
                except KeyboardInterrupt:
                    self.logger.info("Received keyboard interrupt in main loop")
                    break
                except Exception as e:
                    self.error_handler.handle_error(
                        ErrorType.UNKNOWN,
                        e,
                        "main_monitoring_loop",
                        escalate=True
                    )
                    
                    # Check for shutdown before retry delay
                    if self.shutdown_requested:
                        break
                    
                    # Continue running unless it's a critical error
                    await asyncio.sleep(self.config.retry_delay_seconds)
        
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        
        finally:
            await self._shutdown()
    
    async def _run_email_intake_cycle(self) -> None:
        """
        Run one cycle of the Email Intake Process.
        
        This method is a pure orchestrator - it just starts the process and lets it do all the work.
        """
        from semantic_kernel.processes.kernel_process import KernelProcessEvent
        from semantic_kernel.processes.local_runtime.local_kernel_process import start
        from .processes.email_intake_process import EmailIntakeProcess
        
        try:
            self.logger.debug("Starting Email Intake Process")
            
            # Build the email intake process
            if not hasattr(self, 'email_intake_process'):
                self.email_intake_process = EmailIntakeProcess.create_process().build()
            
            # Prepare dependencies to inject
            dependencies = {
                "kernel": self.kernel,
                "config": self.config,
                "state_manager": self.state_manager,
                "graph_client": self.graph_client,
                "response_handler": self.response_handler,
                "srm_help_process": self.srm_help_process,
                "logger": self.logger,
            }
            
            # Start the process - it handles everything
            async with await start(
                process=self.email_intake_process,
                kernel=self.kernel,
                initial_event=KernelProcessEvent(
                    id=EmailIntakeProcess.ProcessEvents.StartProcess.value,
                    data=dependencies
                ),
                max_supersteps=100,
            ) as process_context:
                # Process executes automatically
                final_state = await process_context.get_state()
            
            self.logger.debug("Email Intake Process completed")
            
        except Exception as e:
            self.logger.error(f"Error in Email Intake Process: {e}")
            raise
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
        self.shutdown_requested = True
    
    async def _shutdown(self) -> None:
        """Perform graceful shutdown."""
        self.logger.info("Shutting down SRM Archivist Agent...")
        
        self.running = False
        
        # Save any pending state
        try:
            if self.state_manager:
                # Ensure all state is written
                pass
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        
        self.logger.info("SRM Archivist Agent shutdown complete")


async def main():
    """Main entry point."""
    agent = SrmArchivistAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
