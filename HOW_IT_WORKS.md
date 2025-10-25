# How LiveKit Agents Work

## Understanding the Architecture

### The Three Key Pieces:

```
┌─────────────────────────────────────────────────────────────┐
│  1. YOUR CODE (src/agent.py)                                │
│     - Defines agent behavior, tools, personality            │
│     - This is what you edit and update                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. WORKERS (Running your code)                             │
│     Option A: Local (development)                           │
│        → uv run python src/agent.py dev                     │
│        → Runs on your machine                               │
│        → Shows logs in your terminal                        │
│                                                              │
│     Option B: Cloud (production)                            │
│        → lk agent deploy                                    │
│        → Runs on LiveKit Cloud infrastructure               │
│        → Logs in LiveKit Cloud dashboard                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. DISPATCH (Assigning calls to workers)                   │
│     - Someone calls your phone number                       │
│     - LiveKit creates a room                                │
│     - Available worker picks up the job                     │
│     - Agent starts talking to the caller                    │
└─────────────────────────────────────────────────────────────┘
```

## Common Scenarios

### Scenario 1: Only Running Locally (Development)

```bash
# Terminal 1: Run local worker
uv run python src/agent.py dev

# Terminal 2: Make test call
uv run python scripts/make_call.py +15105550123
```

**What happens:**
1. Your local worker picks up the dispatch request
2. Agent code from your local `src/agent.py` runs
3. You see all logs in Terminal 1
4. Perfect for testing changes!

### Scenario 2: Only Cloud Deployment (Production)

```bash
# Deploy once
lk agent deploy

# Now calls are handled automatically
# No need to run anything locally
```

**What happens:**
1. LiveKit Cloud workers always running
2. They use your deployed code
3. Handle all calls automatically
4. View logs at https://cloud.livekit.io

### Scenario 3: BOTH Running (⚠️ Usually Not Intended)

If you:
1. Have deployed to cloud (`lk agent deploy`)
2. AND are running locally (`uv run python src/agent.py dev`)

**What happens:**
- Both workers compete for jobs!
- Whichever responds first gets the call
- Can be confusing for testing
- **Solution:** Pick one or the other

## The Agent Name

In your `src/agent.py`:

```python
cli.run_app(
    WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm,
        agent_name="my-telephony-agent",  # ← This is the key!
    )
)
```

This name is used to:
1. **Identify the worker type** - All workers with this name can handle jobs for it
2. **Dispatch jobs** - When you create a dispatch, you specify which agent name
3. **Manage deployments** - Cloud deployments are referenced by this name

### Multiple Agents Example:

```python
# Agent 1: Sales agent
agent_name="sales-agent"

# Agent 2: Support agent  
agent_name="support-agent"
```

You can have different agents for different purposes, each with their own:
- Code (different `src/` files)
- Personality (different instructions)
- Tools (different function_tool methods)
- Deployment (different cloud deployments)

## How Calls Get Routed

### Inbound Calls (Someone calls you):

```
Phone Call → SIP Provider (Twilio) → LiveKit SIP → 
Dispatch Rule → Available Worker → Your Agent Code
```

The **dispatch rule** you created in LiveKit Cloud determines:
- Which agent name to use
- What room name pattern to use
- Any custom metadata

### Outbound Calls (You call someone):

```
Your Script → Create Dispatch → Available Worker → 
Your Agent Code → SIP Provider → Phone Call
```

When you run `make_call.py`, it:
1. Creates a dispatch request with `agent_name="my-telephony-agent"`
2. Any available worker with that name can pick it up
3. That worker runs your agent code
4. Agent places the call via SIP

## Checking What's Running

### See active calls/rooms:
```bash
uv run python scripts/check_agent_status.py
```

### See cloud deployments:
```bash
uv run python scripts/list_workers.py
```

### See if local worker is running:
Check your terminal - if you ran `uv run python src/agent.py dev`, you'll see logs

## Development Workflow

### 1. Local Testing (Recommended)
```bash
# Test in console first (no phone needed)
uv run python src/agent.py console

# Test with actual calls
# Terminal 1:
uv run python src/agent.py dev

# Terminal 2:
uv run python scripts/make_call.py +15105550123
```

### 2. Deploy to Production
```bash
# When you're happy with changes
lk agent deploy

# Stop local worker (Ctrl+C in Terminal 1)
# Now all calls go to cloud
```

### 3. Update Production
```bash
# Make changes to src/agent.py
# Deploy again
lk agent deploy

# The cloud deployment updates automatically
```

## Common Questions

### "Does src/agent.py connect to the live agent?"

**No!** `src/agent.py` **IS** the agent. It's the code that defines what the agent does.

Think of it like:
- `src/agent.py` = The recipe
- Workers = The chefs cooking from that recipe
- Cloud/Local = Where the kitchen is located

### "How do I update my deployed agent?"

Just edit `src/agent.py` and run `lk agent deploy` again. The cloud deployment will use your new code.

### "Can I have different versions for testing?"

Yes! Two approaches:

**Approach 1: Different agent names**
```python
# In src/agent.py
agent_name="my-telephony-agent-dev"  # For testing

# Deploy to cloud as production
agent_name="my-telephony-agent"  # For production
```

**Approach 2: Use local for testing, cloud for production**
- Always test locally first
- Only deploy when ready for production

### "How do I see what my agent is doing?"

**Local:**
- Watch your terminal where `uv run python src/agent.py dev` is running
- All logs appear there

**Cloud:**
- Visit https://cloud.livekit.io/projects/p_/agents
- Click on any deployment to see logs
- Or check individual rooms for call-specific logs

## Visual Summary

```
YOU EDIT:               src/agent.py (the code)
                             ↓
RUNS AS:                Workers (local or cloud)
                             ↓
HANDLES:                Inbound/Outbound calls
                             ↓
USING:                  SIP Provider (Twilio, etc.)
                             ↓
TALKS TO:               Your customers on the phone
```

The key insight: **Your `src/agent.py` file is not a separate thing from "the agent" - it IS the agent's code!**

