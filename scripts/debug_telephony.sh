#!/bin/bash
# Telephony debugging script

echo "🔍 TELEPHONY DIAGNOSTICS"
echo "========================"
echo ""

echo "1️⃣ Agent Status:"
echo "----------------"
lk agent status my-telephony-agent
echo ""

echo "2️⃣ Active Rooms:"
echo "----------------"
uv run python scripts/check_agent_status.py
echo ""

echo "3️⃣ Inbound Trunks:"
echo "----------------"
lk sip inbound list
echo ""

echo "4️⃣ Dispatch Rules:"
echo "----------------"
lk sip dispatch list
echo ""

echo "5️⃣ Recent Logs (last 50 lines):"
echo "----------------"
lk agent logs my-telephony-agent | tail -50
echo ""

echo "💡 TIP: To follow logs in real-time, run:"
echo "   lk agent logs my-telephony-agent --follow"

