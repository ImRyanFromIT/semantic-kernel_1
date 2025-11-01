# Vector Store Configuration Guide

## Overview

The semantic-kernel application supports three vector store backends for search and retrieval operations:

1. **SQLite FTS5** (Default, recommended for testing and small deployments)
2. **Azure AI Search** (Production option for distributed systems)
3. **In-Memory Vector Store** (Development, non-persistent)

## Quick Start

### Default Configuration (SQLite)

No configuration needed! The application defaults to SQLite with an in-memory database:

```bash
# Run tests - automatically uses SQLite
pytest
```

### Using Azure AI Search

Set environment variables:

```bash
export VECTOR_STORE_TYPE=azure_search
export AZURE_AI_SEARCH_ENDPOINT=https://your-service.search.windows.net
export AZURE_AI_SEARCH_API_KEY=your-api-key
export AZURE_AI_SEARCH_INDEX_NAME=your-index-name

# Run application
python src/main.py
```

### Using Persistent SQLite Database

```bash
export VECTOR_STORE_TYPE=sqlite
export SQLITE_DB_PATH=/path/to/database.db

# Run application
python src/main.py
```

## Store Types Comparison

| Feature | SQLite FTS5 | Azure AI Search | In-Memory |
|---------|-------------|-----------------|-----------|
| **Cost** | Free | $$ (per hour) | Free |
| **Setup** | Zero dependencies | Requires Azure account | Requires embeddings |
| **Persistence** | Optional (file or memory) | Yes | No |
| **Scale** | ~10K documents | Millions | Limited by RAM |
| **Search Type** | BM25 keyword | BM25 keyword | Vector similarity |
| **Best For** | Testing, local dev | Production | Development |

## Configuration Details

### Environment Variables

```bash
# Store Type Selection
VECTOR_STORE_TYPE=sqlite           # Options: sqlite, azure_search, in_memory

# SQLite Configuration (when VECTOR_STORE_TYPE=sqlite)
SQLITE_DB_PATH=:memory:             # Use ":memory:" or file path

# Azure AI Search Configuration (when VECTOR_STORE_TYPE=azure_search)
AZURE_AI_SEARCH_ENDPOINT=https://your-service.search.windows.net
AZURE_AI_SEARCH_API_KEY=your-api-key
AZURE_AI_SEARCH_INDEX_NAME=your-index-name

# Testing Configuration
SKIP_AZURE_TESTS=1                  # Skip Azure tests in CI/CD
```

### Store Type: SQLite FTS5

**When to use:**
- Local development
- Automated testing (CI/CD)
- Small deployments (<10K documents)
- Zero-cost requirement

**Configuration Options:**

**In-Memory Mode** (default, fastest for tests):
```bash
VECTOR_STORE_TYPE=sqlite
SQLITE_DB_PATH=:memory:
```

**File-Based Mode** (persistent, for development):
```bash
VECTOR_STORE_TYPE=sqlite
SQLITE_DB_PATH=/var/lib/myapp/search.db
```

**Features:**
- BM25 ranking algorithm (same as Azure)
- Full-text search across all searchable fields
- Filter support (Team, Type, SRM_ID)
- Feedback score tracking
- Porter stemming and Unicode tokenization

**Limitations:**
- Single-node only (no distributed search)
- Performance degrades above ~50K documents
- FTS5 query syntax differs slightly from Lucene

**Searchable Fields:**
- Name
- Description
- owner_notes
- hidden_notes
- TechnologiesTeamWorksWith

**Filterable Fields:**
- SRM_ID
- Team
- Type
- id

### Store Type: Azure AI Search

**When to use:**
- Production deployments
- Distributed systems
- >10K documents
- Advanced search features needed

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

**Note:** The feedback fields (`negative_feedback_queries`, `positive_feedback_queries`, `feedback_score_adjustment`) are optional and only used when calling `update_feedback_scores()`. They are not included in standard search operations. If you don't need feedback tracking, you can omit these fields from your index.

**Cost Considerations:**
- Billed per hour (even when idle)
- Typical test usage: ~$50-100/month
- Production usage: Scales with tier

### Store Type: In-Memory Vector Store

**When to use:**
- Development with vector embeddings
- Prototyping semantic search
- Non-persistent test scenarios

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
- Vector similarity search
- Semantic understanding
- Fast for small datasets

**Limitations:**
- Non-persistent (data lost on restart)
- Requires embedding generation (costs API calls)
- Slower than keyword search for exact matches

## Migration Guide

### Migrating from Azure to SQLite (for Testing)

**Step 1:** Update environment variables

```bash
# Remove or comment out Azure config
# VECTOR_STORE_TYPE=azure_search
# AZURE_AI_SEARCH_ENDPOINT=...
# AZURE_AI_SEARCH_API_KEY=...
# AZURE_AI_SEARCH_INDEX_NAME=...

# Add SQLite config
export VECTOR_STORE_TYPE=sqlite
export SQLITE_DB_PATH=:memory:
```

**Step 2:** Run tests

```bash
pytest
```

All tests should now use SQLite with zero Azure costs.

**Step 3:** (Optional) Skip Azure integration tests in CI/CD

```bash
export SKIP_AZURE_TESTS=1
pytest
```

### Migrating from SQLite to Azure (for Production)

**Step 1:** Create Azure AI Search service

1. Log into Azure Portal
2. Create Azure AI Search resource
3. Note endpoint and API key
4. Create index with schema above

**Step 2:** Update environment variables

```bash
export VECTOR_STORE_TYPE=azure_search
export AZURE_AI_SEARCH_ENDPOINT=https://your-service.search.windows.net
export AZURE_AI_SEARCH_API_KEY=your-api-key
export AZURE_AI_SEARCH_INDEX_NAME=your-index-name
```

**Step 3:** Populate index with data

```python
from src.utils.store_factory import create_vector_store

store = create_vector_store()  # Uses Azure based on env vars
await store.upsert(your_records)
```

## Testing

### Running Tests with Different Stores

**SQLite only (fast, default):**
```bash
pytest
# or explicitly
pytest -k "SQLite"
```

**Azure only (requires credentials):**
```bash
export AZURE_AI_SEARCH_ENDPOINT=...
export AZURE_AI_SEARCH_API_KEY=...
export AZURE_AI_SEARCH_INDEX_NAME=...
pytest -k "Azure"
```

**Both (parametrized tests):**
```bash
pytest tests/agent/test_search_plugin.py -v
# Output shows: test_name[SQLite] PASSED, test_name[Azure] PASSED
```

**Skip Azure tests entirely:**
```bash
export SKIP_AZURE_TESTS=1
pytest
```

### Parametrized Test Fixture

Tests using the `parametrized_search_store` fixture run twice:
1. Once with SQLite (always)
2. Once with Azure (if credentials available)

Example:
```python
@pytest.mark.asyncio
async def test_search(parametrized_search_store):
    # This test runs with both SQLite and Azure
    store = parametrized_search_store

    # Test code works with both stores
    await store.upsert([...])
    results = await store.search("query")
    assert len(results) > 0
```

## Programmatic Usage

### Basic Usage

```python
from src.utils.store_factory import create_vector_store

async def example():
    # Create store (uses environment variables)
    store = create_vector_store()

    try:
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
    finally:
        # Cleanup (SQLite only)
        if hasattr(store, 'close'):
            store.close()
```

### Advanced Usage

```python
from src.utils.store_factory import create_vector_store

async def advanced_example():
    # Override environment variables
    store = create_vector_store(
        store_type='sqlite',
        db_path='/tmp/custom.db'
    )

    try:
        # Search with filters
        results = await store.search(
            query="database migration",
            top_k=10,
            filters={"Team": "Database Team", "Type": "Migration"}
        )

        async for result in results:
            print(f"Found: {result.record.name}")
    finally:
        # Cleanup (SQLite only)
        if hasattr(store, 'close'):
            store.close()
```

## Troubleshooting

### SQLite: "no such table: srm_fts"

**Cause:** Database file exists but table not created

**Solution:**
```python
# Ensure collection exists
await store.ensure_collection_exists()
```

### Azure: "The api-key is invalid"

**Cause:** Incorrect API key or endpoint

**Solution:**
1. Verify credentials in Azure Portal
2. Check environment variables are set correctly
3. Ensure no trailing spaces in values

### Tests: "Azure Search tests skipped"

**Cause:** Azure credentials not configured

**Solution:**
This is expected behavior. Set credentials to run Azure tests:
```bash
export AZURE_AI_SEARCH_ENDPOINT=...
export AZURE_AI_SEARCH_API_KEY=...
export AZURE_AI_SEARCH_INDEX_NAME=...
pytest -k "Azure"
```

### Performance: "SQLite search is slow"

**Cause:** Large database file or complex queries

**Solution:**
1. Use in-memory mode for tests (:memory:)
2. Add indexes if using file-based mode
3. Consider Azure for >10K documents

## FAQ

**Q: Can I use both SQLite and Azure at the same time?**

A: Not simultaneously, but you can switch between them using the `VECTOR_STORE_TYPE` environment variable.

**Q: Will my tests still pass after switching from Azure to SQLite?**

A: Yes! Both stores implement the same interface and use BM25 ranking. Parametrized tests validate both backends.

**Q: Is SQLite fast enough for production?**

A: For small deployments (<1000 users, <10K documents), yes. For larger scale, use Azure AI Search.

**Q: Do I need to migrate data when switching stores?**

A: Not for tests (they create fresh data). For production, you'll need to export from one store and import to the other.

**Q: What happens to my Azure index if I switch to SQLite?**

A: Nothing. The index remains unchanged. You can switch back anytime.

## Support

For issues or questions:
1. Check this documentation
2. Review test files in `tests/agent/`
3. Check implementation in `src/memory/`
4. Open an issue on the project repository

## Version History

- **2025-10-31:** Initial documentation
  - Added SQLite FTS5 support
  - Implemented parametrized tests
  - Made SQLite the default store type
