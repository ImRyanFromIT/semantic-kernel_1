# CLI Maintainer Agent - Usage Guide

## Overview

The CLI Maintainer Agent is an interactive REPL-based tool for managing SRM metadata. It uses Semantic Kernel with auto function calling to interact with the chatbot service API.

## Architecture

```
┌─────────────────────┐
│  CLI Maintainer     │
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
│  - Maintainer API   │
│  - Vector Store     │
└─────────────────────┘
```

## Prerequisites

1. **Chatbot service must be running:**
   ```bash
   python run_chatbot.py
   ```

2. **Some SRM data loaded in chatbot:**
   - Chatbot will auto-load from `data/srm_index.csv` on startup

## Starting the CLI Maintainer

```bash
python run_cli_maintainer.py
```

You should see:

```
================================================================================
CLI MAINTAINER AGENT - SRM Metadata Management
================================================================================
[*] Initializing Semantic Kernel...
[+] Kernel initialized
[*] Connecting to chatbot service at http://localhost:8000...
[+] API client plugin loaded
[*] Creating maintainer agent...
[+] Agent created with auto function calling enabled
[+] Chat history initialized
================================================================================
READY
Type your requests or 'quit' to exit
================================================================================

CLI Maintainer>
```

## Usage Examples

### Example 1: Search for an SRM

```
CLI Maintainer> find storage SRMs

[Agent searches and responds]
I found 3 storage-related SRMs:
1. SRM-023: Storage Capacity Expansion
2. SRM-045: File Share Provisioning
3. SRM-089: Backup Storage Request

Which one would you like to work with?
```

### Example 2: View SRM Details

```
CLI Maintainer> show me details for SRM-023

[Agent retrieves and displays]
Here are the details for SRM-023 (Storage Capacity Expansion):
- Category: Storage
- Use Case: Request additional storage capacity
- Owner Notes: Contact storage team for provisioning
- Hidden Notes: (internal notes here)
```

### Example 3: Update Owner Notes

```
CLI Maintainer> update the owner notes for SRM-023 to include SLA information

[Agent responds]
I'll update the owner notes for SRM-023: Storage Capacity Expansion.

Current owner notes:
"Contact storage team for provisioning"

New owner notes will be:
"Contact storage team for provisioning. SLA: 2 business days."

Shall I proceed with this update? (yes/no)

CLI Maintainer> yes

[Agent updates and confirms]
✓ Successfully updated SRM-023.

Changes made:
- owner_notes:
  Before: "Contact storage team for provisioning"
  After: "Contact storage team for provisioning. SLA: 2 business days."
```

### Example 4: Exit

```
CLI Maintainer> quit

Goodbye!
```

## Available Functions

The agent has access to these functions (auto-invoked as needed):

1. **search_srm** - Search for SRMs by keywords
2. **get_srm_by_id** - Get full details of specific SRM
3. **update_srm_metadata** - Update SRM fields (requires confirmation)

## Agent Behavior

The agent follows these patterns:

1. **Search when needed**: If you mention an SRM by name, it will automatically search
2. **Show before updating**: Before any update, it shows current values
3. **Ask for confirmation**: Always confirms before making changes
4. **Show results**: After updates, displays before/after values

## Tips

- Be conversational - the agent understands natural language
- The agent will ask clarifying questions if ambiguous
- Use "quit", "exit", or "q" to exit
- Use Ctrl+C to interrupt (then type "quit" to exit cleanly)

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

## Logs

Logs are written to: `logs/cli_maintainer.log`

Check logs for detailed function call information and errors.

## Development

See:
- `.claude/semantic_kernel_agents.md` - Agent patterns
- `.claude/semantic_kernel_auto-function.md` - Auto function calling
- `.claude/semantic_kernel_plugins.md` - Plugin development
