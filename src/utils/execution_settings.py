"""
Centralized execution settings for different LLM operations.

This module provides pre-configured execution settings for various agent tasks,
ensuring consistent behavior, cost control, and proper function calling configuration.
"""

from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior


# Classification settings - low temperature for consistency
CLASSIFICATION_SETTINGS = AzureChatPromptExecutionSettings(
    temperature=0.3,  # Low for consistent classification decisions
    max_tokens=300,   # Classifications are brief
    top_p=0.9,
    function_choice_behavior=FunctionChoiceBehavior.Auto(
        filters={"included_plugins": ["classification"]}
    )
)

# Extraction settings - slightly higher temperature for flexibility
EXTRACTION_SETTINGS = AzureChatPromptExecutionSettings(
    temperature=0.5,  # Balanced for structured extraction
    max_tokens=800,   # Extraction can be more verbose
    function_choice_behavior=FunctionChoiceBehavior.Auto(
        filters={"included_plugins": ["extraction"]}
    )
)

# Clarification settings - higher temperature for natural conversation
CLARIFICATION_SETTINGS = AzureChatPromptExecutionSettings(
    temperature=0.7,      # Higher for natural, conversational responses
    max_tokens=3000,      # Allow full clarification workflow
    function_choice_behavior=FunctionChoiceBehavior.Auto(
        filters={"included_plugins": ["clarification"]}
    )
)

# Search settings - deterministic, minimal function calling
SEARCH_SETTINGS = AzureChatPromptExecutionSettings(
    temperature=0.0,  # Fully deterministic
    max_tokens=200,   # Search results are concise
    # No function_choice_behavior specified - uses default behavior
)

# Validation settings - deterministic for consistent checks
VALIDATION_SETTINGS = AzureChatPromptExecutionSettings(
    temperature=0.2,  # Very low for consistent validation
    max_tokens=400,
    function_choice_behavior=FunctionChoiceBehavior.Auto(
        filters={"included_plugins": ["extraction"]}
    )
)
