#!/usr/bin/env python3
"""
CLI Maintainer Agent

Interactive REPL agent for managing SRM metadata.
Uses Semantic Kernel with auto function calling to make API requests to chatbot service.

Usage:
    python run_cli_maintainer.py
"""

import asyncio
import sys
import logging
from pathlib import Path

from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.contents import ChatHistory, ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior

from src.utils.kernel_builder import create_kernel
from src.plugins.cli_maintainer.api_client_plugin import MaintainerAPIClientPlugin


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/cli_maintainer.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Reduce verbose logging from SK
logging.getLogger('semantic_kernel').setLevel(logging.WARNING)


class CLIMaintainerAgent:
    """CLI-based maintainer agent for SRM metadata management."""

    def __init__(self, chatbot_url: str = "http://localhost:8000"):
        """
        Initialize CLI maintainer agent.

        Args:
            chatbot_url: URL of chatbot service (hardcoded for demo)
        """
        self.chatbot_url = chatbot_url
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
            print("\n" + "=" * 80)
            print("CLI MAINTAINER AGENT - SRM Metadata Management")
            print("=" * 80)

            # Create kernel
            print("[*] Initializing Semantic Kernel...")
            self.kernel = create_kernel()
            print("[+] Kernel initialized")

            # Add API client plugin
            print(f"[*] Connecting to chatbot service at {self.chatbot_url}...")
            api_client = MaintainerAPIClientPlugin(base_url=self.chatbot_url)
            self.kernel.add_plugin(api_client, plugin_name="api_client")
            print("[+] API client plugin loaded")

            # Create agent with auto function calling
            print("[*] Creating maintainer agent...")
            self.agent = ChatCompletionAgent(
                service_id="chat",
                kernel=self.kernel,
                name="MaintainerAgent",
                instructions="""You are an SRM metadata maintainer assistant.

Your role is to help users update SRM (Service Request Model) metadata like owner notes.

Key behaviors:
1. When user mentions an SRM by name, use search_srm to find the ID
2. Before updating, use get_srm_by_id to show current values
3. Ask for confirmation before calling update_srm_metadata
4. After updating, show the before/after changes clearly

Be conversational but concise. Always confirm before making changes.""",
                execution_settings={
                    "function_choice_behavior": FunctionChoiceBehavior.Auto()
                }
            )
            print("[+] Agent created with auto function calling enabled")

            # Initialize chat history
            self.history = ChatHistory()
            print("[+] Chat history initialized")

            print("=" * 80)
            print("READY")
            print("Type your requests or 'quit' to exit")
            print("=" * 80 + "\n")

            return True

        except Exception as e:
            logger.error(f"Initialization failed: {e}", exc_info=True)
            print(f"\n[ERROR] Failed to initialize: {e}")
            return False

    async def run_repl(self):
        """Run the interactive REPL loop."""
        print("\nCLI Maintainer> ", end='', flush=True)

        while True:
            try:
                # Get user input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                user_input = user_input.strip()

                if not user_input:
                    print("\nCLI Maintainer> ", end='', flush=True)
                    continue

                # Check for quit
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\nGoodbye!")
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
                async for response in self.agent.invoke_stream(self.history):
                    print(response.content, end='', flush=True)

                print()  # Newline after response
                print("\nCLI Maintainer> ", end='', flush=True)

            except KeyboardInterrupt:
                print("\n\nInterrupted. Type 'quit' to exit.")
                print("\nCLI Maintainer> ", end='', flush=True)
            except Exception as e:
                logger.error(f"Error in REPL: {e}", exc_info=True)
                print(f"\n[ERROR] {e}")
                print("\nCLI Maintainer> ", end='', flush=True)


async def main():
    """Main entry point."""
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)

    # Initialize and run agent
    agent = CLIMaintainerAgent()

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
