---
document_type: technical_reference
topic: kernel_basics
framework: semantic_kernel
language: python
version: 1.1
last_updated: 2025-10-26
purpose: persistent_reference_for_agentic_coding
---

# Semantic Kernel - Core Reference

## Critical Rules

1. **ONE kernel per application** - Singleton pattern, initialize at startup
2. **Register ALL services/plugins during initialization** - Not per-request
3. **Never dispose kernel** - Lives for entire application lifecycle
4. **Everything is async** - Use `async/await` for all kernel operations
5. **Use `invoke_prompt()` for AI calls** - Use `invoke()` for plugin functions

---

## Essential Imports

```python
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function, KernelArguments
from semantic_kernel.connectors.ai.open_ai import (
    AzureChatCompletion,
    AzureChatPromptExecutionSettings,
    OpenAIChatCompletion,
)
import os
```

---

## 1. Kernel Setup (Do Once)

```python
# Create kernel
kernel = Kernel()

# Add Azure OpenAI service
kernel.add_service(AzureChatCompletion(
    service_id="chat",  # Unique identifier
    deployment_name=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
    endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
))

# Add OpenAI service (alternative)
kernel.add_service(OpenAIChatCompletion(
    service_id="chat",
    ai_model_id="gpt-4",
    api_key=os.getenv("OPENAI_API_KEY"),
))

# Multiple services example
kernel.add_service(AzureChatCompletion(service_id="gpt-4", ...))
kernel.add_service(AzureChatCompletion(service_id="gpt-35-turbo", ...))
```

**⚠️ Critical:** Each service needs a unique `service_id`

---

## 2. Plugin Creation & Registration

### Basic Plugin Pattern

```python
from semantic_kernel.functions import kernel_function

class MathPlugin:
    @kernel_function(
        name="add",
        description="Adds two numbers together"
    )
    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

    @kernel_function(
        name="multiply",
        description="Multiplies two numbers"
    )
    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers."""
        return a * b

# Register plugin
kernel.add_plugin(MathPlugin(), plugin_name="Math")
```

### Plugin with State/Dependencies

```python
class DatabasePlugin:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.db = self._connect()

    def _connect(self):
        # Setup connection
        return database.connect(self.connection_string)

    @kernel_function(
        name="query",
        description="Execute database query"
    )
    async def query(self, sql: str) -> str:
        """Execute SQL query and return results."""
        result = await self.db.execute(sql)
        return str(result)

# Register with dependencies
kernel.add_plugin(
    DatabasePlugin(os.getenv("DB_CONNECTION_STRING")),
    plugin_name="Database"
)
```

**⚠️ Critical:** Plugin names must be unique across the kernel

---

## 3. Invocation Patterns

### Invoke AI Prompt (Most Common)

```python
from semantic_kernel.functions import KernelArguments

# Simple prompt
result = await kernel.invoke_prompt(
    prompt="What is {{$topic}}?",
    arguments=KernelArguments(topic="quantum computing")
)
response = result.value  # String response from AI

# Prompt with execution settings
settings = AzureChatPromptExecutionSettings(
    service_id="chat",
    max_tokens=500,
    temperature=0.7,
)

result = await kernel.invoke_prompt(
    prompt="Explain {{$topic}} in {{$style}} style.",
    arguments=KernelArguments(
        settings=settings,  # Pass settings to KernelArguments constructor
        topic="recursion",
        style="simple"
    )
)
```

### Invoke Plugin Function

```python
# Method 1: Direct invocation
result = await kernel.invoke(
    plugin_name="Math",
    function_name="add",
    arguments=KernelArguments(a=5, b=3)
)
print(result.value)  # 8.0

# Method 2: Get function reference first
math_plugin = kernel.get_plugin("Math")
add_function = math_plugin["add"]
result = await kernel.invoke(
    add_function,
    arguments=KernelArguments(a=10, b=20)
)
print(result.value)  # 30.0
```

**Key Distinction:**

- `invoke_prompt()` → AI generates response from prompt
- `invoke()` → Executes plugin function code

---

## 4. Execution Settings (AI Parameters)

```python
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings

settings = AzureChatPromptExecutionSettings(
    service_id="chat",              # Required: which service to use
    max_tokens=1000,                # Max response tokens
    temperature=0.7,                # Creativity (0.0=deterministic, 1.0=creative)
    top_p=0.9,                      # Nucleus sampling
    frequency_penalty=0.0,          # Reduce word repetition (0.0-2.0)
    presence_penalty=0.0,           # Encourage topic diversity (0.0-2.0)
)

# Use in invoke_prompt
result = await kernel.invoke_prompt(
    prompt="{{$user_input}}",
    arguments=KernelArguments(
        settings=settings,
        user_input="Hello"
    )
)
```

**Common Temperature Values:**

- `0.0-0.3`: Factual, deterministic tasks
- `0.5-0.7`: Balanced creativity
- `0.8-1.0`: Creative writing, brainstorming

---

## 5. Application Integration Patterns

### Pattern 1: Application Class (Recommended)

```python
class Application:
    def __init__(self):
        self.kernel = Kernel()
        self._setup_services()
        self._setup_plugins()

    def _setup_services(self):
        self.kernel.add_service(AzureChatCompletion(
            service_id="chat",
            deployment_name=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        ))

    def _setup_plugins(self):
        self.kernel.add_plugin(MathPlugin(), plugin_name="Math")
        self.kernel.add_plugin(DatabasePlugin(...), plugin_name="Database")

    async def process(self, user_input: str) -> str:
        result = await self.kernel.invoke_prompt(
            prompt="{{$input}}",
            arguments=KernelArguments(input=user_input)
        )
        return result.value

# Use throughout application
app = Application()
response = await app.process("Hello, world!")
```

### Pattern 2: Dependency Injection

```python
class ChatService:
    def __init__(self, kernel: Kernel):
        self.kernel = kernel

    async def chat(self, message: str) -> str:
        result = await self.kernel.invoke_prompt(
            prompt="{{$message}}",
            arguments=KernelArguments(message=message)
        )
        return result.value

# Setup
kernel = Kernel()
kernel.add_service(AzureChatCompletion(...))
chat_service = ChatService(kernel)
```

### Pattern 3: FastAPI Integration

```python
from fastapi import FastAPI, Depends

app = FastAPI()

def get_kernel() -> Kernel:
    """Singleton kernel for application."""
    if not hasattr(app.state, "kernel"):
        kernel = Kernel()
        kernel.add_service(AzureChatCompletion(
            service_id="chat",
            deployment_name=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        ))
        app.state.kernel = kernel
    return app.state.kernel

@app.post("/chat")
async def chat_endpoint(
    message: str,
    kernel: Kernel = Depends(get_kernel)
):
    result = await kernel.invoke_prompt(
        prompt="{{$message}}",
        arguments=KernelArguments(message=message)
    )
    return {"response": result.value}
```

---

## 6. Common Patterns & Solutions

### Configuration Management

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class KernelConfig:
    azure_endpoint: str
    azure_api_key: str
    azure_deployment: str
    service_id: str = "chat"

    @classmethod
    def from_env(cls) -> "KernelConfig":
        return cls(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", ""),
        )

    def validate(self) -> None:
        """Raises ValueError if config invalid."""
        if not all([self.azure_endpoint, self.azure_api_key, self.azure_deployment]):
            raise ValueError("Missing required Azure OpenAI configuration")

# Usage
config = KernelConfig.from_env()
config.validate()

kernel.add_service(AzureChatCompletion(
    service_id=config.service_id,
    deployment_name=config.azure_deployment,
    endpoint=config.azure_endpoint,
    api_key=config.azure_api_key,
))
```

### Error Handling

```python
from semantic_kernel.exceptions import KernelException

try:
    result = await kernel.invoke_prompt(
        prompt="{{$input}}",
        arguments=KernelArguments(input=user_input)
    )
    return result.value
except KernelException as e:
    logger.error(f"Kernel operation failed: {e}")
    return "I apologize, I encountered an error processing your request."
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

### Service Retrieval (Advanced)

```python
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase

# Get registered service directly
chat_service = kernel.get_service(
    service_id="chat",
    type=ChatCompletionClientBase
)

# Use service methods directly (bypassing kernel)
response = await chat_service.get_chat_message_contents(
    chat_history=history,
    settings=settings,
)
```

---

## 7. Quick Syntax Reference

### Complete Minimal Example

```python
import asyncio
import os
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.functions import KernelArguments

async def main():
    # 1. Create and configure kernel
    kernel = Kernel()
    kernel.add_service(AzureChatCompletion(
        service_id="chat",
        deployment_name=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"),
        endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    ))

    # 2. Use kernel
    result = await kernel.invoke_prompt(
        prompt="What is {{$topic}}?",
        arguments=KernelArguments(topic="AI")
    )

    print(result.value)

if __name__ == "__main__":
    asyncio.run(main())
```

### Template Variable Syntax

```python
# Variables use {{$variable_name}}
prompt = "Translate {{$text}} to {{$language}}"

# In arguments
arguments = KernelArguments(
    text="Hello",
    language="Spanish"
)
```

---

## 8. Troubleshooting Guide

### Common Issues

**Problem:** `AttributeError: 'NoneType' object has no attribute 'value'`

- **Cause:** Kernel invocation returned None
- **Fix:** Check that service is registered and arguments are correct

**Problem:** `Service with id 'X' not found`

- **Cause:** Service not registered or wrong service_id
- **Fix:** Ensure `kernel.add_service()` called with matching service_id

**Problem:** `Plugin 'X' not found`

- **Cause:** Plugin not registered or wrong name
- **Fix:** Ensure `kernel.add_plugin()` called with correct plugin_name

**Problem:** Async function not awaited warning

- **Cause:** Missing `await` keyword
- **Fix:** Always use `await` with kernel operations

**Problem:** Environment variables not found

- **Cause:** Missing `.env` file or environment not loaded
- **Fix:** Use `python-dotenv` and load before kernel creation:
  ```python
  from dotenv import load_dotenv
  load_dotenv()
  ```

---

## Best Practices Summary

### ✅ DO

- Create ONE kernel per application at startup
- Register ALL services and plugins during initialization
- Use environment variables for credentials
- Always use `async/await` with kernel operations
- Implement comprehensive error handling
- Validate configuration before kernel creation
- Use dependency injection patterns
- Use descriptive `service_id` and `plugin_name` values
- Add type hints to plugin functions
- Provide clear descriptions in `@kernel_function` decorator

### ❌ DON'T

- Create multiple kernel instances
- Create kernel per request/user
- Dispose or recreate kernel during runtime
- Register services/plugins in request handlers
- Hardcode API keys or credentials
- Block async operations with synchronous code
- Use global mutable state for kernel
- Forget to await kernel operations
- Mix sync and async code improperly
- Register duplicate service_id or plugin_name values

---

## Quick Lookup: When to Use What

| Task                  | Use                                | Example                          |
| --------------------- | ---------------------------------- | -------------------------------- |
| Call AI for response  | `invoke_prompt()`                  | Generate text, answer questions  |
| Execute plugin code   | `invoke()`                         | Math calculation, database query |
| Configure AI behavior | `AzureChatPromptExecutionSettings` | Set temperature, max_tokens      |
| Pass data to kernel   | `KernelArguments`                  | Provide variables, settings      |
| Add AI service        | `add_service()`                    | Register OpenAI connection       |
| Add custom functions  | `add_plugin()`                     | Register plugin class            |

---

**Last Updated:** 2025-10-26  
**Version:** 1.2
