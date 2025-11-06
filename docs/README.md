# SRM Intelligence System

AI-powered Service Request Management (SRM) coordination demonstrating semantic search and LLM orchestration patterns in a realistic enterprise operations context. Built for exploration and inspection rather than production scale.

## Two Systems

### 🤖 SRM Recommendation Chatbot
**When to use**: Real-time request routing, cross-team coordination
**Who uses it**: Engineering, Operations, and Support teams triaging incoming requests

Natural language interface that matches requests to relevant SRMs from your catalog. Helps teams coordinate across organizational silos without manual catalog searches.

→ [Learn more about the Chatbot](CHATBOT.md)

### 🛠️ CLI Concierge Agent
**When to use**: Bulk maintenance, SRM catalog management
**Who uses it**: Platform teams managing SRM infrastructure

Conversational CLI for catalog operations: migrations, quality audits, bulk updates. Handles administrative tasks that would be tedious through the chatbot interface.

→ [Learn more about the CLI](CLI_CONCIERGE.md)

## Quick Start

1. **Configure Azure OpenAI endpoints** → [SETUP.md](SETUP.md)
2. **Explore chatbot scenarios** → [CHATBOT.md](CHATBOT.md)
3. **Run CLI operations** → [CLI_CONCIERGE.md](CLI_CONCIERGE.md)
4. **Understand architecture** → [ARCHITECTURE.md](ARCHITECTURE.md)

## Tech Stack

- **Vector Store**: In-memory (inspectable, simple)
- **LLM**: Azure OpenAI (gpt-5-chat + text-embedding-3-small)
- **Framework**: Semantic Kernel (Python)

## What This Demonstrates

This codebase showcases practical AI patterns for enterprise coordination:

- **Retrieval Augmented Generation (RAG)**: Vector search retrieves relevant SRMs, LLM generates recommendations grounded in catalog context
- **Semantic Search**: Natural language query matching that captures intent beyond keyword searches
- **Agent Orchestration**: LLM-driven planning with plugin-based tools

The architecture prioritizes readability—you can trace any query from entry point to completion without navigating distributed services.
