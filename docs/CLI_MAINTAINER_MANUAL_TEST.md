# Manual Testing Steps for CLI Maintainer

## Prerequisites

1. Chatbot running: `python run_chatbot.py`
2. Some SRM data loaded in chatbot

## Test Workflow

### 1. Start CLI
```bash
python run_cli_maintainer.py
```

### 2. Test search
```
> search for storage SRMs
```
**Expected:** Agent calls search_srm, shows results

### 3. Test get details
```
> show me details for SRM-001
```
**Expected:** Agent calls get_srm_by_id, shows current values

### 4. Test update (with confirmation)
```
> update the owner notes for SRM-001 to say "Testing maintainer"
```
**Expected:** Agent asks for confirmation, then calls update_srm_metadata

### 5. Verify update
```
> show me SRM-001 again
```
**Expected:** Shows updated owner_notes

### 6. Exit
```
> quit
```

## Expected Behaviors

- Agent uses search_srm when user mentions SRM by name
- Agent uses get_srm_by_id to show current values before updating
- Agent asks for confirmation before calling update_srm_metadata
- Agent shows before/after changes after update
- Agent streams responses naturally

## Starting the Chatbot Service

In one terminal:
```bash
VECTOR_STORE_TYPE=in_memory python run_chatbot.py --host 127.0.0.1 --port 8000
```

Wait for startup (5-10 seconds), then verify health:
```bash
curl -s http://localhost:8000/api/maintainer/health | python -m json.tool
```

Expected response:
```json
{
  "status": "healthy",
  "service": "maintainer-api",
  "plugin_initialized": true,
  "vector_store_initialized": true,
  "timestamp": "..."
}
```

## Quick Connection Test

Test CLI can connect to chatbot:
```bash
timeout 5 python -c "
import asyncio
from run_cli_maintainer import CLIMaintainerAgent

async def test():
    agent = CLIMaintainerAgent('http://localhost:8000')
    success = await agent.initialize()
    print(f'Connection test: {\"✓ SUCCESS\" if success else \"✗ FAILED\"}')

asyncio.run(test())
" || echo "Connection test completed"
```

## Troubleshooting

**Issue:** CLI can't connect to chatbot
- **Solution:** Verify chatbot is running at http://localhost:8000
- **Check:** `curl http://localhost:8000/health`

**Issue:** Agent doesn't call functions
- **Solution:** Verify auto function calling is enabled
- **Check:** Look for "[+] Agent created with auto function calling enabled" in startup logs

**Issue:** Updates fail
- **Solution:** Verify maintainer API endpoints are working
- **Check:** `curl -X POST http://localhost:8000/api/maintainer/health`
