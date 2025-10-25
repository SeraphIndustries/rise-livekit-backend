#!/usr/bin/env python
"""
Script to list active agent workers.

This shows which workers (local or cloud) are currently available
to handle agent dispatch requests.

Usage:
    uv run python scripts/list_workers.py
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from livekit import api

# Load environment variables
load_dotenv(".env.local")


async def list_workers():
    """List all active agent workers."""
    # Get LiveKit credentials from environment
    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([url, api_key, api_secret]):
        print("❌ Error: Missing LiveKit credentials!")
        return

    # Create API client
    lkapi = api.LiveKitAPI(url, api_key, api_secret)

    try:
        print("🔍 Checking for active agent workers...\n")

        # List all agents
        print("=" * 60)
        print("🤖 AGENT WORKERS")
        print("=" * 60)

        # List agent deployments (cloud workers)
        # Note: The Python SDK doesn't currently expose a list_agents method
        # You need to use the LiveKit CLI to see deployed agents
        print("\n📦 CLOUD DEPLOYMENTS:")
        print("   Use the LiveKit CLI to see deployed agents:")
        print("   $ lk agent list")
        print()
        print("   Or view them in the LiveKit Cloud dashboard")

        # Show active rooms as a proxy for agent activity
        print("\n📊 ACTIVE AGENT SESSIONS:")
        try:
            rooms_response = await lkapi.room.list_rooms(api.ListRoomsRequest())
            rooms = rooms_response.rooms

            if not rooms:
                print("   No active sessions")
            else:
                print(f"   {len(rooms)} active room(s)")
                for room in rooms:
                    participants_response = await lkapi.room.list_participants(
                        api.ListParticipantsRequest(room=room.name)
                    )
                    participants = participants_response.participants

                    has_agent = any(p.is_publisher for p in participants)
                    if has_agent:
                        print(f"   ✓ {room.name} - Agent active")
                    else:
                        print(f"   ⏳ {room.name} - Waiting for agent")

                print(
                    f"\n   For details, run: uv run python scripts/check_agent_status.py"
                )
        except Exception as e:
            print(f"   Could not fetch room info: {e}")

        # Note: We can't directly list local workers via API
        # They show up when they connect to handle jobs
        print("\n" + "=" * 60)
        print("💡 TIPS")
        print("=" * 60)
        print(
            """
Local workers (running 'uv run python src/agent.py dev'):
- Are NOT shown in this list
- Only visible when they're actively handling a job
- Check your terminal to see if one is running locally

Cloud workers:
- Deployed via 'lk agent deploy'
- Always available to handle calls
- Shown above if any are deployed

To see active jobs/calls, run:
    uv run python scripts/check_agent_status.py
"""
        )

        print("🔗 View agents in LiveKit Cloud:")
        print("https://cloud.livekit.io/projects/p_/agents")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await lkapi.aclose()


def main():
    asyncio.run(list_workers())


if __name__ == "__main__":
    main()
