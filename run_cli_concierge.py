#!/usr/bin/env python3
"""
CLI Concierge Agent

Interactive REPL agent for managing SRM metadata.
Uses Semantic Kernel with auto function calling to make API requests to chatbot service.

Usage:
    python run_cli_concierge.py [--debug]
"""

import asyncio
import sys
import logging
import argparse
from pathlib import Path

from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.contents import ChatHistory, ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior

from src.utils.kernel_builder import create_kernel
from src.plugins.cli_concierge.api_client_plugin import ConciergeAPIClientPlugin


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/cli_concierge.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Reduce verbose logging from SK
logging.getLogger('semantic_kernel').setLevel(logging.WARNING)


class CLIConciergeAgent:
    """CLI-based concierge agent for SRM metadata management."""

    def __init__(self, chatbot_url: str = "http://localhost:8000", debug: bool = False):
        """
        Initialize CLI concierge agent.

        Args:
            chatbot_url: URL of chatbot service (hardcoded for demo)
            debug: Enable debug output for function calls
        """
        self.chatbot_url = chatbot_url
        self.debug = debug
        self.kernel: Kernel | None = None
        self.agent: ChatCompletionAgent | None = None
        self.history: ChatHistory | None = None

    async def initialize(self) -> bool:
        """
        Initialize kernel, plugins, and agent.

        Returns:
            True if successful, False otherwise
        """
        try:
<<<<<<< HEAD:run_cli_maintainer.py
=======
            print("\n" + r"""
  _____ _____  __  __    _____                _
 / ____|  __ \|  \/  |  / ____|              (_)
| (___ | |__) | \  / | | |     ___  _ __   ___ _  ___ _ __ __ _  ___
 \___ \|  _  /| |\/| | | |    / _ \| '_ \ / __| |/ _ \ '__/ _` |/ _ \
 ____) | | \ \| |  | | | |___| (_) | | | | (__| |  __/ | | (_| |  __/
|_____/|_|  \_\_|  |_|  \_____\___/|_| |_|\___|_|\___|_|  \__, |\___|
                                                            __/ |
                 ~* AI At Your Service *~                  |___/
""")

>>>>>>> ba13b90 (refactor: rebrand CLI Maintainer to SRM Concierge):run_cli_concierge.py
            # Create kernel
            print("[*] Initializing Semantic Kernel...")
            self.kernel = create_kernel()
            print("[+] Kernel initialized")

            # Add API client plugin
            print(f"[*] Connecting to chatbot service at {self.chatbot_url}...")
            api_client = ConciergeAPIClientPlugin(base_url=self.chatbot_url)
            self.kernel.add_plugin(api_client, plugin_name="api_client")
            print("[+] API client plugin loaded")

            # Create agent
            print("[*] Creating concierge agent...")
            self.agent = ChatCompletionAgent(
                kernel=self.kernel,
                name="ConciergeAgent",
                instructions="""You are an SRM Concierge - a helpful AI assistant for Service Request Management.

Your role is to help users manage SRM (Service Request Model) metadata like owner notes.

CAPABILITIES:
- Search for SRMs by keywords or name
- View detailed SRM information
- Update owner notes and hidden notes for SRMs
<<<<<<< HEAD:run_cli_maintainer.py
- Display help information with current system state

HELP COMMAND:
When user types "help", follow these steps:
1. Call get_stats() to get current system state
2. Extract total_srms, temp_srms, and chatbot_url from response
3. Display this formatted response with actual values:

SRM Concierge - Your assistant for managing SRM metadata

WHAT I DO:
I help you search, view, and update SRM (Service Request Model) records.
I can work with individual SRMs or update many at once. I can also create
temporary SRMs for testing without modifying the permanent index.

CURRENT STATE:
• [total_srms] SRMs in permanent index
• [temp_srms] temporary SRMs active
• Connected to chatbot at [chatbot_url]

AVAILABLE COMMANDS:

SEARCH & VIEW:
  'show storage SRMs' or 'find AI SRMs' - Search for SRMs by keywords
  'show me SRM-001' - View specific SRM details
  'list all teams' - Show all teams in index
  'list all types' - Show service types (Services, Consultation, Support)

UPDATE:
  'update SRM-036 owner notes to Contact storage team first'
  'add hidden notes to SRM-036 saying Known issue with Dell arrays'

BATCH OPERATIONS (Coming Soon):
  'add owner notes to all Database Services SRMs saying Contact DBA first'
  'update all Consultation SRMs hidden notes to Requires design review'

TEMP SRMS (Coming Soon):
  'add temp SRM for cloud cost optimization by FinOps team'
  'list temp SRMs' - Show all temporary SRMs
  'delete temp SRM-TEMP-001'

OTHER:
  'help' - Show this message
  'quit' - Exit

Type any natural language request and I'll figure out what you need!
=======
>>>>>>> ba13b90 (refactor: rebrand CLI Maintainer to SRM Concierge):run_cli_concierge.py

EXAMPLE INTERACTIONS:
User: "show storage SRMs"
You: [Search and display table of storage-related SRMs]

User: "find AI SRMs"
You: [Search for "AI" and display matching SRMs in table format]

User: "show me SRM-001"
You: [Display full details including current notes]

User: "update SRM-036 owner_notes to Contact storage team before provisioning"
You: [Get SRM-036, show current owner_notes, ask for confirmation, then update]

User: "add hidden notes to SRM-036 saying 'Known issue with Dell arrays'"
You: [Get SRM-036, show current hidden_notes, ask for confirmation, then update]

KEY BEHAVIORS:
1. When user mentions an SRM by name, use search_srm to find the ID
2. Before updating, use get_srm_by_id to show current values
3. ALWAYS ask for confirmation before calling update_srm_metadata
4. After updating, show the before/after changes clearly

FORMATTING RULES:
5. ALWAYS display search results in this EXACT markdown table format:
   | SRM ID | Name | Category | Use Case Summary |
   |--------|------|----------|------------------|
   | SRM-XXX | ... | ... | ... |
6. Keep use case summaries to 1-2 sentences max

Be conversational, friendly, and helpful. Always confirm before making changes.""",
                function_choice_behavior=FunctionChoiceBehavior.Auto()
            )
            print("[+] Agent created with auto function calling enabled")

            # Initialize chat history
            self.history = ChatHistory()
            print("[+] Chat history initialized\n")

            # ASCII Art Banner
            print(r"""
  _____ _____  __  __    _____                _
 / ____|  __ \|  \/  |  / ____|              (_)
| (___ | |__) | \  / | | |     ___  _ __   ___ _  ___ _ __ __ _  ___
 \___ \|  _  /| |\/| | | |    / _ \| '_ \ / __| |/ _ \ '__/ _\ |/ _ \
 ____) | | \ \| |  | | | |___| (_) | | | | (__| |  __/ | | (_| |  __/
|_____/|_|  \_\_|  |_|  \_____\___/|_| |_|\___|_|\___|_|  \__, |\___|
                                                            __/ |
                 ~* AI At Your Service™ *~                 |___/
""")

            # Examples
            print("=" * 80)
            print("READY - What you can do:")
            print("  • Search for SRMs: 'show storage SRMs' or 'find AI SRMs'")
            print("  • View SRM details: 'show me SRM-001'")
            print("  • Update owner notes: 'update SRM-036 owner_notes to Contact storage team first'")
            print()
            print("Type 'quit' to exit")
            print("=" * 80 + "\n")

            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}", exc_info=True)
            print(f"\n[ERROR] Failed to initialize: {e}")
            return False

    async def run_repl(self):
        """Run the interactive REPL loop."""
        print("\nConcierge> ", end='', flush=True)

        while True:
            try:
                # Get user input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                user_input = user_input.strip()

                if not user_input:
                    print("\nConcierge> ", end='', flush=True)
                    continue

                # Check for quit
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\nThank you for using SRM Concierge. Goodbye!")
                    break

                # Add user message to history
                self.history.add_message(
                    ChatMessageContent(
                        role=AuthorRole.USER,
                        content=user_input
                    )
                )

                # Get agent response (auto function calling enabled)
                print()  # Newline before response

                # Track function calls for progress indicators
                seen_functions = set()

                async for response in self.agent.invoke_stream(self.history):
                    # Check for function calls in the response
                    if hasattr(response, 'items') and response.items:
                        for item in response.items:
                            # Check if this is a function call
                            if hasattr(item, 'function_name') and item.function_name:
                                func_name = item.function_name

                                # Show progress indicator only once per function call
                                if func_name not in seen_functions:
                                    seen_functions.add(func_name)

                                    if self.debug:
                                        # Debug mode: show function name and arguments
                                        args_str = ""
                                        if hasattr(item, 'arguments'):
                                            args_str = f" {item.arguments}"
                                        print(f"\n[DEBUG] Calling {func_name}{args_str}")
                                    else:
                                        # Normal mode: show friendly progress message
                                        if func_name == "search_srm":
                                            print("[*] Searching...", flush=True)
                                        elif func_name == "get_srm_by_id":
                                            print("[*] Getting details...", flush=True)
                                        elif func_name == "update_srm_metadata":
                                            print("[*] Updating...", flush=True)
                                        elif func_name == "get_stats":
                                            print("[*] Getting stats...", flush=True)

                    # Print the actual response content
                    if response.content:
                        print(response.content, end='', flush=True)

                print()  # Newline after response
                print("\nConcierge> ", end='', flush=True)

            except KeyboardInterrupt:
                print("\n\nInterrupted. Type 'quit' to exit.")
                print("\nConcierge> ", end='', flush=True)
            except Exception as e:
                logger.error(f"Error in REPL: {e}", exc_info=True)
                print(f"\n[ERROR] {e}")
                print("\nConcierge> ", end='', flush=True)


async def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="CLI Concierge Agent for SRM metadata management"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output for function calls"
    )
    args = parser.parse_args()

    # Create logs directory
    Path("logs").mkdir(exist_ok=True)

    # Initialize and run agent with debug flag
    agent = CLIConciergeAgent(debug=args.debug)

    if not await agent.initialize():
        print("[!] Failed to initialize. Exiting.")
        sys.exit(1)

    # Run REPL
    await agent.run_repl()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nShutdown complete.")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
