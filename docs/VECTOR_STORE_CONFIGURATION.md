# Vector Store Configuration Guide

## Overview

The semantic-kernel application supports two search backends for retrieval operations:

1. **In-Memory (Local) Vector Store** (Default, recommended for development)
   - Uses semantic vector similarity search
2. **Azure AI Search** (Optional, for production deployments)
   - Uses BM25 keyword search

## Quick Start

### Default Configuration (Local In-Memory Store)

No configuration needed! The application defaults to the local in-memory vector store:

```bash
# Run with default in-memory store
python run_chatbot.py
```

### Using Azure AI Search

Set environment variables:

```bash
export VECTOR_STORE_TYPE=azure_search
export AZURE_AI_SEARCH_ENDPOINT=https://your-service.search.windows.net
export AZURE_AI_SEARCH_API_KEY=your-api-key
export AZURE_AI_SEARCH_INDEX_NAME=your-index-name

# Run application
python run_chatbot.py
```

## Configuration Details

### Environment Variables

```bash
# Store Type Selection
VECTOR_STORE_TYPE=in_memory           # Options: in_memory, azure_search

# Azure AI Search Configuration (when VECTOR_STORE_TYPE=azure_search)
AZURE_AI_SEARCH_ENDPOINT=https://your-service.search.windows.net
AZURE_AI_SEARCH_API_KEY=your-api-key
AZURE_AI_SEARCH_INDEX_NAME=your-index-name

# Testing Configuration
SKIP_AZURE_TESTS=1                  # Skip Azure tests in CI/CD
```

### Store Type: In-Memory (Local) Vector Store

**Search Technology:** Semantic vector similarity - uses embeddings to find conceptually similar results, not just keyword matches.

**When to use:**
- Local development and testing
- Prototyping semantic search features
- Projects where data can be reloaded on startup

**Configuration:**

```python
from semantic_kernel.connectors.ai.open_ai import AzureTextEmbedding
from src.utils.store_factory import create_vector_store

# Create embedding generator
embedding_gen = AzureTextEmbedding(
    deployment_name="text-embedding-ada-002",
    endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY")
)

# Create in-memory store
store = create_vector_store(
    store_type='in_memory',
    embedding_generator=embedding_gen
)
```

**Features:**
- Semantic vector similarity search - finds conceptually related results
- Fast for small-to-medium datasets
- Zero external dependencies

**Characteristics:**
- Data reloaded from CSV on each startup
- Requires embedding generation via Azure OpenAI API
- Memory usage scales with dataset size

### Store Type: Azure AI Search

**Search Technology:** BM25 keyword search - uses text matching and term frequency, not semantic understanding.

**When to use:**
- Production deployments requiring data persistence
- Distributed systems with multiple instances
- Large datasets (>10K documents)
- When you need search results to persist across restarts

**Configuration:**

```bash
VECTOR_STORE_TYPE=azure_search
AZURE_AI_SEARCH_ENDPOINT=https://myservice.search.windows.net
AZURE_AI_SEARCH_API_KEY=your-api-key
AZURE_AI_SEARCH_INDEX_NAME=srm-catalog
```

**Requirements:**
- Azure subscription
- Azure AI Search service created
- Index created with correct schema (see schema below)

**Index Schema:**

```json
{
  "fields": [
    {"name": "id", "type": "Edm.String", "key": true, "filterable": true},
    {"name": "SRM_ID", "type": "Edm.String", "filterable": true, "searchable": true},
    {"name": "Name", "type": "Edm.String", "searchable": true},
    {"name": "Description", "type": "Edm.String", "searchable": true},
    {"name": "URL_Link", "type": "Edm.String", "filterable": true},
    {"name": "Team", "type": "Edm.String", "filterable": true, "searchable": true},
    {"name": "Type", "type": "Edm.String", "filterable": true, "searchable": true},
    {"name": "owner_notes", "type": "Edm.String", "searchable": true},
    {"name": "hidden_notes", "type": "Edm.String", "searchable": true},
    {"name": "negative_feedback_queries", "type": "Collection(Edm.String)"},
    {"name": "positive_feedback_queries", "type": "Collection(Edm.String)"},
    {"name": "feedback_score_adjustment", "type": "Edm.Double"}
  ]
}
```

**Characteristics:**
- Data persists in Azure - no reload needed on restart (run_chatbot.py:153-156)
- BM25 keyword search - matches based on text overlap, not semantic meaning
- Requires Azure subscription and service setup
- Cost: Billed per hour (even when idle)

## Programmatic Usage

### Basic Usage

```python
from src.utils.store_factory import create_vector_store

async def example():
    # Create store (uses environment variables)
    embedding_gen = ...  # Your embedding generator
    store = create_vector_store(embedding_generator=embedding_gen)

    # Upsert records
    await store.upsert(records)

    # Search
    results = await store.search(query="storage expansion", top_k=5)

    async for result in results:
        print(f"Score: {result.score}, Name: {result.record.name}")

    # Get by ID
    record = await store.get_by_id("SRM-051")

    # Update feedback
    await store.update_feedback_scores(
        srm_id="SRM-051",
        query="storage",
        feedback_type="positive"
    )
```

### Advanced Usage

```python
from src.utils.store_factory import create_vector_store

async def advanced_example():
    # Override environment variables for Azure
    store = create_vector_store(
        store_type='azure_search',
        endpoint='https://test.search.windows.net',
        api_key='test-key',
        index_name='test-index'
    )

    # Search with filters
    results = await store.search(
        query="database migration",
        top_k=10,
        filters={"Team": "Database Team", "Type": "Migration"}
    )

    async for result in results:
        print(f"Found: {result.record.name}")
```

## Testing

### Running Tests

**Default (in-memory):**
```bash
pytest
```

**Azure only (requires credentials):**
```bash
export AZURE_AI_SEARCH_ENDPOINT=...
export AZURE_AI_SEARCH_API_KEY=...
export AZURE_AI_SEARCH_INDEX_NAME=...
pytest -k "Azure"
```

**Skip Azure tests entirely:**
```bash
export SKIP_AZURE_TESTS=1
pytest
```

## FAQ

**Q: What's the difference between vector similarity and keyword search?**

A: The in-memory store uses **semantic vector similarity** - it understands meaning and finds conceptually related results. Azure AI Search uses **BM25 keyword search** - it matches text based on word overlap and term frequency. For example, a vector search for "car" might find "automobile" or "vehicle", while keyword search looks for exact word matches.

**Q: Can I use both stores at the same time?**

A: Not simultaneously. Choose one using the `VECTOR_STORE_TYPE` environment variable. You can switch between them anytime.

**Q: Which store should I use for local development?**

A: Use the default in-memory store for local development. It's free, requires zero setup, and provides semantic search capabilities. Only use Azure if you specifically need persistent storage or are testing Azure-specific features.

