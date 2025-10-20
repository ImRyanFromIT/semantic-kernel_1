# SRM Archivist Agent - Quick Start Guide

## Overview

The SRM Archivist Agent is an intelligent email monitoring system that automatically processes SRM (Service Request Management) change requests from the Sparky@greatvaluelab.com mailbox. It uses AI to classify emails, extract structured data, and update the Azure AI Search index.

## 🚀 Testing the Live Agent

### Prerequisites
1. **Environment Setup**: Ensure `.env` file contains all required variables (see `env.example`)
2. **Azure AD Configuration**: Complete Graph API setup (see `GRAPH_API_SETUP.md`)
3. **Dependencies**: Run `pip install -r requirements.txt`

### Running Tests

**Live Agent (Production Mode):**
```bash
python agent/run_live_agent.py
```

**File-Based Testing (Development):**
```bash
python agent/test_file_agent.py
```

**Graph API Integration Test:**
```bash
python agent/test_graph_integration.py
```

### Test Email Examples
Send emails to Sparky@greatvaluelab.com:

**Valid SRM Request:**
```
Subject: Update Database Server SRM
Body: Please update the owner notes for "Database Server - Primary" 
to reflect that John Smith is now the primary contact.
```

**Out of Scope Request:**
```
Subject: Password Help
Body: Can you help me reset my password?
```

## 🛠️ Utilities

### State Management

**Reset Agent State** (`reset_agent_state.py`)
- **Purpose**: Clears agent state for fresh testing
- **Usage**: `python agent/reset_agent_state.py`
- **What it does**: 
  - Removes `state/agent_state.jsonl` and `state/agent_actions.log`
  - Resets file reader processed files tracking
  - Allows reprocessing of test emails

**Wipe Notes Fields** (`wipe_notes_fields.py`)
- **Purpose**: Cleans up Azure AI Search index after testing
- **Usage**: 
  - Dry run: `python agent/wipe_notes_fields.py`
  - Live wipe: `python agent/wipe_notes_fields.py --confirm`
- **What it does**: 
  - Sets `owner_notes` and `hidden_notes` fields to null
  - Processes documents in batches
  - Shows preview before making changes

### Testing Utilities

**File Email Reader** (`utils/file_email_reader.py`)
- **Purpose**: Simulates email processing using local files
- **Usage**: Place test emails in `test_emails/Inbox/`
- **What it does**: Reads `.txt` files as mock emails for development

**Graph Client** (`utils/graph_client.py`)
- **Purpose**: Microsoft Graph API wrapper for email operations
- **What it does**: Handles authentication, email fetching, and sending

**State Manager** (`utils/state_manager.py`)
- **Purpose**: Manages JSONL state file operations
- **What it does**: Atomic reads/writes, backup/recovery, state tracking

## 🔄 Process Overview

### What the Agent Does

The agent runs a continuous monitoring loop every 10 seconds:

1. **Email Intake Process**:
   - Fetches new emails from Sparky@greatvaluelab.com
   - Applies mass email guardrail (halts if >20 emails)
   - Classifies emails using AI: `help`, `dont_help`, or `escalate`
   - Routes emails to appropriate handlers

2. **SRM Help Process** (for `help` emails):
   - **Extract**: Parse email content to extract SRM details
   - **Search**: Find matching SRM in Azure AI Search index
   - **Update**: Apply changes to the SRM record
   - **Notify**: Send confirmation email to requester

3. **Response Handling**:
   - **Help**: Processes SRM updates and sends confirmation
   - **Don't Help**: Sends polite rejection with explanation
   - **Escalate**: Forwards to radmin@greatvaluelab.com with context

### Key Features

- **State Persistence**: Tracks all processed emails in `state/agent_state.jsonl`
- **Error Recovery**: Escalates failed requests to human support
- **Safety Guardrails**: Prevents mass email responses
- **Retry Logic**: Handles API failures gracefully
- **Comprehensive Logging**: All actions logged to `state/agent_actions.log`

### Email Classification Examples

| Classification | Example | Action |
|---------------|---------|---------|
| `help` | "Update owner notes for Database Server SRM" | Process SRM update |
| `dont_help` | "Can you help me with my password?" | Send polite rejection |
| `escalate` | Ambiguous or complex requests | Forward to support team |

## 📊 Monitoring

**Logs**: Check `state/agent_actions.log` for real-time activity
**State**: Review `state/agent_state.jsonl` for processing history
**Health Check**: Agent logs startup validation and configuration

## 🛑 Stopping the Agent

Press `Ctrl+C` to gracefully stop the agent. It will:
1. Finish processing current email
2. Save state
3. Close connections
4. Exit cleanly

## 🔧 Troubleshooting

**Agent won't start**: Check environment variables and Graph API permissions
**No emails processed**: Verify mailbox access and check state file for duplicates
**Updates not working**: Confirm Azure AI Search credentials and index schema

For detailed troubleshooting, see `RUNNING_LIVE_AGENT.md`.
