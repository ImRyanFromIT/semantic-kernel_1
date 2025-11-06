---
document_type: documentation_index
topic: semantic_kernel_reference_index
framework: semantic_kernel
language: python
version: 1.0
last_updated: 2025-10-26
purpose: Navigation guide for AI coding agents working with Semantic Kernel
---

# Semantic Kernel Python - Documentation Index

## Overview

This documentation collection provides comprehensive technical references for building applications with Semantic Kernel Python. All documents are optimized for AI agent consumption with clear patterns, code examples, and best practices.

**Target Version**: Semantic Kernel Python 1.27.0+

---

## Quick Reference Table

| Document | Topics Covered | When to Reference |
|----------|---------------|-------------------|
| **kernel-basics.md** | Kernel initialization, services, plugins, invocation patterns | Starting any SK project, configuring kernel, basic operations |
| **semantic_kernel_plugins.md** | Native functions, semantic functions, plugin patterns, function calling | Creating custom functionality, adding tools to agents |
| **semantic_kernel_agents.md** | ChatCompletionAgent, conversation management, multi-agent orchestration | Building conversational AI, agent workflows, human-in-loop |
| **managing_chat_histories.md** | ChatHistory, persistence, reduction strategies, context management | Managing conversation state, memory optimization, database storage |
| **semantic_kernel_search.md** | Azure AI Search, vector search, hybrid search, RAG patterns | Implementing search functionality, building RAG systems |
| **semantic_kernel_processes.md** | KernelProcess, event-driven workflows, state management, steps | Building complex workflows, step-based automation, process orchestration |
| **semantic_kernel_auto-function.md** | Auto function calling, FunctionChoiceBehavior, tool use, streaming | Enabling agents to use tools, configuring function calling behavior |

---

## Document Summaries

### 1. kernel-basics.md

**Purpose**: Core fundamentals of Semantic Kernel - essential reading for all SK projects

**Key Concepts**:
- Kernel lifecycle management (singleton pattern)
- Service registration (Azure OpenAI, OpenAI)
- Plugin creation and registration
- Invocation patterns (`invoke_prompt()` vs `invoke()`)
- Execution settings configuration
- Application integration patterns (FastAPI, dependency injection)

**Start Here When**:
- Beginning a new Semantic Kernel project
- Setting up kernel infrastructure
- Understanding core architecture
- Troubleshooting kernel-related issues

**Critical Rules**:
- ONE kernel per application
- Register services/plugins at startup
- Never dispose kernel during runtime
- Everything is async
- Use `invoke_prompt()` for AI, `invoke()` for plugin functions

---

### 2. semantic_kernel_plugins.md

**Purpose**: Creating and managing plugins and functions for extending kernel capabilities

**Key Concepts**:
- Native function patterns with `@kernel_function` decorator
- Semantic (prompt-based) functions
- Auto-injected parameters (kernel, arguments, service)
- Plugin loading strategies (directory, class, YAML)
- Function invocation patterns
- Testing strategies

**Start Here When**:
- Adding custom functionality to agents
- Creating reusable tools
- Implementing business logic as plugins
- Enabling function calling for agents

**Best Practices**:
- Use `Annotated` for parameter descriptions
- Leverage auto-injection for kernel access
- Keep functions stateless when possible
- Use PascalCase for plugin names

---

### 3. semantic_kernel_agents.md

**Purpose**: Building conversational AI agents with ChatCompletionAgent

**Key Concepts**:
- Agent fundamentals (service-based vs kernel-based)
- Conversation management with threads (ChatHistoryAgentThread)
- Streaming vs non-streaming responses
- Multi-agent orchestration (handoffs, group chat)
- Human-in-the-loop patterns
- Structured outputs with Pydantic
- Error handling and resilience

**Start Here When**:
- Building chatbots or conversational interfaces
- Implementing multi-agent systems
- Adding human escalation workflows
- Designing agent architectures

**Architecture Patterns**:
- Single Agent with Plugins - Simple Q&A
- Handoff Orchestration - Specialized domain routing
- Group Chat - Collaborative decision-making

---

### 4. managing_chat_histories.md

**Purpose**: Managing conversation context, persistence, and memory optimization

**Key Concepts**:
- ChatHistory creation and message management
- Persistence strategies (file-based, Azure CosmosDB)
- Reduction strategies (truncation, summarization)
- Token limit management
- Performance and security considerations
- Testing strategies

**Start Here When**:
- Managing conversation state across sessions
- Implementing chat history persistence
- Optimizing token usage for long conversations
- Building multi-user chat applications

**Common Patterns**:
- File-based persistence for prototyping
- CosmosDB for production multi-user apps
- Auto-reduce for automatic token management
- Summarization for context-aware reduction

---

### 5. semantic_kernel_search.md

**Purpose**: Integrating Azure AI Search for vector and hybrid search capabilities

**Key Concepts**:
- Vector search with embeddings
- Hybrid search (keyword + semantic)
- CRUD operations on search indexes
- Agent integration with search plugins
- RAG (Retrieval-Augmented Generation) patterns
- Data models with `@vectorstoremodel`
- Filtering and performance optimization

**Start Here When**:
- Building RAG applications
- Implementing semantic search
- Creating knowledge bases for agents
- Adding document retrieval to workflows

**Search Types**:
- `SearchType.VECTOR` - Pure semantic similarity
- `SearchType.KEYWORD_HYBRID` - Combined keyword + semantic

---

### 6. semantic_kernel_processes.md

**Purpose**: Building complex event-driven workflows with KernelProcess

**Key Concepts**:
- Process, Steps, Events, State (4 core concepts)
- Event-driven execution model
- Stateful vs stateless steps
- Process composition with subprocesses
- Domain models with enums
- Common step implementation patterns
- Error handling and retry logic

**Start Here When**:
- Building multi-step workflows
- Implementing business process automation
- Creating reusable process components
- Handling complex state management

**Step Patterns**:
- Stateless Processing - Simple transformations
- Stateful with Self-Repair - Maintenance logic
- Resource Inventory - Tracking consumables
- Conditional Router - Dynamic dispatch

---

### 7. semantic_kernel_auto-function.md

**Purpose**: Configuring automatic function calling for AI agents

**Key Concepts**:
- FunctionChoiceBehavior modes (Auto, Required, None)
- Auto-invoke vs manual execution
- Function filtering (plugins, functions)
- Parallel function execution
- Streaming with function calls
- Configuration patterns (inline, YAML, JSON)
- Error handling and termination

**Start Here When**:
- Enabling agents to use tools autonomously
- Configuring which functions agents can access
- Implementing custom function execution logic
- Optimizing function calling performance

**Modes**:
- `Auto()` - Model decides when to call functions
- `Required()` - Force specific function calls
- `None()` - Disable function calling

---

## Common Scenarios → Document Map

### Starting a New Project
1. **kernel-basics.md** - Set up kernel, services, and plugins
2. **semantic_kernel_plugins.md** - Create custom functionality
3. **semantic_kernel_agents.md** - Build agent interface (if needed)

### Building a Chatbot
1. **kernel-basics.md** - Initialize kernel and services
2. **semantic_kernel_agents.md** - Create ChatCompletionAgent
3. **managing_chat_histories.md** - Manage conversation state
4. **semantic_kernel_auto-function.md** - Enable tool use

### Implementing RAG
1. **semantic_kernel_search.md** - Set up Azure AI Search
2. **semantic_kernel_plugins.md** - Create search plugin
3. **semantic_kernel_agents.md** - Integrate with agent

### Building Complex Workflows
1. **kernel-basics.md** - Set up kernel infrastructure
2. **semantic_kernel_processes.md** - Design process workflows
3. **semantic_kernel_plugins.md** - Create step functions

### Multi-Agent Systems
1. **kernel-basics.md** - Initialize shared kernel
2. **semantic_kernel_agents.md** - Set up orchestration patterns
3. **semantic_kernel_plugins.md** - Create shared plugins
4. **managing_chat_histories.md** - Manage agent conversations

---

## Topic Index

### A-C
- **Agents** → semantic_kernel_agents.md
- **Auto Function Calling** → semantic_kernel_auto-function.md
- **Azure AI Search** → semantic_kernel_search.md
- **Azure OpenAI** → kernel-basics.md
- **ChatCompletion** → kernel-basics.md, semantic_kernel_agents.md
- **ChatHistory** → managing_chat_histories.md
- **Configuration** → kernel-basics.md, semantic_kernel_auto-function.md
- **CosmosDB** → managing_chat_histories.md

### D-F
- **Database Storage** → managing_chat_histories.md
- **Error Handling** → All documents (see specific sections)
- **Events** → semantic_kernel_processes.md
- **Execution Settings** → kernel-basics.md, semantic_kernel_auto-function.md
- **FastAPI Integration** → kernel-basics.md
- **Function Calling** → semantic_kernel_plugins.md, semantic_kernel_auto-function.md
- **FunctionChoiceBehavior** → semantic_kernel_auto-function.md

### G-P
- **Group Chat** → semantic_kernel_agents.md
- **Handoff Orchestration** → semantic_kernel_agents.md
- **Human-in-the-Loop** → semantic_kernel_agents.md
- **Hybrid Search** → semantic_kernel_search.md
- **Kernel** → kernel-basics.md
- **KernelProcess** → semantic_kernel_processes.md
- **Multi-Agent** → semantic_kernel_agents.md
- **Native Functions** → semantic_kernel_plugins.md
- **Persistence** → managing_chat_histories.md
- **Plugins** → semantic_kernel_plugins.md

### R-Z
- **RAG** → semantic_kernel_search.md
- **Reduction** → managing_chat_histories.md
- **Search** → semantic_kernel_search.md
- **Semantic Functions** → semantic_kernel_plugins.md
- **Services** → kernel-basics.md
- **State Management** → semantic_kernel_processes.md
- **Streaming** → semantic_kernel_agents.md, semantic_kernel_auto-function.md
- **Threads** → semantic_kernel_agents.md
- **Vector Search** → semantic_kernel_search.md
- **Workflows** → semantic_kernel_processes.md

---

## Best Practices Across All Documents

### Architecture
- ✓ One kernel per application (singleton pattern)
- ✓ Register services and plugins at startup
- ✓ Use dependency injection for kernel access
- ✓ Separate domain models from implementation
- ✓ Design for testability

### Code Quality
- ✓ Always use async/await
- ✓ Use type hints with Annotated
- ✓ Write descriptive function descriptions
- ✓ Implement comprehensive error handling
- ✓ Use environment variables for credentials

### Performance
- ✓ Batch operations when possible
- ✓ Use async context managers for cleanup
- ✓ Implement token reduction strategies
- ✓ Optimize database queries and indexing
- ✓ Use parallel execution for independent operations

### Security
- ✓ Never hardcode credentials
- ✓ Use managed identities when available
- ✓ Validate and sanitize inputs
- ✓ Implement access controls
- ✓ Encrypt sensitive data at rest

---

## Quick Lookup: When to Use Each Document

| Question | Document |
|----------|----------|
| How do I create a kernel? | kernel-basics.md |
| How do I add plugins? | semantic_kernel_plugins.md |
| How do I build an agent? | semantic_kernel_agents.md |
| How do I manage conversation history? | managing_chat_histories.md |
| How do I implement search? | semantic_kernel_search.md |
| How do I build workflows? | semantic_kernel_processes.md |
| How do I enable function calling? | semantic_kernel_auto-function.md |
| How do I configure execution settings? | kernel-basics.md, semantic_kernel_auto-function.md |
| How do I handle multi-agent orchestration? | semantic_kernel_agents.md |
| How do I persist chat history? | managing_chat_histories.md |
| How do I build RAG applications? | semantic_kernel_search.md |
| How do I create custom functions? | semantic_kernel_plugins.md |
| How do I manage state? | semantic_kernel_processes.md |
| How do I optimize token usage? | managing_chat_histories.md |
| How do I filter available functions? | semantic_kernel_auto-function.md |

---

## Document Relationships

```
kernel-basics.md (Foundation)
    ├─ semantic_kernel_plugins.md (Extensions)
    │  └─ semantic_kernel_auto-function.md (Tool Use)
    ├─ semantic_kernel_agents.md (Conversational AI)
    │  ├─ managing_chat_histories.md (State)
    │  └─ semantic_kernel_search.md (Knowledge)
    └─ semantic_kernel_processes.md (Workflows)
```

**Reading Path**:
1. Start with **kernel-basics.md** for fundamentals
2. Add **semantic_kernel_plugins.md** for functionality
3. Choose based on use case:
   - Conversational AI → **semantic_kernel_agents.md** + **managing_chat_histories.md**
   - Search/RAG → **semantic_kernel_search.md**
   - Workflows → **semantic_kernel_processes.md**
4. Enable tool use with **semantic_kernel_auto-function.md**

---

## Getting Help

Each document includes:
- ✓ Complete working code examples
- ✓ Common pitfalls and solutions
- ✓ Best practices sections
- ✓ Troubleshooting guides
- ✓ Quick reference tables

**When coding with Semantic Kernel**:
1. Identify your use case in this index
2. Reference the recommended documents
3. Follow the patterns and examples provided
4. Adapt code templates to your specific needs

---

**Index Version**: 1.0  
**Last Updated**: 2025-10-26  
**Collection Status**: Complete (7/7 documents)
