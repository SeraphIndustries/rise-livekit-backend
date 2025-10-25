# Agent Scripts

This directory contains utility scripts for managing your LiveKit agent.

## Available Scripts

### `make_call.py`
Initiate an outbound call from your agent.

**Usage:**
```bash
# Basic usage
uv run python scripts/make_call.py +15105550123

# With custom agent name
uv run python scripts/make_call.py +15105550123 --agent-name my-agent
```

**Requirements:**
- LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET must be set (in .env.local or environment)
- Outbound SIP trunk must be configured in LiveKit Cloud
- Your agent must be running (`uv run python src/agent.py dev`)

### `check_agent_status.py`
Check the status of your agent and view active rooms/calls.

**Usage:**
```bash
uv run python scripts/check_agent_status.py
```

**Shows:**
- Active rooms
- Participants in each room
- Room durations
- Agent status

### `list_workers.py`
List active agent workers (cloud deployments).

**Usage:**
```bash
uv run python scripts/list_workers.py
```

**Shows:**
- Cloud-deployed agents
- Agent versions and metadata
- Tips for checking local workers

### `encode_firebase_credentials.sh`
Encode your Firebase service account JSON for deployment.

**Usage:**
```bash
./scripts/encode_firebase_credentials.sh firebase-service-account.json
```

**What it does:**
- Converts your Firebase credentials to base64 format
- Outputs the value you need to set as `FIREBASE_SERVICE_ACCOUNT_JSON` in deployment
- Makes it safe to pass credentials as environment variables in LiveKit Cloud

## Setting Up

1. Copy `.env.example` to `.env.local`:
   ```bash
   cp .env.example .env.local
   ```

2. Fill in your LiveKit credentials in `.env.local`

3. Make sure your agent is running:
   ```bash
   uv run python src/agent.py dev
   ```

4. Run any script:
   ```bash
   uv run python scripts/make_call.py +15105550123
   ```

## Need Help?

See the main [DEPLOYMENT.md](../DEPLOYMENT.md) guide for more information on:
- Updating agent logic
- Monitoring your agent
- Deploying to production

