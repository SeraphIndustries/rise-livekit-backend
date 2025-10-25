#!/usr/bin/env python
"""
Script to check the status of your LiveKit agent and active rooms.

Usage:
    uv run python scripts/check_agent_status.py
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from livekit import api

# Load environment variables
load_dotenv(".env.local")


async def check_status():
    """Check the status of agents and active rooms."""
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
        print("🔍 Checking LiveKit status...\n")

        # List active rooms
        print("=" * 60)
        print("📋 ACTIVE ROOMS")
        print("=" * 60)

        rooms_response = await lkapi.room.list_rooms(api.ListRoomsRequest())
        rooms = rooms_response.rooms

        if not rooms:
            print("No active rooms")
        else:
            for room in rooms:
                print(f"\n🏠 Room: {room.name}")
                print(f"   SID: {room.sid}")
                print(f"   Participants: {room.num_participants}")
                print(f"   Created: {datetime.fromtimestamp(room.creation_time)}")

                # Get participants in this room
                participants_response = await lkapi.room.list_participants(
                    api.ListParticipantsRequest(room=room.name)
                )
                participants = participants_response.participants

                if participants:
                    print(f"   👥 Participants:")
                    for p in participants:
                        participant_type = "🤖 Agent" if p.is_publisher else "👤 User"
                        state = p.state.name if hasattr(p.state, "name") else p.state
                        print(
                            f"      {participant_type}: {p.identity} (state: {state})"
                        )

        print("\n" + "=" * 60)
        print("🔗 View full dashboard:")
        print("=" * 60)
        print("https://cloud.livekit.io/projects/p_/rooms")

    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        await lkapi.aclose()


def main():
    asyncio.run(check_status())


if __name__ == "__main__":
    main()
