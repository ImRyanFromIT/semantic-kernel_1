---
document_type: technical_reference
topic: chat_history_management
framework: semantic_kernel
language: python
version: 1.0
last_updated: 2025-10-26
subtopics:
  - introduction_and_core_concepts
  - basic_usage
  - persistence_strategies
  - reduction_strategies
  - advanced_patterns
  - code_patterns
  - best_practices
  - common_pitfalls
---

---

## Introduction and Core Concepts

### What is ChatHistory?

`ChatHistory` is a core component in Semantic Kernel that maintains the conversational context between users and AI assistants. It stores a sequence of messages that form a conversation, enabling the AI to understand context and provide coherent responses across multiple turns.

### Basic Architecture

A conversational AI application in Semantic Kernel typically consists of two main components:

1. **ChatHistory**: Tracks and stores conversation messages
2. **ChatCompletionService**: Generates AI responses based on the chat history

```python
from semantic_kernel.contents import ChatHistory
from samples.concepts.setup.chat_completion_services import get_chat_completion_service_and_request_settings

# Create chat history and service
chat_history = ChatHistory(system_message="You are a helpful assistant.")
chat_completion_service, request_settings = get_chat_completion_service_and_request_settings(Services.OPENAI)
```

### Message Types

Chat histories contain four primary message types:

- **System Messages**: Define the AI's behavior, personality, and constraints
- **User Messages**: Input from the human user
- **Assistant Messages**: Responses from the AI assistant
- **Tool Messages**: Results from function/tool calls

Each message type plays a specific role in maintaining conversational context and enabling function calling capabilities.

---

## Basic Chat History Usage

### Creating and Using ChatHistory

The simplest way to build a chatbot is to use a `ChatHistory` object with a `ChatCompletionService`.

```python
from semantic_kernel.contents import ChatHistory

# Create chat history with system message
system_message = "You are a helpful assistant."
chat_history = ChatHistory(system_message=system_message)

# Add user message
chat_history.add_user_message("Hello, how are you?")

# Get response from chat completion service
response = await chat_completion_service.get_chat_message_content(
    chat_history=chat_history,
    settings=request_settings,
)

# Add assistant response to history
if response:
    print(f"Assistant: {response}")
    chat_history.add_message(response)
```

### Adding Messages

The `ChatHistory` class provides convenient methods for adding different message types:

```python
# Add system message (typically done once at initialization)
chat_history.add_system_message("You are a helpful assistant.")

# Add user message
chat_history.add_user_message("What is the weather today?")

# Add assistant message
chat_history.add_assistant_message("I can help you with that.")

# Add a generic message (useful for adding response objects directly)
chat_history.add_message(response)

# Add tool/function result message
chat_history.add_tool_message([function_result_content])
```

### Basic Chat Loop Pattern

A typical chat loop follows this pattern:

```python
async def chat() -> bool:
    """
    Prompt the user for input and show the assistant's response.
    Returns False to exit the loop.
    """
    try:
        user_input = input("User:> ")
    except (KeyboardInterrupt, EOFError):
        print("\n\nExiting chat...")
        return False

    if user_input.lower().strip() == "exit":
        print("\n\nExiting chat...")
        return False

    # Add user message to history
    chat_history.add_user_message(user_input)

    # Get AI response
    response = await chat_completion_service.get_chat_message_content(
        chat_history=chat_history,
        settings=request_settings,
    )

    if response:
        print(f"Assistant:> {response}")
        # Add response to history for context continuity
        chat_history.add_message(response)

    return True

# Main loop
async def main() -> None:
    chatting = True
    while chatting:
        chatting = await chat()
```

---

## Chat History Persistence

Persistent chat histories enable conversations to continue across sessions, providing continuity and a better user experience.

### File-Based Serialization

The simplest persistence mechanism is JSON file serialization.

#### Saving Chat History

```python
# Store chat history to a JSON file
chat_history.store_chat_history_to_file(file_path="chat_session.json")
```

#### Loading Chat History

```python
from semantic_kernel.contents import ChatHistory

try:
    # Load existing chat history from file
    chat_history = ChatHistory.load_chat_history_from_file(file_path="chat_session.json")
    print(f"Loaded {len(chat_history.messages)} messages.")
except Exception:
    # Create new chat history if file doesn't exist
    print("Chat history file not found. Starting a new conversation.")
    chat_history = ChatHistory()
    chat_history.add_system_message("You are a helpful assistant.")
```

#### JSON Format

Chat histories are serialized as JSON arrays of message objects:

```json
[
  {
    "role": "system",
    "content": "You are a helpful assistant."
  },
  {
    "role": "user",
    "content": "Hello!"
  },
  {
    "role": "assistant",
    "content": "Hi! How can I help you today?"
  }
]
```

#### Use Cases and Limitations

**Best for:**

- Single-user applications
- Development and testing
- Simple chatbots with limited concurrent users
- Quick prototyping

**Limitations:**

- Not suitable for multi-user applications
- No built-in concurrency control
- Limited query capabilities
- File I/O overhead

**Best Practices:**

- Persist after each conversation turn or at conversation end (not both)
- Implement error handling for file operations
- Use temporary files for testing
- Consider file rotation for long-running conversations

```python
# Example: Persist at conversation end (more efficient)
async def main() -> None:
    chatting = True
    file_path = "chat_session.json"

    # Load existing history
    try:
        chat_history = ChatHistory.load_chat_history_from_file(file_path)
    except Exception:
        chat_history = ChatHistory()

    # Chat loop
    while chatting:
        chatting = await chat()

    # Save only at the end
    chat_history.store_chat_history_to_file(file_path)
```

### Database Storage (Azure CosmosDB)

For production applications, database storage provides scalability, concurrency, and advanced features.

#### Creating a Data Model

Use the `@vectorstoremodel` decorator to define your chat history schema:

```python
from dataclasses import dataclass
from typing import Annotated
from semantic_kernel.data.vector import VectorStoreField, vectorstoremodel

@vectorstoremodel
@dataclass
class ChatHistoryModel:
    # Primary key for the conversation session
    session_id: Annotated[str, VectorStoreField("key")]

    # User identifier (indexed for querying)
    user_id: Annotated[str, VectorStoreField("data", is_indexed=True)]

    # Serialized messages
    messages: Annotated[list[dict[str, str]], VectorStoreField("data", is_indexed=True)]
```

#### Extending ChatHistory Class

Create a custom class that extends `ChatHistory` with persistence methods:

```python
from semantic_kernel.contents import ChatHistory
from semantic_kernel.data.vector import VectorStore, VectorStoreCollection

class ChatHistoryInCosmosDB(ChatHistory):
    """ChatHistory with CosmosDB persistence capabilities."""

    session_id: str
    user_id: str
    store: VectorStore
    collection: VectorStoreCollection[str, ChatHistoryModel] | None = None

    async def create_collection(self, collection_name: str) -> None:
        """Create or get the CosmosDB collection."""
        self.collection = self.store.get_collection(
            collection_name=collection_name,
            record_type=ChatHistoryModel,
        )
        await self.collection.ensure_collection_exists()

    async def store_messages(self) -> None:
        """Store chat history in CosmosDB."""
        if self.collection:
            await self.collection.upsert(
                ChatHistoryModel(
                    session_id=self.session_id,
                    user_id=self.user_id,
                    messages=[msg.model_dump() for msg in self.messages],
                )
            )

    async def read_messages(self) -> None:
        """Read chat history from CosmosDB."""
        if self.collection:
            record = await self.collection.get(self.session_id)
            if record:
                for message in record.messages:
                    self.messages.append(ChatMessageContent.model_validate(message))
```

#### Using the Custom ChatHistory

```python
from semantic_kernel.connectors.azure_cosmos_db import CosmosNoSqlStore

async def main() -> None:
    session_id = "user123_session1"

    # Connect to CosmosDB
    async with CosmosNoSqlStore(create_database=True) as store:
        # Create custom chat history
        history = ChatHistoryInCosmosDB(
            store=store,
            session_id=session_id,
            user_id="user123"
        )

        # Create collection
        await history.create_collection(collection_name="chat_history")

        # Load existing messages
        await history.read_messages()
        print(f"Loaded {len(history.messages)} messages.")

        # Chat loop
        while chatting:
            chatting = await chat(history)

        # Clean up (optional - for demo purposes)
        if delete_when_done and history.collection:
            await history.collection.ensure_collection_deleted()
```

#### Model Serialization

**Serializing Messages:**

```python
# Convert ChatMessageContent objects to dictionaries
messages_dict = [msg.model_dump() for msg in chat_history.messages]
```

**Deserializing Messages:**

```python
from semantic_kernel.contents import ChatMessageContent

# Convert dictionaries back to ChatMessageContent objects
for message_dict in record.messages:
    chat_history.messages.append(ChatMessageContent.model_validate(message_dict))
```

#### Benefits of Database Storage

- **Multi-user support**: Each user/session has unique identifiers
- **Scalability**: Handle thousands of concurrent conversations
- **Query capabilities**: Search conversations by user, date, content
- **Reliability**: Built-in redundancy and backup
- **Enhanced features**: Add vectors for semantic search, summaries, metadata

---

## History Reduction Strategies

As conversations grow longer, they consume more tokens, increase costs, and may exceed model context limits. History reduction strategies address these challenges.

### Why Reduce Chat History?

1. **Token Limits**: LLMs have maximum context windows (e.g., 4K, 8K, 128K tokens)
2. **Cost Management**: Fewer tokens = lower API costs
3. **Performance**: Smaller histories result in faster response times
4. **Relevance**: Recent context is often more relevant than distant history

### Truncation Reducer

Truncation simply removes the oldest messages, keeping the most recent conversation context.

#### How Truncation Works

The truncation reducer discards older messages once the message count exceeds a threshold, retaining only the most recent messages up to the target count.

```
Before: [system, msg1, msg2, msg3, msg4, msg5, msg6]
After:  [system, msg5, msg6]  (target_count=3)
```

#### Creating a Truncation Reducer

```python
from semantic_kernel.contents import ChatHistoryTruncationReducer

truncation_reducer = ChatHistoryTruncationReducer(
    service=kernel.get_service(),
    target_count=3,        # Keep 3 most recent messages
    threshold_count=2,     # Buffer before triggering reduction
)

# Add system message
truncation_reducer.add_system_message("You are a helpful assistant.")
```

#### Key Parameters

**`target_count`**

- **Purpose**: Number of messages to retain after reduction
- **Smaller values**: Minimal memory usage, less context
- **Larger values**: More context, higher token usage
- **Recommendation**: Balance between context needs and token limits

**`threshold_count`**

- **Purpose**: Buffer to avoid premature reduction
- **How it works**: Reduction triggers when `len(messages) > target_count + threshold_count`
- **Smaller values**: More aggressive reduction
- **Larger values**: Prevents orphaning message pairs (user question + assistant answer)
- **Recommendation**: Set to 1-2 for typical use cases

#### Manual Reduction

```python
async def chat() -> bool:
    user_input = input("User:> ")

    # Manually trigger reduction before processing
    await truncation_reducer.reduce()

    # Add user message and get response
    kernel_arguments = KernelArguments(
        settings=request_settings,
        chat_history=truncation_reducer,
        user_input=user_input,
    )

    answer = await kernel.invoke(
        plugin_name="ChatBot",
        function_name="Chat",
        arguments=kernel_arguments
    )

    if answer:
        print(f"Assistant:> {answer}")
        truncation_reducer.add_user_message(user_input)
        truncation_reducer.add_message(answer.value[0])

    return True
```

#### When to Use Truncation

**Best for:**

- Short-term conversations where history depth isn't critical
- Applications with strict token budgets
- Real-time systems requiring fast responses
- Scenarios where recent context is most important

**Not ideal for:**

- Long conversations requiring historical context
- Problem-solving that builds on earlier discussion
- Complex multi-turn tasks

### Summarization Reducer

Summarization creates a condensed version of older messages using the LLM itself, preserving key information while reducing token count.

#### How Summarization Works

Instead of discarding old messages, the summarization reducer generates an AI summary of the conversation history and replaces older messages with this summary.

```
Before: [system, msg1, msg2, msg3, msg4, msg5, msg6]
After:  [system, summary_of_msg1-4, msg5, msg6]
```

#### Creating a Summarization Reducer

```python
from semantic_kernel.contents import ChatHistorySummarizationReducer

summarization_reducer = ChatHistorySummarizationReducer(
    service=kernel.get_service(),
    target_count=3,        # Keep 3 most recent messages
    threshold_count=2,     # Buffer before triggering summarization
)

# Add system message
summarization_reducer.add_system_message("You are a helpful assistant.")
```

#### Parameters

The parameters work identically to truncation reducer:

- **`target_count`**: Messages to keep after summarization
- **`threshold_count`**: Buffer before triggering summarization

#### Accessing Summary Metadata

Summaries are marked with special metadata:

```python
# Check if reduction occurred
if is_reduced := await summarization_reducer.reduce():
    print(f"History reduced to {len(summarization_reducer.messages)} messages.")

    # Find and display the summary
    for msg in summarization_reducer.messages:
        if msg.metadata and msg.metadata.get("__summary__"):
            print("=" * 60)
            print(f"Summary: {msg.content}")
            print("=" * 60)
            break
```

#### When to Use Summarization

**Best for:**

- Long conversations requiring context preservation
- Complex problem-solving scenarios
- Customer support with extended interactions
- Educational or tutoring applications

**Considerations:**

- Higher API costs (summarization requires LLM calls)
- Slightly slower than truncation
- Summary quality depends on the LLM's capabilities

### Auto-Reduce Feature

Both truncation and summarization reducers support automatic reduction when messages are added asynchronously.

#### Enabling Auto-Reduce

```python
# Truncation with auto-reduce
truncation_reducer = ChatHistoryTruncationReducer(
    service=kernel.get_service(),
    target_count=3,
    threshold_count=2,
    auto_reduce=True,  # Enable automatic reduction
)

# Summarization with auto-reduce
summarization_reducer = ChatHistorySummarizationReducer(
    service=kernel.get_service(),
    target_count=3,
    threshold_count=2,
    auto_reduce=True,  # Enable automatic reduction
)
```

#### Using add_message_async

When `auto_reduce=True`, use `add_message_async()` instead of `add_message()`:

```python
async def chat() -> bool:
    user_input = input("User:> ")

    # No manual reduce() call needed
    answer = await kernel.invoke(
        plugin_name="ChatBot",
        function_name="Chat",
        arguments=kernel_arguments
    )

    if answer:
        print(f"Assistant:> {answer}")
        truncation_reducer.add_user_message(user_input)

        # Automatic reduction happens here
        await truncation_reducer.add_message_async(answer.value[0])

    print(f"Current number of messages: {len(truncation_reducer.messages)}")
    return True
```

#### Manual vs Auto-Reduce

**Manual Reduction:**

```python
await reducer.reduce()  # Explicit control
reducer.add_message(message)
```

**Auto Reduction:**

```python
await reducer.add_message_async(message)  # Reduction handled automatically
```

**Choose manual when:**

- You need fine-grained control over when reduction occurs
- You want to reduce before adding new messages
- You're implementing custom reduction logic

**Choose auto when:**

- You want simpler code with less boilerplate
- Reduction after message addition is acceptable
- You prefer declarative configuration

---

## Advanced Patterns

### Combining Persistence with Reduction

For production applications, combine database persistence with history reduction:

```python
class PersistentReducedChatHistory(ChatHistoryInCosmosDB):
    """ChatHistory with both persistence and reduction."""

    def __init__(self, store, session_id, user_id, service):
        super().__init__(store=store, session_id=session_id, user_id=user_id)
        self.reducer = ChatHistorySummarizationReducer(
            service=service,
            target_count=10,
            threshold_count=3,
        )

    async def add_and_reduce(self, message):
        """Add message, reduce if needed, and persist."""
        self.add_message(message)

        # Reduce if necessary
        if await self.reducer.reduce():
            # Update self with reduced messages
            self.messages = self.reducer.messages

        # Persist to database
        await self.store_messages()
```

#### Best Practices for Persistence + Reduction

1. **Reduce before persisting**: Store the reduced history, not the full history
2. **Store summaries**: Include summary metadata for audit trails
3. **Versioning**: Keep track of reduction events for debugging
4. **Batch operations**: Persist periodically, not after every message

```python
async def chat_with_smart_persistence(history):
    """Chat with periodic persistence."""
    message_count = 0
    persist_interval = 5  # Persist every 5 messages

    while True:
        # Get user input and response
        response = await get_response(history)
        history.add_message(response)
        message_count += 1

        # Reduce if needed
        await history.reduce()

        # Persist periodically
        if message_count % persist_interval == 0:
            await history.store_messages()
```

### Function Content Preservation

When using function calling with summarization, you may want to preserve function call details.

#### Enabling Function Content in Summaries

```python
summarization_reducer = ChatHistorySummarizationReducer(
    service=kernel.get_service(),
    target_count=3,
    threshold_count=2,
    include_function_content_in_summary=True,  # Preserve function details
)
```

#### Tracking Function Calls

Maintain sets to track processed function calls and results:

```python
from semantic_kernel.contents.function_call_content import FunctionCallContent
from semantic_kernel.contents.function_result_content import FunctionResultContent

# Track processed function content
processed_fccs: set[FunctionCallContent] = set()
processed_frcs: set[FunctionResultContent] = set()

async def chat() -> bool:
    global processed_fccs, processed_frcs

    # Get response with function calling
    answer = await kernel.invoke(
        plugin_name="ChatBot",
        function_name="Chat",
        arguments=kernel_arguments
    )

    if answer:
        # Extract chat history from response metadata
        chat_history: ChatHistory = answer.metadata.get("messages")

        if chat_history:
            # Extract new function calls and results
            fcc: list[FunctionCallContent] = []
            frc: list[FunctionResultContent] = []

            for msg in chat_history.messages:
                if msg.items:
                    for item in msg.items:
                        match item:
                            case FunctionCallContent():
                                if item.id not in processed_fccs:
                                    fcc.append(item)
                            case FunctionResultContent():
                                if item.id not in processed_frcs:
                                    frc.append(item)

            # Add function calls and results to history
            for i, item in enumerate(fcc):
                summarization_reducer.add_assistant_message([item])
                processed_fccs.add(item.id)

                # Add matching result
                if i < len(frc):
                    assert fcc[i].id == frc[i].id
                    summarization_reducer.add_tool_message([frc[i]])
                    processed_frcs.add(item.id)
```

#### Use Cases

**Preserve function content when:**

- Tool interactions are critical to conversation context
- Debugging function calling behavior
- Auditing tool usage
- Building complex multi-step workflows

**Skip function content when:**

- Function results are verbose but contextually unimportant
- Minimizing token usage is priority
- Functions are simple utilities (time, math)

---

## Code Patterns for Agentic Coders

### Basic Chat History Setup

```python
from semantic_kernel.contents import ChatHistory
from samples.concepts.setup.chat_completion_services import (
    Services,
    get_chat_completion_service_and_request_settings
)

# Initialize service and settings
chat_completion_service, request_settings = get_chat_completion_service_and_request_settings(
    Services.OPENAI
)

# Create chat history
chat_history = ChatHistory(
    system_message="You are a helpful AI assistant."
)

# Basic interaction
chat_history.add_user_message("Hello!")
response = await chat_completion_service.get_chat_message_content(
    chat_history=chat_history,
    settings=request_settings
)
chat_history.add_message(response)
```

### File Persistence Pattern

```python
import os
from semantic_kernel.contents import ChatHistory

def load_or_create_history(file_path: str, system_message: str) -> ChatHistory:
    """Load existing history or create new one."""
    if os.path.exists(file_path):
        try:
            history = ChatHistory.load_chat_history_from_file(file_path)
            print(f"Loaded {len(history.messages)} messages from {file_path}")
            return history
        except Exception as e:
            print(f"Error loading history: {e}")

    # Create new history
    print(f"Creating new chat history")
    history = ChatHistory()
    history.add_system_message(system_message)
    return history

def save_history(history: ChatHistory, file_path: str) -> None:
    """Save history with error handling."""
    try:
        history.store_chat_history_to_file(file_path)
        print(f"Saved {len(history.messages)} messages to {file_path}")
    except Exception as e:
        print(f"Error saving history: {e}")

# Usage
history = load_or_create_history("chat.json", "You are helpful.")
# ... chat interactions ...
save_history(history, "chat.json")
```

### Custom Storage Implementation Skeleton

```python
from dataclasses import dataclass
from typing import Annotated
from semantic_kernel.contents import ChatHistory, ChatMessageContent
from semantic_kernel.data.vector import (
    VectorStore,
    VectorStoreCollection,
    VectorStoreField,
    vectorstoremodel
)

@vectorstoremodel
@dataclass
class ChatHistoryModel:
    """Data model for chat history storage."""
    session_id: Annotated[str, VectorStoreField("key")]
    user_id: Annotated[str, VectorStoreField("data", is_indexed=True)]
    messages: Annotated[list[dict[str, str]], VectorStoreField("data")]
    # Optional: Add metadata fields
    created_at: Annotated[str, VectorStoreField("data", is_indexed=True)]
    updated_at: Annotated[str, VectorStoreField("data")]

class CustomChatHistory(ChatHistory):
    """Chat history with custom storage backend."""

    def __init__(self, store: VectorStore, session_id: str, user_id: str):
        super().__init__()
        self.store = store
        self.session_id = session_id
        self.user_id = user_id
        self.collection: VectorStoreCollection | None = None

    async def initialize(self, collection_name: str) -> None:
        """Initialize storage collection."""
        self.collection = self.store.get_collection(
            collection_name=collection_name,
            record_type=ChatHistoryModel,
        )
        await self.collection.ensure_collection_exists()

    async def load(self) -> None:
        """Load messages from storage."""
        if not self.collection:
            raise RuntimeError("Collection not initialized")

        record = await self.collection.get(self.session_id)
        if record:
            for message_dict in record.messages:
                self.messages.append(
                    ChatMessageContent.model_validate(message_dict)
                )

    async def save(self) -> None:
        """Save messages to storage."""
        if not self.collection:
            raise RuntimeError("Collection not initialized")

        from datetime import datetime

        await self.collection.upsert(
            ChatHistoryModel(
                session_id=self.session_id,
                user_id=self.user_id,
                messages=[msg.model_dump() for msg in self.messages],
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
            )
        )

    async def delete(self) -> None:
        """Delete history from storage."""
        if self.collection:
            await self.collection.delete(self.session_id)

# Usage
async def main():
    async with YourVectorStore() as store:
        history = CustomChatHistory(
            store=store,
            session_id="session123",
            user_id="user456"
        )
        await history.initialize("chat_histories")
        await history.load()
        # ... use history ...
        await history.save()
```

### Truncation Reducer Setup

```python
from semantic_kernel import Kernel
from semantic_kernel.contents import ChatHistoryTruncationReducer

# Create kernel with service
kernel = Kernel()
kernel.add_service(chat_completion_service)

# Configure truncation reducer
truncation_reducer = ChatHistoryTruncationReducer(
    service=kernel.get_service(),
    target_count=5,        # Keep 5 recent messages
    threshold_count=2,     # Reduce when exceeding by 2
    auto_reduce=False,     # Manual control
)

# Add system message
truncation_reducer.add_system_message("You are a helpful assistant.")

# In chat loop
async def chat_with_truncation():
    user_input = input("User:> ")

    # Manual reduction
    was_reduced = await truncation_reducer.reduce()
    if was_reduced:
        print(f"[History truncated to {len(truncation_reducer.messages)} messages]")

    # Get response
    truncation_reducer.add_user_message(user_input)
    response = await chat_completion_service.get_chat_message_content(
        chat_history=truncation_reducer,
        settings=request_settings
    )

    if response:
        truncation_reducer.add_message(response)
```

### Summarization Reducer Setup

```python
from semantic_kernel import Kernel
from semantic_kernel.contents import ChatHistorySummarizationReducer

# Create kernel with service
kernel = Kernel()
kernel.add_service(chat_completion_service)

# Configure summarization reducer
summarization_reducer = ChatHistorySummarizationReducer(
    service=kernel.get_service(),
    target_count=5,                              # Keep 5 recent messages
    threshold_count=2,                           # Summarize when exceeding by 2
    auto_reduce=False,                           # Manual control
    include_function_content_in_summary=False,   # Exclude function details
)

# Add system message
summarization_reducer.add_system_message("You are a helpful assistant.")

# In chat loop
async def chat_with_summarization():
    user_input = input("User:> ")

    # Manual summarization
    was_reduced = await summarization_reducer.reduce()
    if was_reduced:
        print(f"[History summarized to {len(summarization_reducer.messages)} messages]")

        # Display summary
        for msg in summarization_reducer.messages:
            if msg.metadata and msg.metadata.get("__summary__"):
                print(f"[Summary: {msg.content[:100]}...]")
                break

    # Get response
    summarization_reducer.add_user_message(user_input)
    response = await chat_completion_service.get_chat_message_content(
        chat_history=summarization_reducer,
        settings=request_settings
    )

    if response:
        summarization_reducer.add_message(response)
```

### Error Handling and Recovery

```python
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RobustChatHistory:
    """Chat history with comprehensive error handling."""

    def __init__(self, file_path: str, system_message: str):
        self.file_path = file_path
        self.system_message = system_message
        self.history = self._load_or_create()

    def _load_or_create(self) -> ChatHistory:
        """Load history with fallback to new instance."""
        try:
            history = ChatHistory.load_chat_history_from_file(self.file_path)
            logger.info(f"Loaded {len(history.messages)} messages")
            return history
        except FileNotFoundError:
            logger.info("No existing history found, creating new")
            history = ChatHistory()
            history.add_system_message(self.system_message)
            return history
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            logger.info("Creating new history as fallback")
            history = ChatHistory()
            history.add_system_message(self.system_message)
            return history

    def save(self) -> bool:
        """Save history with error handling."""
        try:
            self.history.store_chat_history_to_file(self.file_path)
            logger.info(f"Saved {len(self.history.messages)} messages")
            return True
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
            return False

    def save_backup(self) -> bool:
        """Save backup copy."""
        backup_path = f"{self.file_path}.backup"
        try:
            self.history.store_chat_history_to_file(backup_path)
            logger.info(f"Backup saved to {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save backup: {e}")
            return False

    async def safe_add_response(
        self,
        service,
        settings,
        max_retries: int = 3
    ) -> Optional[ChatMessageContent]:
        """Get response with retry logic."""
        for attempt in range(max_retries):
            try:
                response = await service.get_chat_message_content(
                    chat_history=self.history,
                    settings=settings
                )
                if response:
                    self.history.add_message(response)
                return response
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error("All retry attempts exhausted")
                    return None
        return None

# Usage
async def main():
    robust_history = RobustChatHistory(
        file_path="chat.json",
        system_message="You are helpful."
    )

    # Add user message
    robust_history.history.add_user_message("Hello!")

    # Get response with retry
    response = await robust_history.safe_add_response(
        service=chat_completion_service,
        settings=request_settings,
        max_retries=3
    )

    # Save with backup
    robust_history.save_backup()
    robust_history.save()
```

---

## Best Practices and Recommendations

### When to Use Each Persistence Strategy

#### File-Based Persistence

- **Use for**: Development, testing, single-user apps, demos
- **Avoid for**: Production multi-user systems, concurrent access scenarios

#### Database Persistence

- **Use for**: Production applications, multi-user systems, analytics needs
- **Avoid for**: Simple prototypes, when database infrastructure isn't available

### When to Use Truncation vs Summarization

#### Truncation

- **Use when**:
  - Recent context is most important
  - Token budget is tight
  - Response speed is critical
  - Conversation topics change frequently
- **Example scenarios**:
  - Customer service quick queries
  - FAQ bots
  - Command-and-control interfaces

#### Summarization

- **Use when**:
  - Historical context matters
  - Complex problem-solving
  - Long-form conversations
  - Building on previous discussion
- **Example scenarios**:
  - Educational tutoring
  - Technical troubleshooting
  - Creative writing assistance
  - Multi-session therapy or counseling

#### Combined Approach

For very long conversations, use both:

1. Summarize older history
2. Truncate if even summarized history grows too large

```python
# Example: Two-tier reduction
primary_reducer = ChatHistorySummarizationReducer(
    service=service,
    target_count=20,
    threshold_count=5
)

# If even summarized history is too large
async def emergency_truncate():
    if len(primary_reducer.messages) > 50:
        # Aggressively truncate
        truncator = ChatHistoryTruncationReducer(
            service=service,
            target_count=10,
            threshold_count=2
        )
        truncator.messages = primary_reducer.messages
        await truncator.reduce()
        primary_reducer.messages = truncator.messages
```

### Performance Considerations

1. **Batch Operations**: Persist every N messages, not every turn
2. **Async I/O**: Use async methods for file and database operations
3. **Connection Pooling**: Reuse database connections
4. **Caching**: Cache frequently accessed histories in memory
5. **Indexing**: Index user_id, session_id, timestamps in databases

```python
# Good: Batch persistence
if message_counter % 5 == 0:
    await history.save()

# Bad: Persist every message
await history.save()  # Called after each message
```

### Security Considerations

1. **Input Validation**: Sanitize user inputs before adding to history
2. **Access Control**: Verify user permissions before loading histories
3. **Data Encryption**: Encrypt sensitive conversations at rest
4. **PII Protection**: Remove or redact personally identifiable information
5. **Audit Logging**: Track access to conversation histories

```python
import re

def sanitize_input(user_input: str) -> str:
    """Basic input sanitization."""
    # Remove potential injection attempts
    sanitized = user_input.strip()

    # Limit length
    max_length = 1000
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    # Remove control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)

    return sanitized

# Usage
user_input = input("User:> ")
sanitized_input = sanitize_input(user_input)
chat_history.add_user_message(sanitized_input)
```

### Testing Strategies

1. **Unit Tests**: Test individual history operations
2. **Integration Tests**: Test persistence and reduction together
3. **Load Tests**: Verify performance under concurrent load
4. **Edge Cases**: Test empty histories, very long histories, malformed data

```python
import pytest
from semantic_kernel.contents import ChatHistory

@pytest.mark.asyncio
async def test_chat_history_persistence(tmp_path):
    """Test saving and loading chat history."""
    file_path = tmp_path / "test_chat.json"

    # Create and save history
    history1 = ChatHistory()
    history1.add_system_message("Test system")
    history1.add_user_message("Test user")
    history1.store_chat_history_to_file(str(file_path))

    # Load and verify
    history2 = ChatHistory.load_chat_history_from_file(str(file_path))
    assert len(history2.messages) == 2
    assert history2.messages[0].role == "system"
    assert history2.messages[1].role == "user"

@pytest.mark.asyncio
async def test_truncation_reducer():
    """Test truncation reducer behavior."""
    from semantic_kernel.contents import ChatHistoryTruncationReducer

    # Create mock service
    mock_service = create_mock_service()

    reducer = ChatHistoryTruncationReducer(
        service=mock_service,
        target_count=3,
        threshold_count=1
    )

    # Add messages
    reducer.add_system_message("System")
    for i in range(10):
        reducer.add_user_message(f"Message {i}")

    # Reduce
    await reducer.reduce()

    # Verify
    assert len(reducer.messages) <= 3
```

---

## Common Pitfalls and Solutions

### Forgetting to Add Messages to History

**Problem**: Not adding assistant responses to history breaks conversation context.

```python
# Bad: Response not added to history
response = await chat_completion_service.get_chat_message_content(
    chat_history=chat_history,
    settings=request_settings
)
print(f"Assistant: {response}")
# Missing: chat_history.add_message(response)
```

**Solution**: Always add responses to maintain context.

```python
# Good: Response added to history
response = await chat_completion_service.get_chat_message_content(
    chat_history=chat_history,
    settings=request_settings
)
if response:
    print(f"Assistant: {response}")
    chat_history.add_message(response)  # Maintains context
```

### Not Handling Serialization Errors

**Problem**: File corruption or schema changes cause crashes.

```python
# Bad: No error handling
history = ChatHistory.load_chat_history_from_file("chat.json")
```

**Solution**: Always handle potential errors gracefully.

```python
# Good: Graceful error handling
try:
    history = ChatHistory.load_chat_history_from_file("chat.json")
except FileNotFoundError:
    logger.info("Starting new conversation")
    history = ChatHistory()
except json.JSONDecodeError:
    logger.error("Corrupted history file, starting fresh")
    history = ChatHistory()
    # Optionally backup corrupted file
    shutil.copy("chat.json", "chat.json.corrupted")
except Exception as e:
    logger.error(f"Unexpected error loading history: {e}")
    history = ChatHistory()
```

### Reducer Configuration Issues

**Problem**: Incorrect `target_count` or `threshold_count` values.

```python
# Bad: threshold_count > target_count makes reduction ineffective
reducer = ChatHistoryTruncationReducer(
    service=service,
    target_count=5,
    threshold_count=10,  # Too high!
)
# Reduction only triggers when messages > 15
```

**Solution**: Set `threshold_count` appropriately.

```python
# Good: Reasonable threshold
reducer = ChatHistoryTruncationReducer(
    service=service,
    target_count=5,
    threshold_count=2,  # Triggers at 7 messages
)
```

**Common mistakes**:

- Setting `target_count` too low (loses context)
- Setting `target_count` too high (defeats purpose)
- Not accounting for system messages in counts
- Forgetting to call `reduce()` with manual mode

### Memory Management in Long Conversations

**Problem**: Unlimited history growth causes memory issues.

```python
# Bad: No reduction strategy
chat_history = ChatHistory()
# After 1000s of messages, memory usage balloons
```

**Solution**: Implement appropriate reduction strategy.

```python
# Good: Bounded memory usage
reducer = ChatHistorySummarizationReducer(
    service=service,
    target_count=10,
    threshold_count=3,
    auto_reduce=True
)

# Memory stays bounded
```

### Mixing Synchronous and Asynchronous Methods

**Problem**: Using sync methods with async reducers causes issues.

```python
# Bad: Using sync add_message with auto_reduce
reducer = ChatHistoryTruncationReducer(
    service=service,
    target_count=5,
    threshold_count=2,
    auto_reduce=True
)
reducer.add_message(response)  # auto_reduce won't trigger!
```

**Solution**: Use async methods with auto-reduce.

```python
# Good: Using async method
await reducer.add_message_async(response)  # auto_reduce triggers
```

### Not Preserving System Messages

**Problem**: Reduction accidentally removes system message.

**Solution**: System messages are automatically preserved by reducers, but verify:

```python
# Verify system message is present
assert len(reducer.messages) > 0
assert reducer.messages[0].role == "system"
```

### Inefficient Persistence Patterns

**Problem**: Excessive I/O operations.

```python
# Bad: Persist after every message
for message in messages:
    chat_history.add_message(message)
    chat_history.store_chat_history_to_file("chat.json")  # Slow!
```

**Solution**: Batch persistence operations.

```python
# Good: Batch persistence
for message in messages:
    chat_history.add_message(message)

# Persist once at the end
chat_history.store_chat_history_to_file("chat.json")
```

---

## Summary

Effective chat history management in Semantic Kernel requires understanding:

1. **Basic Operations**: Creating histories, adding messages, maintaining context
2. **Persistence**: Choosing between file-based and database storage
3. **Reduction**: Selecting truncation or summarization based on use case
4. **Advanced Patterns**: Combining techniques for production systems
5. **Best Practices**: Performance, security, and testing considerations

By applying these patterns, agentic coders can build robust conversational AI applications that scale effectively while maintaining conversation quality and context.
