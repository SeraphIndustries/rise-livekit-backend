# Quick Reference Guide

## 🚀 Making Outbound Calls

### Option 1: Use the script (easiest)
```bash
uv run python scripts/make_call.py +15105550123
```

### Option 2: Use LiveKit CLI
```bash
lk dispatch create \
    --new-room \
    --agent-name my-telephony-agent \
    --metadata '{"phone_number": "+15105550123"}'
```

### Option 3: From your own Python code
```python
from livekit import api
import json

lkapi = api.LiveKitAPI(url, api_key, api_secret)
await lkapi.agent_dispatch.create_dispatch(
    api.CreateAgentDispatchRequest(
        agent_name="my-telephony-agent",
        room="outbound-12345",
        metadata=json.dumps({"phone_number": "+15105550123"})
    )
)
```

## 🔄 Updating Agent Logic

### 1. Edit the agent
```bash
# Open the agent file
code src/agent.py  # or your preferred editor
```

### 2. Common changes:

**Change personality:**
```python
class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="Your new instructions here...",
        )
```

**Add a tool:**
```python
@function_tool
async def my_tool(self, ctx: RunContext, param: str):
    """Description of what the tool does."""
    logger.info(f"Tool called with: {param}")
    return "Result"
```

**Change voice/models:**
```python
session = AgentSession(
    stt="assemblyai/universal-streaming:en",
    llm="openai/gpt-4.1-mini",
    tts="cartesia/sonic-2:YOUR-VOICE-ID",  # Change this
)
```

### 3. Test locally
```bash
# Test in console
uv run python src/agent.py console

# Or test with live connections
uv run python src/agent.py dev
```

### 4. Deploy updates

**LiveKit Cloud:**
```bash
lk agent deploy
```

**Self-hosted:**
```bash
docker build -t my-agent .
docker push my-agent
# Then restart your deployment
```

## 👀 Monitoring Your Agent

### Check active rooms/calls
```bash
uv run python scripts/check_agent_status.py
```

### Check deployed agents and active sessions
```bash
uv run python scripts/list_workers.py
```

Or use the LiveKit CLI:
```bash
lk agent list
```

### View logs
When running locally (`uv run python src/agent.py dev`), you'll see logs like:
```
============================================================
🚀 Agent starting up
📋 Job ID: AJ_xxxxx
🏠 Room: outbound-1234567890
📞 Outbound call to: +15105550123
============================================================
🔧 Starting agent session...
✅ Agent session started successfully
🔗 Connecting to room...
✅ Connected to room
```

### LiveKit Cloud Dashboard
- **Active calls:** https://cloud.livekit.io/projects/p_/rooms
- **Agent deployments:** https://cloud.livekit.io/projects/p_/agents
- **Logs:** Available in each room/deployment view

### Metrics
At the end of each call, you'll see usage metrics:
```
Usage: {
  'stt_chars': 1234,
  'llm_tokens': 5678,
  'tts_chars': 910
}
```

## 📁 Project Structure

```
rise-livekit-backend/
├── src/
│   └── agent.py          # Your agent logic (EDIT THIS)
├── scripts/
│   ├── make_call.py      # Make outbound calls
│   └── check_agent_status.py  # View agent status
├── tests/
│   └── test_agent.py     # Agent tests
├── DEPLOYMENT.md         # Detailed deployment guide
└── QUICKSTART.md         # This file
```

## 🛠️ Common Tasks

### Run local dev agent (won't conflict with production)
```bash
./scripts/dev.sh
```

### Make a test call (to dev agent)
```bash
uv run python scripts/make_call.py +15105550123 --agent-name my-telephony-agent-dev
```

### Check status
```bash
uv run python scripts/check_agent_status.py
```

### Test changes locally (no phone needed!)
```bash
uv run python src/agent.py console
```
This is the **fastest** way to test! Just type or speak to your agent in the terminal.

### Run tests
```bash
uv run pytest
```

### Format code
```bash
uv run ruff format
```

### Deploy
```bash
lk agent deploy
```

## 📚 More Information

- **Full deployment guide:** See [DEPLOYMENT.md](DEPLOYMENT.md)
- **LiveKit Agents docs:** https://docs.livekit.io/agents
- **Telephony docs:** https://docs.livekit.io/sip
- **Tool building:** https://docs.livekit.io/agents/build/tools
- **Workflows:** https://docs.livekit.io/agents/build/workflows

