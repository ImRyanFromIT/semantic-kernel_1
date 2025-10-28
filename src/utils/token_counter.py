"""
Token counting utilities for chat history management.

Provides token estimation for managing chat history size and preventing
context window overflow.
"""

from typing import Dict
from semantic_kernel.contents import ChatHistory, ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole


# Model context window sizes (in tokens)
MODEL_CONTEXT_LIMITS = {
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-16k": 16384,
}


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a text string.

    Uses a rough approximation: ~4 characters per token for English text.
    This is conservative - actual tokenization may differ but this prevents
    underestimating token usage.

    Args:
        text: The text to estimate tokens for

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    # Conservative estimate: 4 chars per token
    # Real tokenizers may be more efficient, but better to overestimate
    return max(1, len(text) // 4)


def count_message_tokens(message: ChatMessageContent) -> int:
    """
    Estimate token count for a single chat message.

    Includes tokens for role, content, and message structure overhead.

    Args:
        message: The chat message to count tokens for

    Returns:
        Estimated token count including overhead
    """
    # Start with content tokens
    content_tokens = 0
    if message.content:
        content_tokens = estimate_tokens(str(message.content))

    # Add tokens for items (function calls, etc.)
    items_tokens = 0
    if hasattr(message, 'items') and message.items:
        for item in message.items:
            # Function calls and results add tokens
            if hasattr(item, 'to_dict'):
                item_str = str(item.to_dict())
                items_tokens += estimate_tokens(item_str)

    # Add overhead for message structure
    # Each message has: role, timestamp, metadata
    overhead = 10  # Approximate overhead per message

    return content_tokens + items_tokens + overhead


def count_history_tokens(chat_history: ChatHistory) -> int:
    """
    Count total estimated tokens in a chat history.

    Sums token counts across all messages including system messages.

    Args:
        chat_history: The ChatHistory object to count tokens for

    Returns:
        Total estimated token count
    """
    total_tokens = 0

    for message in chat_history.messages:
        total_tokens += count_message_tokens(message)

    return total_tokens


def get_model_context_limit(model_name: str) -> int:
    """
    Get the context window size for a given model.

    Args:
        model_name: Name of the model (e.g., "gpt-4", "gpt-3.5-turbo")

    Returns:
        Context window size in tokens, defaults to 4096 if model unknown
    """
    # Normalize model name (remove version suffixes)
    for known_model, limit in MODEL_CONTEXT_LIMITS.items():
        if model_name.startswith(known_model):
            return limit

    # Default to conservative limit if model unknown
    return 4096


def calculate_safe_limit(model_name: str, reserve_percentage: float = 0.2) -> int:
    """
    Calculate a safe token limit that reserves space for responses.

    Args:
        model_name: Name of the model
        reserve_percentage: Percentage to reserve for response (default 20%)

    Returns:
        Safe token limit for chat history
    """
    context_limit = get_model_context_limit(model_name)

    # Reserve space for model response
    safe_limit = int(context_limit * (1 - reserve_percentage))

    return safe_limit


def get_token_usage_percentage(current_tokens: int, model_name: str) -> float:
    """
    Calculate what percentage of context window is being used.

    Args:
        current_tokens: Current token count in history
        model_name: Name of the model

    Returns:
        Percentage of context window used (0.0 to 1.0)
    """
    context_limit = get_model_context_limit(model_name)

    if context_limit == 0:
        return 1.0

    return current_tokens / context_limit


def should_reduce_history(
    current_tokens: int,
    max_tokens: int,
    threshold: float = 0.8
) -> bool:
    """
    Determine if chat history should be reduced.

    Args:
        current_tokens: Current token count in history
        max_tokens: Maximum allowed tokens
        threshold: Reduction trigger threshold (default 80%)

    Returns:
        True if history should be reduced
    """
    if max_tokens == 0:
        return False

    usage_ratio = current_tokens / max_tokens

    return usage_ratio >= threshold


def get_history_statistics(chat_history: ChatHistory, model_name: str = "gpt-4") -> Dict:
    """
    Get comprehensive statistics about a chat history.

    Args:
        chat_history: The ChatHistory to analyze
        model_name: Model name for context limit calculation

    Returns:
        Dictionary with statistics:
            - message_count: Total number of messages
            - total_tokens: Estimated total tokens
            - context_limit: Model's context window size
            - usage_percentage: Percentage of context used
            - system_message_count: Number of system messages
            - user_message_count: Number of user messages
            - assistant_message_count: Number of assistant messages
    """
    message_count = len(chat_history.messages)
    total_tokens = count_history_tokens(chat_history)
    context_limit = get_model_context_limit(model_name)
    usage_percentage = get_token_usage_percentage(total_tokens, model_name)

    # Count by role
    role_counts = {
        'system': 0,
        'user': 0,
        'assistant': 0,
        'tool': 0
    }

    for message in chat_history.messages:
        role = message.role.value if hasattr(message.role, 'value') else str(message.role)
        if role in role_counts:
            role_counts[role] += 1

    return {
        'message_count': message_count,
        'total_tokens': total_tokens,
        'context_limit': context_limit,
        'usage_percentage': usage_percentage,
        'system_message_count': role_counts['system'],
        'user_message_count': role_counts['user'],
        'assistant_message_count': role_counts['assistant'],
        'tool_message_count': role_counts['tool'],
    }
