# SRM Recommendation Chatbot

## Purpose

Routes incoming requests to relevant SRMs by understanding natural language queries and matching against the SRM catalog. Helps teams coordinate across Engineering, Operations, and Support without manual catalog searches.

## Business Scenarios

### Scenario 1: Engineering → Operations Handoff

Engineering team discovers database performance degradation during sprint. Instead of searching Ops SRM catalog manually, engineer asks chatbot: **"database slow queries impacting API response time."**

Chatbot recommends **SRM-OPS-142** (Database Performance Investigation) with correct priority and Ops contact. Engineer files SRM in 30 seconds instead of 15-minute catalog hunt.

### Scenario 2: Support → Engineering Escalation

Support agent receives customer report about failed login attempts. Asks chatbot: **"users can't login, getting timeout errors."**

Chatbot identifies **SRM-ENG-089** (Authentication Service Investigation) and flags related SRMs for session management and load balancer issues. Support creates accurate SRM with engineering context, reducing back-and-forth triage.

### Scenario 3: Cross-Team Infrastructure Coordination

Ops team planning infrastructure upgrade that impacts multiple teams. Queries: **"schedule maintenance window for kubernetes cluster upgrade."**

Chatbot surfaces **SRM-OPS-201** (Planned Infrastructure Maintenance) plus links to Engineering's deployment freeze SRM and Support's customer communication SRM. All three teams coordinate from single query instead of separate conversations.

## How It Works

1. **User submits natural language query**
2. **Query embedded** using Azure OpenAI (text-embedding-3-small)
3. **Vector similarity search** against in-memory SRM catalog
4. **GPT-5 analyzes** top matches and generates recommendation with reasoning
5. **Returns relevant SRM** with context explaining why it matches

The entire flow executes in a single process, making it easy to trace and debug.

## Architecture Evolution

> ### Previous Approach: Email-Based Agent with Azure AI Search
>
> - **Complex**: Email integration required Microsoft Graph API, mailbox permissions, webhook configuration
> - **Costly**: Azure AI Search excellent for production scale, but infrastructure overhead for learning/demo
> - **Opaque**: Distributed search service made query flow harder to trace through system
>
> ### Current Approach: Direct Chatbot with In-Memory Vector Store
>
> - **Simple**: Query → Embed → Search → Recommend flow in single process
> - **Inspectable**: Entire vector search visible in local memory, easy to debug and understand
> - **Focused**: Removed email complexity to highlight core AI patterns (RAG, semantic search, agent orchestration)

The evolution trades production-grade distribution for development-friendly simplicity. For a demonstration codebase, inspectability matters more than scale.

## Running the Chatbot

See the main README for execution instructions and example queries.
