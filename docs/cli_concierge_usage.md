# CLI Concierge Agent - Usage Guide

## Overview

The CLI Concierge Agent (formerly CLI Maintainer) is an interactive REPL tool for managing SRM metadata through natural language commands. It uses Semantic Kernel with auto function calling to interact with the chatbot service API.

## Features

### 1. Help Command

Get information about available commands and current system state:

```
CLI Concierge> help
```

Shows:
- What the agent can do
- Current SRM counts (permanent + temp)
- Available commands with examples
- Connection status to chatbot service

The help command dynamically displays:
- Total SRMs in permanent index
- Number of temporary SRMs active
- Chatbot service URL

### 2. Search and View

Search for SRMs by keywords:

```
CLI Concierge> show storage SRMs
CLI Concierge> find AI SRMs
CLI Concierge> list all teams
CLI Concierge> list all types
```

View specific SRM details:

```
CLI Concierge> show me SRM-001
CLI Concierge> show details for SRM-023
```

Results are displayed in formatted tables with:
- SRM ID
- Name
- Category
- Use Case Summary

### 3. Update Operations

Update individual SRM metadata:

```
CLI Concierge> update SRM-036 owner notes to Contact storage team first
CLI Concierge> add hidden notes to SRM-036 saying Known issue with Dell arrays
```

The agent will:
1. Search for the SRM by ID or name
2. Display current values
3. Ask for confirmation
4. Show before/after changes

### 4. Batch Operations

Update multiple SRMs matching filter criteria:

```
CLI Concierge> add owner notes to all Database Services SRMs saying Contact DBA first
CLI Concierge> update all Consultation SRMs hidden notes to Requires design review
```

Batch operation workflow:
1. Agent parses filter criteria (team, type)
2. Searches and displays matching SRMs
3. Shows the exact update to be applied
4. Asks "Confirm? (yes/no)"
5. Updates all SRMs after confirmation
6. Displays results with updated IDs

**Limitations:**
- Maximum 20 SRMs per batch for safety
- Supports filtering by team and type
- Requires explicit "yes" confirmation

### 5. Temp SRMs

Create temporary SRMs for testing (not persisted to CSV):

```
CLI Concierge> add temp SRM for cloud cost optimization by FinOps team
```

The agent will guide you through providing:
- Name: Main title
- Category: Services, Consultation, or Support
- Owning team: Team name (can be new team)
- Use case: What the SRM does

List temporary SRMs:

```
CLI Concierge> list temp SRMs
```

Delete temporary SRM:

```
CLI Concierge> delete temp SRM-TEMP-001
```

**Temp SRM Characteristics:**
- Get IDs like SRM-TEMP-001, SRM-TEMP-002
- Appear in search results with [TEMP] marker
- Lost on chatbot restart (not persisted to CSV)
- Stored in-memory only
- Useful for testing before adding to real index

## Running the Agent

### Prerequisites

1. **Chatbot service must be running:**
   ```bash
   python run_chatbot.py
   ```

2. **SRM data should be loaded:**
   - Chatbot auto-loads from `data/srm_index.csv` on startup
   - You should see "Loaded and indexed X SRM records"

### Starting the CLI Concierge

```bash
python run_cli_concierge.py
```

You should see:

```
================================================================================
SRM CONCIERGE AGENT - SRM Metadata Management
================================================================================
[*] Initializing Semantic Kernel...
[+] Kernel initialized
[*] Connecting to chatbot service at http://localhost:8000...
[+] API client plugin loaded
[*] Creating concierge agent...
[+] Agent created with auto function calling enabled
[+] Chat history initialized
================================================================================
READY
Type your requests or 'quit' to exit
================================================================================

CLI Concierge>
```

## Example Interactions

### Example 1: Getting Help

```
CLI Concierge> help

SRM Concierge Agent - Your assistant for managing SRM metadata

WHAT I DO:
I help you search, view, and update SRM (Service Request Model) records.
I can work with individual SRMs or update many at once. I can also create
temporary SRMs for testing without modifying the permanent index.

CURRENT STATE:
• 55 SRMs in permanent index
• 0 temporary SRMs active
• Connected to chatbot at http://localhost:8000

AVAILABLE COMMANDS:
[... full help text ...]
```

### Example 2: Search and Update

```
CLI Concierge> find storage SRMs

I found 3 storage-related SRMs:

| SRM ID | Name | Category | Use Case Summary |
|--------|------|----------|------------------|
| SRM-023 | Storage Capacity Expansion | Services | Request additional storage |
| SRM-045 | File Share Provisioning | Services | Provision new file shares |
| SRM-089 | Backup Storage Request | Services | Request backup storage |

CLI Concierge> update SRM-023 owner notes to include SLA information

I'll update the owner notes for SRM-023: Storage Capacity Expansion.

Current owner notes:
"Contact storage team for provisioning"

New owner notes will be:
"Contact storage team for provisioning. SLA: 2 business days."

Shall I proceed with this update? (yes/no)

CLI Concierge> yes

✓ Successfully updated SRM-023.

Changes made:
- owner_notes:
  Before: "Contact storage team for provisioning"
  After: "Contact storage team for provisioning. SLA: 2 business days."
```

### Example 3: Batch Update

```
CLI Concierge> add owner notes to all Database Services SRMs saying Contact DBA first

I found 5 Database Services SRMs that will be updated:
- SRM-011: Database Access Request
- SRM-012: Database Provisioning
- SRM-013: Database Schema Change
- SRM-014: Database Performance Tuning
- SRM-015: Database Backup Restore

Update to apply:
  owner_notes: "Contact DBA first"

Confirm batch update? (yes/no)

CLI Concierge> yes

✓ Successfully updated 5 SRMs
Updated IDs: SRM-011, SRM-012, SRM-013, SRM-014, SRM-015
```

### Example 4: Creating Temp SRM

```
CLI Concierge> add temp SRM for cloud cost optimization by FinOps team

I'll help you create a temporary SRM. Let me gather the details:

What category is this? (Services/Consultation/Support)
CLI Concierge> Consultation

What's the use case or description?
CLI Concierge> Analyze AWS and Azure spending to identify cost savings opportunities

Creating temporary SRM with:
- Name: Cloud Cost Optimization
- Category: Consultation
- Team: FinOps Team
- Use Case: Analyze AWS and Azure spending to identify cost savings opportunities

Proceed? (yes/no)

CLI Concierge> yes

✓ Created temp SRM: SRM-TEMP-001

This SRM will appear in searches but won't be saved to CSV.
It will be lost when the chatbot restarts.
```

## Available Functions

The agent has access to these functions (auto-invoked as needed):

1. **search_srm** - Search for SRMs by keywords
2. **get_srm_by_id** - Get full details of specific SRM
3. **update_srm_metadata** - Update SRM fields (requires confirmation)
4. **get_stats** - Get system statistics (total SRMs, temp SRMs, status)
5. **batch_update_srms** - Update multiple SRMs matching criteria (requires confirmation)
6. **create_temp_srm** - Create temporary SRM (not persisted)
7. **list_temp_srms** - List all temporary SRMs
8. **delete_temp_srm** - Delete temporary SRM by ID

## Agent Behavior

The agent follows these key patterns:

1. **Search when needed**: If you mention an SRM by name, it will automatically search
2. **Show before updating**: Before any update, it shows current values
3. **Ask for confirmation**: Always confirms before making changes
4. **Show results**: After updates, displays before/after values
5. **Format tables**: Search results are displayed in markdown tables
6. **Mark temp SRMs**: Temporary SRMs show [TEMP] prefix in search results

## Architecture

```
┌─────────────────────┐
│  CLI Concierge      │
│  (REPL Agent)       │
│  - SK Agent         │
│  - Auto Functions   │
│  - API Client Plugin│
└──────────┬──────────┘
           │ HTTP API Calls
           ▼
┌─────────────────────┐
│  Chatbot Service    │
│  (FastAPI)          │
│  - Concierge API    │
│  - Vector Store     │
│  - Temp SRM Storage │
└─────────────────────┘
```

**Key Points:**
- Agent handles natural language understanding and conversation flow
- Chatbot manages all data operations (search, update, temp storage)
- Communication via HTTP API ensures consistent data management
- Temp SRMs are stored in chatbot's in-memory state

## Tips

- Be conversational - the agent understands natural language
- The agent will ask clarifying questions if ambiguous
- Use "quit", "exit", or "q" to exit
- Use Ctrl+C to interrupt (then type "quit" to exit cleanly)
- Type "help" anytime to see available commands
- Batch operations are safer than manual loops
- Use temp SRMs to test before modifying permanent index

## Troubleshooting

### "Failed to initialize"
- **Cause**: Chatbot service not running
- **Fix**: Start chatbot with `python run_chatbot.py`

### "API call failed"
- **Cause**: Network error or chatbot crashed
- **Fix**: Check chatbot logs, restart if needed

### Agent not calling functions
- **Cause**: Request too ambiguous
- **Fix**: Be more specific (mention SRM names or IDs)

### Batch update rejected
- **Cause**: Too many matches (>20 SRMs)
- **Fix**: Use more specific filters or update in smaller batches

### Temp SRM not appearing
- **Cause**: Chatbot restarted
- **Fix**: Temp SRMs are lost on restart - recreate if needed

## Logs

Logs are written to: `logs/cli_concierge.log`

Check logs for:
- Detailed function call information
- API request/response details
- Error stack traces
- Agent decision-making process

## Testing

Run the test suite:

```bash
# All concierge tests
./run_tests.sh tests/cli_concierge/

# Integration tests
./run_tests.sh tests/cli_concierge/test_concierge_workflows.py

# Specific test
./run_tests.sh tests/cli_concierge/test_concierge_workflows.py::test_batch_update_workflow
```

## Development

See:
- `.claude/semantic_kernel_agents.md` - Agent patterns
- `.claude/semantic_kernel_auto-function.md` - Auto function calling
- `.claude/semantic_kernel_plugins.md` - Plugin development
- `docs/CLI_MAINTAINER_GUIDE.md` - Original basic guide
- `docs/CLI_MAINTAINER_MANUAL_TEST.md` - Manual testing procedures

## API Endpoints Used

The CLI Concierge uses these chatbot API endpoints:

- `GET /api/concierge/stats` - Get system statistics
- `POST /api/concierge/search` - Search for SRMs
- `POST /api/concierge/get` - Get SRM by ID
- `POST /api/concierge/update` - Update SRM metadata
- `POST /api/concierge/batch/update` - Batch update SRMs
- `POST /api/concierge/temp/create` - Create temp SRM
- `GET /api/concierge/temp/list` - List temp SRMs
- `POST /api/concierge/temp/delete` - Delete temp SRM

For API documentation, visit: http://localhost:8000/docs (when chatbot is running)
