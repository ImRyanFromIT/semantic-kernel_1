# AI Concierge

An AI chatbot built with Semantic Kernel that helps users find relevant information and 
recommendations. The system uses semantic search with vector embeddings and a process-based workflow 
to analyze queries, retrieve relevant information, and provide confident recommendations.

## Features

- **Input validation** with guardrails for security and quality
- **Query clarification** to handle ambiguous requests
- **Dual storage backends**: Azure AI Search (BM25 text) or in-memory vector store
- **Semantic reranking** for better recommendation quality
- **Telemetry logging** for monitoring and debugging
- **Web and CLI interfaces** for flexible access

## Architecture

Process flow with 5 main steps:

```
User Query → ValidationStep → ClarityStep → RetrievalStep → RerankStep → AnswerStep → Response
                                   ↓
                              (if unclear)
                          Clarification Question
```

**ValidationStep**: Validates input against guardrails (length, patterns, content)  
**ClarityStep**: Analyzes queries and determines if clarification is needed  
**RetrievalStep**: Performs search to find candidate SRMs  
**RerankStep**: Uses LLM to semantically score and select best recommendations  
**AnswerStep**: Formats the final response with SRM details and alternatives

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp env.example .env
```

Edit `.env` with your Azure OpenAI credentials:

```
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-5-chat
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-small

# Vector Store Configuration
# Options: "azure_search" (BM25 text search) or "in_memory" (vector embeddings)
VECTOR_STORE_TYPE=azure_search

# Azure AI Search Configuration (if using azure_search)
AZURE_AI_SEARCH_ENDPOINT=your_search_endpoint
AZURE_AI_SEARCH_API_KEY=your_search_key
AZURE_AI_SEARCH_INDEX_NAME=search-semantics
```

## Usage

### Web Interface (Recommended)

Start the FastAPI web server:

```bash
python app.py
```

Or using uvicorn directly:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Then open your browser to: http://localhost:8000

The web interface provides a modern chat experience for interacting with the AI Concierge.

### CLI Interactive Mode

```bash
python main.py
```

### Test Mode

```bash
python main.py --test

## Project Structure

- `app.py` - FastAPI web interface entry point
- `main.py` - CLI entry point
- `web/` - Web interface files (HTML, CSS, JavaScript)
- `src/processes/` - Process and steps (Validation, Clarity, Retrieval, Rerank, Answer)
- `src/memory/` - Vector store implementations (Azure AI Search, in-memory)
- `src/plugins/` - LLM prompt plugins
- `src/utils/` - Utilities (kernel, telemetry, store factory)
- `data/` - Data catalog files

### Example Query

You: I need to expand storage on a file share

[*] Searching...

Assistant:
## Recommended SRM: Storage Expansion - SAN/NAS/File Share

**Category:** Services

**Use Case:** Expand existing storage infrastructure including SAN arrays, NAS systems, and file share volumes. Includes capacity addition through disk shelf expansion, LUN provisioning, volume extension, and file system growth with zero downtime. Ensures proper zoning, masking, and integration with existing storage architecture.

**Owning Team:** Data Storage Team

**URL:** https://portal.company.com/srm/storage-expansion

### Alternative Options:

1. **Storage Capacity Planning** (Consultation) - Analyze current and projected storage usage to capacity plans that align with business growth. Includes trend analysis, forecasting models, expansion of existing resources, and procurement recommendations.
   **URL:** https://portal.company.com/srm/storage-capacity-planning
2. **Storage Performance Analysis** (Support) - Investigate storage performance issues including latency, throughput, and IOPS bottlenecks. Provides detailed analysis with recommendations for optimization and remediation strategies.
   **URL:** https://portal.company.com/srm/storage-performance-analysis

---
*If this doesn't match your need, please provide more details and I'll search again.*