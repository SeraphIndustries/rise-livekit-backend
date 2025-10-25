#!/usr/bin/env python
"""
Script to make outbound calls with your LiveKit agent.

Usage:
    uv run python scripts/make_call.py +15105550123

Or with custom agent name:
    uv run python scripts/make_call.py +15105550123 --agent-name my-agent
"""

import argparse
import asyncio
import json
import os
import random
from dotenv import load_dotenv
from livekit import api

# Load environment variables
load_dotenv(".env.local")


async def make_call(phone_number: str, agent_name: str = "my-telephony-agent"):
    """
    Initiate an outbound call using LiveKit agent dispatch.

    Args:
        phone_number: Phone number to call (e.g., +15105550123)
        agent_name: Name of the agent to dispatch
    """
    # Get LiveKit credentials from environment
    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not all([url, api_key, api_secret]):
        print("❌ Error: Missing LiveKit credentials!")
        print(
            "Please ensure LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are set"
        )
        print("You can set them in .env.local or as environment variables")
        return

    # Create a unique room name for this call
    room_name = f"outbound-{''.join(str(random.randint(0, 9)) for _ in range(10))}"

    print(f"📞 Initiating call to {phone_number}")
    print(f"🏠 Room: {room_name}")
    print(f"🤖 Agent: {agent_name}")

    # Create API client
    lkapi = api.LiveKitAPI(url, api_key, api_secret)

    try:
        # Dispatch the agent to a new room with the phone number in metadata
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=agent_name,
                room=room_name,
                metadata=json.dumps({"phone_number": phone_number}),
            )
        )

        print(f"✅ Dispatch created successfully!")
        print(f"📋 Dispatch ID: {dispatch.id}")
        print(
            f"🔗 View in LiveKit Cloud: https://cloud.livekit.io/projects/p_/rooms/{room_name}"
        )
        print(f"\n💡 The agent will now call {phone_number}")
        print(f"   You can monitor the call in the LiveKit Cloud dashboard")

        return dispatch

    except Exception as e:
        print(f"❌ Error creating dispatch: {e}")
        raise
    finally:
        await lkapi.aclose()


def main():
    parser = argparse.ArgumentParser(
        description="Make an outbound call using your LiveKit agent"
    )
    parser.add_argument(
        "phone_number", help="Phone number to call (e.g., +15105550123)"
    )
    parser.add_argument(
        "--agent-name",
        default="my-telephony-agent",
        help="Name of the agent to dispatch (default: my-telephony-agent)",
    )

    args = parser.parse_args()

    # Run the async function
    asyncio.run(make_call(args.phone_number, args.agent_name))


if __name__ == "__main__":
    main()
