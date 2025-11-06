"""
Chat History Management Tests

Purpose: Test chat history management including token counting,
         sliding window reduction, and persistence.

Type: Integration
Test Count: 16

Key Test Areas:
- Token counting and estimation
- Sliding window reduction
- History persistence
- Summarization functionality
- Message tracking

Dependencies:
- Chat history fixtures
- Token counter fixtures
"""

import pytest
import tempfile
import asyncio
from pathlib import Path

from semantic_kernel.contents import ChatHistory
from semantic_kernel.contents.utils.author_role import AuthorRole

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.token_counter import (
    estimate_tokens,
    count_message_tokens,
    count_history_tokens,
    should_reduce_history,
    get_history_statistics
)
from src.utils.chat_history_manager import ChatHistoryManager


class TestTokenCounter:
    """Tests for token counting utilities."""

    def test_estimate_tokens_basic(self):
        """Test basic token estimation."""
        # Rough estimate: 4 chars per token
        text = "This is a test message with multiple words"
        tokens = estimate_tokens(text)

        assert tokens > 0
        assert tokens < len(text)  # Should be less than character count
        # Approximate check (4 chars per token)
        assert abs(tokens - len(text) // 4) < 5

    def test_estimate_tokens_empty(self):
        """Test token estimation for empty string."""
        assert estimate_tokens("") == 0
        assert estimate_tokens(None) == 0

    def test_count_message_tokens(self):
        """Test counting tokens in a message."""
        history = ChatHistory()
        history.add_user_message("This is a test message")

        message = history.messages[0]
        tokens = count_message_tokens(message)

        assert tokens > 0
        # Should include content + overhead
        assert tokens > estimate_tokens("This is a test message")

    def test_count_history_tokens(self):
        """Test counting total tokens in history."""
        history = ChatHistory()
        history.add_system_message("You are a helpful assistant")
        history.add_user_message("Hello")
        history.add_assistant_message("Hi there! How can I help?")

        total_tokens = count_history_tokens(history)

        assert total_tokens > 0
        # Should be sum of individual messages
        individual_sum = sum(count_message_tokens(m) for m in history.messages)
        assert total_tokens == individual_sum

    def test_should_reduce_history(self):
        """Test reduction trigger logic."""
        # Below threshold
        assert not should_reduce_history(300, 1000, 0.8)  # 30% usage

        # At threshold
        assert should_reduce_history(800, 1000, 0.8)  # 80% usage

        # Above threshold
        assert should_reduce_history(900, 1000, 0.8)  # 90% usage

    def test_get_history_statistics(self):
        """Test statistics generation."""
        history = ChatHistory()
        history.add_system_message("System prompt")
        history.add_user_message("User message 1")
        history.add_assistant_message("Assistant response 1")
        history.add_user_message("User message 2")
        history.add_assistant_message("Assistant response 2")

        stats = get_history_statistics(history, "gpt-4")

        assert stats['message_count'] == 5
        assert stats['system_message_count'] == 1
        assert stats['user_message_count'] == 2
        assert stats['assistant_message_count'] == 2
        assert stats['total_tokens'] > 0
        assert stats['context_limit'] == 8192  # GPT-4 limit
        assert 0 <= stats['usage_percentage'] <= 1


class TestChatHistoryManager:
    """Tests for ChatHistoryManager."""

    def test_initialization(self):
        """Test basic initialization."""
        manager = ChatHistoryManager(
            max_messages=50,
            max_tokens=4000
        )

        assert manager.max_messages == 50
        assert manager.max_tokens == 4000
        assert manager.get_history() is not None
        assert len(manager.get_history().messages) == 0

    def test_add_messages(self):
        """Test adding messages through manager."""
        manager = ChatHistoryManager(max_messages=100, max_tokens=10000)

        manager.add_user_message("Hello")
        manager.add_assistant_message("Hi there")

        history = manager.get_history()
        assert len(history.messages) == 2
        assert history.messages[0].role == AuthorRole.USER
        assert history.messages[1].role == AuthorRole.ASSISTANT

    def test_token_counting(self):
        """Test token counting through manager."""
        manager = ChatHistoryManager()

        manager.add_user_message("This is a test message")
        tokens = manager.count_tokens()

        assert tokens > 0

    def test_sliding_window_reduction(self):
        """Test sliding window reduction."""
        manager = ChatHistoryManager(max_messages=10, max_tokens=100000)

        # Add system message
        manager.get_history().add_system_message("System prompt")

        # Add more than max_messages
        for i in range(15):
            manager.add_user_message(f"Message {i}")
            manager.add_assistant_message(f"Response {i}")

        # Should have triggered reduction
        history = manager.get_history()

        # Should have system message + last 10 non-system messages
        system_count = sum(1 for m in history.messages if m.role == AuthorRole.SYSTEM)
        assert system_count == 1

        # Total should be system + last 10
        assert len(history.messages) <= 11  # 1 system + 10 others

    def test_should_reduce_threshold(self):
        """Test reduction threshold detection."""
        manager = ChatHistoryManager(max_messages=100, max_tokens=100)

        # Add messages until approaching token limit
        for i in range(20):
            manager.add_user_message(f"This is a test message number {i}")

        # Should trigger reduction due to token limit
        assert manager.should_reduce()

    def test_persistence_save_load(self):
        """Test saving and loading chat history."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "test_history.jsonl"

            # Create manager and add messages
            manager = ChatHistoryManager(
                max_messages=50,
                max_tokens=4000,
                storage_path=str(storage_path)
            )

            manager.add_system_message("System prompt")
            manager.add_user_message("Hello")
            manager.add_assistant_message("Hi there")

            # Save
            assert manager.save_to_file()
            assert storage_path.exists()

            # Create new manager and load
            manager2 = ChatHistoryManager(
                max_messages=50,
                max_tokens=4000,
                storage_path=str(storage_path)
            )

            assert manager2.load_from_file()

            # Verify loaded history matches
            loaded_history = manager2.get_history()
            assert len(loaded_history.messages) == 3
            assert loaded_history.messages[0].role == AuthorRole.SYSTEM
            assert loaded_history.messages[1].role == AuthorRole.USER
            assert loaded_history.messages[2].role == AuthorRole.ASSISTANT

    def test_clear_preserves_system_messages(self):
        """Test that clear() preserves system messages."""
        manager = ChatHistoryManager()

        manager.add_system_message("System prompt")
        manager.add_user_message("Hello")
        manager.add_assistant_message("Hi")

        manager.clear()

        history = manager.get_history()
        assert len(history.messages) == 1
        assert history.messages[0].role == AuthorRole.SYSTEM

    def test_get_statistics(self):
        """Test statistics retrieval."""
        manager = ChatHistoryManager()

        manager.add_user_message("Test message")
        manager.add_assistant_message("Test response")

        stats = manager.get_statistics()

        assert 'message_count' in stats
        assert 'total_tokens' in stats
        assert 'usage_percentage' in stats
        assert stats['message_count'] == 2

    def test_no_reduction_when_under_limits(self):
        """Test that no reduction occurs when under limits."""
        manager = ChatHistoryManager(max_messages=100, max_tokens=10000)

        # Add a few messages
        manager.add_user_message("Message 1")
        manager.add_assistant_message("Response 1")
        manager.add_user_message("Message 2")

        initial_count = len(manager.get_history().messages)

        # Should not reduce
        assert not manager.should_reduce()

        # Manually call reduce (should do nothing)
        manager.reduce_sliding_window()

        # Count should be same
        assert len(manager.get_history().messages) == initial_count


# Async test for summarization (requires actual kernel)
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires configured Semantic Kernel instance")
async def test_summarization_reduction():
    """
    Test LLM-based summarization reduction.

    NOTE: This test requires a configured Semantic Kernel with LLM service.
    Skipped by default. Remove skip marker to run with real kernel.
    """
    from src.utils.kernel_builder import create_kernel

    # Create kernel
    kernel = create_kernel()

    manager = ChatHistoryManager(
        max_messages=100,
        max_tokens=500,  # Low limit to trigger summarization
        enable_summarization=True,
        kernel=kernel
    )

    # Add many messages
    for i in range(30):
        manager.add_user_message(f"User message {i}: discussing topic {i}")
        manager.add_assistant_message(f"Assistant response {i}: addressing topic {i}")

    # Trigger summarization
    await manager.reduce_with_summarization(keep_recent_n=10)

    # Should have summary + recent messages
    history = manager.get_history()

    # Check for summary message
    system_messages = [m for m in history.messages if m.role == AuthorRole.SYSTEM]
    assert any("Summary" in str(m.content) for m in system_messages)

    # Should be significantly reduced
    assert len(history.messages) < 30


if __name__ == "__main__":
    """Run tests with: python -m agent.tests.test_chat_history_management"""
    print("\nRunning Chat History Management Tests...\n")

    # Run basic tests
    test_token = TestTokenCounter()
    test_token.test_estimate_tokens_basic()
    test_token.test_estimate_tokens_empty()
    test_token.test_count_message_tokens()
    test_token.test_count_history_tokens()
    test_token.test_should_reduce_history()
    test_token.test_get_history_statistics()
    print("✓ Token counter tests passed")

    test_manager = TestChatHistoryManager()
    test_manager.test_initialization()
    test_manager.test_add_messages()
    test_manager.test_token_counting()
    test_manager.test_sliding_window_reduction()
    test_manager.test_should_reduce_threshold()
    test_manager.test_persistence_save_load()
    test_manager.test_clear_preserves_system_messages()
    test_manager.test_get_statistics()
    test_manager.test_no_reduction_when_under_limits()
    print("✓ ChatHistoryManager tests passed")

    print("\n✅ All tests passed!\n")
