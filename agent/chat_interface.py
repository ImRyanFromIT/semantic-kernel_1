"""
Interactive chat interface for the SRM Archivist Agent.

Allows human operators to interact with the agent, ask questions,
and issue commands.
"""

import asyncio
import sys
from typing import Optional


class ChatInterface:
    """
    Chat interface for interacting with the SRM Archivist Agent.
    """
    
    def __init__(self, agent):
        """
        Initialize chat interface.
        
        Args:
            agent: SrmArchivistAgent instance
        """
        self.agent = agent
        self.running = False
    
    async def start_interactive_chat(self) -> None:
        """
        Start interactive chat loop.
        
        Human operator can type messages and the agent will respond.
        """
        print("\n" + "="*60)
        print("SRM ARCHIVIST AGENT - INTERACTIVE CHAT MODE")
        print("="*60)
        print("\nAvailable commands:")
        print("  status        - Get current agent status")
        print("  check         - Force immediate email check")
        print("  config        - Show current configuration")
        print("  history       - Show recent processing history")
        print("  help          - Show available commands")
        print("  exit/quit     - Exit chat mode")
        print("\nYou can also ask questions in natural language.")
        print("="*60 + "\n")
        
        self.running = True
        
        # Use a separate task for reading input to avoid blocking
        try:
            while self.running and not self.agent.shutdown_requested:
                # Read user input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, input, "You: "
                )
                
                user_input = user_input.strip()
                
                if not user_input:
                    continue
                
                # Check for exit commands
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print("\nExiting chat mode...")
                    self.running = False
                    break
                
                # Handle built-in commands
                if user_input.lower() == 'help':
                    self._print_help()
                    continue
                
                # Send to agent for processing
                try:
                    response = await self.agent._handle_chat_message(user_input)
                    print(f"\nAgent: {response}\n")
                except Exception as e:
                    print(f"\nError: {e}\n")
                
        except KeyboardInterrupt:
            print("\n\nChat interrupted by user.")
            self.running = False
        except Exception as e:
            print(f"\nChat error: {e}")
            self.running = False
    
    def _print_help(self) -> None:
        """Print help information."""
        print("\n" + "="*60)
        print("AVAILABLE COMMANDS")
        print("="*60)
        print("""
status      - Get current agent status (emails processed, pending, etc.)
check       - Force immediate email check (overrides schedule)
config      - Display current configuration settings
history     - Show recent email processing history
help        - Show this help message
exit/quit   - Exit chat mode and return to autonomous operation

NATURAL LANGUAGE QUERIES:
You can also ask questions like:
  - "What have you done today?"
  - "Check for new emails right now"
  - "How many emails are pending?"
  - "Show me the last 5 emails you processed"
  - "What's the status of email ID abc123?"
        """)
        print("="*60 + "\n")


async def run_chat_mode(agent) -> None:
    """
    Run the agent in interactive chat mode.
    
    Args:
        agent: SrmArchivistAgent instance
    """
    chat = ChatInterface(agent)
    await chat.start_interactive_chat()

