# CLI Concierge Agent

## Purpose

Maintains SRM catalog infrastructure through conversational CLI. Handles bulk operations, data quality checks, and catalog management that would be tedious through chatbot interface.

## Business Scenarios

### Scenario 1: Department Migration

Platform team migrating Support SRMs from legacy system. CSV contains 200 SRM templates with inconsistent formatting.

CLI agent command: **`import srms from support_migration.csv, normalize categories, validate required fields`**

Agent processes batch, flags 23 SRMs with missing escalation contacts, auto-fixes category naming, imports clean SRMs to catalog. 200 SRMs migrated in 5 minutes versus days of manual cleanup and validation.

### Scenario 2: Catalog Quality Audit

Engineering manager notices teams creating duplicate SRMs across organizational boundaries.

CLI command: **`analyze catalog for duplicates, focus on engineering and ops categories`**

Agent finds 12 near-duplicate SRMs, suggests merges with reasoning: *"SRM-ENG-045 and SRM-OPS-078 both handle API timeout investigations, differ only in assigned team."* Manager reviews suggestions, approves merges, catalog deduplicated in 10-minute session.

### Scenario 3: Bulk Metadata Updates

Company reorganizes: Ops team splits into Platform and Infrastructure teams.

CLI: **`update all SRMs tagged 'ops-team', reassign to 'platform-team' if category contains kubernetes|docker|cloud, else 'infrastructure-team'`**

Agent previews 47 SRMs to update with reasoning, asks confirmation, executes bulk update. Team handoff metadata updated in minutes without manual SRM editing or database queries.

## How It Works

1. **User issues natural language CLI command**
2. **Agent parses intent and parameters** using GPT-5
3. **Loads relevant SRM data** from vector store
4. **Executes operation** (read-only analysis or write operations with confirmation)
5. **Returns structured results** with explanations

The CLI provides conversational access to administrative operations that don't fit the chatbot's single-query pattern.

## Why CLI vs Chatbot?

### 🤖 Chatbot: Real-Time Operations
- "What SRM do I need for database issues?"
- Quick lookup, recommendation, guidance
- Single-query interactions
- Engineering/Ops/Support daily workflows

### 🛠️ CLI Agent: Batch Operations
- "Update all SRMs matching criteria X"
- Data quality, migrations, infrastructure management
- Multi-step administrative tasks
- Platform team maintenance workflows

The CLI handles operations where you need programmatic control, batch processing, or administrative privileges over the catalog.

## Running the CLI

See `docs/cli_concierge_usage.md` for detailed command examples and usage patterns.

## Example Commands

```bash
# View available SRMs
show all temp srms

# Add new SRM
add temp SRM for cloud cost optimization by FinOps team

# Analyze catalog
find duplicate SRMs in engineering category

# Bulk operations
update all SRMs with priority 'high', add tag 'requires-oncall'
```

The agent understands natural language commands and confirms destructive operations before executing.
