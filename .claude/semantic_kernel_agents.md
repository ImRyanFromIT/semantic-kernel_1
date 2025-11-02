---
document_type: technical_reference
topic: semantic_kernel_agents
framework: semantic_kernel
language: python
version: 1.0
last_updated: 2025-10-26
subtopics:
  - agent_fundamentals
  - conversation_management
  - human_in_the_loop
  - multi_agent_orchestration
  - structured_outputs
  - logging_and_observability
  - error_handling
  - common_patterns
---

# Semantic Kernel Agents - Reference

## Core Concepts

**Key Points:**

- ChatCompletionAgent is the primary class for building conversational AI
- Threads maintain conversation state across multiple turns
- Orchestration patterns enable multi-agent coordination
- Agents support both streaming and non-streaming response modes

**Keywords**: ChatCompletionAgent, conversation management, threads, orchestration, agent patterns, response streaming

### Agent Architecture

A `ChatCompletionAgent` is a conversational AI component that can:

- Process user messages and generate responses
- Maintain conversation history via threads
- Invoke plugins/tools autonomously
- Participate in multi-agent workflows
- Stream responses for real-time interaction

**Key Characteristics:**

- Service-based or kernel-based configuration
- Instruction-driven behavior
- Stateless agent design (state managed by threads)
- Supports both Azure and OpenAI services

---

<!-- section: agent_fundamentals -->

## 1. Agent Fundamentals

**Key Points:**

- Two configuration approaches: service-based and kernel-based
- Keep agent instructions clear and focused
- Choose configuration based on whether plugins are needed
- Service-based is simpler, kernel-based enables plugins and reuse

**Keywords**: ChatCompletionAgent creation, service configuration, kernel configuration, agent instructions

### Basic Agent Creation

```python
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from azure.identity import AzureCliCredential

agent = ChatCompletionAgent(
    service=AzureChatCompletion(credential=AzureCliCredential()),
    name="Assistant",
    instructions="You are a helpful assistant that manages user requests.",
)
```

✓ **Best Practice**: Keep instructions clear and focused. Be specific about agent capabilities and boundaries.

### Kernel-Based Configuration

```python
from semantic_kernel import Kernel

service_id = "agent"
kernel = Kernel()
kernel.add_service(AzureChatCompletion(service_id=service_id, credential=AzureCliCredential()))

agent = ChatCompletionAgent(
    kernel=kernel,
    name="Assistant",
    instructions="Manage user requests and database operations.",
)
```

✓ **Best Practice**: Use kernel-based configuration when you need to share services or plugins across multiple agents.

⚠️ **Warning**: Choose either `service=` or `kernel=` parameter, not both.

---

<!-- section: conversation_management -->

## 2. Conversation Management

**Key Points:**

- Threads maintain conversation state across multiple turns
- Two response modes: streaming (invoke) and non-streaming (get_response)
- Always preserve thread references for context continuity
- Threads should be cleaned up when conversations end

**Keywords**: ChatHistoryAgentThread, conversation state, thread management, streaming responses, invoke method, get_response method

### Thread Management

**Use Case**: Maintaining conversation context across multiple user interactions

Threads maintain conversation history across multiple turns:

```python
from semantic_kernel.agents import ChatHistoryAgentThread

# Initialize thread (None for first interaction)
thread: ChatHistoryAgentThread = None

# For each user message
user_input = "Create a user account for John Doe"
async for response in agent.invoke(messages=user_input, thread=thread):
    print(f"{response.name}: {response}")
    thread = response.thread  # Preserve thread for next interaction

# Always cleanup
await thread.delete() if thread else None
```

✓ **Best Practice**: Always preserve the `thread` reference returned from agent responses.

✓ **Best Practice**: Use `await thread.delete()` in cleanup to free resources.

### Streaming vs Non-Streaming

```python
# Streaming (use invoke) - returns async iterator
async for response in agent.invoke(messages=user_input, thread=thread):
    print(f"{response.name}: {response}")
    thread = response.thread

# Non-streaming (use get_response) - returns single response
response = await agent.get_response(messages=user_input, thread=thread)
print(f"{response.name}: {response}")
thread = response.thread
```

✓ **Best Practice**: Use `invoke()` for real-time user interfaces. Use `get_response()` for batch processing or when you need the complete response at once.

### Thread Persistence

**Use Case**: Maintaining conversation context across sessions or application restarts

```python
# Store thread reference for later retrieval
thread_id = thread.id
session_store[user_id] = thread_id

# Retrieve thread in next interaction
stored_thread_id = session_store.get(user_id)
# Note: Thread reconstruction from ID requires additional implementation
```

✓ **Best Practice**: Store thread references to maintain conversation context across sessions.

---

<!-- section: human_in_the_loop -->

## 3. Human-in-the-Loop Patterns

**Key Points:**

- Custom managers control when human input is requested
- `should_request_user_input()` determines escalation triggers
- `human_response_function` integrates human input into agent workflows
- Escalation can be explicit (via plugins) or implicit (via managers)

**Keywords**: human escalation, RoundRobinGroupChatManager, should_request_user_input, human_response_function, escalation patterns

### Custom Manager for Escalation

**Use Case**: Automatically pausing agent workflows to request human intervention based on conversation state

```python
from semantic_kernel.agents.orchestration.group_chat import RoundRobinGroupChatManager, BooleanResult
from semantic_kernel.contents import ChatHistory, AuthorRole, ChatMessageContent

class EscalationManager(RoundRobinGroupChatManager):
    """Custom manager that escalates to human when agent needs help."""

    async def should_request_user_input(self, chat_history: ChatHistory) -> BooleanResult:
        """Determine if human intervention is needed."""
        if len(chat_history.messages) == 0:
            return BooleanResult(result=False, reason="No messages yet.")

        last_message = chat_history.messages[-1]

        # Escalation triggers
        escalation_keywords = ["escalate", "human needed", "cannot proceed", "requires approval"]
        if any(keyword in last_message.content.lower() for keyword in escalation_keywords):
            return BooleanResult(result=True, reason="Agent requested escalation.")

        return BooleanResult(result=False, reason="No escalation needed.")

# Human response function
async def human_response_function(chat_history: ChatHistory) -> ChatMessageContent:
    """Get input from human operator."""
    # In production, this would integrate with your ticketing/notification system
    user_input = await get_human_input_from_system()
    return ChatMessageContent(role=AuthorRole.USER, content=user_input)
```

✓ **Best Practice**: Define clear escalation criteria (keywords, confidence thresholds, specific scenarios).

✓ **Best Practice**: Integrate human response functions with your existing ticketing or notification systems.

### Escalation via Plugins

**Use Case**: Allowing agents to explicitly trigger human escalation through function calls

```python
from semantic_kernel.functions import kernel_function
from typing import Annotated

class EscalationPlugin:
    @kernel_function(description="Escalate to human when agent needs assistance.")
    def escalate_to_human(
        self,
        reason: Annotated[str, "Reason for escalation"],
    ) -> Annotated[str, "Escalation confirmation"]:
        """Notify human operators and pause automated responses."""
        # Your notification logic here
        return f"Escalated to human operator: {reason}"
```

✓ **Best Practice**: Make escalation a plugin function that agents can invoke autonomously.

---

<!-- section: multi_agent_orchestration -->

## 4. Multi-Agent Orchestration

**Key Points:**

- Handoff orchestration enables dynamic agent-to-agent transfers
- `OrchestrationHandoffs` defines routing relationships between agents
- `InProcessRuntime` manages agent lifecycle
- Agent callbacks provide observability into multi-agent workflows

**Keywords**: HandoffOrchestration, OrchestrationHandoffs, InProcessRuntime, agent callbacks, multi-agent patterns, agent routing

### Handoff Pattern for Dynamic Routing

**Use Case**: Routing conversations between specialized agents based on request type or complexity

Use handoff orchestration when conversations need dynamic routing between specialized agents:

```python
from semantic_kernel.agents import HandoffOrchestration, OrchestrationHandoffs
from semantic_kernel.agents.runtime import InProcessRuntime

# Define specialized agents
support_agent = ChatCompletionAgent(
    name="SupportAgent",
    instructions="Handle general customer inquiries and route to specialists.",
    service=AzureChatCompletion(credential=AzureCliCredential()),
)

refund_agent = ChatCompletionAgent(
    name="RefundAgent",
    instructions="Process refund requests.",
    service=AzureChatCompletion(credential=AzureCliCredential()),
    plugins=[RefundPlugin()],
)

order_agent = ChatCompletionAgent(
    name="OrderAgent",
    instructions="Check order status and tracking.",
    service=AzureChatCompletion(credential=AzureCliCredential()),
    plugins=[OrderPlugin()],
)

# Define handoff relationships
handoffs = (
    OrchestrationHandoffs()
    .add_many(
        source_agent=support_agent.name,
        target_agents={
            refund_agent.name: "Transfer for refund-related issues",
            order_agent.name: "Transfer for order status inquiries",
        },
    )
    .add(
        source_agent=refund_agent.name,
        target_agent=support_agent.name,
        description="Return to support after processing refund",
    )
)

# Create orchestration
orchestration = HandoffOrchestration(
    members=[support_agent, refund_agent, order_agent],
    handoffs=handoffs,
)

# Run with runtime
runtime = InProcessRuntime()
runtime.start()

result = await orchestration.invoke(
    task="I need help with my order",
    runtime=runtime,
)

await result.get()
await runtime.stop_when_idle()
```

✓ **Best Practice**: Use handoff orchestration for scenarios where the conversation flow is dynamic and requires routing between specialists.

✓ **Best Practice**: Define clear handoff descriptions that guide when transfers should occur.

### Agent Callbacks for Observability

```python
from semantic_kernel.contents import ChatMessageContent, FunctionCallContent, FunctionResultContent

def agent_response_callback(message: ChatMessageContent) -> None:
    """Track all agent actions and responses."""
    print(f"[{message.name}] {message.content}")

    # Log function calls
    for item in message.items:
        if isinstance(item, FunctionCallContent):
            log_function_call(item.name, item.arguments)
        if isinstance(item, FunctionResultContent):
            log_function_result(item.name, item.result)

# Use in orchestration
orchestration = HandoffOrchestration(
    members=agents,
    handoffs=handoffs,
    agent_response_callback=agent_response_callback,
)
```

✓ **Best Practice**: Use agent callbacks to track all agent actions, function calls, and results for debugging and auditing.

---

<!-- section: structured_outputs -->

## 5. Structured Outputs

**Key Points:**

- Structured outputs force agents to return data in a specific Pydantic model format
- Use `response_format` in prompt execution settings to configure
- Always validate with `model_validate()` before using the data
- Requires compatible models (GPT-4 or newer)

**Keywords**: structured outputs, Pydantic models, response_format, AzureChatPromptExecutionSettings, model validation

### Using Pydantic Models for Reliable Data

**Use Case**: Ensuring agents return consistently formatted data for downstream processing

Structured outputs ensure consistent, parseable responses from agents:

```python
from pydantic import BaseModel
import json

# Define structured output models
class Step(BaseModel):
    explanation: str
    output: str

class Reasoning(BaseModel):
    steps: list[Step]
    final_answer: str

# Configure agent with structured output
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings

settings = AzureChatPromptExecutionSettings()
settings.response_format = Reasoning

agent = ChatCompletionAgent(
    service=AzureChatCompletion(credential=AzureCliCredential()),
    name="Assistant",
    instructions="Answer the user's questions with step-by-step reasoning.",
    arguments=KernelArguments(settings=settings),
)

# Parse and validate response
response = await agent.get_response(messages="How can I solve 8x + 7y = -23, and 4x=12?")
reasoned_result = Reasoning.model_validate(json.loads(response.message.content))

# Access structured data
for step in reasoned_result.steps:
    print(f"Step: {step.explanation} → {step.output}")
print(f"Final: {reasoned_result.final_answer}")
```

✓ **Best Practice**: Use structured outputs when you need consistent, parseable data formats (API responses, data processing, etc.).

✓ **Best Practice**: Always validate with `model_validate()` before using the data.

⚠️ **Warning**: Structured outputs require compatible models (GPT-4 or newer). Check model support before deployment.

---

<!-- section: logging_and_observability -->

## 6. Logging and Observability

**Key Points:**

- Semantic Kernel automatically logs agent interactions when logging is enabled
- Use Python's standard logging module to capture SK events
- INFO level provides good production visibility
- DEBUG level shows detailed execution traces

**Keywords**: logging, observability, agent monitoring, logging.basicConfig, agent callbacks

### Basic Logging

**Use Case**: Monitoring agent behavior and troubleshooting issues

```python
import logging

# Enable logging at application startup
logging.basicConfig(level=logging.INFO)

# Semantic Kernel automatically logs agent interactions
```

✓ **Best Practice**: Enable `logging.INFO` level minimum for production. Use `logging.DEBUG` for troubleshooting.

### Agent Callbacks for Observability

**Use Case**: Tracking agent actions and function calls for debugging and analytics

```python
from semantic_kernel.contents import ChatMessageContent, FunctionCallContent, FunctionResultContent

def agent_response_callback(message: ChatMessageContent) -> None:
    """Track all agent actions and responses."""
    print(f"[{message.name}] {message.content}")

    # Log function calls
    for item in message.items:
        if isinstance(item, FunctionCallContent):
            print(f"Calling function: {item.name}")
        if isinstance(item, FunctionResultContent):
            print(f"Function result from {item.name}: {item.result}")

# Use in orchestration
orchestration = HandoffOrchestration(
    members=agents,
    handoffs=handoffs,
    agent_response_callback=agent_response_callback,
)
```

✓ **Best Practice**: Use agent callbacks to observe function calls and agent behavior in multi-agent workflows.

---

<!-- section: error_handling -->

## 7. Error Handling and Resilience

**Key Points:**

- Always clean up threads with try-finally blocks
- Use asyncio.timeout for preventing hanging operations
- Handle exceptions specific to agent operations
- Thread cleanup is critical for resource management

**Keywords**: error handling, thread cleanup, try-finally, asyncio timeout, exception handling, resource management

### Thread Cleanup Pattern

**Use Case**: Ensuring threads are properly cleaned up even when errors occur

```python
async def process_request(user_input: str):
    thread = None
    try:
        async for response in agent.invoke(messages=user_input, thread=thread):
            thread = response.thread
            # Process response
    except Exception as e:
        print(f"Error processing request: {e}")
        # Handle error
    finally:
        # Always cleanup resources
        if thread:
            await thread.delete()
```

✓ **Best Practice**: Always use try-finally blocks to ensure thread cleanup.

### Timeout Support

**Use Case**: Preventing agent operations from hanging indefinitely

```python
import asyncio

async def process_with_timeout(user_input: str, timeout_seconds: int = 30):
    """Process request with timeout support."""
    try:
        async with asyncio.timeout(timeout_seconds):
            response = await agent.get_response(messages=user_input, thread=thread)
            return response
    except asyncio.TimeoutError:
        print("Request timed out")
        return None
```

✓ **Best Practice**: Implement timeouts for agent operations in production systems.

---

<!-- section: common_patterns -->

## 8. Common Agent Patterns

**Key Points:**

- Three fundamental patterns: Single Agent, Multi-Agent Handoff, and Group Chat
- Choose pattern based on workflow complexity and routing needs
- Thread management strategies depend on conversation duration
- Start with simple patterns and add complexity as needed

**Keywords**: agent patterns, single agent, multi-agent, handoff orchestration, group chat, pattern selection

### Pattern: Single Agent with Plugins

**Use Case**: Simple conversational workflows with tool/function calling

```python
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

agent = ChatCompletionAgent(
    service=AzureChatCompletion(credential=AzureCliCredential()),
    name="Assistant",
    instructions="You are a helpful assistant.",
    plugins=[MenuPlugin(), SearchPlugin()],
)

# Handle conversation with thread management
async def handle_conversation(user_input: str, thread=None):
    async for response in agent.invoke(messages=user_input, thread=thread):
        thread = response.thread
        return response, thread
```

✓ **Best Practice**: Start with single agent pattern for most use cases.

### Pattern: Multi-Agent Handoff

**Use Case**: Specialized agents for different domains or capabilities

```python
from semantic_kernel.agents import HandoffOrchestration, OrchestrationHandoffs
from semantic_kernel.agents.runtime import InProcessRuntime

# Create specialized agents
support_agent = ChatCompletionAgent(name="Support", ...)
technical_agent = ChatCompletionAgent(name="Technical", ...)

# Define handoffs
handoffs = OrchestrationHandoffs().add_many(
    source_agent=support_agent.name,
    target_agents={technical_agent.name: "Transfer for technical issues"}
)

orchestration = HandoffOrchestration(
    members=[support_agent, technical_agent],
    handoffs=handoffs,
)

# Execute with runtime
runtime = InProcessRuntime()
runtime.start()
result = await orchestration.invoke(task="Help me", runtime=runtime)
```

✓ **Best Practice**: Use handoff orchestration for domain-specific routing.

### Architecture Decision Guide

**When to use Single Agent:**

- Simple Q&A or task completion
- All capabilities can be handled by one agent
- No need for specialized expertise routing

**When to use Handoff Orchestration:**

- Multiple specialized domains (technical support, billing, etc.)
- Dynamic routing based on conversation context
- Need to transfer conversations between specialists

**When to use Group Chat:**

- Collaborative decision-making between agents
- Multiple perspectives needed on same problem
- Complex workflows requiring agent coordination

---

<!-- section: quick_reference -->

## Quick Reference

### Essential Imports

```python
from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.agents import HandoffOrchestration, OrchestrationHandoffs
from azure.identity import AzureCliCredential
```

### Common Patterns Checklist

- ✓ Use kernel-based configuration when sharing services across agents
- ✓ Maintain thread references for conversation continuity
- ✓ Implement try-finally blocks for thread cleanup
- ✓ Use structured outputs for consistent data formats
- ✓ Enable logging.INFO level minimum for observability
- ✓ Define clear escalation criteria for human-in-the-loop scenarios
- ✓ Use handoff orchestration for specialized agent routing
- ✓ Implement timeouts for agent operations

---

## Related Documentation

- [Kernel Fundamentals](../getting_started/KERNEL_FUNDAMENTALS.md) - Core Semantic Kernel concepts
- [Process Orchestration](../getting_started_with_processes/semantic_kernel_processes_claude.md) - Step-based workflows
- [Chat Completion Samples](./chat_completion/) - Complete working examples
- [Multi-Agent Orchestration Samples](./multi_agent_orchestration/) - Advanced patterns

---

**Document Version**: 1.0  
**Last Updated**: 2025-10  
**Target SK Version**: 1.27.0+
