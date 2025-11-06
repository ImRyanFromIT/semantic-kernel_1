---
document_type: technical_reference
topic: auto_function_calling
framework: semantic_kernel
language: python
version: 1.0
last_updated: 2025-10-26
subtopics:
  - function_choice_behavior_fundamentals
  - configuration_patterns
  - streaming_and_non_streaming
  - function_filtering
  - parallel_function_calling
  - manual_function_calling
  - advanced_patterns
  - best_practices
  - common_patterns
---

# Semantic Kernel Auto Function Calling - Reference

## Core Concepts

**Key Points:**

- Auto function calling enables AI models to autonomously select and invoke registered kernel functions
- `FunctionChoiceBehavior` controls when and how functions are called (Auto, Required, None)
- Functions execute automatically when `auto_invoke=True` (default for Auto mode)
- Supports both streaming and non-streaming response patterns
- Filters enable precise control over which functions are available to the model
- Kernel executes independent functions in parallel for optimal performance

**Keywords**: FunctionChoiceBehavior, auto_invoke, function calling, tool calling, Auto mode, Required mode, function filters, parallel execution, streaming, ChatCompletion, PromptExecutionSettings

### Auto Function Calling Architecture

Auto function calling is a capability where the AI model can:

- Analyze user queries and determine which functions to invoke
- Automatically execute functions with appropriate parameters
- Use function results to generate informed responses
- Chain multiple function calls to satisfy complex requests
- Execute independent functions concurrently for performance

**Key Characteristics:**

- Model-driven function selection based on descriptions and signatures
- Automatic argument extraction from natural language
- Seamless integration with conversation history
- Support for complex nested function calls
- Built-in retry and error handling mechanisms

**Use Cases:**

- Conversational AI with dynamic tool usage (e.g., calculators, weather APIs)
- Math and computation assistance (adding plugins for mathematical operations)
- Time and date queries with real-time information
- Database operations triggered by natural language
- Multi-step workflows requiring multiple tool invocations
- Code interpretation and execution (Azure Python Code Interpreter)

---

<!-- section: function_choice_behavior_fundamentals -->

## 1. Function Choice Behavior Fundamentals

**Key Points:**

- `FunctionChoiceBehavior.Auto()` - model decides if and which functions to call
- `FunctionChoiceBehavior.Required()` - model must call specified functions
- `FunctionChoiceBehavior.None()` - disables function calling entirely
- `auto_invoke` parameter controls automatic vs manual execution
- Configuration applies per request via execution settings

**Keywords**: FunctionChoiceBehavior, Auto mode, Required mode, None mode, auto_invoke, execution settings, request settings

### FunctionChoiceBehavior.Auto()

The most common mode where the model autonomously decides whether to call functions:

```python
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings

# Enable auto function calling
execution_settings = AzureChatPromptExecutionSettings(
    service_id="chat",
    max_tokens=2000,
    temperature=0.7,
)

# Set function choice behavior to Auto with auto_invoke=True (default)
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()
```

✓ **Best Practice**: Use `Auto()` mode for conversational AI where the model should intelligently decide when tools are needed.

**Auto-Invoke Enabled (Default):**

- Functions execute automatically when the model requests them
- Function results are fed back to the model for final response generation
- Multiple invocation rounds occur until the model has sufficient information

**Auto-Invoke Disabled:**

```python
# Model suggests functions but doesn't execute them
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(auto_invoke=False)
```

With `auto_invoke=False`, the response contains `FunctionCallContent` objects that you must manually handle.

### FunctionChoiceBehavior.Required()

Forces the model to call one or more specified functions:

```python
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior

# Require specific functions to be called
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Required(
    auto_invoke=False,
    filters={"included_functions": ["time-time", "time-date"]},
)
```

✓ **Best Practice**: Use `Required()` when you need guaranteed function execution for specific operations (e.g., always check time before responding).

⚠️ **Warning**: By default, `maximum_auto_invoke_attempts` is set to 1 for Required mode. If the model exhausts available function calls before reaching this limit, it may repeat calls or return tool call responses.

### FunctionChoiceBehavior.None()

Completely disables function calling:

```python
execution_settings.function_choice_behavior = FunctionChoiceBehavior.None()
```

Use this when you want the model to respond using only its internal knowledge without invoking any tools.

### Auto-Invoke Control

The `auto_invoke` parameter determines execution behavior:

| `auto_invoke` Value       | Behavior                                                                |
| ------------------------- | ----------------------------------------------------------------------- |
| `True` (default for Auto) | Kernel automatically executes functions and feeds results back to model |
| `False`                   | Model returns function call instructions; you handle execution manually |

**When to use `auto_invoke=False`:**

- Custom authorization or validation before function execution
- Logging or auditing function calls before execution
- Implementing custom retry or fallback logic
- Rate limiting or quota management

---

<!-- section: configuration_patterns -->

## 2. Configuration Patterns

**Key Points:**

- Three configuration approaches: inline code, YAML files, JSON files
- Function choice behavior is set on execution settings
- Execution settings are passed via `KernelArguments`
- YAML/JSON configs enable external configuration management
- All approaches support the same feature set

**Keywords**: configuration, execution settings, YAML configuration, JSON configuration, PromptExecutionSettings, KernelArguments

### Inline Configuration (Programmatic)

The most direct approach using Python code:

```python
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.functions import KernelArguments
from semantic_kernel.core_plugins import MathPlugin, TimePlugin

# Initialize kernel and add services
kernel = Kernel()
kernel.add_service(AzureChatCompletion(service_id="chat"))

# Add plugins
kernel.add_plugin(MathPlugin(), plugin_name="math")
kernel.add_plugin(TimePlugin(), plugin_name="time")

# Configure execution settings with function choice behavior
execution_settings = AzureChatPromptExecutionSettings(
    service_id="chat",
    max_tokens=2000,
    temperature=0.7,
)

# Enable auto function calling with plugin filtering
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(
    filters={"excluded_plugins": ["ChatBot"]}
)

# Pass settings to kernel via arguments
arguments = KernelArguments(settings=execution_settings)
result = await kernel.invoke(chat_function, arguments=arguments)
```

✓ **Best Practice**: Use inline configuration for dynamic scenarios where function choice behavior changes based on runtime conditions.

### YAML-Based Configuration

Store function choice behavior in YAML prompt configuration files:

**YAML Configuration File** (`function_choice_yaml/ChatBot/config.json` or `config.yaml`):

```yaml
execution_settings:
  chat:
    function_choice_behavior:
      type: auto
      maximum_auto_invoke_attempts: 5
      functions:
        - time.date
        - time.time
        - math.Add
```

**Loading and Using YAML Config:**

```python
import os
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.core_plugins import MathPlugin, TimePlugin

kernel = Kernel()
service_id = "chat"
kernel.add_service(OpenAIChatCompletion(service_id=service_id))

# Add plugins
kernel.add_plugin(MathPlugin(), plugin_name="math")
kernel.add_plugin(TimePlugin(), plugin_name="time")

# Load plugin with YAML config
plugin_path = os.path.join(os.path.dirname(__file__), "resources")
chat_plugin = kernel.add_plugin(plugin_name="function_choice_yaml", parent_directory=plugin_path)

# Extract execution settings from loaded plugin
execution_settings = chat_plugin["ChatBot"].prompt_execution_settings[service_id]

# Use the function with its embedded settings
result = await kernel.invoke(chat_plugin["ChatBot"], arguments=arguments)
```

**YAML Configuration Fields:**

- `type`: One of "auto", "required", or "none"
- `maximum_auto_invoke_attempts`: Number of function invocation rounds (default: 5 for Auto, 1 for Required)
- `functions`: List of specific functions to include (format: "plugin.function")
- `auto_invoke_kernel_functions`: Set to `false` to disable auto-invocation

✓ **Best Practice**: Use YAML configuration for prompt templates that are version-controlled and shared across teams.

### JSON-Based Configuration

Similar to YAML but using JSON format:

**JSON Configuration File** (`function_choice_json/ChatBot/config.json`):

```json
{
  "execution_settings": {
    "chat": {
      "function_choice_behavior": {
        "type": "auto",
        "maximum_auto_invoke_attempts": 5,
        "functions": ["time.date", "time.time", "math.Add"]
      }
    }
  }
}
```

**Loading and Using JSON Config:**

```python
# Load plugin with JSON config
plugin_path = os.path.join(os.path.dirname(__file__), "resources")
chat_plugin = kernel.add_plugin(plugin_name="function_choice_json", parent_directory=plugin_path)

# Extract and use execution settings
execution_settings = chat_plugin["ChatBot"].prompt_execution_settings[service_id]
result = await kernel.invoke(chat_plugin["ChatBot"], arguments=arguments)
```

✓ **Best Practice**: Use JSON configuration when integrating with systems that prefer JSON or when JavaScript/TypeScript teams share configurations.

### Disabling Auto-Invoke via Configuration

Two methods to disable automatic function invocation:

**Method 1: Set `maximum_auto_invoke_attempts` to 0**

```yaml
execution_settings:
  chat:
    function_choice_behavior:
      type: auto
      maximum_auto_invoke_attempts: 0
```

**Method 2: Set `auto_invoke_kernel_functions` to false**

```yaml
execution_settings:
  chat:
    function_choice_behavior:
      type: auto
      auto_invoke_kernel_functions: false
```

Both methods achieve the same result: the model returns function call instructions without executing them.

---

<!-- section: streaming_and_non_streaming -->

## 3. Streaming and Non-Streaming Responses

**Key Points:**

- Non-streaming: `kernel.invoke()` returns complete response after all function calls
- Streaming: `kernel.invoke_stream()` provides real-time response chunks
- Auto-invoke works seamlessly with both modes
- Streaming requires special handling for function call chunks
- Use `return_function_results=False` to exclude function results from stream

**Keywords**: streaming, non-streaming, kernel.invoke, kernel.invoke_stream, real-time responses, StreamingChatMessageContent

### Non-Streaming Function Calling

The simplest approach where the kernel returns the final response after all functions execute:

```python
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.functions import KernelArguments
from semantic_kernel.contents import ChatHistory
from semantic_kernel.core_plugins import MathPlugin, TimePlugin

# Setup kernel with plugins
kernel = Kernel()
kernel.add_service(chat_completion_service)
kernel.add_plugin(MathPlugin(), plugin_name="math")
kernel.add_plugin(TimePlugin(), plugin_name="time")

# Create chat function
chat_function = kernel.add_function(
    prompt="{{$chat_history}}{{$user_input}}",
    plugin_name="ChatBot",
    function_name="Chat",
)

# Configure auto function calling
execution_settings = AzureChatPromptExecutionSettings(
    service_id="chat",
    function_choice_behavior=FunctionChoiceBehavior.Auto(
        filters={"excluded_plugins": ["ChatBot"]}
    )
)

arguments = KernelArguments(settings=execution_settings)

# Non-streaming invocation
history = ChatHistory()
arguments["user_input"] = "What is 3 + 5?"
arguments["chat_history"] = history

result = await kernel.invoke(chat_function, arguments=arguments)
print(f"Assistant: {result}")

# Update history with the complete result
history.add_user_message("What is 3 + 5?")
history.add_message(result.value[0])
```

**Flow with Auto-Invoke:**

1. Kernel sends user message to model
2. Model decides to call `math-Add` function
3. Kernel automatically executes the function
4. Kernel sends function result back to model
5. Model generates final natural language response
6. `kernel.invoke()` returns the complete response

✓ **Best Practice**: Use non-streaming for batch processing, APIs, or scenarios where response latency is acceptable.

### Streaming Function Calling

Provides real-time streaming of the assistant's response:

```python
from semantic_kernel.contents.streaming_chat_message_content import StreamingChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole

# Setup (same as non-streaming)
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()
arguments = KernelArguments(settings=execution_settings)

arguments["user_input"] = "What is 15 - 7?"
arguments["chat_history"] = history

print("Assistant: ", end="", flush=True)

streamed_response_chunks = []

# Stream the response
async for message in kernel.invoke_stream(
    chat_function,
    return_function_results=False,  # Don't stream function results
    arguments=arguments,
):
    msg = message[0]

    # Filter for assistant messages only
    if isinstance(msg, StreamingChatMessageContent) and msg.role == AuthorRole.ASSISTANT:
        streamed_response_chunks.append(msg)
        print(str(msg), end="", flush=True)

print("\n")

# Reconstruct full response for history
if streamed_response_chunks:
    result = "".join([str(content) for content in streamed_response_chunks])
    history.add_user_message("What is 15 - 7?")
    history.add_assistant_message(result)
```

**Key Parameters:**

- `return_function_results=False`: Prevents function results from appearing in the stream; only the final assistant response streams
- `return_function_results=True`: Includes all intermediate function calls in the stream (useful for debugging)

✓ **Best Practice**: Use streaming for interactive chat interfaces where users expect real-time responses.

⚠️ **Warning**: With `return_function_results=False`, function calls happen silently in the background. The stream only shows the model's final natural language response.

### Handling Function Calls in Streamed Responses

When `auto_invoke=False`, streaming responses include function call chunks:

```python
from functools import reduce

execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(auto_invoke=False)

streamed_tool_chunks = []
streamed_response_chunks = []

async for message in kernel.invoke_stream(
    chat_function,
    return_function_results=False,
    arguments=arguments,
):
    msg = message[0]

    if not isinstance(msg, StreamingChatMessageContent) or msg.role != AuthorRole.ASSISTANT:
        continue

    # Check if this chunk contains function call information
    if hasattr(msg, "function_invoke_attempt"):
        streamed_tool_chunks.append(msg)
    else:
        streamed_response_chunks.append(msg)
        print(str(msg), end="", flush=True)

# Process collected tool call chunks
if streamed_tool_chunks:
    # Group by function_invoke_attempt
    grouped_chunks = {}
    for chunk in streamed_tool_chunks:
        key = getattr(chunk, "function_invoke_attempt", None)
        if key is not None:
            grouped_chunks.setdefault(key, []).append(chunk)

    # Combine chunks for each function call
    for attempt, chunks in grouped_chunks.items():
        combined_content = reduce(lambda first, second: first + second, chunks)
        # combined_content now contains FunctionCallContent items
        # You can extract and manually execute them
```

✓ **Best Practice**: Use `auto_invoke=False` with streaming when you need to show users which tools are being called in real-time.

---

<!-- section: function_filtering -->

## 4. Function Filtering

**Key Points:**

- Filters control which functions are available to the model
- Four filter types: excluded_plugins, included_plugins, excluded_functions, included_functions
- Filters prevent exposing internal/utility functions to the model
- Function name format: "PluginName-FunctionName" or "PluginName.FunctionName"
- Use filters to reduce token usage and improve model accuracy

**Keywords**: function filters, plugin filtering, included_functions, excluded_functions, function selection, plugin exclusion

### Filter Types

Filters are passed as a dictionary to `FunctionChoiceBehavior`:

```python
# Exclude entire plugins
FunctionChoiceBehavior.Auto(filters={"excluded_plugins": ["ChatBot", "Internal"]})

# Include only specific plugins
FunctionChoiceBehavior.Auto(filters={"included_plugins": ["math", "time"]})

# Exclude specific functions
FunctionChoiceBehavior.Auto(filters={"excluded_functions": ["math-Divide", "time-Time"]})

# Include only specific functions
FunctionChoiceBehavior.Auto(filters={"included_functions": ["math-Add", "math-Subtract", "time-Date"]})
```

**Function Name Formats:**

- Dash format: `"math-Add"`, `"time-Date"`
- Dot format: `"math.Add"`, `"time.Date"`

Both formats are equivalent and interchangeable.

### Excluding Plugins

Common pattern to exclude the chat function itself from being called:

```python
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior

# Create a chat function
chat_function = kernel.add_function(
    prompt="{{$chat_history}}{{$user_input}}",
    plugin_name="ChatBot",
    function_name="Chat",
)

# Exclude the ChatBot plugin to prevent recursive calls
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(
    filters={"excluded_plugins": ["ChatBot"]}
)
```

✓ **Best Practice**: Always exclude the chat/prompt function plugin to prevent the model from trying to recursively call itself.

**Why Exclude the Chat Plugin?**

- Prevents infinite loops where the chat function calls itself
- Reduces token usage by not including the chat function in tool descriptions
- Improves model accuracy by focusing only on actual utility functions

### Including Specific Functions

Restrict the model to use only designated functions:

```python
# Allow only specific time-related functions
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Required(
    auto_invoke=False,
    filters={"included_functions": ["time-time", "time-date"]},
)
```

**Use Cases:**

- Limit function calls for security or cost reasons
- Focus the model on specific capabilities for a given task
- Implement role-based access control (RBAC) by filtering available functions per user

### Combining Filters

You cannot combine `included_*` and `excluded_*` filters of the same type, but you can combine different types:

```python
# Valid: Include specific plugins, exclude specific functions within them
FunctionChoiceBehavior.Auto(filters={
    "included_plugins": ["math", "time"],
    "excluded_functions": ["math-Divide"]  # Division not allowed
})

# Invalid: Cannot use both included and excluded plugins
# FunctionChoiceBehavior.Auto(filters={
#     "included_plugins": ["math"],
#     "excluded_plugins": ["time"]  # This will cause an error
# })
```

✓ **Best Practice**: Use `included_plugins` for allowlist approach (more restrictive, better for production) or `excluded_plugins` for blocklist approach (more flexible, better for development).

### Dynamic Filtering

Filters can change based on runtime conditions:

```python
def get_function_filters(user_role: str) -> dict:
    """Return filters based on user role."""
    if user_role == "admin":
        return {"excluded_plugins": ["ChatBot"]}  # Admin has access to all
    elif user_role == "user":
        return {"included_functions": ["math-Add", "math-Subtract"]}  # Limited access
    else:
        return {}  # No function calling for guest

# Apply role-based filters
user_role = get_user_role()
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(
    filters=get_function_filters(user_role)
)
```

✓ **Best Practice**: Implement dynamic filtering for multi-tenant systems or role-based access control.

---

<!-- section: parallel_function_calling -->

## 5. Parallel Function Calling

**Key Points:**

- Kernel automatically executes independent function calls in parallel
- Dependent function calls execute sequentially (when one depends on another's result)
- Parallel execution significantly reduces total execution time
- Works transparently with both streaming and non-streaming modes
- No code changes needed to enable parallel execution

**Keywords**: parallel execution, concurrent function calls, performance optimization, async execution, function dependencies

### How Parallel Execution Works

When the model requests multiple independent functions, the kernel executes them concurrently:

```python
import asyncio
import logging
import sys
from typing import Annotated
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.functions import kernel_function

# Enable logging to see parallel execution
def set_up_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s.%(msecs)03d %(levelname)s] %(message)s",
                         datefmt="%Y-%m-%d %H:%M:%S"),
    )
    # Filter to show only chat completion client logs
    handler.addFilter(
        lambda record: record.name == "semantic_kernel.connectors.ai.chat_completion_client_base"
    )
    root_logger.addHandler(handler)

# Example plugin with long-running functions
class EmployeePlugin:
    @kernel_function(name="get_name", description="Find the name of the employee by the id")
    async def get_name(
        self, id: Annotated[str, "The ID of the employee"]
    ) -> Annotated[str, "The name of the employee"]:
        await asyncio.sleep(10)  # Simulate long-running operation
        return "John Doe"

    @kernel_function(name="get_age", description="Get the age of the employee by the id")
    async def get_age(
        self, id: Annotated[str, "The ID of the employee"]
    ) -> Annotated[int, "The age of the employee"]:
        await asyncio.sleep(10)  # Simulate long-running operation
        return 30

# Setup
kernel = Kernel()
kernel.add_service(OpenAIChatCompletion(service_id="open_ai"))
kernel.add_plugin(EmployeePlugin(), "EmployeePlugin")

# Query that triggers parallel execution
query = "What is the name and age of the employee of ID 123?"

arguments = KernelArguments(
    settings=PromptExecutionSettings(
        function_choice_behavior=FunctionChoiceBehavior.Auto(),
    )
)

import time
start = time.perf_counter()

result = await kernel.invoke_prompt(query, arguments=arguments)
print(result)

elapsed = time.perf_counter() - start
print(f"Time elapsed: {elapsed:.2f}s")

# Expected output:
# [2024-09-11 10:15:35.070 INFO] processing 2 tool calls in parallel.
# The employee with ID 123 is named John Doe and they are 30 years old.
# Time elapsed: 11.96s
```

**Expected Behavior:**

- **Without parallel execution**: 20+ seconds (10s + 10s sequentially)
- **With parallel execution**: ~12 seconds (both functions run simultaneously)

### When Functions Execute in Parallel

The model and kernel coordinate to determine parallelization:

**Functions Execute in Parallel When:**

- They are independent (no data dependencies)
- The model requests them in the same response
- Both functions use async execution

**Example of Parallel Execution:**

```python
# Query: "What is the name and age of employee 123?"
# Model calls: get_name(id="123") AND get_age(id="123")
# Execution: Both run concurrently → ~10s total
```

**Functions Execute Sequentially When:**

- One function depends on another's result
- The model makes calls across multiple invocation rounds

**Example of Sequential Execution:**

```python
# Query: "Get the employee's name by ID 123, then find their manager's email"
# Round 1: get_name(id="123") → "John Doe"
# Round 2: get_manager_email(name="John Doe") → "manager@example.com"
# Execution: Must run sequentially → 20s total
```

✓ **Best Practice**: Design function signatures to be independent when possible. If dependencies exist, the kernel handles them automatically.

### Parallel Execution with Streaming

Parallel execution works identically with streaming:

```python
start = time.perf_counter()

async for result in kernel.invoke_prompt_stream(query, arguments=arguments):
    print(str(result[0]), end="")
print()

print(f"Time elapsed: {time.perf_counter() - start:.2f}s")
```

The streaming output appears after all parallel function calls complete.

### Observing Parallel Execution

Enable logging to see parallel execution in action:

```python
set_up_logging()  # From example above

# Logs will show:
# [2024-09-11 10:15:35.070 INFO] processing 2 tool calls in parallel.
```

This confirms the kernel detected independent calls and executed them concurrently.

---

<!-- section: manual_function_calling -->

## 6. Manual Function Calling

**Key Points:**

- Set `auto_invoke=False` to prevent automatic function execution
- Model returns `FunctionCallContent` objects containing call instructions
- You manually extract, validate, and execute function calls
- Useful for authorization, logging, rate limiting, or custom error handling
- Works with both streaming and non-streaming modes

**Keywords**: manual function calling, auto_invoke=False, FunctionCallContent, tool calls, manual execution, function authorization

### Disabling Auto-Invoke

Configure function choice behavior with manual control:

```python
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior

# Model suggests functions but doesn't execute them
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(auto_invoke=False)
```

### Extracting Function Call Content

When auto-invoke is disabled, responses contain function call instructions:

```python
from semantic_kernel.contents.function_call_content import FunctionCallContent
from semantic_kernel.contents.chat_message_content import ChatMessageContent

# Invoke with auto_invoke=False
result = await kernel.invoke(chat_function, arguments=arguments)

# Extract function calls from the result
if result and result.value:
    message = result.value[-1]  # Get the last message
    function_calls = [
        item for item in message.items
        if isinstance(item, FunctionCallContent)
    ]

    if function_calls:
        # Process function calls manually
        for fc in function_calls:
            print(f"Function: {fc.name}")
            print(f"Arguments: {fc.arguments}")
            print(f"ID: {fc.id}")
```

### Pretty-Printing Tool Calls

Helper function to display tool call information:

```python
def print_tool_calls(message: ChatMessageContent) -> None:
    """
    Pretty print the tool calls found in a ChatMessageContent message.
    Useful when auto tool invocation is disabled.
    """
    items = message.items
    formatted_tool_calls = []

    for i, item in enumerate(items, start=1):
        if isinstance(item, FunctionCallContent):
            tool_call_id = item.id
            function_name = item.name
            function_arguments = item.arguments
            formatted_str = (
                f"tool_call {i} id: {tool_call_id}\n"
                f"tool_call {i} function name: {function_name}\n"
                f"tool_call {i} arguments: {function_arguments}"
            )
            formatted_tool_calls.append(formatted_str)

    if len(formatted_tool_calls) > 0:
        print("\n[Tool calls returned by the model]:\n" + "\n\n".join(formatted_tool_calls))
    else:
        print("\n[No tool calls returned by the model]")

# Usage
result = await kernel.invoke(chat_function, arguments=arguments)
if result and result.value:
    print_tool_calls(result.value[0])
```

**Example Output:**

```
[Tool calls returned by the model]:

tool_call 1 id: call_abc123
tool_call 1 function name: math-Add
tool_call 1 arguments: {"input": 5, "amount": 3}
```

### Manual Execution Pattern (Non-Streaming)

Complete example with manual function execution:

```python
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents import ChatHistory
from semantic_kernel.core_plugins import MathPlugin

# Setup
kernel = Kernel()
kernel.add_service(chat_completion_service)
kernel.add_plugin(MathPlugin(), plugin_name="math")

chat_function = kernel.add_function(
    prompt="{{$chat_history}}{{$user_input}}",
    plugin_name="ChatBot",
    function_name="Chat",
)

# Configure with auto_invoke=False
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(auto_invoke=False)
arguments = KernelArguments(settings=execution_settings)

history = ChatHistory()
user_input = "What is 7 + 3?"

arguments["user_input"] = user_input
arguments["chat_history"] = history

# Invoke with manual control
result = await kernel.invoke(chat_function, arguments=arguments)

# Check for function calls
function_calls = [
    item for item in result.value[-1].items
    if isinstance(item, FunctionCallContent)
]

if function_calls:
    print_tool_calls(result.value[0])

    # Implement your custom logic here:
    # - Validate function call authorization
    # - Log function calls for audit
    # - Apply rate limiting
    # - Execute with custom error handling

    # Example: Manual execution (if authorized)
    for fc in function_calls:
        if authorize_function_call(fc.name, user_role):
            # Execute the function manually
            function_result = await kernel.invoke_function_call(fc, history)
            # Process result...
else:
    # No function calls, just a regular response
    print(f"Assistant: {result}")
    history.add_user_message(user_input)
    history.add_assistant_message(str(result))
```

✓ **Best Practice**: Use manual function calling when you need control over execution (authorization, logging, rate limiting).

### Manual Execution Pattern (Streaming)

Handle function calls in streaming mode:

```python
from functools import reduce
from semantic_kernel.contents.streaming_chat_message_content import StreamingChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole

# Configure for streaming with auto_invoke=False
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(auto_invoke=False)

arguments["user_input"] = user_input
arguments["chat_history"] = history

print("Assistant: ", end="", flush=True)

streamed_tool_chunks = []
streamed_response_chunks = []

# Stream the response
async for message in kernel.invoke_stream(
    chat_function,
    return_function_results=False,
    arguments=arguments,
):
    msg = message[0]

    if not isinstance(msg, StreamingChatMessageContent) or msg.role != AuthorRole.ASSISTANT:
        continue

    # Separate tool calls from regular response text
    if hasattr(msg, "function_invoke_attempt"):
        streamed_tool_chunks.append(msg)
    else:
        streamed_response_chunks.append(msg)
        print(str(msg), end="", flush=True)

print("\n")

# Process collected tool call chunks
if streamed_tool_chunks:
    # Group by function_invoke_attempt
    grouped_chunks = {}
    for chunk in streamed_tool_chunks:
        key = getattr(chunk, "function_invoke_attempt", None)
        if key is not None:
            grouped_chunks.setdefault(key, []).append(chunk)

    # Process each function call attempt
    for attempt, chunks in grouped_chunks.items():
        combined_content = reduce(lambda first, second: first + second, chunks)

        print(f"[Function invoke attempt {attempt}]")
        print_tool_calls(combined_content)

        # Implement your custom execution logic here
```

✓ **Best Practice**: With streaming and manual calling, show users which tools are being invoked in real-time for transparency.

### Use Cases for Manual Function Calling

**Authorization and Security:**

```python
def authorize_function_call(function_name: str, user_role: str) -> bool:
    """Check if user is authorized to call this function."""
    admin_only_functions = ["database-Delete", "system-Restart"]

    if function_name in admin_only_functions:
        return user_role == "admin"

    return True  # All other functions allowed

# Use in manual execution
if authorize_function_call(fc.name, user_role):
    result = await kernel.invoke_function_call(fc, history)
else:
    print(f"Unauthorized: {fc.name} requires admin role")
```

**Rate Limiting:**

```python
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_calls: int, time_window: timedelta):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []

    def allow_call(self) -> bool:
        now = datetime.now()
        # Remove old calls outside time window
        self.calls = [t for t in self.calls if now - t < self.time_window]

        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        return False

rate_limiter = RateLimiter(max_calls=10, time_window=timedelta(minutes=1))

# Use in manual execution
if rate_limiter.allow_call():
    result = await kernel.invoke_function_call(fc, history)
else:
    print("Rate limit exceeded. Please try again later.")
```

**Audit Logging:**

```python
import logging

audit_logger = logging.getLogger("audit")

def log_function_call(function_name: str, arguments: str, user_id: str):
    audit_logger.info(
        f"Function call: {function_name} | Args: {arguments} | User: {user_id}"
    )

# Use in manual execution
for fc in function_calls:
    log_function_call(fc.name, fc.arguments, user_id)
    result = await kernel.invoke_function_call(fc, history)
```

---

<!-- section: advanced_patterns -->

## 7. Advanced Patterns

**Key Points:**

- Custom filters enable cross-cutting concerns (logging, validation, modification)
- `@kernel.filter(FilterTypes.AUTO_FUNCTION_INVOCATION)` decorates filter functions
- Filters can inspect, modify, or terminate function invocation
- Required mode with `maximum_auto_invoke_attempts` controls retry behavior
- Integration with specialized tools like Azure Python Code Interpreter

**Keywords**: function filters, AutoFunctionInvocationContext, kernel filters, FilterTypes, maximum_auto_invoke_attempts, Azure Code Interpreter, custom filters

### Custom Auto Function Invocation Filters

Filters intercept function calls before execution, enabling custom logic:

```python
from semantic_kernel.filters.auto_function_invocation.auto_function_invocation_context import (
    AutoFunctionInvocationContext,
)
from semantic_kernel.filters.filter_types import FilterTypes

@kernel.filter(FilterTypes.AUTO_FUNCTION_INVOCATION)
async def auto_function_invocation_filter(context: AutoFunctionInvocationContext, next):
    """
    A filter called for each function call in the response.

    Args:
        context: Contains function metadata, arguments, and control flow
        next: Call this to proceed to the next filter or the function itself
    """
    print(f"\n[Auto Function Invocation Filter]")
    print(f"  Function: {context.function.fully_qualified_name}")
    print(f"  Arguments: {context.arguments}")

    # Call next to execute the function
    # If you don't call next, the function is skipped
    await next(context)

    # Access the result after execution
    print(f"  Result: {context.function_result}")
```

**Filter Signature:**

- `context: AutoFunctionInvocationContext` - Contains function information and results
- `next` - Coroutine to invoke the next filter or the function itself

**AutoFunctionInvocationContext Properties:**

- `context.function` - The `KernelFunction` being invoked
- `context.function.fully_qualified_name` - Full name like "math-Add"
- `context.arguments` - `KernelArguments` passed to the function
- `context.function_result` - Result after execution (available after `await next(context)`)
- `context.terminate` - Set to `True` to stop the function calling sequence

### Terminating Function Invocation

Prevent a function from executing or stop the chain:

```python
@kernel.filter(FilterTypes.AUTO_FUNCTION_INVOCATION)
async def conditional_filter(context: AutoFunctionInvocationContext, next):
    """Only allow math functions, block all others."""
    function_name = context.function.fully_qualified_name

    if function_name.startswith("math-"):
        print(f"✓ Allowing function: {function_name}")
        await next(context)
    else:
        print(f"✗ Blocking function: {function_name}")
        # Don't call next - function won't execute
        context.terminate = True  # Stop the entire function calling sequence
```

✓ **Best Practice**: Use `context.terminate = True` when you want to abort the entire function calling process, not just skip one function.

### Modifying Function Arguments

Intercept and modify arguments before execution:

```python
@kernel.filter(FilterTypes.AUTO_FUNCTION_INVOCATION)
async def argument_modification_filter(context: AutoFunctionInvocationContext, next):
    """Add validation or modify arguments before execution."""
    function_name = context.function.fully_qualified_name

    # Example: Clamp math operations to safe ranges
    if function_name == "math-Add":
        input_val = context.arguments.get("input", 0)
        amount = context.arguments.get("amount", 0)

        # Clamp to prevent overflow
        MAX_VALUE = 1_000_000
        if abs(input_val) > MAX_VALUE or abs(amount) > MAX_VALUE:
            print(f"⚠ Clamping large values for safety")
            context.arguments["input"] = max(-MAX_VALUE, min(MAX_VALUE, input_val))
            context.arguments["amount"] = max(-MAX_VALUE, min(MAX_VALUE, amount))

    await next(context)
```

### Required Function Calling with Maximum Attempts

Control how many times the model can invoke functions:

```python
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior

# Require specific functions with custom attempt limit
execution_settings = OpenAIChatPromptExecutionSettings(
    service_id="chat",
    max_tokens=2000,
    temperature=0.7,
    function_choice_behavior=FunctionChoiceBehavior.Required(
        auto_invoke=False,
        filters={"included_functions": ["time-time", "time-date"]},
    ),
)
```

**Default Behavior:**

- `Auto` mode: `maximum_auto_invoke_attempts = 5`
- `Required` mode: `maximum_auto_invoke_attempts = 1`

**Customizing Maximum Attempts:**

```python
# Via code (if supported by your connector)
execution_settings.function_choice_behavior.maximum_auto_invoke_attempts = 3

# Via YAML config
# execution_settings:
#   chat:
#     function_choice_behavior:
#       type: required
#       maximum_auto_invoke_attempts: 3
#       functions:
#         - time.time
```

⚠️ **Warning**: If `maximum_auto_invoke_attempts` exceeds the number of unique functions the model calls, it may repeat function calls or return incomplete responses.

**Example Scenario:**

```python
# Config: Required mode, max_attempts=5, functions=["math-Multiply", "math-Add"]
# Query: "What is 3+4*5?"

# Execution:
# Attempt 1: math-Multiply(4, 5) → 20
# Attempt 2: math-Add(3, 20) → 23
# Attempts 3-5: Model may repeat math-Add since it's still in "required" mode
# Final: May return tool call response instead of natural language
```

✓ **Best Practice**: Set `maximum_auto_invoke_attempts` to match the expected number of function calls for the task, or use `Auto` mode for most scenarios.

### Azure Python Code Interpreter Integration

Execute Python code dynamically using Azure's code interpreter:

```python
from azure.identity import AzureCliCredential
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.core_plugins.sessions_python_tool.sessions_python_plugin import SessionsPythonTool
from semantic_kernel.core_plugins.time_plugin import TimePlugin

kernel = Kernel()

# Add Azure chat service
service_id = "sessions-tool"
credential = AzureCliCredential()
chat_service = AzureChatCompletion(service_id=service_id, credential=credential)
kernel.add_service(chat_service)

# Add the Sessions Python Tool
sessions_tool = SessionsPythonTool(credential=credential)
kernel.add_plugin(sessions_tool, "SessionsTool")
kernel.add_plugin(TimePlugin(), "Time")

# Create chat function
chat_function = kernel.add_function(
    prompt="{{$chat_history}}{{$user_input}}",
    plugin_name="ChatBot",
    function_name="Chat",
)

# Enable auto function calling
req_settings = AzureChatPromptExecutionSettings(
    service_id=service_id,
    tool_choice="auto"
)
req_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(
    filters={"excluded_plugins": ["ChatBot"]}
)

arguments = KernelArguments(settings=req_settings)
history = ChatHistory()

# Ask the model to execute Python code
arguments["chat_history"] = history
arguments["user_input"] = "What is 1+1? Use Python to calculate it."

answer = await kernel.invoke(function=chat_function, arguments=arguments)
print(f"Assistant: {answer}")

# The model automatically invokes SessionsPythonTool to execute Python code
```

**Use Cases:**

- Data analysis and visualization
- Mathematical computations beyond simple arithmetic
- File processing and manipulation
- Integration with Python libraries not available as kernel functions

✓ **Best Practice**: Use Azure Python Code Interpreter for complex computations or when you need full Python capabilities without defining explicit functions.

### Multi-Filter Chains

Register multiple filters for layered logic:

```python
@kernel.filter(FilterTypes.AUTO_FUNCTION_INVOCATION)
async def logging_filter(context: AutoFunctionInvocationContext, next):
    """First filter: Log all function calls."""
    print(f"[LOG] Calling: {context.function.fully_qualified_name}")
    await next(context)
    print(f"[LOG] Result: {context.function_result}")

@kernel.filter(FilterTypes.AUTO_FUNCTION_INVOCATION)
async def authorization_filter(context: AutoFunctionInvocationContext, next):
    """Second filter: Check authorization."""
    if is_authorized(context.function.fully_qualified_name):
        await next(context)
    else:
        print(f"[AUTH] Blocked: {context.function.fully_qualified_name}")
        context.terminate = True

@kernel.filter(FilterTypes.AUTO_FUNCTION_INVOCATION)
async def caching_filter(context: AutoFunctionInvocationContext, next):
    """Third filter: Cache results."""
    cache_key = f"{context.function.fully_qualified_name}:{context.arguments}"

    if cache_key in cache:
        print(f"[CACHE] Hit: {cache_key}")
        context.function_result = cache[cache_key]
    else:
        await next(context)
        cache[cache_key] = context.function_result
        print(f"[CACHE] Miss: {cache_key}")

# Filters execute in registration order:
# Request → logging_filter → authorization_filter → caching_filter → Function
```

---

<!-- section: best_practices -->

## 8. Best Practices

**Key Points:**

- Choose the right mode: Auto for flexibility, Required for guarantees, None to disable
- Always exclude chat/prompt functions from available tools
- Use filters for cross-cutting concerns (auth, logging, rate limiting)
- Handle errors gracefully with try-except blocks
- Consider token costs when exposing many functions
- Test with different model versions as capabilities vary

**Keywords**: best practices, production deployment, error handling, performance, security, token optimization, model compatibility

### Choosing the Right Function Choice Behavior

| Mode         | When to Use                                                             | Auto-Invoke Default |
| ------------ | ----------------------------------------------------------------------- | ------------------- |
| `Auto()`     | Most conversational AI scenarios where the model should decide          | `True`              |
| `Required()` | When specific functions must be called (e.g., always check permissions) | `False`             |
| `None()`     | When you want purely generative responses without tools                 | N/A                 |

**Decision Tree:**

```
Do you need function calling at all?
├─ No → Use FunctionChoiceBehavior.None()
└─ Yes → Do specific functions MUST be called?
    ├─ Yes → Use FunctionChoiceBehavior.Required()
    └─ No → Use FunctionChoiceBehavior.Auto()
```

### Plugin and Function Organization

**Do: Exclude Chat/Prompt Functions**

```python
# Always exclude the chat plugin to prevent recursive calls
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(
    filters={"excluded_plugins": ["ChatBot"]}
)
```

**Do: Use Descriptive Function Names and Descriptions**

```python
@kernel_function(
    name="calculate_loan_payment",  # Clear, specific name
    description="Calculate the monthly payment for a loan given the principal, interest rate, and term in months"  # Detailed description
)
def calculate_loan_payment(
    self,
    principal: Annotated[float, "The loan principal amount in dollars"],
    annual_rate: Annotated[float, "Annual interest rate as a percentage (e.g., 5.5 for 5.5%)"],
    months: Annotated[int, "Loan term in months"],
) -> Annotated[float, "Monthly payment amount"]:
    # Implementation
    pass
```

**Don't: Use Vague Descriptions**

```python
@kernel_function(
    name="calc",  # Too vague
    description="Does a calculation"  # Not helpful
)
def calc(self, a, b):  # No type hints
    pass
```

✓ **Best Practice**: Invest time in clear function names and detailed descriptions. The model relies on these to decide when to call functions.

### Error Handling

**Do: Wrap Kernel Invocations**

```python
from semantic_kernel.exceptions import KernelException

try:
    result = await kernel.invoke(chat_function, arguments=arguments)
    history.add_user_message(user_input)
    history.add_message(result.value[0])
except KernelException as e:
    logger.error(f"Kernel invocation failed: {e}")
    print("I'm sorry, I encountered an error processing your request.")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    print("An unexpected error occurred.")
```

**Do: Handle Function Execution Errors**

```python
@kernel_function(description="Divide two numbers")
def divide(
    self,
    numerator: Annotated[float, "The numerator"],
    denominator: Annotated[float, "The denominator"],
) -> Annotated[float, "The quotient"]:
    """Divide numerator by denominator."""
    if denominator == 0:
        raise ValueError("Cannot divide by zero")
    return numerator / denominator

# The kernel will catch this exception and report it to the model
# The model can then respond appropriately (e.g., "I can't divide by zero")
```

✓ **Best Practice**: Raise descriptive exceptions from functions. The model receives error messages and can handle them gracefully.

### Performance Optimization

**Do: Limit the Number of Available Functions**

```python
# Instead of exposing 50+ functions, use filters
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(
    filters={"included_functions": [
        "math-Add", "math-Subtract", "math-Multiply",
        "time-Date", "time-Time"
    ]}
)
```

**Why:** Each function's description is included in the prompt, consuming tokens. Fewer functions = lower cost and faster responses.

**Do: Design Functions for Parallel Execution**

```python
# Good: Independent functions that can run in parallel
@kernel_function(description="Get user's email")
async def get_user_email(self, user_id: str) -> str:
    # This can run in parallel with get_user_phone
    pass

@kernel_function(description="Get user's phone")
async def get_user_phone(self, user_id: str) -> str:
    # This can run in parallel with get_user_email
    pass
```

**Don't: Create Sequential Dependencies Unnecessarily**

```python
# Bad: Forces sequential execution
@kernel_function(description="Get user's ID by email")
async def get_user_id(self, email: str) -> str:
    pass

@kernel_function(description="Get user's phone by ID")
async def get_phone_by_id(self, user_id: str) -> str:
    # Must wait for get_user_id to complete
    pass

# Better: Combine into one function if they're always used together
@kernel_function(description="Get user's phone by email")
async def get_phone_by_email(self, email: str) -> str:
    user_id = await self.get_user_id(email)
    return await self.get_phone_by_id(user_id)
```

### Security Considerations

**Do: Validate Function Inputs**

```python
@kernel_function(description="Delete a file")
def delete_file(self, file_path: Annotated[str, "Path to the file"]) -> str:
    """Delete a file from the filesystem."""
    import os

    # Validate: Only allow files in specific directory
    allowed_dir = "/safe/user/files/"
    abs_path = os.path.abspath(file_path)

    if not abs_path.startswith(allowed_dir):
        raise ValueError(f"Cannot delete files outside {allowed_dir}")

    os.remove(abs_path)
    return f"Deleted {file_path}"
```

**Do: Use Authorization Filters**

```python
@kernel.filter(FilterTypes.AUTO_FUNCTION_INVOCATION)
async def authorization_filter(context: AutoFunctionInvocationContext, next):
    """Check user permissions before executing functions."""
    user_role = get_current_user_role()  # Get from context/session
    required_role = get_function_required_role(context.function.fully_qualified_name)

    if user_has_role(user_role, required_role):
        await next(context)
    else:
        logger.warning(f"Unauthorized function call: {context.function.fully_qualified_name}")
        context.terminate = True
```

**Don't: Expose Dangerous Functions Without Protection**

```python
# Bad: Unrestricted system access
@kernel_function(description="Execute a shell command")
def execute_command(self, command: str) -> str:
    import subprocess
    return subprocess.check_output(command, shell=True)
```

✓ **Best Practice**: Never expose unrestricted system access. Always validate inputs and implement authorization.

### Service Compatibility

Auto function calling is supported by these AI services:

| Service            | Function Calling Support | Notes                                      |
| ------------------ | ------------------------ | ------------------------------------------ |
| OpenAI             | ✓                        | Models gpt-3.5-turbo-0613+ and gpt-4-0613+ |
| Azure OpenAI       | ✓                        | Same model requirements as OpenAI          |
| Azure AI Inference | ✓                        | Service-dependent                          |
| Anthropic          | ✓                        | Claude 2.1+                                |
| Google AI          | ✓                        | Gemini models                              |
| Vertex AI          | ✓                        | Gemini models on Vertex                    |
| Mistral AI         | ✓                        | Specific models only                       |
| Bedrock            | ✓                        | Depends on underlying model                |
| Ollama             | ✓                        | Model-dependent                            |
| ONNX               | ✓                        | Limited support                            |
| DeepSeek           | ✓                        | Recent models                              |

⚠️ **Warning**: Not all models support function calling. Check your specific model's documentation.

**Testing for Compatibility:**

```python
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

service = OpenAIChatCompletion(service_id="test")

# Check if the service supports function calling
# (Most modern services do, but always test)
```

### Token Usage Optimization

**Do: Monitor Function Description Length**

```python
# Good: Concise but informative
@kernel_function(
    description="Add two numbers and return the sum"
)
def add(self, a: float, b: float) -> float:
    return a + b

# Bad: Overly verbose description wastes tokens
@kernel_function(
    description="""
    This function performs the mathematical operation of addition
    on two numeric inputs provided by the user. It takes two parameters,
    both of which should be numeric values (integers or floating-point numbers),
    and returns their sum as a result. This is useful for any scenario
    where arithmetic addition is required...
    """  # This consumes unnecessary tokens!
)
def add_verbose(self, a: float, b: float) -> float:
    return a + b
```

**Do: Use Function Filtering to Reduce Token Usage**

```python
# Context-aware filtering reduces tokens
if user_query_is_about_math():
    filters = {"included_plugins": ["math"]}
elif user_query_is_about_time():
    filters = {"included_plugins": ["time"]}
else:
    filters = {"excluded_plugins": ["ChatBot"]}

execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(filters=filters)
```

### Testing and Debugging

**Do: Enable Logging for Development**

```python
import logging

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)

# Or specific logger
logger = logging.getLogger("semantic_kernel.connectors.ai.chat_completion_client_base")
logger.setLevel(logging.DEBUG)
```

**Do: Test with Manual Mode First**

```python
# Start with auto_invoke=False to see what the model is calling
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(auto_invoke=False)

result = await kernel.invoke(chat_function, arguments=arguments)

# Inspect function calls
function_calls = [item for item in result.value[-1].items if isinstance(item, FunctionCallContent)]
for fc in function_calls:
    print(f"Model wants to call: {fc.name} with args: {fc.arguments}")

# Once verified, enable auto_invoke
```

**Do: Use Filters During Development**

```python
# During development, log every function call
@kernel.filter(FilterTypes.AUTO_FUNCTION_INVOCATION)
async def dev_logging_filter(context: AutoFunctionInvocationContext, next):
    import json
    print(f"\n{'='*60}")
    print(f"Function: {context.function.fully_qualified_name}")
    print(f"Arguments: {json.dumps(dict(context.arguments), indent=2)}")

    await next(context)

    print(f"Result: {context.function_result}")
    print(f"{'='*60}\n")
```

---

<!-- section: common_patterns -->

## 9. Common Patterns

**Key Points:**

- Standard chatbot pattern with math and time plugins is the foundation
- Multi-turn conversations require proper history management
- Complex workflows may need multiple invocation rounds
- Handle edge cases like no function calls or repeated attempts
- Streaming UX benefits from showing function call status

**Keywords**: chatbot pattern, conversation management, multi-turn conversations, edge cases, workflow patterns, user experience

### Standard Chatbot with Auto Function Calling

The most common pattern for building a conversational AI:

```python
import asyncio
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents import ChatHistory
from semantic_kernel.core_plugins import MathPlugin, TimePlugin
from semantic_kernel.functions import KernelArguments

# System message defines chatbot personality and capabilities
system_message = """
You are a helpful assistant. You can help with:
- Math calculations (addition, subtraction, multiplication, division)
- Time and date queries
- General questions using your knowledge
"""

# Initialize kernel
kernel = Kernel()
kernel.add_service(AzureChatCompletion(service_id="chat"))

# Add plugins for extended capabilities
kernel.add_plugin(MathPlugin(), plugin_name="math")
kernel.add_plugin(TimePlugin(), plugin_name="time")

# Create chat function
chat_function = kernel.add_function(
    prompt="{{$chat_history}}{{$user_input}}",
    plugin_name="ChatBot",
    function_name="Chat",
)

# Configure execution settings
execution_settings = AzureChatPromptExecutionSettings(
    service_id="chat",
    max_tokens=2000,
    temperature=0.7,
)

execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(
    filters={"excluded_plugins": ["ChatBot"]}
)

arguments = KernelArguments(settings=execution_settings)

# Initialize chat history
history = ChatHistory()
history.add_system_message(system_message)

async def chat() -> bool:
    """Handle a single chat turn."""
    try:
        user_input = input("User> ")
    except (KeyboardInterrupt, EOFError):
        print("\nExiting...")
        return False

    if user_input.lower().strip() == "exit":
        print("Goodbye!")
        return False

    # Prepare arguments
    arguments["user_input"] = user_input
    arguments["chat_history"] = history

    # Invoke with auto function calling
    result = await kernel.invoke(chat_function, arguments=arguments)

    # Display response
    if result:
        print(f"Assistant> {result}")

        # Update history
        history.add_user_message(user_input)
        history.add_message(result.value[0])

    return True

async def main():
    print("Chatbot initialized. Type 'exit' to quit.")
    print("Try asking: 'What is 15 + 27?' or 'What time is it?'\n")

    chatting = True
    while chatting:
        chatting = await chat()

if __name__ == "__main__":
    asyncio.run(main())
```

✓ **Best Practice**: This pattern is production-ready with minimal modifications (add error handling, logging, persistence).

### Multi-Turn Conversation with Context

Maintaining context across multiple turns:

```python
# Conversation demonstrating context maintenance
async def demo_conversation():
    history = ChatHistory()
    history.add_system_message("You are a helpful math tutor.")

    # Turn 1: User asks a math question
    arguments["user_input"] = "What is 15 + 27?"
    arguments["chat_history"] = history
    result = await kernel.invoke(chat_function, arguments=arguments)
    print(f"Assistant: {result}")  # "15 + 27 equals 42"
    history.add_user_message("What is 15 + 27?")
    history.add_message(result.value[0])

    # Turn 2: User references previous result
    arguments["user_input"] = "Now multiply that by 2"
    arguments["chat_history"] = history
    result = await kernel.invoke(chat_function, arguments=arguments)
    print(f"Assistant: {result}")  # "42 multiplied by 2 equals 84"
    history.add_user_message("Now multiply that by 2")
    history.add_message(result.value[0])

    # Turn 3: User asks follow-up
    arguments["user_input"] = "What was the first number I asked about?"
    arguments["chat_history"] = history
    result = await kernel.invoke(chat_function, arguments=arguments)
    print(f"Assistant: {result}")  # "The first calculation was 15 + 27"
    history.add_user_message("What was the first number I asked about?")
    history.add_message(result.value[0])
```

**Key Points:**

- Always update history after each turn
- The model uses history to maintain context
- Function calls are automatically incorporated into history

### Streaming Chatbot with Status Updates

Enhanced UX by showing function calling status:

```python
async def chat_with_status():
    """Chat with visual feedback on function calls."""
    user_input = input("User> ")

    arguments["user_input"] = user_input
    arguments["chat_history"] = history

    print("Assistant> ", end="", flush=True)

    streamed_chunks = []
    function_calls_made = False

    async for message in kernel.invoke_stream(
        chat_function,
        return_function_results=False,
        arguments=arguments,
    ):
        msg = message[0]

        if isinstance(msg, StreamingChatMessageContent) and msg.role == AuthorRole.ASSISTANT:
            streamed_chunks.append(msg)
            print(str(msg), end="", flush=True)

    print("\n")

    # Update history
    if streamed_chunks:
        result = "".join([str(content) for content in streamed_chunks])
        history.add_user_message(user_input)
        history.add_assistant_message(result)
```

**Enhanced Version with Function Call Indicators:**

```python
async def chat_with_function_indicators():
    """Show when functions are being called."""
    user_input = input("User> ")

    # Add a custom filter to show function call status
    @kernel.filter(FilterTypes.AUTO_FUNCTION_INVOCATION)
    async def status_filter(context: AutoFunctionInvocationContext, next):
        # Show what's being called
        print(f"  [Calling {context.function.fully_qualified_name}...]", end="", flush=True)
        await next(context)
        print(f" Done")

    arguments["user_input"] = user_input
    arguments["chat_history"] = history

    print("Assistant> ", end="", flush=True)

    # Stream response
    # (Functions execute before streaming starts)
    async for message in kernel.invoke_stream(chat_function, arguments=arguments):
        msg = message[0]
        if isinstance(msg, StreamingChatMessageContent):
            print(str(msg), end="", flush=True)

    print("\n")
```

**Example Output:**

```
User> What is 15 + 27?
  [Calling math-Add...] Done
Assistant> The sum of 15 and 27 is 42.
```

### Handling Edge Cases

**No Function Calls Made:**

```python
result = await kernel.invoke(chat_function, arguments=arguments)

# Check if any function calls were made
# (This is automatic with auto_invoke=True, but useful for logging)
if result and result.value:
    message = result.value[0]
    has_function_calls = any(
        isinstance(item, FunctionCallContent)
        for item in message.items
    )

    if has_function_calls:
        logger.info("Response included function calls")
    else:
        logger.info("Response used only model knowledge")
```

**Maximum Attempts Reached:**

```python
# With maximum_auto_invoke_attempts set
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()
execution_settings.function_choice_behavior.maximum_auto_invoke_attempts = 3

result = await kernel.invoke(chat_function, arguments=arguments)

# If the model hasn't finished after 3 attempts, it may return a partial response
# Check the response and handle accordingly
if "I need more information" in str(result).lower():
    print("The assistant needs additional context. Please provide more details.")
```

**Empty or Invalid Responses:**

```python
try:
    result = await kernel.invoke(chat_function, arguments=arguments)

    if not result or not result.value:
        print("Assistant> I'm sorry, I didn't generate a response. Please try again.")
        return True

    print(f"Assistant> {result}")
    history.add_user_message(user_input)
    history.add_message(result.value[0])

except Exception as e:
    logger.error(f"Error during invocation: {e}")
    print("Assistant> I encountered an error. Please try again.")
    return True
```

### Complex Workflows

**Sequential Function Calls:**

```python
# Query that requires multiple sequential steps
# Example: "Find employee John's ID, then get his email"

# The model will:
# 1. Call get_employee_id(name="John") → id=123
# 2. Call get_employee_email(id=123) → email="john@example.com"
# 3. Generate response: "John's email is john@example.com"

query = "Find employee John's ID, then get his email"
result = await kernel.invoke_prompt(query, arguments=arguments)
print(result)
```

**Parallel + Sequential Combination:**

```python
# Query: "Get John's and Mary's IDs, then find their common manager"

# The model will:
# 1. Parallel: get_employee_id(name="John") and get_employee_id(name="Mary")
# 2. Sequential: get_common_manager(id1=123, id2=456)
# 3. Generate response

query = "Get John's and Mary's IDs, then find their common manager"
result = await kernel.invoke_prompt(query, arguments=arguments)
print(result)
```

### Troubleshooting Common Issues

**Issue: Functions Are Not Being Called**

**Possible Causes:**

1. Function descriptions are unclear
2. Function names don't match model expectations
3. `FunctionChoiceBehavior` is set to `None` or not configured
4. Functions are filtered out

**Solutions:**

```python
# 1. Improve function descriptions
@kernel_function(
    description="Add two numbers together and return the sum"  # Clear and specific
)

# 2. Check configuration
print(execution_settings.function_choice_behavior)  # Should not be None

# 3. Verify filters
filters = execution_settings.function_choice_behavior.filters
print(f"Filters: {filters}")  # Make sure needed functions aren't excluded

# 4. Test with auto_invoke=False to see what the model tries
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(auto_invoke=False)
result = await kernel.invoke(chat_function, arguments=arguments)
# Check if FunctionCallContent exists in result
```

**Issue: Wrong Functions Are Called**

**Possible Causes:**

1. Similar function names/descriptions causing confusion
2. Too many functions available
3. Model version doesn't support function calling well

**Solutions:**

```python
# 1. Make descriptions more distinct
@kernel_function(
    description="Add two numbers (a + b)"  # Specify format
)
def add(self, a: float, b: float) -> float:
    pass

@kernel_function(
    description="Concatenate two strings (str1 + str2)"  # Different operation
)
def concat(self, str1: str, str2: str) -> str:
    pass

# 2. Reduce available functions with filters
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto(
    filters={"included_functions": ["math-Add", "math-Subtract"]}
)

# 3. Upgrade model or adjust temperature
execution_settings.temperature = 0.3  # Lower temperature = more deterministic
```

**Issue: Infinite or Repeated Function Calls**

**Possible Causes:**

1. Function returns data the model doesn't understand
2. Function errors not properly reported
3. `maximum_auto_invoke_attempts` set too high

**Solutions:**

```python
# 1. Return clear, structured responses
@kernel_function(description="Get user info")
def get_user(self, user_id: str) -> str:
    user = database.get_user(user_id)
    # Good: Return formatted string
    return f"User {user.name}, email: {user.email}, role: {user.role}"
    # Bad: Return complex object or raw JSON that's unclear

# 2. Raise clear exceptions
@kernel_function(description="Get user info")
def get_user(self, user_id: str) -> str:
    user = database.get_user(user_id)
    if not user:
        raise ValueError(f"User with ID {user_id} not found")
    return f"User {user.name}, email: {user.email}"

# 3. Limit maximum attempts
execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()
execution_settings.function_choice_behavior.maximum_auto_invoke_attempts = 3
```

---

## 10. Quick Reference

| Task                               | Code                                                                                 |
| ---------------------------------- | ------------------------------------------------------------------------------------ |
| Enable auto function calling       | `execution_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()`        |
| Disable auto-invoke                | `FunctionChoiceBehavior.Auto(auto_invoke=False)`                                     |
| Require specific functions         | `FunctionChoiceBehavior.Required(filters={"included_functions": ["time-Date"]})`     |
| Exclude plugins                    | `FunctionChoiceBehavior.Auto(filters={"excluded_plugins": ["ChatBot"]})`             |
| Include only specific functions    | `FunctionChoiceBehavior.Auto(filters={"included_functions": ["math-Add"]})`          |
| Non-streaming invocation           | `result = await kernel.invoke(function, arguments=arguments)`                        |
| Streaming invocation               | `async for msg in kernel.invoke_stream(function, arguments=arguments):`              |
| Extract function calls             | `[item for item in result.value[-1].items if isinstance(item, FunctionCallContent)]` |
| Add custom filter                  | `@kernel.filter(FilterTypes.AUTO_FUNCTION_INVOCATION)`                               |
| Access function in filter          | `context.function.fully_qualified_name`                                              |
| Terminate function calling         | `context.terminate = True`                                                           |
| Check filter result                | `context.function_result` (after `await next(context)`)                              |
| Set max attempts                   | `execution_settings.function_choice_behavior.maximum_auto_invoke_attempts = 5`       |
| Configure in YAML                  | `function_choice_behavior: {type: auto, maximum_auto_invoke_attempts: 5}`            |
| Disable streaming function results | `kernel.invoke_stream(function, return_function_results=False, arguments=args)`      |

---

## Supported Services

Auto function calling is supported by the following connectors:

- **OpenAI** (`OpenAIChatCompletion`)
- **Azure OpenAI** (`AzureChatCompletion`)
- **Azure AI Inference** (`AzureAIInferenceChatCompletion`)
- **Anthropic** (`AnthropicChatCompletion`)
- **Google AI** (`GoogleAIChatCompletion`)
- **Vertex AI** (`VertexAIChatCompletion`)
- **Mistral AI** (`MistralAIChatCompletion`)
- **Amazon Bedrock** (`BedrockChatCompletion`)
- **Ollama** (`OllamaChatCompletion`)
- **ONNX** (`ONNXGenAIChatCompletion`)
- **DeepSeek** (`DeepSeekChatCompletion`)

⚠️ **Note**: Function calling support depends on the underlying model version. Check your specific model's documentation for capabilities.

---

## Additional Resources

- **Core Plugins**: Use built-in plugins (`MathPlugin`, `TimePlugin`) for common operations
- **Custom Plugins**: Create your own using `@kernel_function` decorator
- **Filters**: Implement cross-cutting concerns with `@kernel.filter()`
- **Configuration**: Store settings in YAML/JSON for version control and team sharing
- **Performance**: Leverage parallel execution for independent function calls

For more examples, see the sample files in `python/samples/concepts/auto_function_calling/`.
