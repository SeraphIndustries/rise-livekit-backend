import json
import logging
import os
from datetime import datetime

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, firestore
from livekit import api
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
    metrics,
)
from livekit.plugins import noise_cancellation, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)

load_dotenv(".env.local")

# Initialize Firebase
firebase_app = None
db = None

try:
    # Try to get Firebase credentials from environment
    # Option 1: File path (for local development)
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")

    # Option 2: Base64-encoded JSON (for deployment)
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

    if service_account_json:
        # Decode base64 JSON credentials (used in deployment)
        import base64

        decoded_json = base64.b64decode(service_account_json).decode("utf-8")
        cred_dict = json.loads(decoded_json)
        cred = credentials.Certificate(cred_dict)
        firebase_app = firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("✅ Firebase initialized successfully (from env JSON)")
    elif service_account_path and os.path.exists(service_account_path):
        # Use file path (local development)
        cred = credentials.Certificate(service_account_path)
        firebase_app = firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("✅ Firebase initialized successfully (from file)")
    else:
        logger.warning(
            "⚠️  Firebase credentials not found. Set FIREBASE_SERVICE_ACCOUNT_PATH or FIREBASE_SERVICE_ACCOUNT_JSON"
        )
except Exception as e:
    logger.warning(f"⚠️  Could not initialize Firebase: {e}")
    logger.warning("   Data will be logged but not saved to database")


class Assistant(Agent):
    def __init__(self, user_name: str = None, user_phone: str = None) -> None:
        # Determine if this is a new user or returning user
        is_new_user = user_name is None

        name_instruction = (
            f"The user's name is {user_name}. Use their name naturally in conversation in english."
            if user_name
            else "FIRST, get their name by asking warmly what their name is. Once they tell you, use their name naturally throughout the conversation in english."
        )

        super().__init__(
            instructions=f"""You are a personal growth coach helping users build better habits. The user is interacting with you via voice.
            
            IMPORTANT: You must always speak in English, regardless of what language the user speaks to you in.
            
            {"This is the user's first call with you." if is_new_user else "This user has called before."} Your goal is to gather key information through a natural, conversational flow:
            
            1. {name_instruction}
            
            2. SECOND: Understand their habits and goals
               - Ask what habits they want to build or improve
               - Ask about their goals and what they're working toward
               - Be curious and encouraging. Ask follow-up questions to understand their "why"
            
            3. THIRD: Plan for today
               - Ask what they plan to do today to work toward their goals
               - Help them be specific and realistic
            
            After gathering all this information, use the save_onboarding_info tool to save everything.
            
            Keep your responses:
            - Conversational and warm, not robotic
            - Concise (1-2 sentences at a time)
            - Without complex formatting, emojis, or asterisks
            - Encouraging and supportive
            
            Move through the conversation naturally - don't rush, but don't linger too long on one topic.""",
        )
        self.user_data = {
            "name": user_name,
            "phone": user_phone,
            "habits_and_goals": None,
            "today_plan": None,
        }

    @function_tool
    async def save_onboarding_info(
        self,
        context: RunContext,
        user_name: str,
        habits_and_goals: str,
        today_plan: str,
    ):
        """Save the user's onboarding information after gathering their name, habits/goals, and today's plan.

        Call this tool ONLY after you have collected all three pieces of information from the user.

        Args:
            user_name: The user's name (use the one provided, even if you already knew their name)
            habits_and_goals: A summary of the habits they want to build and their goals
            today_plan: What they plan to do today toward their goals
        """
        logger.info("💾 Saving onboarding information")
        logger.info(f"   Name: {user_name}")
        logger.info(f"   Habits/Goals: {habits_and_goals}")
        logger.info(f"   Today's Plan: {today_plan}")

        # Store in instance for this session
        self.user_data["name"] = user_name
        self.user_data["habits_and_goals"] = habits_and_goals
        self.user_data["today_plan"] = today_plan

        # Save to Firebase Firestore
        if db is not None:
            try:
                # Check if we need to look up the user document by phone
                user_doc_ref = None
                if self.user_data.get("phone"):
                    # Try to find existing user document by phone
                    users_ref = db.collection("users")
                    query = users_ref.where(
                        "phone", "==", self.user_data["phone"]
                    ).limit(1)
                    docs = list(query.stream())
                    if docs:
                        user_doc_ref = docs[0].reference
                        logger.info(f"📝 Updating existing user document: {docs[0].id}")

                # Prepare the data to save
                onboarding_data = {
                    "habits_and_goals": habits_and_goals,
                    "today_plan": today_plan,
                    "onboarding_completed_at": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                }

                if user_doc_ref:
                    # Update existing user document
                    user_doc_ref.update(onboarding_data)
                    logger.info(f"✅ Updated existing user in Firestore")
                else:
                    # Create new user document (for users not in the system yet)
                    onboarding_data.update(
                        {
                            "name": user_name,
                            "phone": self.user_data.get("phone", ""),
                            "createdAt": firestore.SERVER_TIMESTAMP,
                        }
                    )
                    doc_ref = db.collection("users").add(onboarding_data)
                    logger.info(
                        f"✅ Created new user in Firestore with ID: {doc_ref[1].id}"
                    )

            except Exception as e:
                logger.error(f"❌ Error saving to Firestore: {e}")
                logger.info("   Data logged locally but not saved to database")
        else:
            logger.warning("   Firebase not configured - data logged only")

        return f"Perfect! I've saved all your information, {user_name}. I'm excited to help you on your journey. Let me know if there's anything else I can help you with today, or feel free to end the call whenever you're ready."

    # Example tool: End call
    @function_tool
    async def end_call(self, ctx: RunContext):
        """Call this tool when the user wants to end the call or says goodbye."""
        logger.info("📞 User requested to end call")

        # Let the agent finish speaking before hanging up
        await ctx.wait_for_playout()

        # Get the job context to access the room
        from livekit.agents import get_job_context

        job_ctx = get_job_context()
        if job_ctx:
            try:
                await job_ctx.api.room.delete_room(
                    api.DeleteRoomRequest(room=job_ctx.room.name)
                )
                logger.info("✅ Call ended successfully")
            except Exception as e:
                logger.error(f"❌ Error ending call: {e}")

        return "Goodbye! The call has been ended."


async def lookup_user_by_phone(phone_number: str) -> dict:
    """Look up user information from Firebase by phone number.

    Args:
        phone_number: Phone number in E.164 format (e.g., +18327228729)

    Returns:
        dict with user info if found, or None if not found
    """
    if db is None:
        logger.warning("⚠️  Firebase not initialized, cannot lookup user")
        return None

    try:
        # Query the users collection for a document with matching phone number
        users_ref = db.collection("users")
        query = users_ref.where("phone", "==", phone_number).limit(1)
        docs = query.stream()

        # Get the first matching document
        for doc in docs:
            user_data = doc.to_dict()
            logger.info(
                f"✅ Found user in Firebase: {user_data.get('name')} ({phone_number})"
            )
            return {
                "doc_id": doc.id,
                "name": user_data.get("name"),
                "email": user_data.get("email"),
                "phone": user_data.get("phone"),
                "timezone": user_data.get("timezone"),
                "schedule_time": user_data.get("scheduleTime"),
            }

        logger.info(f"ℹ️  No user found for phone number: {phone_number}")
        return None

    except Exception as e:
        logger.error(f"❌ Error looking up user by phone: {e}")
        return None


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Enhanced logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
        "job_id": ctx.job.id,
    }

    logger.info("=" * 60)
    logger.info("🚀 Agent starting up")
    logger.info(f"📋 Job ID: {ctx.job.id}")
    logger.info(f"🏠 Room: {ctx.room.name}")
    logger.info(f"📝 Metadata: {ctx.job.metadata}")
    logger.info("=" * 60)

    # Get phone number from metadata (outbound) or will get from SIP participant (inbound)
    phone_number = None

    # For testing in console mode: check for TEST_PHONE_NUMBER env var
    test_phone = os.getenv("TEST_PHONE_NUMBER")
    if test_phone:
        phone_number = test_phone
        logger.info(
            f"🧪 TEST MODE: Using phone number from environment: {phone_number}"
        )

    # Otherwise get from metadata (production/real calls)
    if not test_phone:
        try:
            if ctx.job.metadata:
                metadata = json.loads(ctx.job.metadata)
                phone_number = metadata.get("phone_number")
                if phone_number:
                    logger.info(f"📞 Outbound call to: {phone_number}")
        except json.JSONDecodeError:
            logger.warning("⚠️  Could not parse job metadata")
        except Exception as e:
            logger.warning(f"⚠️  Error reading metadata: {e}")

    # If still no phone number, connect and check for SIP participant (inbound call)
    already_connected = False
    if not phone_number and not test_phone:
        logger.info("📥 Waiting for SIP participant to join (inbound call)...")
        await ctx.connect()
        already_connected = True

        # Give participant a moment to fully join
        import asyncio

        await asyncio.sleep(0.5)

        # Get the caller's phone number from SIP participant attributes
        for participant in ctx.room.remote_participants.values():
            if hasattr(participant, "attributes"):
                # SIP participants have their phone number in attributes
                caller_number = participant.attributes.get(
                    "sip.phoneNumber"
                ) or participant.attributes.get("sip.callerId")
                if caller_number:
                    phone_number = caller_number
                    logger.info(f"📞 Inbound call from: {phone_number}")
                    break

        if not phone_number:
            logger.warning(
                "⚠️  Could not determine caller phone number from SIP participant"
            )

    # Look up user information by phone number
    user_info = None
    user_name = None
    if phone_number:
        user_info = await lookup_user_by_phone(phone_number)
        if user_info:
            user_name = user_info.get("name")
            logger.info(f"👤 User identified: {user_name}")
        else:
            logger.info(f"👤 New user - phone number not in database: {phone_number}")

    # 🧪 TEST: Log call session to Firebase
    if db is not None:
        try:
            session_doc = {
                "job_id": ctx.job.id,
                "room_name": ctx.room.name,
                "phone_number": phone_number,
                "user_name": user_name,  # Will be None if user not found
                "metadata": ctx.job.metadata or "",
                "started_at": firestore.SERVER_TIMESTAMP,
                "agent_type": "onboarding",
            }
            doc_ref = db.collection("call_sessions").add(session_doc)
            logger.info(
                f"✅ Firebase TEST: Logged session to Firestore (ID: {doc_ref[1].id})"
            )
        except Exception as e:
            logger.error(f"❌ Firebase TEST failed: {e}")
    else:
        logger.warning("⚠️  Firebase TEST skipped: DB not initialized")

    # Using OpenAI Realtime API - single model for speech, understanding, and response
    # This is simpler and faster than the traditional pipeline (STT + LLM + TTS)
    # Voice options: alloy, ash, ballad, coral, echo, sage, shimmer, verse
    # See: https://docs.livekit.io/agents/models/realtime/plugins/openai
    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            voice="alloy",  # Change this to your preferred voice
            temperature=0.8,
            # instructions are set in the Assistant class above
        )
    )

    # Metrics collection, to measure pipeline performance
    # For more information, see https://docs.livekit.io/agents/build/metrics/
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    logger.info("🔧 Starting agent session...")
    await session.start(
        agent=Assistant(user_name=user_name, user_phone=phone_number),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    logger.info("✅ Agent session started successfully")

    # Join the room and connect to the user (if not already connected)
    if not already_connected:
        logger.info("🔗 Connecting to room...")
        await ctx.connect()
        logger.info("✅ Connected to room")
    else:
        logger.info("✅ Already connected to room (from inbound call detection)")

    # For outbound calls, wait for the call to be picked up before greeting
    # For inbound calls or test mode, greet immediately
    if phone_number is None or test_phone or already_connected:
        # Inbound call or test mode - greet immediately
        if test_phone:
            logger.info("🧪 TEST MODE: Starting console conversation with user lookup")
        elif already_connected:
            logger.info("📥 Greeting inbound caller")
        else:
            logger.info("👋 Starting onboarding conversation")

        # Greet based on whether we know the user's name
        if user_name:
            await session.generate_reply(
                instructions=f"Warmly greet {user_name} by name and start the onboarding conversation. Ask about their habits and goals. Keep it brief, friendly, and natural - like a coach starting a conversation."
            )
        else:
            await session.generate_reply(
                instructions="Warmly welcome the user and start the onboarding by asking for their name. Keep it brief, friendly, and natural - like a coach starting a conversation."
            )
    else:
        # Real outbound call - wait for them to answer
        logger.info("📞 Waiting for outbound call to be answered...")
        # For outbound calls, we'll greet once they answer
        # The greeting will be personalized if user_name is set


if __name__ == "__main__":
    # Set agent name for explicit dispatch (required for telephony)
    # You can override this with --agent-name flag
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            # Set a name to use explicit dispatch for telephony
            # Comment this out if you want automatic dispatch
            agent_name="my-telephony-agent",
        )
    )
