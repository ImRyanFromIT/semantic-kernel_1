# Concierge Connectors - AI Service Management System

An AI-powered service management system built with Microsoft Semantic Kernel that helps users discover the right Service Request (SRM) for their needs and provides intelligent hostname lookups. The system combines semantic search, process-based workflows, and email monitoring to deliver accurate recommendations and automated service catalog management.

## Features

**SRM Discovery Agent**
- Natural language query understanding with input validation and guardrails
- Intelligent query clarification for ambiguous requests
- Dual storage backends: Azure AI Search (BM25) or in-memory vector embeddings
- Semantic reranking using LLM for improved recommendation quality
- User feedback collection and processing for continuous improvement
- Multi-language support (English, Spanish)

**Hostname Lookup Agent**
- Quick hostname information retrieval from Azure AI Search
- Application and team ownership details
- Integration with existing infrastructure databases

**Email Monitoring Agent (SRM Archivist)**
- Continuous email inbox monitoring for SRM change requests
- Multi-turn conversational clarification for incomplete requests
- Automated Azure AI Search index updates
- Conflict detection and resolution
- State persistence with JSONL storage
- Support team notification system

## Architecture

The system uses Microsoft Semantic Kernel's process framework to implement multi-step and auto function calling workflows:

### SRM Discovery Process Flow

```
User Query → ValidationStep → ClarityStep → RetrievalStep → RerankStep → AnswerStep → Response
                                   ↓
                              (if unclear)
                          Clarification Question
```

- **ValidationStep**: Validates input against guardrails (length, patterns, content)
- **ClarityStep**: Analyzes queries and determines if clarification is needed
- **RetrievalStep**: Performs search to find candidate SRMs using BM25 or vector search
- **RerankStep**: Uses LLM to semantically score and select the best recommendation
- **AnswerStep**: Formats the final response with SRM details and alternatives

### Email Monitoring Process Flow

```
Email Inbox → EmailIntakeProcess → Classification → Extraction → Search → Update Index
                                         ↓
                                    (if incomplete)
                                  Request Clarification
```

The email agent monitors an inbox, classifies incoming emails, extracts change requests, searches for existing SRMs, and updates the search index automatically.

## Requirements

- Python 3.10 or higher
- Azure OpenAI account with deployments for:
  - Chat completion model (e.g., GPT-4)
  - Text embedding model (e.g., text-embedding-3-small)
- Azure AI Search service (for production use)
- Microsoft Graph API access (for email monitoring features)

## Installation

Clone the repository and install dependencies:

```bash
git clone <repository-url>
cd semantic-kernel_1

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Configuration

### 1. Environment Variables

Copy the example environment file and configure your credentials:

```bash
cp env.example .env
```

Edit `.env` with your configuration:

```bash
# Azure OpenAI Configuration
GLOBAL_LLM_SERVICE="AzureOpenAI"
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME="gpt-4"
AZURE_OPENAI_TEXT_DEPLOYMENT_NAME="gpt-4o"
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME="text-embedding-3-small"
AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/"
AZURE_OPENAI_API_KEY="your-api-key"

# Vector Store Configuration
# Options: "azure_search" (BM25 text search) or "in_memory" (vector embeddings)
VECTOR_STORE_TYPE="azure_search"

# Azure AI Search Configuration (required for azure_search mode)
AZURE_AI_SEARCH_ENDPOINT="https://your-search-service.search.windows.net"
AZURE_AI_SEARCH_API_KEY="your-search-api-key"
AZURE_AI_SEARCH_INDEX_NAME="search-semantics"

# Azure AI Search - Hostname Lookup Indexes
AZURE_AI_SEARCH_APP_MACHINES_INDEX="search-app-machines2"
AZURE_AI_SEARCH_APP_TEAM_INDEX="search-app-team-index2"

# Microsoft Graph API Configuration (for Email Monitoring Agent)
TENANT_ID="your-tenant-id"
CLIENT_ID="your-client-id"
CLIENT_SECRET="your-client-secret"
MAILBOX_EMAIL="srm-updates@your-domain.com"
SUPPORT_TEAM_EMAIL="support@your-domain.com"
```

### 2. Agent Configuration (Optional)

For the email monitoring agent, configure `config/agent_config.yaml`:

```yaml
agent_name: SRM_Archivist_Agent
description: Monitors email inbox for SRM change requests
state_file: src/state/agent_state.jsonl
log_file: logs/agent_actions.log
mock_updates: false  # Set to true for testing without updating the index

configuration:
  email_scan_interval_seconds: 10
  confidence_threshold_for_classification: 70
  stale_item_hours: 48
  clarification_wait_hours: 48
```

### 3. Data Setup

For in-memory vector store mode, ensure your SRM catalog is available:

```bash
# Place your SRM catalog at:
data/srm_catalog.csv
```

The CSV should contain columns: `srm_metadata`, `owning_team`, `use_case`

For Azure AI Search mode, ensure your indexes are populated with SRM data.

## Usage

### Web Interface (Recommended)

Start the web service for interactive SRM discovery:

```bash
python run_chatbot.py
```

Or with custom host/port:

```bash
python run_chatbot.py --host 0.0.0.0 --port 8000
```

Access the web interface at: **http://localhost:8000**

The web interface provides:
- Natural language query input
- Hostname lookup with prefix (e.g., "lookup: server-name")
- User feedback collection
- Multi-language support
- Dark/light theme toggle

### Email Monitoring Agent

Start the email monitoring service:

```bash
python run_email_agent.py
```

With custom configuration:

```bash
python run_email_agent.py --config config/agent_config.yaml
```

Test mode (uses file-based email reader):

```bash
python run_email_agent.py --test
```

The agent will:
- Continuously monitor the configured mailbox
- Process SRM change requests from emails
- Send clarification emails for incomplete requests
- Update the Azure AI Search index automatically
- Log all actions to the configured log file

### Reset Agent State

If you need to reset the email agent's state:

```bash
python reset_agent_state.py
```

This clears the JSONL state file while preserving conversation history for active threads.

## API Endpoints

The web service exposes the following REST API endpoints:

### SRM Discovery

```bash
POST /api/query
Content-Type: application/json

{
  "query": "I need to restore a backup from yesterday"
}
```

### Hostname Lookup

```bash
POST /api/hostname
Content-Type: application/json

{
  "hostname": "srv-web-001-prod"
}
```

### User Feedback

```bash
POST /api/feedback
Content-Type: application/json

{
  "session_id": "abc123",
  "incorrect_srm_id": "srm-001",
  "correct_srm_id": "srm-002",
  "feedback_text": "This SRM is more appropriate",
  "feedback_type": "correction"
}
```

### Health Check

```bash
GET /health
```

API documentation is available at: **http://localhost:8000/docs**

## Project Structure

```
.
├── run_chatbot.py           # Web service entry point
├── run_email_agent.py       # Email monitoring agent entry point
├── reset_agent_state.py     # State management utility
├── requirements.txt         # Python dependencies
├── config/
│   └── agent_config.yaml   # Agent configuration
├── data/
│   └── srm_catalog.csv     # SRM data (for in-memory mode)
├── web/                    # Web interface files
│   ├── index.html
│   ├── script.js
│   └── style.css
├── src/
│   ├── processes/          # Process definitions
│   │   ├── discovery/     # SRM discovery and hostname lookup
│   │   └── agent/         # Email monitoring workflows
│   ├── plugins/           # LLM prompt plugins
│   │   └── agent/        # Email agent plugins
│   ├── memory/            # Vector store implementations
│   ├── models/            # Data models
│   ├── utils/             # Utilities and helpers
│   └── data/              # Data loading utilities
├── tests/                 # Unit and integration tests
└── logs/                  # Application logs
```

## Example Queries

**SRM Discovery:**
- "I need to expand storage on a file share"
- "How do I restore a VM snapshot?"
- "Create a new backup job for my server"

**Hostname Lookup:**
- "lookup: srv-vmcap-001-prod"
- "hostname: web-app-server-01"

The system will:
1. Validate your input
2. Determine if clarification is needed
3. Search for relevant SRMs or hostname info
4. Rank and select the best match
5. Present a formatted response with alternatives

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_azure_search_config.py -v
```
## Telemetry and Monitoring

The system includes comprehensive telemetry logging:

- Process state transitions
- Search queries and results
- User feedback events
- Email processing events
- Error conditions

Logs are written to:
- Console output (INFO level)
- `logs/email_agent.log` (agent activities)
- `logs/agent_actions.log` (detailed action log)

## Demo

A video demonstration of the system is available showing:
- Natural language SRM discovery
- Query clarification flow
- Hostname lookup functionality
- Email-based SRM updates
- User feedback collection

https://www.youtube.com/watch?v=kT2XtW68z7A

## Contributing

This project uses:
- **Semantic Kernel**: Process orchestration and LLM integration
- **FastAPI**: Web service framework
- **Azure AI Search**: Search and retrieval backend
- **Microsoft Graph**: Email integration
- **Pydantic**: Data validation

## Support

For issues or questions:
- Check the API documentation at `/docs`
- Review the plugin architecture in `PLUGINS_README.md`
- Examine telemetry logs for debugging
- Contact the support team configured in your environment

---

Built with Microsoft Semantic Kernel for Python
