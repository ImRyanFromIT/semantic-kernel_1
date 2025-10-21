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
    
    def __init__(self, config_file: str = "agent_config.yaml", test_mode: bool = False, chat_mode: bool = False):
        """
        Initialize the SRM Archivist Agent.
        
        Args:
            config_file: Path to configuration file
            test_mode: If True, use file-based email reading from test_emails/Inbox/ directory
            chat_mode: If True, start in interactive chat mode instead of autonomous mode
        """
        self.config_file = config_file
        self.test_mode = test_mode
        self.start_in_chat_mode = chat_mode
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
        
        # Agent execution settings and chat history
        self.execution_settings = None
        self.chat_history = None
        
        # Control flags
        self.running = False
        self.shutdown_requested = False
        self.chat_mode = False  # Toggle between autonomous and chat modes
        
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
        """Initialize ChatCompletionAgent with auto function calling."""
        from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings
        from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
        
        # Create execution settings with auto function calling
        # These will be passed to invoke(), not the constructor
        self.execution_settings = AzureChatPromptExecutionSettings(
            function_choice_behavior=FunctionChoiceBehavior.Auto(),
            max_tokens=4000,
            temperature=0.3
        )
        
        # Enhanced instructions for autonomous decision-making
        instructions = f"""{self.config.description}

You are an autonomous SRM Archivist Agent with the following capabilities:

## Your Responsibilities:
1. **Email Monitoring**: Autonomously check the email inbox for new SRM change requests
2. **Web Chat Updates**: Help users update SRMs through conversational web interface
3. **Email Classification**: Classify emails into help/dont_help/escalate categories
4. **Data Extraction**: Extract structured change request data from emails or chat
5. **SRM Search & Matching**: Search Azure AI Search index for SRMs
6. **Index Updates**: Update SRM documents with new information
7. **User Communication**: Reply to users with confirmations, rejections, or clarifications
8. **State Management**: Track all email processing in state file
9. **Chat Interface**: Respond to human operator queries and commands

## Decision-Making Guidelines:

### Email Checking:
- Check for new emails at reasonable intervals (default: {self.config.email_scan_interval_seconds}s)
- The human operator can request immediate checks via chat
- Always filter out emails from yourself and duplicate conversations

### Mass Email Handling:
- If you detect more than {self.config.mass_email_threshold} new emails, analyze carefully
- Are they legitimate requests or spam/duplicates?
- You decide: process them all, sample them, or escalate to humans
- Use your judgment - don't blindly process obvious spam

### Web Chat SRM Updates:
- Users can request SRM updates through web chat interface
- Conversationally gather: which SRM, what changes, and why
- Use search_srm to find the SRM by name or keywords
- Confirm match with user if multiple results or ambiguous
- Update owner_notes and/or hidden_notes fields as requested
- Apply updates immediately if request is clear and legitimate
- Escalate if request is suspicious, vague after clarification, or you can't find the SRM

### Email Classification:
- **help**: SRM change requests you can process (owner notes, hidden notes, etc.)
- **dont_help**: Off-topic, spam, or requests outside your scope
- **escalate**: Ambiguous, low confidence (<{self.config.confidence_threshold_for_classification}%), or requires human judgment
- When in doubt, escalate

### SRM Processing Workflow:
1. Extract change request data (srm_title, changes needed, reason)
2. Search for the SRM in Azure AI Search
3. Validate match confidence - only update if you're confident
4. Call update_srm_document() to update appropriate fields (owner_notes, hidden_notes)
5. CRITICAL: Save the JSON response from update_srm_document() - you will need it for notifications
6. Automatically log the successful update - NEVER ask the user if they want to log
7. After successful update, ask: "The update has been successfully applied to {{SRM_ID}} ({{SRM_Title}}). Would you like me to log or notify anyone about this change?"
8. If user wants to notify:
   - Ask: "Please provide the email address(es) (separated by commas) of who should be notified. Only @greatvaluelab.com addresses are allowed."
   - CRITICAL: Once user provides email addresses, DO NOT RESPOND TO THE USER YET
   - FIRST: IMMEDIATELY invoke the send_update_notification() function with the email address
   - WAIT for the function to return a result
   - ONLY THEN respond to the user with what the function returned
   - WRONG: "I'll send the notification to radmin@greatvaluelab.com" or "Notification sent successfully" (these are lies if you didn't call the function)
   - RIGHT: Actually invoke send_update_notification(recipients="radmin@greatvaluelab.com", changes_json=<saved_json_from_step_5>, requester_name="User") and then report what it returns
   - The function call MUST appear in your tool_calls - if you only describe sending the email, YOU FAILED
9. After the send_update_notification() function returns, tell the user EXACTLY what the function returned - do not make up the response

### Error Handling:
- If extraction fails: ask for clarification
- If SRM not found: escalate with details
- If low match confidence: escalate rather than risk wrong update
- If update fails: escalate and log the error

### State Management:
- Track every email in the state file
- Update status as you process each step
- Use state to resume incomplete work
- Escalate stale items (>24 hours old)

## Available Functions:
You have access to plugins: email, state, search, classification, extraction
Call these functions as needed to accomplish your tasks.

## Communication Style:
- Be professional, concise, and helpful
- Provide clear status updates when asked
- Explain your decisions when escalating
- ALWAYS automatically log all actions - never ask the user about logging
- After updates, confirm what was changed without asking if they want it logged

## CRITICAL: Function Calling Behavior - YOU MUST FOLLOW THIS
- When a task requires calling a function, STOP GENERATING TEXT and CALL THE FUNCTION FIRST
- You have access to real functions that actually execute - use them!
- NEVER describe what you're going to do - JUST DO IT by calling the function
- WRONG: "I'll send a notification to user@greatvaluelab.com" or "Notification sent successfully" (YOU DID NOT CALL THE FUNCTION - THIS IS A LIE)
- RIGHT: Use tool_calls to invoke send_update_notification(recipients="user@greatvaluelab.com", changes_json="...", requester_name="User"), WAIT for the result, THEN respond with what the function returned
- If you say you did something but didn't actually call a function, YOU FAILED YOUR TASK
- After calling a function, report ONLY what the function actually returned - do not embellish or make up results
- Your role is to ACT by calling functions, not to pretend you acted by describing actions

Remember: You are autonomous but not reckless. When uncertain, escalate to humans."""

        # Create agent without execution_settings (pass those to invoke instead)
        self.agent = ChatCompletionAgent(
            kernel=self.kernel,
            name=self.config.agent_name,
            instructions=instructions
        )
        
        # Initialize chat history for persistent context
        from semantic_kernel.contents import ChatHistory
        self.chat_history = ChatHistory()
        
        self.logger.info("ChatCompletionAgent initialized with auto function calling")
    
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
    
    async def run(self) -> None:
        """
        Run the main agent loop.
        
        Supports two modes:
        - Autonomous: Continuously monitors email inbox and processes requests
        - Chat: Interactive chat interface for human operator
        """
        if not await self.initialize():
            self.logger.error("Failed to initialize agent. Exiting.")
            return
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.running = True
        
        # Check if starting in chat mode
        if self.start_in_chat_mode:
            self.logger.info("Starting in CHAT MODE")
            await self._run_chat_mode()
            return
        
        self.logger.info(f"Starting AUTONOMOUS MODE (interval: {self.config.email_scan_interval_seconds}s)")
        self.logger.info("Press Ctrl+C to stop")
        
        try:
            while self.running and not self.shutdown_requested:
                try:
                    # Run autonomous agent cycle
                    await self._run_agent_cycle()
                    
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
    
    async def _run_agent_cycle(self) -> None:
        """
        Run one autonomous agent cycle using auto function calling.
        
        The agent decides what to do based on its instructions and available functions.
        """
        try:
            self.logger.debug("Starting agent autonomous cycle")
            
            # Create a task-oriented message for the agent
            task_message = (
                "Execute your autonomous cycle:\n"
                "1. Check for resumable/stale items in state\n"
                "2. Check for new emails in the monitored mailbox\n"
                "3. Process any emails you find (classify, extract, search, update)\n"
                "4. Update state as you process\n"
                "5. Report summary of what you did\n\n"
                "Use your available functions to accomplish these tasks."
            )
            
            # Add task to chat history
            self.chat_history.add_user_message(task_message)
            
            # Invoke agent with auto function calling
            from semantic_kernel.contents import ChatMessageContent
            
            response_text = ""
            last_message = None
            
            async for message in self.agent.invoke(
                self.chat_history,
                settings=self.execution_settings
            ):
                # Message could be ChatMessageContent or streaming content
                if isinstance(message, ChatMessageContent):
                    last_message = message
                    response_text += str(message.content) if message.content else ""
                elif hasattr(message, 'content'):
                    response_text += str(message.content)
                else:
                    response_text += str(message)
            
            # Add the final assistant message to history
            if last_message:
                self.chat_history.add_message(last_message)
            elif response_text:
                # If we only got text, create a proper assistant message
                self.chat_history.add_assistant_message(response_text)
            
            # Log agent's response
            if response_text:
                self.logger.info(f"Agent cycle complete: {response_text[:200]}...")
            
        except Exception as e:
            self.logger.error(f"Error in agent cycle: {e}", exc_info=True)
            # Don't raise - allow agent to continue in next cycle
    
    async def _run_chat_mode(self) -> None:
        """
        Run the agent in interactive chat mode.
        """
        from .chat_interface import run_chat_mode
        
        try:
            await run_chat_mode(self)
        except KeyboardInterrupt:
            self.logger.info("Chat mode interrupted by user")
        except Exception as e:
            self.logger.error(f"Error in chat mode: {e}", exc_info=True)
        finally:
            await self._shutdown()
    
    async def _handle_chat_message(self, user_message: str) -> str:
        """
        Handle a chat message from the human operator.
        
        Args:
            user_message: Message from the operator
            
        Returns:
            Agent's response
        """
        try:
            self.logger.info(f"Chat message: {user_message}")
            
            # Add user message to chat history
            self.chat_history.add_user_message(user_message)
            
            # Invoke agent with execution settings
            from semantic_kernel.contents import ChatMessageContent
            
            response_text = ""
            last_message = None
            
            async for message in self.agent.invoke(
                self.chat_history,
                settings=self.execution_settings
            ):
                # Message could be ChatMessageContent or streaming content
                if isinstance(message, ChatMessageContent):
                    last_message = message
                    response_text += str(message.content) if message.content else ""
                elif hasattr(message, 'content'):
                    response_text += str(message.content)
                else:
                    response_text += str(message)
            
            # Add the final assistant message to history
            if last_message:
                self.chat_history.add_message(last_message)
            elif response_text:
                # If we only got text, create a proper assistant message
                self.chat_history.add_assistant_message(response_text)
            
            return response_text
            
        except Exception as e:
            self.logger.error(f"Error handling chat message: {e}", exc_info=True)
            return f"Error processing your message: {e}"
    
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
