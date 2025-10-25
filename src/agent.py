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
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a personal growth coach helping users build better habits. The user is interacting with you via voice.
            
            IMPORTANT: You must always speak in English, regardless of what language the user speaks to you in.
            
            This is the user's first call with you. Your goal is to gather key information through a natural, conversational flow:
            
            1. FIRST: Get their name
               - Ask warmly what their name is
               - Once they tell you, use their name naturally throughout the conversation
            
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
            "name": None,
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
            user_name: The user's name
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
                # Create a new user document in the 'users' collection
                user_doc = {
                    "name": user_name,
                    "habits_and_goals": habits_and_goals,
                    "today_plan": today_plan,
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "onboarding_completed_at": firestore.SERVER_TIMESTAMP,
                }

                # Add the document - Firestore will auto-generate an ID
                doc_ref = db.collection("users").add(user_doc)
                logger.info(f"✅ Saved to Firestore with ID: {doc_ref[1].id}")

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

    # Check if this is an outbound call
    phone_number = None
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

    # 🧪 TEST: Log call session to Firebase
    if db is not None:
        try:
            session_doc = {
                "job_id": ctx.job.id,
                "room_name": ctx.room.name,
                "phone_number": phone_number,
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

    # Alternative: Traditional voice pipeline (STT + LLM + TTS)
    # Uncomment this and comment out the Realtime API above if you want more control
    # session = AgentSession(
    #     stt="assemblyai/universal-streaming:en",
    #     llm="openai/gpt-4.1-mini",
    #     tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
    #     turn_detection=MultilingualModel(),
    #     vad=ctx.proc.userdata["vad"],
    #     preemptive_generation=True,
    # )

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
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    logger.info("✅ Agent session started successfully")

    # Join the room and connect to the user
    logger.info("🔗 Connecting to room...")
    await ctx.connect()
    logger.info("✅ Connected to room")

    # For outbound calls, wait for the call to be picked up before greeting
    # For inbound calls, greet immediately
    if phone_number is None:
        logger.info("👋 Starting onboarding conversation (inbound call)")
        await session.generate_reply(
            instructions="Warmly welcome the user and start the onboarding by asking for their name. Keep it brief, friendly, and natural - like a coach starting a conversation."
        )
    else:
        logger.info("📞 Waiting for outbound call to be answered...")
        # For outbound calls, we'll greet once they answer


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
