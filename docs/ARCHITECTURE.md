# Architecture

## Vector Store: In-Memory

The SRM catalog is loaded into memory as vector embeddings. Each query follows this flow:

1. **Embed query text** using Azure OpenAI (text-embedding-3-small)
2. **Compute cosine similarity** against all SRM embeddings in memory
3. **Return top-k matches** ranked by relevance
4. **LLM analyzes matches** and generates contextual response

### Why In-Memory?

- **Inspectable**: Entire search process visible in local process, easy to trace from query to result
- **Simple**: No distributed service dependencies, runs locally with minimal setup
- **Fast enough**: Catalog size (hundreds of SRMs) fits comfortably in memory, sub-second search
- **Learning-focused**: Removes infrastructure complexity to highlight AI patterns

For production scale (millions of documents), distributed vector search makes sense. For demonstration and exploration, in-memory is optimal.

## Architecture Evolution

> ### Previous: Azure AI Search
>
> - **Better for production**: Distributed vector search, handles massive scale
> - **Infrastructure overhead**: Requires Azure deployment, index management, cost monitoring
> - **Harder to inspect**: Query flow spans multiple services, harder to trace and debug
>
> ### Current: In-Memory Vector Store
>
> - **Perfect for learning**: Entire flow visible in single process
> - **Trade**: Less scalable (catalog must fit in memory)
> - **Gain**: Simpler setup, easier debugging, focus on AI patterns not infrastructure
>
> The evolution prioritizes inspectability over scale. For a codebase demonstrating AI patterns to professional developers, being able to trace every step matters more than handling millions of documents.

## Agent Architecture

Both chatbot and CLI use Semantic Kernel's agent orchestration pattern:

### Plugins
Modular functions that provide specific capabilities:
- `search_catalog`: Vector similarity search over SRM embeddings
- `analyze_srm`: LLM-based analysis of SRM relevance
- `format_response`: Structure results for user display
- `manage_temp_srms`: CRUD operations on catalog (CLI only)

### Planner
LLM decides which plugins to call based on user input. For complex queries, may chain multiple plugin calls:
1. Search catalog for matches
2. Analyze each match for relevance
3. Format top recommendation with reasoning

### Memory
Conversation history maintained for multi-turn interactions:
- Chatbot: Remember context across clarifying questions
- CLI: Track state across related administrative commands

## Key AI Patterns Demonstrated

### 1. Retrieval Augmented Generation (RAG)
- Vector search retrieves relevant SRMs from catalog
- LLM generates response grounded in retrieved context
- Prevents hallucination: recommendations based on actual SRMs, not invented

### 2. Semantic Search
- Natural language query matching beyond keyword search
- "database slow" matches "performance degradation" through embedding similarity
- Captures intent: query and SRM don't need exact word overlap

### 3. Agent Orchestration
- LLM plans multi-step operations dynamically
- Plugins provide tools, LLM decides when and how to use them
- Handles complex queries by decomposing into plugin calls

### 4. Conversational Context
- Multi-turn interactions maintain state
- Follow-up questions reference previous context
- CLI can chain related administrative commands

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | Semantic Kernel (Python) | Agent orchestration, plugin management |
| **Chat LLM** | Azure OpenAI GPT-5 | Reasoning, planning, response generation |
| **Embeddings** | Azure OpenAI text-embedding-3-small | Vector representations for semantic search |
| **Vector Store** | In-memory (NumPy/simple cosine similarity) | SRM catalog storage and retrieval |
| **Deployment** | Local Python process | Simple execution, easy debugging |

## Code Organization

```
src/
├── memory/
│   └── vector_store.py          # In-memory vector store implementation
├── plugins/
│   └── cli_concierge/
│       └── api_client_plugin.py # CLI agent plugins
└── utils/
    └── store_factory.py         # Vector store abstraction

run_cli_concierge.py             # CLI agent entry point
```

The architecture is intentionally flat and direct. You can trace any query from entry point to completion without navigating complex service hierarchies.

## What Makes This Inspectable

1. **Single process**: No distributed tracing needed, add print statements anywhere
2. **In-memory data**: Examine vector store state at any point
3. **Synchronous flow**: No async complexity hiding execution order
4. **Minimal abstractions**: Direct path from user input to LLM to response

For professional developers evaluating this code, every decision is traceable and every component is accessible.
