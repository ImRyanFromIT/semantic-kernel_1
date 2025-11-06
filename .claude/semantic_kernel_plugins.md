---
document_type: technical_reference
topic: plugins_and_functions
framework: semantic_kernel
language: python
version: 1.0
last_updated: 2025-10-26
subtopics:
  - native_functions
  - semantic_functions
  - plugin_loading
  - function_invocation
  - function_calling
  - auto_injection
  - testing
  - best_practices
---

# Semantic Kernel - Plugins and Functions

## Native Functions (Preferred Pattern)

### Basic Native Function

```python
from typing import Annotated
from semantic_kernel.functions import kernel_function

class MyPlugin:
    """Plugin description for the entire class."""

    @kernel_function(name="MyFunction", description="What this function does")
    async def my_function(
        self,
        param1: Annotated[str, "Description of param1"],
        param2: Annotated[int, "Description of param2"] = 10,
    ) -> Annotated[str, "Description of return value"]:
        """Detailed docstring explaining the function."""
        result = f"Processed {param1} with {param2}"
        return result

# Register plugin
kernel.add_plugin(MyPlugin(), "MyPluginName")
```

### Auto-Injected Parameters

SK automatically injects these parameters when present in function signature:

| Parameter Name       | Type                      | Description            |
| -------------------- | ------------------------- | ---------------------- |
| `kernel`             | `Kernel`                  | The Kernel instance    |
| `service`            | `AIServiceClientBase`     | Selected AI service    |
| `execution_settings` | `PromptExecutionSettings` | Execution settings     |
| `arguments`          | `KernelArguments`         | All function arguments |

```python
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function, KernelArguments

class AdvancedPlugin:
    @kernel_function(name="AdvancedFunc", description="Uses auto-injection")
    async def advanced_function(
        self,
        user_query: Annotated[str, "The user's query"],
        kernel: Kernel,                     # Auto-injected
        arguments: KernelArguments,         # Auto-injected
    ) -> Annotated[str, "The result"]:
        """Function with auto-injected parameters."""
        # kernel is automatically provided by SK
        chat_service = kernel.get_service("chat")

        # arguments contains ALL parameters
        print(f"All args: {arguments}")

        return f"Processed: {user_query}"
```

**IMPORTANT**: Never pass auto-injected parameters explicitly during invocation.

## Semantic Functions (Prompt-Based)

### Inline Semantic Function

```python
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings
from semantic_kernel.prompt_template import InputVariable, PromptTemplateConfig

prompt = """{{$input}}

Summarize the content above in 2-3 sentences."""

config = PromptTemplateConfig(
    template=prompt,
    name="summarize",
    template_format="semantic-kernel",
    input_variables=[
        InputVariable(name="input", description="Content to summarize", is_required=True),
    ],
    execution_settings=AzureChatPromptExecutionSettings(
        service_id="chat",
        max_tokens=2000,
        temperature=0.7,
    ),
)

summarize_function = kernel.add_function(
    function_name="Summarize",
    plugin_name="SummarizePlugin",
    prompt_template_config=config,
)
```

### File-Based Semantic Functions

```python
# Directory structure:
# Plugins/
#   MyPlugin/
#     Describe/
#       skprompt.txt
#       config.json

# Load entire plugin directory
my_plugin = kernel.add_plugin(
    parent_directory="Plugins",
    plugin_name="MyPlugin"
)

# Access specific function
describe_function = my_plugin["Describe"]
```

## Plugin Loading Patterns

### From Directory (Batch Loading)

```python
# Load all plugins from a directory
plugins_dir = "path/to/plugins"

# Option 1: Load specific plugin
plugin = kernel.add_plugin(
    parent_directory=plugins_dir,
    plugin_name="WeatherPlugin"
)

# Option 2: Load multiple plugins
for plugin_name in ["WeatherPlugin", "SearchPlugin", "EmailPlugin"]:
    kernel.add_plugin(
        parent_directory=plugins_dir,
        plugin_name=plugin_name
    )
```

### From Class Instance

```python
class UtilityPlugin:
    @kernel_function(name="FormatDate")
    async def format_date(self, date: Annotated[str, "ISO date"]) -> str:
        # Implementation
        return formatted_date

# Register class instance
plugin = kernel.add_plugin(UtilityPlugin(), "Utilities")
```

### From YAML

```python
# plugin_config.yaml:
# name: MyPlugin
# functions:
#   - name: Greet
#     prompt: "Hello, {{$name}}!"
#     description: "Greets the user"

plugin = kernel.add_plugin_from_yaml("path/to/plugin_config.yaml")
```

## Function Invocation Patterns

### Direct Invocation via Kernel

```python
# Simple invocation
result = await kernel.invoke(function, input="some text")
print(result.value)

# With multiple arguments
from semantic_kernel.functions import KernelArguments

args = KernelArguments(
    param1="value1",
    param2="value2",
    param3=42
)
result = await kernel.invoke(function, args)
```

### Via Plugin Reference

```python
# Get plugin
plugin = kernel.get_plugin("PluginName")

# Invoke function
result = await plugin["FunctionName"].invoke(kernel, input="data")
print(result.value)

# With arguments
result = await plugin["FunctionName"].invoke(
    kernel,
    KernelArguments(param1="value", param2=10)
)
```

### With Execution Settings

```python
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings

settings = AzureChatPromptExecutionSettings(
    service_id="chat",
    max_tokens=1000,
    temperature=0.3,
)

result = await kernel.invoke(
    function,
    input="data",
    settings=settings
)
```

## Function Calling (Tool Use)

### Auto Function Calling

```python
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior

# Enable automatic function calling
settings = AzureChatPromptExecutionSettings(
    service_id="chat",
    max_tokens=4000,
    function_choice_behavior=FunctionChoiceBehavior.Auto(
        filters={"included_plugins": ["WeatherPlugin", "SearchPlugin"]}
    ),
)

# Kernel will automatically call functions as needed
result = await kernel.invoke(prompt_function, input="What's the weather in NYC?", settings=settings)
```

### Manual Function Selection

```python
# Require specific function
settings = AzureChatPromptExecutionSettings(
    function_choice_behavior=FunctionChoiceBehavior.Required(
        filters={"included_functions": ["WeatherPlugin-GetWeather"]}
    ),
)

# No function calling
settings = AzureChatPromptExecutionSettings(
    function_choice_behavior=FunctionChoiceBehavior.NoneInvoke(),
)
```

## Complex Plugin Example

```python
from typing import Annotated
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function, KernelArguments
import aiohttp

class WebSearchPlugin:
    """Plugin for web search operations."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    @kernel_function(
        name="Search",
        description="Search the web for information"
    )
    async def search(
        self,
        query: Annotated[str, "The search query"],
        max_results: Annotated[int, "Maximum number of results"] = 5,
        kernel: Kernel = None,
    ) -> Annotated[str, "Search results as JSON"]:
        """
        Performs a web search and returns results.

        Args:
            query: The search query string
            max_results: Maximum number of results to return (default: 5)
            kernel: Auto-injected kernel instance

        Returns:
            JSON string containing search results
        """
        async with aiohttp.ClientSession() as session:
            # Implementation
            results = await self._perform_search(session, query, max_results)
            return results

    async def _perform_search(self, session, query: str, max_results: int):
        # Private helper method
        pass

# Register with initialization
search_plugin = WebSearchPlugin(api_key=os.getenv("SEARCH_API_KEY"))
kernel.add_plugin(search_plugin, "WebSearch")
```

## Plugin Organization Best Practices

### File Structure

```
project/
├── plugins/
│   ├── weather/
│   │   ├── __init__.py
│   │   └── weather_plugin.py
│   ├── search/
│   │   ├── __init__.py
│   │   └── search_plugin.py
│   └── email/
│       ├── __init__.py
│       └── email_plugin.py
├── semantic_functions/
│   ├── Summarize/
│   │   ├── skprompt.txt
│   │   └── config.json
│   └── Translate/
│       ├── skprompt.txt
│       └── config.json
└── main.py
```

### Plugin Registration at Startup

```python
# main.py
from plugins.weather.weather_plugin import WeatherPlugin
from plugins.search.search_plugin import SearchPlugin

def initialize_kernel():
    kernel = Kernel()

    # Add services
    kernel.add_service(...)

    # Add native plugins
    kernel.add_plugin(WeatherPlugin(), "Weather")
    kernel.add_plugin(SearchPlugin(), "Search")

    # Add semantic functions
    kernel.add_plugin(
        parent_directory="semantic_functions",
        plugin_name="Summarize"
    )

    return kernel
```

## Testing Functions

```python
import pytest
from semantic_kernel import Kernel

@pytest.mark.asyncio
async def test_plugin_function():
    kernel = Kernel()
    kernel.add_service(...)

    # Register plugin
    plugin = kernel.add_plugin(MyPlugin(), "Test")

    # Test function
    result = await plugin["MyFunction"].invoke(
        kernel,
        KernelArguments(param1="test", param2=5)
    )

    assert result.value == "expected_output"

@pytest.mark.asyncio
async def test_with_mock_service():
    kernel = Kernel()

    # Add mock service for testing
    mock_service = MockChatService()
    kernel.add_service(mock_service, service_id="chat")

    # Test with mock
    result = await kernel.invoke(function, input="test")
    assert result.value is not None
```

## Best Practices

1. **Type Annotations**: Always use `Annotated` for parameter descriptions
2. **Docstrings**: Write clear docstrings for all functions
3. **Auto-Injection**: Leverage auto-injected parameters (kernel, arguments)
4. **Plugin Names**: Use PascalCase for plugin names, CamelCase for function names
5. **Error Handling**: Handle exceptions gracefully within functions
6. **Async**: Prefer async functions for I/O operations
7. **Stateless**: Keep functions stateless when possible
8. **Single Responsibility**: Each function should do one thing well
