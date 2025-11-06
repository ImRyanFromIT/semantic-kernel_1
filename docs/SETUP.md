# Setup Guide

## Required Azure OpenAI Endpoints

You need two Azure OpenAI endpoints configured via Azure AI Foundry:

### 1. Chat Completion Endpoint
- **Deployment**: `gpt-5-chat` (or gpt-4/gpt-35-turbo)
- **Used for**: SRM recommendations, agent reasoning, natural language understanding

### 2. Embedding Endpoint
- **Deployment**: `text-embedding-3-small`
- **Used for**: Vector similarity search in SRM catalog

## Configuration

1. **Copy the example environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Configure required settings** in `.env`:
   ```bash
   # Required
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
   AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-5-chat
   AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME=text-embedding-3-small

   # Authentication (choose one)
   AZURE_OPENAI_API_KEY=your-key           # API key auth
   # OR leave empty to use Azure CLI credential

   # Optional
   AZURE_OPENAI_API_VERSION=2024-05-01-preview
   ```

3. **Verify vector store is set to in-memory**:
   ```bash
   VECTOR_STORE_TYPE=in_memory
   ```

## Authentication Options

### Option 1: API Key
Set `AZURE_OPENAI_API_KEY` in your `.env` file with your Azure OpenAI API key.

### Option 2: Azure CLI Credential (Recommended)
Leave `AZURE_OPENAI_API_KEY` empty and authenticate via Azure CLI:
```bash
az login
```

## Verification

Run the chatbot or CLI agent:
- **Success**: You'll see query processing start with embedding generation and search results
- **Failure**: Authentication errors will indicate missing or incorrect endpoint configuration

No separate verification script needed—the applications will fail fast with clear error messages if endpoints aren't configured correctly.

## What You DON'T Need

- ~~Microsoft Graph API~~ (removed with email agent migration)
- ~~Azure AI Search~~ (replaced with in-memory vector store)
- ~~Email/mailbox configuration~~ (no longer email-based)

The setup is intentionally minimal to focus on core AI patterns.
