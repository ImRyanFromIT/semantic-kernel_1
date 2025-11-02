"""
Chat History Manager for managing chat history with reduction and persistence.

Provides automatic reduction strategies, token management, and file-based persistence
to prevent unbounded chat history growth and context limit failures.
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from semantic_kernel import Kernel
from semantic_kernel.contents import ChatHistory, ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole

from .token_counter import (
    count_history_tokens,
    count_message_tokens,
    should_reduce_history,
    get_history_statistics
)


logger = logging.getLogger(__name__)


class ChatHistoryManager:
    """
    Manages chat history with automatic reduction and persistence.

    Features:
    - Sliding window reduction (keep last N messages)
    - LLM-based summarization of old messages
    - Token counting and limits
    - File-based persistence (JSONL format)
    - Automatic reduction when approaching limits
    """

    def __init__(
        self,
        history: Optional[ChatHistory] = None,
        max_messages: int = 50,
        max_tokens: int = 4000,
        storage_path: Optional[str] = None,
        enable_summarization: bool = True,
        summarization_threshold: float = 0.8,
        kernel: Optional[Kernel] = None
    ):
        """
        Initialize chat history manager.

        Args:
            history: Existing ChatHistory to manage (creates new if None)
            max_messages: Maximum messages before sliding window reduction
            max_tokens: Maximum tokens before reduction triggered
            storage_path: Path to JSONL file for persistence
            enable_summarization: Whether to use LLM summarization
            summarization_threshold: Trigger reduction at this % of max_tokens
            kernel: Semantic Kernel instance (required for summarization)
        """
        self.history = history if history else ChatHistory()
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.storage_path = Path(storage_path) if storage_path else None
        self.enable_summarization = enable_summarization
        self.summarization_threshold = summarization_threshold
        self.kernel = kernel

        # Create storage directory if needed
        if self.storage_path:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"ChatHistoryManager initialized: max_messages={max_messages}, "
            f"max_tokens={max_tokens}, storage={storage_path}"
        )

    def get_history(self) -> ChatHistory:
        """Get the managed chat history."""
        return self.history

    def add_message(self, message: ChatMessageContent) -> None:
        """
        Add a message to history with automatic reduction.

        Args:
            message: The message to add
        """
        self.history.add_message(message)

        # Check if reduction needed
        if self.should_reduce():
            logger.info("Reduction threshold reached, applying reduction strategy")
            self.reduce()

    def add_user_message(self, content: str) -> None:
        """Add a user message to history."""
        self.history.add_user_message(content)
        if self.should_reduce():
            self.reduce()

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to history."""
        self.history.add_assistant_message(content)
        if self.should_reduce():
            self.reduce()

    def add_system_message(self, content: str) -> None:
        """Add a system message to history."""
        self.history.add_system_message(content)
        if self.should_reduce():
            self.reduce()

    def count_tokens(self) -> int:
        """
        Count estimated tokens in current history.

        Returns:
            Estimated token count
        """
        return count_history_tokens(self.history)

    def should_reduce(self) -> bool:
        """
        Check if history should be reduced.

        Returns:
            True if reduction needed
        """
        current_tokens = self.count_tokens()
        message_count = len(self.history.messages)

        # Check message count limit
        if message_count > self.max_messages:
            logger.debug(f"Message count {message_count} exceeds limit {self.max_messages}")
            return True

        # Check token limit with threshold
        if should_reduce_history(current_tokens, self.max_tokens, self.summarization_threshold):
            logger.debug(f"Token count {current_tokens} approaching limit {self.max_tokens}")
            return True

        return False

    def reduce(self) -> None:
        """
        Reduce history using appropriate strategy.

        Uses LLM summarization if enabled and kernel available,
        otherwise falls back to sliding window.
        """
        current_tokens = self.count_tokens()
        message_count = len(self.history.messages)

        logger.info(
            f"Reducing history: {message_count} messages, {current_tokens} tokens"
        )

        # Try summarization first if enabled
        if self.enable_summarization and self.kernel:
            try:
                self.reduce_with_summarization()
                return
            except Exception as e:
                logger.debug(f"Summarization failed, falling back to sliding window: {e}")

        # Fall back to sliding window
        self.reduce_sliding_window()

    def reduce_sliding_window(self, keep_last_n: Optional[int] = None) -> None:
        """
        Apply sliding window reduction - keep only last N messages.

        Args:
            keep_last_n: Number of messages to keep (uses max_messages if None)
        """
        keep_count = keep_last_n if keep_last_n else self.max_messages

        if len(self.history.messages) <= keep_count:
            logger.debug("No reduction needed - message count within limit")
            return

        # Separate system messages from others
        system_messages = [m for m in self.history.messages if m.role == AuthorRole.SYSTEM]
        other_messages = [m for m in self.history.messages if m.role != AuthorRole.SYSTEM]

        # Keep last N non-system messages
        kept_messages = other_messages[-keep_count:]

        # Rebuild history with system messages + recent messages
        new_history = ChatHistory()
        for msg in system_messages:
            new_history.add_message(msg)
        for msg in kept_messages:
            new_history.add_message(msg)

        old_count = len(self.history.messages)
        self.history = new_history
        new_count = len(self.history.messages)

        logger.info(
            f"Sliding window reduction: {old_count} → {new_count} messages "
            f"(kept system + last {keep_count})"
        )

    async def reduce_with_summarization(self, keep_recent_n: int = 20) -> None:
        """
        Reduce history by summarizing old messages.

        Creates a context summary of older messages and keeps only
        recent messages in full.

        Args:
            keep_recent_n: Number of recent messages to keep unsummarized
        """
        if not self.kernel:
            raise ValueError("Kernel required for summarization")

        messages = self.history.messages
        if len(messages) <= keep_recent_n:
            logger.debug("Too few messages for summarization")
            return

        # Separate messages
        system_messages = [m for m in messages if m.role == AuthorRole.SYSTEM]
        non_system_messages = [m for m in messages if m.role != AuthorRole.SYSTEM]

        if len(non_system_messages) <= keep_recent_n:
            return

        # Messages to summarize (older ones)
        to_summarize = non_system_messages[:-keep_recent_n]
        to_keep = non_system_messages[-keep_recent_n:]

        # Build text to summarize
        summary_text = self._build_summary_text(to_summarize)

        # Use LLM to create summary
        summary_prompt = f"""Summarize the following conversation history concisely, preserving key context and decisions:

{summary_text}

Provide a concise summary in 2-3 paragraphs that captures the essential context."""

        try:
            # Get chat completion service
            chat_service = self.kernel.get_service("chat")

            # Create temporary history for summarization
            temp_history = ChatHistory()
            temp_history.add_user_message(summary_prompt)

            # Get summary
            result = await chat_service.get_chat_message_content(
                chat_history=temp_history,
                settings=None
            )

            summary_content = str(result.content) if result and result.content else "No summary generated"

            # Rebuild history with summary
            new_history = ChatHistory()

            # Add system messages
            for msg in system_messages:
                new_history.add_message(msg)

            # Add summary as system message
            new_history.add_system_message(
                f"[Previous Conversation Summary]\n{summary_content}"
            )

            # Add recent messages
            for msg in to_keep:
                new_history.add_message(msg)

            old_count = len(self.history.messages)
            old_tokens = self.count_tokens()

            self.history = new_history

            new_count = len(self.history.messages)
            new_tokens = count_history_tokens(self.history)

            logger.info(
                f"Summarization reduction: {old_count} → {new_count} messages, "
                f"{old_tokens} → {new_tokens} tokens "
                f"(summarized {len(to_summarize)} messages)"
            )

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            raise

    def _build_summary_text(self, messages: List[ChatMessageContent]) -> str:
        """
        Build text representation of messages for summarization.

        Args:
            messages: Messages to convert to text

        Returns:
            Formatted text
        """
        lines = []
        for msg in messages:
            role = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
            content = str(msg.content) if msg.content else ""
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def save_to_file(self) -> bool:
        """
        Save chat history to JSONL file.

        Uses atomic write (temp file + move) to prevent corruption.

        Returns:
            True if save successful
        """
        if not self.storage_path:
            logger.warning("No storage path configured, skipping save")
            return False

        try:
            # Write to temporary file first
            temp_path = Path(f"{self.storage_path}.tmp")

            with open(temp_path, 'w', encoding='utf-8') as f:
                # Save metadata
                metadata = {
                    'type': 'metadata',
                    'timestamp': datetime.utcnow().isoformat(),
                    'message_count': len(self.history.messages),
                    'token_count': self.count_tokens()
                }
                f.write(json.dumps(metadata) + '\n')

                # Save each message
                for message in self.history.messages:
                    message_dict = {
                        'type': 'message',
                        'role': message.role.value if hasattr(message.role, 'value') else str(message.role),
                        'content': str(message.content) if message.content else "",
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    f.write(json.dumps(message_dict, ensure_ascii=False) + '\n')

            # Atomic move
            shutil.move(str(temp_path), str(self.storage_path))

            logger.info(
                f"Chat history saved to {self.storage_path}: "
                f"{len(self.history.messages)} messages"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save chat history: {e}")
            # Clean up temp file if exists
            if temp_path.exists():
                temp_path.unlink()
            return False

    def load_from_file(self) -> bool:
        """
        Load chat history from JSONL file.

        Returns:
            True if load successful
        """
        if not self.storage_path or not self.storage_path.exists():
            logger.debug(f"No saved history found at {self.storage_path}")
            return False

        try:
            new_history = ChatHistory()
            message_count = 0

            with open(self.storage_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    if data['type'] == 'metadata':
                        # Log metadata
                        logger.info(f"Loading saved history: {data.get('message_count', 0)} messages")
                    elif data['type'] == 'message':
                        role = data['role']
                        content = data['content']

                        # Add message based on role
                        if role == 'system':
                            new_history.add_system_message(content)
                        elif role == 'user':
                            new_history.add_user_message(content)
                        elif role == 'assistant':
                            new_history.add_assistant_message(content)

                        message_count += 1

            self.history = new_history

            logger.info(
                f"Chat history loaded from {self.storage_path}: "
                f"{message_count} messages, {self.count_tokens()} tokens"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to load chat history: {e}")
            return False

    def clear(self) -> None:
        """Clear all messages from history (keeps system messages)."""
        system_messages = [m for m in self.history.messages if m.role == AuthorRole.SYSTEM]

        self.history = ChatHistory()
        for msg in system_messages:
            self.history.add_message(msg)

        logger.info("Chat history cleared (system messages preserved)")

    def get_statistics(self, model_name: str = "gpt-4") -> dict:
        """
        Get comprehensive statistics about current history.

        Args:
            model_name: Model name for context calculations

        Returns:
            Dictionary with statistics
        """
        return get_history_statistics(self.history, model_name)
