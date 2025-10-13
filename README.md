# AI Concierge - SRM Discovery Chatbot

An AI chatbot built with Semantic Kernel that helps users find the right Service Request Model (SRM) for service needs. The system uses semantic search with vector embeddings and a process-based workflow to analyze queries, retrieve relevant information, and provide confident recommendations.

## Architecture

Process flow with 4 main steps:

User Query → ClarityStep → RetrievalStep → RerankStep → AnswerStep → Response
              ↓
         (if unclear)
         Clarification Question

**ClarityStep**: Analyzes queries and determines if clarification is needed  
**RetrievalStep**: Performs vector search to find candidate SRMs  
**RerankStep**: Scores and selects the best recommendations  
**AnswerStep**: Formats the final response with SRM details

## Installation

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp env.example .env

Edit `.env` with your Azure OpenAI credentials:

AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-5-chat
AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-small

## Usage

### Interactive Mode

python main.py

Example conversation:

You: I need to add storage to a file share

[*] Searching...

[+] Generated query embedding for hybrid search
Assistant:
## Recommended SRM: Enterprise File Share Provisioning

**Category:** Services

**Use Case:** Provision new SMB or NFS file share for team or project use. Includes capacity planning, access control configuration, and integration with existing storage infrastructure. Typical turnaround: 2-3 business days.

**Owning Team:** Data Storage Team

**URL:** https://portal.company.com/srm/file-share-provisioning

### Alternative Options:

1. **File Share Quota Expansion** (Services) - Increase storage capacity for existing file shares to accommodate growth. Includes impact analysis, approval routing, and capacity verification. Emergency expansions available for critical systems.
   **URL:** https://portal.company.com/srm/quota-expansion
2. **Storage Decommission and Data Migration** (Services) - Safely retire storage volumes and migrate data to new infrastructure. Includes data validation, cutover planning, and rollback procedures to ensure zero data loss during transitions.
   **URL:** https://portal.company.com/srm/storage-decommission


*If this doesn't match your need, please provide more details and I'll search again.*

### Test Mode

python main.py --test

## Project Structure

- `main.py` - CLI entry point
- `src/processes/` - Process and steps (Clarity, Retrieval, Rerank, Answer)
- `src/memory/` - Vector store implementations
- `src/plugins/` - LLM prompt plugins
- `data/srm_index.csv` - SRM catalog

### Example Query

You: We need to expand resources on a VM

[*] Searching...

[+] Generated query embedding for hybrid search
Assistant:
## Recommended SRM: Virtualization Architecture Consultation

**Category:** Consultation

**Use Case:** Expert advice on VM design, resource planning, and hypervisor selection. Includes capacity modeling, high availability design, and migration strategies from physical to virtual infrastructure.

**Owning Team:** Virtualization Team

**URL:** https://portal.company.com/srm/virtualization-consulting

### Alternative Options:

1. **VM Resource Modification** (Services) - Increase or decrease vCPU, memory, or disk resources for existing VMs. Includes change approval workflow, scheduling options, and post-change validation to ensure optimal performance.
   **URL:** https://portal.company.com/srm/vm-resource-change
2. **VM Snapshot Management** (Services) - Create, restore, or delete VM snapshots for change control or testing purposes. Includes snapshot consolidation and cleanup 
to prevent storage bloat and performance degradation.
   **URL:** https://portal.company.com/srm/vm-snapshot-management

---
*If this doesn't match your need, please provide more details and I'll search again.*