---
document_type: technical_reference
topic: azure_ai_search_integration
framework: semantic_kernel
language: python
version: 1.0
last_updated: 2025-10-26
subtopics:
  - vector_search
  - hybrid_search
  - crud_operations
  - agent_integration
  - declarative_agents
  - custom_search_plugins
  - rag_patterns
  - data_models
  - filtering
  - configuration
  - authentication
  - error_handling
  - performance_optimization
  - best_practices
---

# Azure AI Search with Semantic Kernel - Reference Guide

**Purpose**: Comprehensive reference for Azure AI Search integration with Semantic Kernel Python, optimized for AI agent consumption.

---

## Table of Contents

1. [Quick Reference Tables](#quick-reference-tables)
2. [Configuration & Setup](#configuration--setup)
3. [Pattern Library](#pattern-library)
   - [Pattern: Basic Vector Search](#pattern-basic-vector-search)
   - [Pattern: Hybrid Search with Filtering](#pattern-hybrid-search-with-filtering)
   - [Pattern: CRUD Operations](#pattern-crud-operations)
   - [Pattern: Agent with Azure AI Search Tool](#pattern-agent-with-azure-ai-search-tool)
   - [Pattern: Declarative Agent Configuration](#pattern-declarative-agent-configuration)
   - [Pattern: Custom Search Plugin](#pattern-custom-search-plugin)
   - [Pattern: RAG with Chat Completion](#pattern-rag-with-chat-completion)
4. [Data Model Patterns](#data-model-patterns)
5. [Advanced Features](#advanced-features)

---

## Quick Reference Tables

### Environment Variables

| Variable                     | Purpose                          | Example                                 |
| ---------------------------- | -------------------------------- | --------------------------------------- |
| `AZURE_AI_SEARCH_ENDPOINT`   | Azure AI Search service endpoint | `https://my-service.search.windows.net` |
| `AZURE_AI_SEARCH_API_KEY`    | API key for authentication       | `<your-api-key>`                        |
| `AZURE_AI_SEARCH_INDEX_NAME` | Default index/collection name    | `my-index`                              |

### Authentication Methods

| Method               | Use Case                   | Code                                            |
| -------------------- | -------------------------- | ----------------------------------------------- |
| API Key              | Simple authentication      | `api_key="<key>"`                               |
| Token Credential     | Azure managed identity     | `token_credentials=AzureCliCredential()`        |
| Azure Key Credential | Explicit credential object | `azure_credentials=AzureKeyCredential("<key>")` |

### Search Types

| Search Type                 | Purpose                          | When to Use                                |
| --------------------------- | -------------------------------- | ------------------------------------------ |
| `SearchType.VECTOR`         | Pure vector similarity search    | Semantic search, finding similar content   |
| `SearchType.KEYWORD_HYBRID` | Combined keyword + vector search | Best of both worlds, relevance + semantics |

### Distance Functions

| Function                              | Azure AI Search Metric | Use Case                             |
| ------------------------------------- | ---------------------- | ------------------------------------ |
| `DistanceFunction.COSINE_DISTANCE`    | `COSINE`               | Default, normalized similarity (0-1) |
| `DistanceFunction.DOT_PROD`           | `DOT_PRODUCT`          | Fast, unnormalized similarity        |
| `DistanceFunction.EUCLIDEAN_DISTANCE` | `EUCLIDEAN`            | Geometric distance                   |
| `DistanceFunction.HAMMING`            | `HAMMING`              | Binary vector comparison             |

### Index Algorithms

| Algorithm        | Type                               | Performance | Accuracy |
| ---------------- | ---------------------------------- | ----------- | -------- |
| `IndexKind.HNSW` | Hierarchical Navigable Small World | Fast        | High     |
| `IndexKind.FLAT` | Exhaustive KNN                     | Slower      | Perfect  |

---

## Configuration & Setup

### Basic Initialization with Environment Variables

**Required Imports**:

```python
from semantic_kernel.connectors.azure_ai_search import AzureAISearchSettings
```

**Configuration**:

```python
# Environment variables required:
# AZURE_AI_SEARCH_ENDPOINT=https://my-service.search.windows.net
# AZURE_AI_SEARCH_API_KEY=<your-api-key>
# AZURE_AI_SEARCH_INDEX_NAME=<index-name>

settings = AzureAISearchSettings()
# Access values:
# settings.endpoint
# settings.api_key
# settings.index_name
```

### Authentication Options

**API Key Authentication**:

```python
from semantic_kernel.connectors.azure_ai_search import AzureAISearchCollection

collection = AzureAISearchCollection(
    record_type=YourModel,
    collection_name="my-index",
    api_key="your-api-key",
    search_endpoint="https://my-service.search.windows.net"
)
```

**Token Credential Authentication**:

```python
from azure.identity.aio import AzureCliCredential
from semantic_kernel.connectors.azure_ai_search import AzureAISearchCollection

collection = AzureAISearchCollection(
    record_type=YourModel,
    collection_name="my-index",
    token_credentials=AzureCliCredential(),
    search_endpoint="https://my-service.search.windows.net"
)
```

---

## Pattern Library

### Pattern: Basic Vector Search

**Purpose**: Search for semantically similar records using vector embeddings.

**Required Imports**:

```python
import asyncio
from dataclasses import dataclass, field
from typing import Annotated
from uuid import uuid4

from semantic_kernel.connectors.ai.open_ai import OpenAITextEmbedding
from semantic_kernel.connectors.azure_ai_search import AzureAISearchCollection
from semantic_kernel.data.vector import VectorStoreField, vectorstoremodel
```

**Data Model**:

```python
@vectorstoremodel(collection_name="simple-index")
@dataclass
class SimpleModel:
    text: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    id: Annotated[str, VectorStoreField("key")] = field(default_factory=lambda: str(uuid4()))
    embedding: Annotated[
        list[float] | str | None,
        VectorStoreField("vector", dimensions=1536)
    ] = None

    def __post_init__(self):
        if self.embedding is None:
            self.embedding = self.text
```

**Complete Example**:

```python
async def vector_search_example():
    # Create records
    records = [
        SimpleModel(text="Azure AI Search is a cloud search service"),
        SimpleModel(text="Semantic Kernel is an SDK for AI orchestration"),
        SimpleModel(text="Vector databases store embeddings efficiently"),
    ]

    # Create collection with embedding generator
    async with AzureAISearchCollection[str, SimpleModel](
        record_type=SimpleModel,
        embedding_generator=OpenAITextEmbedding()
    ) as collection:
        # Create index and upsert records
        await collection.ensure_collection_exists()
        await collection.upsert(records)

        # Perform vector search
        results = await collection.search(
            values="What is Azure AI Search?",
            vector_property_name="embedding",
            top=3
        )

        # Process results
        async for result in results.results:
            print(f"Text: {result.record.text}")
            print(f"Score: {result.score}\n")

        # Cleanup
        await collection.ensure_collection_deleted()

if __name__ == "__main__":
    asyncio.run(vector_search_example())
```

**Key Parameters**:

- `values`: Query text to search for
- `vector_property_name`: Name of the vector field in your model
- `top`: Maximum number of results to return (default: 5)
- `skip`: Number of results to skip for pagination
- `include_vectors`: Whether to include vector data in results (default: False)

---

### Pattern: Hybrid Search with Filtering

**Purpose**: Combine keyword search with vector search and apply filters.

**Required Imports**:

```python
import asyncio
from dataclasses import dataclass, field
from typing import Annotated
from uuid import uuid4

from semantic_kernel.connectors.ai.open_ai import OpenAITextEmbedding
from semantic_kernel.connectors.azure_ai_search import AzureAISearchCollection
from semantic_kernel.data.vector import VectorStoreField, vectorstoremodel
```

**Data Model with Filterable Fields**:

```python
@vectorstoremodel(collection_name="filtered-index")
@dataclass
class FilterableModel:
    text: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    category: Annotated[str, VectorStoreField("data", is_indexed=True)]
    rating: Annotated[float, VectorStoreField("data", is_indexed=True)]
    id: Annotated[str, VectorStoreField("key")] = field(default_factory=lambda: str(uuid4()))
    embedding: Annotated[
        list[float] | str | None,
        VectorStoreField("vector", dimensions=1536)
    ] = None

    def __post_init__(self):
        if self.embedding is None:
            self.embedding = self.text
```

**Complete Example**:

```python
async def hybrid_search_with_filter():
    records = [
        FilterableModel(text="Luxury hotel with pool", category="hotel", rating=4.5),
        FilterableModel(text="Budget motel near airport", category="motel", rating=3.2),
        FilterableModel(text="Premium resort with spa", category="resort", rating=4.8),
    ]

    async with AzureAISearchCollection[str, FilterableModel](
        record_type=FilterableModel,
        embedding_generator=OpenAITextEmbedding()
    ) as collection:
        await collection.ensure_collection_exists()
        await collection.upsert(records)

        # Hybrid search with filter
        results = await collection.hybrid_search(
            values="luxury accommodation",
            vector_property_name="embedding",
            additional_property_name="text",  # Field for keyword search
            filter=lambda x: x.rating >= 4.0,  # Only high-rated items
            top=5
        )

        async for result in results.results:
            print(f"Text: {result.record.text}")
            print(f"Category: {result.record.category}")
            print(f"Rating: {result.record.rating}")
            print(f"Score: {result.score}\n")

        await collection.ensure_collection_deleted()

if __name__ == "__main__":
    asyncio.run(hybrid_search_with_filter())
```

**Filter Expression Syntax**:

```python
# Comparison filters
filter=lambda x: x.rating >= 4.0
filter=lambda x: x.category == "hotel"
filter=lambda x: x.price < 200.0

# Boolean combinations
filter=lambda x: x.rating >= 4.0 and x.category == "hotel"
filter=lambda x: x.price < 200.0 or x.price > 500.0

# Nested property access
filter=lambda x: x.Address.City == "Seattle"
filter=lambda x: x.Address.Country == "USA" and x.Rating >= 4.0

# Multiple filters (list)
filter=[
    lambda x: x.rating >= 4.0,
    lambda x: x.category == "hotel"
]
```

**Key Parameters**:

- `values`: Query text for both keyword and vector search
- `vector_property_name`: Vector field name
- `additional_property_name`: Text field for keyword search (optional, auto-detects if None)
- `filter`: Lambda expression or list of lambda expressions
- `top`: Maximum results
- `skip`: Pagination offset

---

### Pattern: CRUD Operations

**Purpose**: Create, Read, Update, Delete operations on Azure AI Search collection.

**Required Imports**:

```python
import asyncio
from dataclasses import dataclass, field
from typing import Annotated
from uuid import uuid4

from semantic_kernel.connectors.azure_ai_search import AzureAISearchCollection
from semantic_kernel.data.vector import VectorStoreField, vectorstoremodel
```

**Complete Example**:

```python
@vectorstoremodel(collection_name="crud-index")
@dataclass
class CrudModel:
    name: Annotated[str, VectorStoreField("data")]
    id: Annotated[str, VectorStoreField("key")] = field(default_factory=lambda: str(uuid4()))

async def crud_operations():
    async with AzureAISearchCollection[str, CrudModel](
        record_type=CrudModel
    ) as collection:
        # CREATE: Ensure collection exists
        await collection.ensure_collection_exists()
        print("Collection created")

        # Check if collection exists
        exists = await collection.collection_exists()
        print(f"Collection exists: {exists}")

        # CREATE/UPDATE: Upsert records
        records = [
            CrudModel(id="1", name="Record One"),
            CrudModel(id="2", name="Record Two"),
            CrudModel(id="3", name="Record Three"),
        ]
        keys = await collection.upsert(records)
        print(f"Upserted records with keys: {keys}")

        # READ: Get specific records by key
        retrieved = await collection.get(keys=["1", "2"])
        print(f"Retrieved {len(retrieved)} records")
        for record in retrieved:
            print(f"  {record.id}: {record.name}")

        # READ: Get records with ordering and pagination
        ordered_records = await collection.get(
            order_by={"name": True},  # True = ascending, False = descending
            top=2,
            skip=0
        )
        print(f"Retrieved {len(ordered_records)} ordered records")

        # UPDATE: Modify and upsert existing record
        record_to_update = retrieved[0]
        record_to_update.name = "Updated Record One"
        await collection.upsert([record_to_update])
        print(f"Updated record {record_to_update.id}")

        # DELETE: Remove specific records
        await collection.delete(keys=["3"])
        print("Deleted record with key '3'")

        # DELETE: Remove entire collection
        await collection.ensure_collection_deleted()
        print("Collection deleted")

if __name__ == "__main__":
    asyncio.run(crud_operations())
```

**Key Methods**:

- `ensure_collection_exists()`: Create index if it doesn't exist
- `collection_exists()`: Check if index exists
- `upsert(records)`: Insert or update records (returns keys)
- `get(keys=None, order_by=None, top=None, skip=None)`: Retrieve records
- `delete(keys)`: Delete specific records
- `ensure_collection_deleted()`: Delete entire index

---

### Pattern: Agent with Azure AI Search Tool

**Purpose**: Create an Azure AI Agent that uses Azure AI Search as a tool.

**Required Imports**:

```python
import asyncio
import logging

from azure.ai.agents.models import AzureAISearchTool
from azure.ai.projects.models import ConnectionType
from azure.identity.aio import AzureCliCredential

from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings, AzureAIAgentThread

logging.basicConfig(level=logging.WARNING)
```

**Configuration**:

```python
# Environment variables required:
# AZURE_AI_AGENT_ENDPOINT=<your-ai-agent-endpoint>
# AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME=<model-deployment>

# Azure AI Search index must be pre-created
AZURE_AI_SEARCH_INDEX_NAME = "hotels-sample-index"
```

**Complete Example**:

```python
async def agent_with_azure_ai_search():
    ai_agent_settings = AzureAIAgentSettings()

    async with (
        AzureCliCredential() as creds,
        AzureAIAgent.create_client(credential=creds, endpoint=ai_agent_settings.endpoint) as client,
    ):
        # Get Azure AI Search connection ID from project
        ai_search_conn_id = ""
        async for connection in client.connections.list():
            if connection.type == ConnectionType.AZURE_AI_SEARCH:
                ai_search_conn_id = connection.id
                break

        # Create Azure AI Search tool
        ai_search = AzureAISearchTool(
            index_connection_id=ai_search_conn_id,
            index_name=AZURE_AI_SEARCH_INDEX_NAME
        )

        # Create agent with Azure AI Search tool
        agent_definition = await client.agents.create_agent(
            model=ai_agent_settings.model_deployment_name,
            instructions="Answer questions about hotels using your index.",
            tools=ai_search.definitions,
            tool_resources=ai_search.resources,
            headers={"x-ms-enable-preview": "true"},
        )

        # Create the agent
        agent = AzureAIAgent(
            client=client,
            definition=agent_definition,
        )

        # Create thread and invoke
        thread: AzureAIAgentThread = None
        user_inputs = [
            "Which hotels are available with full-sized kitchens in Nashville, TN?",
            "Fun hotels with free WiFi.",
        ]

        try:
            for user_input in user_inputs:
                print(f"# User: '{user_input}'\n")
                async for response in agent.invoke(messages=user_input, thread=thread):
                    print(f"# Agent: {response}\n")
                    thread = response.thread
        finally:
            # Cleanup
            await thread.delete() if thread else None
            await client.agents.delete_agent(agent.id)

if __name__ == "__main__":
    asyncio.run(agent_with_azure_ai_search())
```

**Key Components**:

- `AzureAISearchTool`: Wraps Azure AI Search as an agent tool
- `index_connection_id`: Connection ID from Azure AI project
- `index_name`: Name of the Azure AI Search index
- Agent automatically uses the search tool when answering questions

---

### Pattern: Declarative Agent Configuration

**Purpose**: Create an agent using YAML configuration with Azure AI Search tool.

**Required Imports**:

```python
import asyncio

from azure.identity.aio import AzureCliCredential

from semantic_kernel.agents import AgentRegistry, AzureAIAgent, AzureAIAgentSettings
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.function_call_content import FunctionCallContent
from semantic_kernel.contents.function_result_content import FunctionResultContent
```

**YAML Configuration**:

```python
spec = """
type: foundry_agent
name: AzureAISearchAgent
instructions: Answer questions using your index to provide grounding context.
description: This agent answers questions using AI Search to provide grounding context.
model:
  id: ${AzureAI:ChatModelId}
  options:
    temperature: 0.4
tools:
  - type: azure_ai_search
    options:
      tool_connections:
        - ${AzureAI:AzureAISearchConnectionId}
      index_name: ${AzureAI:AzureAISearchIndexName}
"""
```

**Complete Example**:

```python
async def declarative_agent():
    settings = AzureAIAgentSettings()

    async with (
        AzureCliCredential() as creds,
        AzureAIAgent.create_client(credential=creds) as client,
    ):
        try:
            # Create agent from YAML spec with extras
            agent: AzureAIAgent = await AgentRegistry.create_from_yaml(
                yaml_str=spec,
                client=client,
                settings=settings,
                extras={
                    "AzureAISearchConnectionId": "<azure-ai-search-connection-id>",
                    "AzureAISearchIndexName": "<azure-ai-search-index-name>",
                },
            )

            TASK = "What is Semantic Kernel?"
            print(f"# User: '{TASK}'")

            # Callback to handle intermediate messages
            async def on_intermediate_message(message: ChatMessageContent):
                if message.items:
                    for item in message.items:
                        if isinstance(item, FunctionCallContent):
                            print(f"# FunctionCallContent: arguments={item.arguments}")
                        elif isinstance(item, FunctionResultContent):
                            print(f"# FunctionResultContent: result={item.result}")

            # Invoke agent
            async for response in agent.invoke(
                messages=TASK,
                on_intermediate_message=on_intermediate_message
            ):
                print(f"# {response.name}: {response}")
        finally:
            await client.agents.delete_agent(agent.id)

if __name__ == "__main__":
    asyncio.run(declarative_agent())
```

**YAML Configuration Parameters**:

- `type: foundry_agent`: Agent type
- `model.id`: Use `${AzureAI:ChatModelId}` for environment variable
- `tools.type: azure_ai_search`: Specifies Azure AI Search tool
- `tool_connections`: Azure AI Search connection ID
- `index_name`: Azure AI Search index name

**Variable Substitution Formats**:

- Long format: `${AzureAI:VariableName}` (in YAML)
- Short format: Pass directly in `extras` dict (no prefix needed)

---

### Pattern: Custom Search Plugin

**Purpose**: Create custom search functions from a collection to use as plugins with agents.

**Required Imports**:

```python
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from semantic_kernel.agents import AgentThread, ChatCompletionAgent
from semantic_kernel.connectors.ai import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion, OpenAITextEmbedding
from semantic_kernel.connectors.azure_ai_search import AzureAISearchCollection
from semantic_kernel.filters import FilterTypes, FunctionInvocationContext
from semantic_kernel.functions import KernelParameterMetadata, KernelPlugin
from semantic_kernel.kernel_types import OptionalOneOrList
```

**Data Model** (using hotel example):

```python
from typing import Annotated
from pydantic import BaseModel
from semantic_kernel.data.vector import VectorStoreField, vectorstoremodel

class Address(BaseModel):
    StreetAddress: str
    City: str | None
    StateProvince: str | None
    Country: str | None

@vectorstoremodel(collection_name="hotel-index")
class HotelModel(BaseModel):
    HotelId: Annotated[str, VectorStoreField("key")]
    HotelName: Annotated[str | None, VectorStoreField("data")] = None
    Description: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    DescriptionVector: Annotated[list[float] | str | None, VectorStoreField("vector", dimensions=1536)] = None
    Rating: Annotated[float, VectorStoreField("data")]
    Address: Annotated[Address, VectorStoreField("data")]

    def model_post_init(self, context: Any) -> None:
        if self.DescriptionVector is None:
            self.DescriptionVector = self.Description
```

**Complete Example**:

```python
# Create collection
collection = AzureAISearchCollection[str, HotelModel](
    record_type=HotelModel,
    embedding_generator=OpenAITextEmbedding()
)

# Custom filter update function for city filtering
def filter_update(
    filter: OptionalOneOrList[Callable | str] | None = None,
    parameters: list["KernelParameterMetadata"] | None = None,
    **kwargs: Any,
) -> OptionalOneOrList[Callable | str] | None:
    if "city" in kwargs:
        city = kwargs["city"]
        new_filter = f"lambda x: x.Address.City == '{city}'"
        if filter is None:
            filter = new_filter
        elif isinstance(filter, list):
            filter.append(new_filter)
        else:
            filter = [filter, new_filter]
    return filter

# Create search plugin with custom functions
search_plugin = KernelPlugin(
    name="azure_ai_search",
    description="A plugin that allows you to search for hotels.",
    functions=[
        # Function 1: Generic hotel search
        collection.create_search_function(
            description="Search for hotels in specific cities, use '*' for all",
            search_type="keyword_hybrid",
            filter=lambda x: x.Address.Country == "USA",  # Static filter
            parameters=[
                KernelParameterMetadata(
                    name="query",
                    description="What to search for.",
                    type="str",
                    is_required=True,
                    type_object=str,
                ),
                KernelParameterMetadata(
                    name="city",
                    description="The city to search in",
                    type="str",
                    type_object=str,
                ),
                KernelParameterMetadata(
                    name="top",
                    description="Number of results to return.",
                    type="int",
                    default_value=5,
                    type_object=int,
                ),
            ],
            filter_update_function=filter_update,  # Custom filter logic
            string_mapper=lambda x: f"(hotel_id:{x.record.HotelId}) {x.record.HotelName} - {x.record.Description}",
        ),
        # Function 2: Get hotel details by ID
        collection.create_search_function(
            function_name="get_details",
            description="Get details about a hotel by ID",
            top=1,
            parameters=[
                KernelParameterMetadata(
                    name="HotelId",
                    description="The hotel ID to get details for.",
                    type="str",
                    is_required=True,
                    type_object=str,
                ),
            ],
        ),
    ],
)

# Create agent with search plugin
travel_agent = ChatCompletionAgent(
    name="TravelAgent",
    description="A travel agent that helps you find a hotel.",
    service=OpenAIChatCompletion(),
    instructions="You are a travel agent. Help people find hotels.",
    function_choice_behavior=FunctionChoiceBehavior.Auto(),
    plugins=[search_plugin],
)

# Add filter to log search calls
@travel_agent.kernel.filter(filter_type=FilterTypes.FUNCTION_INVOCATION)
async def log_search_filter(
    context: FunctionInvocationContext,
    next: Callable[[FunctionInvocationContext], Awaitable[None]]
):
    print(f"Calling Azure AI Search ({context.function.name}) with arguments:")
    for arg in context.arguments:
        if arg not in ("chat_history",):
            print(f'  {arg}: "{context.arguments[arg]}"')
    await next(context)

# Use the agent
async def main():
    async with collection:
        await collection.ensure_collection_exists()
        # ... load records ...

        thread: AgentThread | None = None
        user_input = "Find me a luxury hotel in Seattle"
        result = await travel_agent.get_response(messages=user_input, thread=thread)
        print(f"Agent: {result.content}")

if __name__ == "__main__":
    asyncio.run(main())
```

**Key Components**:

- `create_search_function()`: Creates a kernel function from the collection
- `search_type`: "vector" or "keyword_hybrid"
- `parameters`: List of `KernelParameterMetadata` defining function parameters
- `filter`: Static filter (lambda or list)
- `filter_update_function`: Dynamic filter based on parameters
- `string_mapper`: Function to format search results for LLM

**Common Variations**:

```python
# Vector-only search function
collection.create_search_function(
    description="Semantic search for hotels",
    search_type="vector",
    vector_property_name="DescriptionVector",
    top=5
)

# Hybrid search with custom mapping
collection.create_search_function(
    search_type="keyword_hybrid",
    vector_property_name="DescriptionVector",
    additional_property_name="Description",
    string_mapper=lambda x: f"{x.record.HotelName}: {x.record.Description} (Score: {x.score})"
)
```

---

### Pattern: RAG with Chat Completion

**Purpose**: Use Azure AI Search as a data source for chat completion (Retrieval-Augmented Generation).

**Required Imports**:

```python
import asyncio
import logging

from azure.identity import AzureCliCredential

from semantic_kernel.connectors.ai.open_ai import (
    AzureAISearchDataSource,
    AzureChatCompletion,
    AzureChatPromptExecutionSettings,
    ExtraBody,
)
from semantic_kernel.connectors.memory.azure_cognitive_search.azure_ai_search_settings import AzureAISearchSettings
from semantic_kernel.contents import ChatHistory
from semantic_kernel.functions import KernelArguments
from semantic_kernel.kernel import Kernel
from semantic_kernel.prompt_template import InputVariable, PromptTemplateConfig

logging.basicConfig(level=logging.DEBUG)
```

**Configuration**:

```python
# Environment variables required:
# AZURE_AI_SEARCH_ENDPOINT=<endpoint>
# AZURE_AI_SEARCH_API_KEY=<api-key>
# AZURE_AI_SEARCH_INDEX_NAME=<index-name>
# AZURE_OPENAI_ENDPOINT=<endpoint>
# AZURE_OPENAI_DEPLOYMENT_NAME=<deployment>
# AZURE_OPENAI_API_KEY=<api-key>

# Example: AI Search index with fields "title", "chunk", and "vector"
```

**Complete Example**:

```python
async def rag_chat_completion():
    kernel = Kernel()

    # Configure Azure AI Search data source
    azure_ai_search_settings = AzureAISearchSettings()
    azure_ai_search_settings_dict = azure_ai_search_settings.model_dump()

    # Add field mappings for your index
    azure_ai_search_settings_dict["fieldsMapping"] = {
        "titleField": "title",
        "contentFields": ["chunk"],
        "vectorFields": ["vector"],
    }

    # Configure embedding deployment for vector search
    azure_ai_search_settings_dict["embeddingDependency"] = {
        "type": "DeploymentName",
        "deploymentName": "ada-002",
    }
    azure_ai_search_settings_dict["query_type"] = "vector"

    # Create data source and execution settings
    az_source = AzureAISearchDataSource(parameters=azure_ai_search_settings_dict)
    extra = ExtraBody(data_sources=[az_source])
    service_id = "chat-gpt"
    req_settings = AzureChatPromptExecutionSettings(
        service_id=service_id,
        extra_body=extra
    )

    # Add chat service (use 2024-02-15-preview API version for data sources)
    chat_service = AzureChatCompletion(
        service_id="chat-gpt",
        api_version="2024-02-15-preview",
        credential=AzureCliCredential()
    )
    kernel.add_service(chat_service)

    # Create prompt template
    prompt_template_config = PromptTemplateConfig(
        template="{{$chat_history}}{{$user_input}}",
        name="chat",
        template_format="semantic-kernel",
        input_variables=[
            InputVariable(
                name="chat_history",
                description="The history of the conversation",
                is_required=True,
                default=""
            ),
            InputVariable(
                name="request",
                description="The user input",
                is_required=True
            ),
        ],
        execution_settings=req_settings,
    )

    # Create chat function
    chat_function = kernel.add_function(
        plugin_name="ChatBot",
        function_name="Chat",
        prompt_template_config=prompt_template_config
    )

    # Chat loop
    chat_history = ChatHistory()
    chat_history.add_user_message("Hi there, who are you?")
    chat_history.add_assistant_message("I am an AI assistant here to answer your questions.")

    user_input = "Who are Emily and David?"  # Question about content in the index

    arguments = KernelArguments(
        chat_history=chat_history,
        user_input=user_input,
        execution_settings=req_settings
    )

    # Stream response
    print("Assistant:> ", end="")
    full_message = None
    async for message in kernel.invoke_stream(chat_function, arguments=arguments):
        print(str(message[0]), end="")
        full_message = message[0] if not full_message else full_message + message[0]
    print("\n")

    # Add to chat history
    if full_message:
        chat_history.add_user_message(user_input)
        for message in AzureChatCompletion.split_message(full_message):
            chat_history.add_message(message)

if __name__ == "__main__":
    asyncio.run(rag_chat_completion())
```

**Key Configuration**:

- `fieldsMapping`: Maps your index fields to Azure AI Search data source
  - `titleField`: Field containing document titles
  - `contentFields`: Fields containing text content (list)
  - `vectorFields`: Fields containing vector embeddings (list)
- `embeddingDependency`: Specifies embedding model for queries
  - `type`: "DeploymentName" for Azure OpenAI
  - `deploymentName`: Name of your embedding deployment
- `query_type`: "vector", "simple", or "semantic"
- `api_version`: Must be "2024-02-15-preview" or later for data sources

---

## Data Model Patterns

### Basic Data Model

**Purpose**: Simple record with key, data, and vector fields.

```python
from dataclasses import dataclass, field
from typing import Annotated
from uuid import uuid4

from semantic_kernel.data.vector import VectorStoreField, vectorstoremodel

@vectorstoremodel(collection_name="simple-index")
@dataclass
class SimpleModel:
    text: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    id: Annotated[str, VectorStoreField("key")] = field(default_factory=lambda: str(uuid4()))
    embedding: Annotated[
        list[float] | str | None,
        VectorStoreField("vector", dimensions=1536)
    ] = None

    def __post_init__(self):
        # Auto-populate embedding from text if None
        if self.embedding is None:
            self.embedding = self.text
```

**Field Type Annotations**:

- `VectorStoreField("key")`: Primary key field (required, must be str)
- `VectorStoreField("data")`: Regular data field
- `VectorStoreField("vector", dimensions=<int>)`: Vector embedding field

**Field Options**:

- `is_full_text_indexed=True`: Enable full-text search on this field
- `is_indexed=True`: Enable filtering on this field
- `dimensions=<int>`: Vector dimensions (required for vector fields)
- `type=<SearchFieldDataType>`: Explicit Azure field type

### Complex Data Model with Nested Objects

**Purpose**: Model with nested Pydantic models and complex types.

```python
from typing import Annotated, Any
from pydantic import BaseModel, ConfigDict
from azure.search.documents.indexes.models import SearchFieldDataType

from semantic_kernel.data.vector import VectorStoreField, vectorstoremodel

class Address(BaseModel):
    StreetAddress: str
    City: str | None
    StateProvince: str | None
    Country: str | None

    model_config = ConfigDict(extra="ignore")

class Room(BaseModel):
    Type: str
    Description: str
    BaseRate: float
    SleepsCount: int
    Tags: list[str]

    model_config = ConfigDict(extra="ignore")

@vectorstoremodel(collection_name="hotel-index")
class HotelModel(BaseModel):
    HotelId: Annotated[str, VectorStoreField("key")]
    HotelName: Annotated[str | None, VectorStoreField("data")] = None
    Description: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    DescriptionVector: Annotated[
        list[float] | str | None,
        VectorStoreField("vector", dimensions=1536)
    ] = None
    Category: Annotated[str, VectorStoreField("data")]
    Tags: Annotated[list[str], VectorStoreField("data", is_indexed=True)]
    ParkingIncluded: Annotated[bool | None, VectorStoreField("data")] = None
    LastRenovationDate: Annotated[
        str | None,
        VectorStoreField("data", type=SearchFieldDataType.DateTimeOffset)
    ] = None
    Rating: Annotated[float, VectorStoreField("data")]
    Location: Annotated[
        dict[str, Any],
        VectorStoreField("data", type=SearchFieldDataType.GeographyPoint)
    ]
    Address: Annotated[Address, VectorStoreField("data")]
    Rooms: Annotated[list[Room], VectorStoreField("data")]

    model_config = ConfigDict(extra="ignore")

    def model_post_init(self, context: Any) -> None:
        if self.DescriptionVector is None:
            self.DescriptionVector = self.Description
```

**Supported Complex Types**:

- `dict`: ComplexType in Azure AI Search
- `list[dict]`: Collection(ComplexType)
- `BaseModel`: Nested Pydantic model (ComplexType)
- `list[BaseModel]`: Collection of nested models
- `list[str]`, `list[int]`, `list[float]`: Collections of primitives

**Special Azure Types**:

- `SearchFieldDataType.DateTimeOffset`: Date/time fields
- `SearchFieldDataType.GeographyPoint`: Geospatial coordinates
- `SearchFieldDataType.Int64`: Large integers
- `SearchFieldDataType.Double`: Floating-point numbers

### Model with Multiple Vector Fields

**Purpose**: Support multiple vector embeddings (e.g., multilingual).

```python
@vectorstoremodel(collection_name="multilingual-index")
class MultilingualModel(BaseModel):
    id: Annotated[str, VectorStoreField("key")]
    text_en: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    text_fr: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    vector_en: Annotated[
        list[float] | str | None,
        VectorStoreField("vector", dimensions=1536)
    ] = None
    vector_fr: Annotated[
        list[float] | str | None,
        VectorStoreField("vector", dimensions=1536)
    ] = None

    def model_post_init(self, context: Any) -> None:
        if self.vector_en is None:
            self.vector_en = self.text_en
        if self.vector_fr is None:
            self.vector_fr = self.text_fr
```

**Usage**:

```python
# Search using English vectors
results = await collection.search(
    values="search query",
    vector_property_name="vector_en"
)

# Search using French vectors
results = await collection.search(
    values="requête de recherche",
    vector_property_name="vector_fr"
)
```

---

## Advanced Features

### Custom Index Configuration

**Purpose**: Manually define Azure AI Search index schema for complex scenarios.

**Required Imports**:

```python
from azure.search.documents.indexes.models import (
    ComplexField,
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    VectorSearch,
    VectorSearchProfile,
)
```

**Complete Example**:

```python
custom_index = SearchIndex(
    name="custom-hotel-index",
    fields=[
        # Key field
        SearchField(
            name="HotelId",
            type="Edm.String",
            key=True,
            hidden=False,
            filterable=True,
            sortable=False,
            facetable=False,
            searchable=True,
        ),
        # Text fields
        SearchField(
            name="Description",
            type="Edm.String",
            hidden=False,
            filterable=False,
            sortable=False,
            facetable=False,
            searchable=True,
        ),
        # Vector field
        SearchField(
            name="DescriptionVector",
            type="Collection(Edm.Single)",
            hidden=False,
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="hnsw",
        ),
        # Filterable field
        SearchField(
            name="Rating",
            type="Edm.Double",
            hidden=False,
            filterable=True,
            sortable=True,
            facetable=True,
            searchable=False,
        ),
        # Complex nested field
        ComplexField(
            name="Address",
            collection=False,
            fields=[
                SearchField(name="City", type="Edm.String", filterable=True),
                SearchField(name="Country", type="Edm.String", filterable=True),
            ],
        ),
    ],
    vector_search=VectorSearch(
        profiles=[
            VectorSearchProfile(
                name="hnsw",
                algorithm_configuration_name="hnsw"
            )
        ],
        algorithms=[
            HnswAlgorithmConfiguration(name="hnsw")
        ],
        vectorizers=[],  # Empty for client-side vectorization
    ),
)

# Use custom index
async with AzureAISearchCollection[str, HotelModel](
    record_type=HotelModel,
    embedding_generator=OpenAITextEmbedding()
) as collection:
    await collection.ensure_collection_exists(index=custom_index)
    # ... rest of operations ...
```

**When to Use Custom Index**:

- Complex nested structures that auto-generation doesn't handle
- Specific field configurations (analyzers, scoring profiles)
- Migration from existing indexes
- Fine-tuned performance settings

### Vector Search Algorithms

**HNSW (Hierarchical Navigable Small World)**:

```python
from semantic_kernel.data.vector import IndexKind, DistanceFunction, VectorStoreField

embedding: Annotated[
    list[float] | str | None,
    VectorStoreField(
        "vector",
        dimensions=1536,
        index_kind=IndexKind.HNSW,  # Fast approximate search
        distance_function=DistanceFunction.COSINE_DISTANCE
    )
] = None
```

**Flat (Exhaustive KNN)**:

```python
embedding: Annotated[
    list[float] | str | None,
    VectorStoreField(
        "vector",
        dimensions=1536,
        index_kind=IndexKind.FLAT,  # Exact search, slower but perfect recall
        distance_function=DistanceFunction.EUCLIDEAN_DISTANCE
    )
] = None
```

**Distance Function Comparison**:
| Function | Range | Best For |
|----------|-------|----------|
| COSINE_DISTANCE | 0-1 (higher = more similar) | Text embeddings (normalized) |
| DOT_PRODUCT | Unbounded | Raw embeddings, recommender systems |
| EUCLIDEAN_DISTANCE | 0-∞ (lower = more similar) | Spatial data |
| HAMMING | Integer | Binary vectors |

### Azure AI Search Store (Multiple Collections)

**Purpose**: Manage multiple collections from a single store instance.

**Required Imports**:

```python
from semantic_kernel.connectors.azure_ai_search import AzureAISearchStore
```

**Complete Example**:

```python
async def multi_collection_example():
    # Create store
    async with AzureAISearchStore(
        search_endpoint="https://my-service.search.windows.net",
        api_key="<api-key>",
        embedding_generator=OpenAITextEmbedding()
    ) as store:
        # Get collection 1
        collection1 = store.get_collection(
            record_type=Model1,
            collection_name="collection-1"
        )

        # Get collection 2
        collection2 = store.get_collection(
            record_type=Model2,
            collection_name="collection-2"
        )

        # List all collections
        collection_names = await store.list_collection_names()
        print(f"Collections: {collection_names}")

        # Work with collections
        await collection1.ensure_collection_exists()
        await collection2.ensure_collection_exists()

        # ... perform operations ...

if __name__ == "__main__":
    asyncio.run(multi_collection_example())
```

**Key Benefits**:

- Shared connection management
- Single authentication point
- Centralized embedding generator
- Easy collection enumeration

### Embedding Generation Options

**Client-Side Embedding (Default)**:

```python
from semantic_kernel.connectors.ai.open_ai import OpenAITextEmbedding

collection = AzureAISearchCollection(
    record_type=MyModel,
    embedding_generator=OpenAITextEmbedding()  # Generates embeddings client-side
)
```

**Azure AI Search Integrated Vectorization**:

```python
# Step 1: Configure custom index with vectorizer
from azure.search.documents.indexes.models import (
    AzureOpenAIVectorizer,
    AzureOpenAIParameters,
)

custom_index = SearchIndex(
    name="integrated-vectorization-index",
    fields=[...],
    vector_search=VectorSearch(
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm_configuration_name="hnsw",
                vectorizer_name="openai-vectorizer"  # Reference vectorizer
            )
        ],
        algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
        vectorizers=[
            AzureOpenAIVectorizer(
                name="openai-vectorizer",
                parameters=AzureOpenAIParameters(
                    resource_url="<azure-openai-endpoint>",
                    deployment_name="<embedding-deployment>",
                    api_key="<api-key>",
                )
            )
        ],
    ),
)

# Step 2: Create collection WITHOUT embedding_generator
collection = AzureAISearchCollection(
    record_type=MyModel,
    # No embedding_generator - Azure AI Search handles it
)

await collection.ensure_collection_exists(index=custom_index)
```

**When to Use Each**:

- **Client-Side**: More control, works with any embedding service, easier debugging
- **Server-Side**: Lower latency, reduced data transfer, Azure handles scaling

### Advanced Filter Expressions

**Comparison Operators**:

```python
# Equality
filter=lambda x: x.category == "hotel"
filter=lambda x: x.rating != 3.0

# Numeric comparisons
filter=lambda x: x.rating >= 4.0
filter=lambda x: x.price < 200.0
filter=lambda x: x.rooms > 2

# String contains (full-text)
filter=lambda x: "pool" in x.description  # Note: Limited support
```

**Boolean Logic**:

```python
# AND
filter=lambda x: x.rating >= 4.0 and x.category == "hotel"

# OR
filter=lambda x: x.category == "hotel" or x.category == "resort"

# NOT
filter=lambda x: not (x.category == "motel")

# Complex combinations
filter=lambda x: (x.rating >= 4.0 and x.price < 300) or x.category == "luxury"
```

**Nested Property Access**:

```python
# Access nested object properties using dot notation
filter=lambda x: x.Address.City == "Seattle"
filter=lambda x: x.Address.Country == "USA" and x.Address.StateProvince == "WA"

# Multiple levels
filter=lambda x: x.Location.Coordinates.Latitude > 40.0
```

**Multiple Filters (List)**:

```python
# All filters are combined with AND
filter=[
    lambda x: x.rating >= 4.0,
    lambda x: x.Address.Country == "USA",
    lambda x: x.ParkingIncluded == True,
]
```

**Filter with Search**:

```python
results = await collection.search(
    values="luxury hotel",
    vector_property_name="embedding",
    filter=lambda x: x.rating >= 4.5 and x.Address.City == "Seattle",
    top=10
)
```

### Error Handling Best Practices

**Required Imports**:

```python
from semantic_kernel.exceptions import (
    ServiceInitializationError,
    VectorSearchExecutionException,
    VectorStoreInitializationException,
    VectorStoreOperationException,
)
```

**Complete Example**:

```python
async def safe_collection_operations():
    try:
        # Collection initialization
        async with AzureAISearchCollection[str, MyModel](
            record_type=MyModel,
            collection_name="my-index",
            embedding_generator=OpenAITextEmbedding()
        ) as collection:

            # Ensure collection exists
            try:
                await collection.ensure_collection_exists()
            except VectorStoreInitializationException as e:
                print(f"Failed to create collection: {e}")
                raise

            # Check existence before operations
            if not await collection.collection_exists():
                print("Collection does not exist")
                return

            # Upsert with error handling
            try:
                keys = await collection.upsert(records)
                print(f"Upserted {len(keys)} records")
            except VectorStoreOperationException as e:
                print(f"Upsert failed: {e}")
                raise

            # Search with error handling
            try:
                results = await collection.search(
                    values="search query",
                    vector_property_name="embedding",
                    top=5
                )
                async for result in results.results:
                    print(f"Found: {result.record.text}")
            except VectorSearchExecutionException as e:
                print(f"Search failed: {e}")
                raise

    except ServiceInitializationError as e:
        print(f"Service initialization failed: {e}")
        # Check credentials, endpoint, network connectivity
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(safe_collection_operations())
```

**Common Exceptions**:

- `ServiceInitializationError`: Invalid credentials or endpoint
- `VectorStoreInitializationException`: Collection creation failed
- `VectorStoreOperationException`: CRUD operation failed
- `VectorSearchExecutionException`: Search query failed

---

## Best Practices & Tips

### When to Use Vector vs Hybrid Search

**Use Vector Search When**:

- Semantic similarity is primary concern
- Users use natural language queries
- You want to find conceptually similar items
- Exact keyword matches are less important

```python
results = await collection.search(
    values="What is machine learning?",
    vector_property_name="embedding"
)
```

**Use Hybrid Search When**:

- You need both semantic and keyword matching
- Users might use specific terminology or proper nouns
- Best recall across different query types
- Combining relevance signals improves results

```python
results = await collection.hybrid_search(
    values="Azure AI Search",  # Matches keywords AND semantics
    vector_property_name="embedding",
    additional_property_name="text"
)
```

### Performance Optimization

**1. Use Appropriate Index Algorithm**:

```python
# HNSW for large datasets (fast, approximate)
VectorStoreField("vector", dimensions=1536, index_kind=IndexKind.HNSW)

# FLAT for small datasets or exact search requirements
VectorStoreField("vector", dimensions=1536, index_kind=IndexKind.FLAT)
```

**2. Limit Fields in Results**:

```python
# Exclude vectors from results when not needed
results = await collection.get(
    keys=["1", "2", "3"],
    include_vectors=False  # Faster, less data transfer
)
```

**3. Use Pagination**:

```python
# Get results in batches
page_size = 50
page = 0
results = await collection.get(
    top=page_size,
    skip=page * page_size,
    order_by={"created_at": False}  # Descending
)
```

**4. Optimize Filter Expressions**:

```python
# Put most selective filters first (indexed fields)
filter=lambda x: x.category == "hotel" and x.rating >= 4.0

# Use indexed fields for filtering
# Mark fields as indexed in model:
category: Annotated[str, VectorStoreField("data", is_indexed=True)]
```

**5. Batch Upsert Operations**:

```python
# Upsert records in batches
batch_size = 100
for i in range(0, len(all_records), batch_size):
    batch = all_records[i:i+batch_size]
    await collection.upsert(batch)
```

### Security Considerations

**1. Use Managed Identity When Possible**:

```python
from azure.identity.aio import DefaultAzureCredential

collection = AzureAISearchCollection(
    record_type=MyModel,
    token_credentials=DefaultAzureCredential(),  # No API keys
    search_endpoint="https://my-service.search.windows.net"
)
```

**2. Store Credentials Securely**:

```python
# Use environment variables, not hardcoded
import os

api_key = os.environ.get("AZURE_AI_SEARCH_API_KEY")
collection = AzureAISearchCollection(
    record_type=MyModel,
    api_key=api_key,
    search_endpoint=os.environ.get("AZURE_AI_SEARCH_ENDPOINT")
)
```

**3. Implement Access Controls**:

```python
# Use Azure RBAC roles
# - Search Index Data Reader (read-only)
# - Search Index Data Contributor (read/write)
# - Search Service Contributor (manage indexes)
```

### Common Pitfalls and Solutions

**Pitfall 1: Forgetting to Set Embedding Field**:

```python
# Solution: Use __post_init__ or model_post_init
@dataclass
class MyModel:
    text: str
    embedding: list[float] | str | None = None

    def __post_init__(self):
        if self.embedding is None:
            self.embedding = self.text  # Auto-populate
```

**Pitfall 2: Using Wrong Collection Name**:

```python
# Solution: Use decorator to define collection name
@vectorstoremodel(collection_name="my-consistent-name")
class MyModel:
    ...

# Collection will use "my-consistent-name" by default
```

**Pitfall 3: Filter Field Not Indexed**:

```python
# Problem:
category: Annotated[str, VectorStoreField("data")]  # Not indexed!
filter=lambda x: x.category == "hotel"  # May be slow

# Solution:
category: Annotated[str, VectorStoreField("data", is_indexed=True)]
```

**Pitfall 4: Not Closing Connections**:

```python
# Problem:
collection = AzureAISearchCollection(...)
# ... operations ...
# No cleanup!

# Solution: Use async context manager
async with AzureAISearchCollection(...) as collection:
    # ... operations ...
# Automatically closed
```

## Quick Code Templates

### Template: Complete Vector Search Setup

```python
import asyncio
from dataclasses import dataclass, field
from typing import Annotated
from uuid import uuid4

from semantic_kernel.connectors.ai.open_ai import OpenAITextEmbedding
from semantic_kernel.connectors.azure_ai_search import AzureAISearchCollection
from semantic_kernel.data.vector import VectorStoreField, vectorstoremodel

@vectorstoremodel(collection_name="my-index")
@dataclass
class MyModel:
    text: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    id: Annotated[str, VectorStoreField("key")] = field(default_factory=lambda: str(uuid4()))
    embedding: Annotated[list[float] | str | None, VectorStoreField("vector", dimensions=1536)] = None

    def __post_init__(self):
        if self.embedding is None:
            self.embedding = self.text

async def main():
    records = [MyModel(text="Example text")]

    async with AzureAISearchCollection[str, MyModel](
        record_type=MyModel,
        embedding_generator=OpenAITextEmbedding()
    ) as collection:
        await collection.ensure_collection_exists()
        await collection.upsert(records)

        results = await collection.search(values="search query", vector_property_name="embedding")
        async for result in results.results:
            print(f"{result.record.text} (score: {result.score})")

        await collection.ensure_collection_deleted()

if __name__ == "__main__":
    asyncio.run(main())
```

### Template: Agent with Search Plugin

```python
import asyncio
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.ai import FunctionChoiceBehavior
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion, OpenAITextEmbedding
from semantic_kernel.connectors.azure_ai_search import AzureAISearchCollection
from semantic_kernel.functions import KernelParameterMetadata, KernelPlugin

# Define your model here (see above)

async def main():
    collection = AzureAISearchCollection[str, MyModel](
        record_type=MyModel,
        embedding_generator=OpenAITextEmbedding()
    )

    search_plugin = KernelPlugin(
        name="search",
        description="Search plugin",
        functions=[
            collection.create_search_function(
                description="Search for items",
                search_type="keyword_hybrid",
                parameters=[
                    KernelParameterMetadata(name="query", type="str", is_required=True, type_object=str),
                ],
            )
        ],
    )

    agent = ChatCompletionAgent(
        name="SearchAgent",
        service=OpenAIChatCompletion(),
        instructions="Help users search for items.",
        function_choice_behavior=FunctionChoiceBehavior.Auto(),
        plugins=[search_plugin],
    )

    async with collection:
        await collection.ensure_collection_exists()
        # ... load data ...

        result = await agent.get_response(messages="Find relevant items")
        print(result.content)

if __name__ == "__main__":
    asyncio.run(main())
```

---
