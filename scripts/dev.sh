#!/bin/bash
# Helper script to run the agent in development mode with a dev-specific name
# This ensures your local worker doesn't conflict with production

echo "🚀 Starting agent in DEVELOPMENT mode"
echo "   Agent name: my-telephony-agent-dev"
echo ""
echo "To make a test call, run in another terminal:"
echo "   uv run python scripts/make_call.py +15105550123 --agent-name my-telephony-agent-dev"
echo ""
echo "Press Ctrl+C to stop"
echo ""

AGENT_NAME=my-telephony-agent-dev uv run python src/agent.py dev

