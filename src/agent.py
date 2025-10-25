import json
import logging
import os
from datetime import datetime, timedelta

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, firestore
from livekit import api
from livekit.agents import (
    Agent,
    AgentSession,
    ConversationItemAddedEvent,
    FunctionToolsExecutedEvent,
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
    def __init__(
        self,
        user_name: str = None,
        user_phone: str = None,
        user_doc_id: str = None,
        conversation_id: str = None,
        existing_habits: list = None,
        exceptional_events: list = None,
    ) -> None:
        # Determine if this is a new user or returning user
        is_new_user = user_name is None
        has_habits = existing_habits and len(existing_habits) > 0
        has_events = exceptional_events and len(exceptional_events) > 0

        name_instruction = (
            f"Only speak in english. The user's name is {user_name}. Use their name naturally in conversation in english."
            if user_name
            else "FIRST, get their name by asking warmly what their name is. Once they tell you, use their name naturally throughout the conversation in english."
        )

        # Build habits context for the agent
        habits_context = ""
        if has_habits:
            habits_list = "\n".join(
                [
                    f"   - {h.get('name', 'Unnamed habit')}: {h.get('description', 'No description')}"
                    for h in existing_habits
                ]
            )
            habits_context = f"""
            
EXISTING HABITS:
The user is already working on these habits:
{habits_list}

When appropriate, ask about their progress on these habits and use the log_habit_progress tool to record updates.
If they mention wanting to work on something related to an existing habit, acknowledge it and ask if they want to update that habit or create a new one.
"""

        # Build exceptional events context
        events_context = ""
        if has_events:
            events_list = "\n".join(
                [
                    f"   - {e.get('title')} ({e.get('event_type')}, impact: {e.get('current_impact', 0):.0%})"
                    for e in exceptional_events
                ]
            )
            events_context = f"""

EXCEPTIONAL EVENTS:
The user is currently dealing with these temporary situations:
{events_list}

Be understanding and adapt your coaching:
- Don't push too hard on affected habits
- Acknowledge these challenges when discussing progress
- Use update_exceptional_event when they mention improvements or setbacks
- Be compassionate about any habit disruptions related to these events

For example:
- If injured, don't encourage intense exercise
- If stressed at work, be extra supportive about any lapses
- If traveling, acknowledge disrupted routines are normal
"""

        super().__init__(
            instructions=f"""You are a personal growth coach helping users build better habits. The user is interacting with you via voice.
            
            IMPORTANT: You must always speak in English, regardless of what language the user speaks to you in.
            
            {"This is the user's first call with you." if is_new_user else "This user has called before."}{habits_context}{events_context}
            
            Your conversation flow:
            
            1. {name_instruction}
            
            2. {"Ask what habits they want to build or improve." if not has_habits else "Check in on their existing habits and see if they want to add new ones."}
               - Be curious and encouraging. Ask follow-up questions to understand their "why"
               - When they mention a specific habit they want to work on, use the create_or_update_habit tool to save it
               - When they share progress on an existing habit, use the log_habit_progress tool
               - If they mention an injury, illness, stress, or other temporary disruption, use create_exceptional_event tool
            
            3. Plan for today
               - Ask what they plan to do today to work toward their goals
               - Help them be specific and realistic
            
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
            "user_doc_id": user_doc_id,
            "habits_and_goals": None,
            "today_plan": None,
        }
        self.conversation_id = conversation_id
        self.existing_habits = existing_habits or []
        self.exceptional_events = exceptional_events or []

    @function_tool
    async def create_or_update_habit(
        self,
        context: RunContext,
        habit_name: str,
        description: str,
        goal: str = None,
    ):
        """Create a new habit or update an existing one for the user.

        Use this when the user mentions a specific habit they want to work on or improve.

        Args:
            habit_name: Short name for the habit (e.g., "Sleep consistently", "Morning exercise")
            description: Detailed description of what the habit involves
            goal: Optional specific goal (e.g., "8 hours per night", "30 minutes daily")
        """
        if not self.user_data.get("user_doc_id"):
            return "I can't save habits yet because I don't have your user information. Let's continue our conversation first."

        logger.info(f"💪 Creating/updating habit: {habit_name}")

        if db is None:
            return "I've noted that you want to work on this habit, but I'm having trouble saving it right now."

        try:
            user_doc_id = self.user_data["user_doc_id"]
            habits_ref = (
                db.collection("users").document(user_doc_id).collection("habits")
            )

            # Check if habit with similar name already exists
            existing_query = habits_ref.where("name", "==", habit_name).limit(1)
            existing_docs = list(existing_query.stream())

            habit_data = {
                "name": habit_name,
                "description": description,
                "goal": goal,
                "updated_at": firestore.SERVER_TIMESTAMP,
                "status": "active",
            }

            if existing_docs:
                # Update existing habit
                habit_id = existing_docs[0].id
                habits_ref.document(habit_id).update(habit_data)
                logger.info(f"✅ Updated existing habit: {habit_id}")
                return f"Perfect! I've updated your '{habit_name}' habit. {description}"
            else:
                # Create new habit
                habit_data["created_at"] = firestore.SERVER_TIMESTAMP
                new_habit_ref = habits_ref.add(habit_data)
                habit_id = new_habit_ref[1].id
                logger.info(f"✅ Created new habit: {habit_id}")
                return (
                    f"Great! I've saved your new habit: '{habit_name}'. {description}"
                )

        except Exception as e:
            logger.error(f"❌ Error saving habit: {e}")
            return f"I've made a note of your '{habit_name}' habit, but had trouble saving it."

    @function_tool
    async def log_habit_progress(
        self,
        context: RunContext,
        habit_name: str,
        progress_note: str,
        sentiment: str = "neutral",
    ):
        """Log progress or an update on an existing habit.

        Use this when the user shares how they're doing with one of their habits.

        Args:
            habit_name: The name of the habit they're updating
            progress_note: What they shared about their progress
            sentiment: How they feel about their progress - "positive", "negative", or "neutral"
        """
        if not self.user_data.get("user_doc_id"):
            return "I've noted your progress! Keep up the great work."

        logger.info(f"📈 Logging progress for habit: {habit_name}")

        if db is None:
            return "Thanks for sharing! I've noted your progress."

        try:
            user_doc_id = self.user_data["user_doc_id"]
            habits_ref = (
                db.collection("users").document(user_doc_id).collection("habits")
            )

            # Find the habit by name
            habit_query = (
                habits_ref.where("name", "==", habit_name)
                .where("status", "==", "active")
                .limit(1)
            )
            habit_docs = list(habit_query.stream())

            if not habit_docs:
                return f"I don't have '{habit_name}' saved yet. Would you like me to create it as a new habit?"

            habit_id = habit_docs[0].id

            # Create progress entry in subcollection
            progress_data = {
                "conversation_id": self.conversation_id,
                "note": progress_note,
                "sentiment": sentiment,
                "timestamp": firestore.SERVER_TIMESTAMP,
            }

            progress_ref = (
                habits_ref.document(habit_id).collection("progress").add(progress_data)
            )

            # Update habit's last_updated timestamp
            habits_ref.document(habit_id).update(
                {"updated_at": firestore.SERVER_TIMESTAMP}
            )

            logger.info(f"✅ Logged progress for habit {habit_id}")

            if sentiment == "positive":
                return f"That's wonderful progress on {habit_name}! Keep it up!"
            elif sentiment == "negative":
                return f"I appreciate you sharing that. Progress isn't always linear with {habit_name}, and it's okay to have setbacks."
            else:
                return (
                    f"Thanks for the update on {habit_name}. I've logged your progress."
                )

        except Exception as e:
            logger.error(f"❌ Error logging habit progress: {e}")
            return "Thanks for sharing your progress! I've made a note of it."

    @function_tool
    async def create_exceptional_event(
        self,
        context: RunContext,
        event_type: str,
        title: str,
        description: str,
        severity: str = "medium",
        affected_habit_names: list = None,
    ):
        """Record a new exceptional event that might affect the user's habits.

        Use this when the user mentions something temporary but impactful:
        - Injury or illness
        - Travel or vacation
        - Work stress or major project
        - Family events
        - Any other disruption to their routine

        Args:
            event_type: Type of event - "injury", "illness", "travel", "work_stress", "family_event", or "other"
            title: Short title for the event (e.g., "Knee injury", "Work deadline stress")
            description: What the user said about it
            severity: How severe - "low", "medium", or "high"
            affected_habit_names: List of habit names this might affect (optional)
        """
        if not self.user_data.get("user_doc_id"):
            return "I've made a note of this. Let me know if it affects your routine and I'll help adjust."

        logger.info(f"🚨 Creating exceptional event: {title}")

        if db is None:
            return f"I understand you're dealing with {title}. I'll keep that in mind."

        try:
            user_doc_id = self.user_data["user_doc_id"]

            # Determine initial impact based on severity
            impact_levels = {"low": 0.3, "medium": 0.6, "high": 0.9}
            impact_level = impact_levels.get(severity, 0.6)

            # Determine decay rate based on event type
            decay_rates = {
                "injury": "medium",
                "illness": "fast",
                "travel": "fast",
                "work_stress": "slow",
                "family_event": "medium",
                "other": "medium",
            }
            decay_rate = decay_rates.get(event_type, "medium")

            # Find affected habit IDs if names provided
            affected_habit_ids = []
            if affected_habit_names:
                habits_ref = (
                    db.collection("users").document(user_doc_id).collection("habits")
                )
                for habit_name in affected_habit_names:
                    habit_docs = list(
                        habits_ref.where("name", "==", habit_name).limit(1).stream()
                    )
                    if habit_docs:
                        affected_habit_ids.append(habit_docs[0].id)

            # Create event
            event_data = {
                "event_type": event_type,
                "title": title,
                "description": description,
                "severity": severity,
                "impact_level": impact_level,
                "decay_rate": decay_rate,
                "status": "active",
                "affected_habits": affected_habit_ids,
                "conversation_id": self.conversation_id,
                "created_at": firestore.SERVER_TIMESTAMP,
                "detected_at": firestore.SERVER_TIMESTAMP,
                "last_mentioned_at": firestore.SERVER_TIMESTAMP,
                "mention_count": 1,
                "resolved_at": None,
            }

            events_ref = (
                db.collection("users")
                .document(user_doc_id)
                .collection("exceptional_events")
            )
            new_event = events_ref.add(event_data)
            event_id = new_event[1].id

            logger.info(f"✅ Created exceptional event: {event_id}")

            return f"I've noted that you're dealing with {title}. I'll keep this in mind when we talk about your habits and progress."

        except Exception as e:
            logger.error(f"❌ Error creating exceptional event: {e}")
            return f"I understand about {title}. I'll remember to be understanding about this."

    @function_tool
    async def update_exceptional_event(
        self,
        context: RunContext,
        event_title: str,
        progress_note: str,
        feeling: str = "same",
    ):
        """Update an existing exceptional event with progress.

        Use this when the user mentions an update about a previous event.

        Args:
            event_title: The title of the event being updated
            progress_note: What the user said about their progress
            feeling: How they feel about it - "better", "worse", or "same"
        """
        if not self.user_data.get("user_doc_id"):
            return "Thanks for the update! I hope things improve soon."

        logger.info(f"📝 Updating exceptional event: {event_title}")

        if db is None:
            return "Thanks for letting me know how you're doing."

        try:
            user_doc_id = self.user_data["user_doc_id"]
            events_ref = (
                db.collection("users")
                .document(user_doc_id)
                .collection("exceptional_events")
            )

            # Find event by title
            event_docs = list(
                events_ref.where("title", "==", event_title)
                .where("status", "in", ["active", "improving"])
                .limit(1)
                .stream()
            )

            if not event_docs:
                return f"I don't have a record of '{event_title}'. Would you like me to create it as a new event?"

            event_doc = event_docs[0]
            event_id = event_doc.id
            event_data = event_doc.to_dict()

            # Calculate impact change based on feeling
            current_impact = event_data.get("impact_level", 0.5)
            impact_changes = {"better": -0.2, "worse": 0.2, "same": 0.0}
            impact_change = impact_changes.get(feeling, 0.0)
            new_impact = max(0.0, min(1.0, current_impact + impact_change))

            # Determine new status
            new_status = event_data.get("status", "active")
            if feeling == "better" and new_impact < 0.3:
                new_status = "improving"
            elif feeling == "worse":
                new_status = "active"

            # Update event
            update_data = {
                "impact_level": new_impact,
                "status": new_status,
                "last_mentioned_at": firestore.SERVER_TIMESTAMP,
                "mention_count": event_data.get("mention_count", 1) + 1,
            }

            # Mark as resolved if impact is very low
            if new_impact < 0.05:
                update_data["status"] = "resolved"
                update_data["resolved_at"] = firestore.SERVER_TIMESTAMP

            events_ref.document(event_id).update(update_data)

            # Log update in subcollection
            update_entry = {
                "conversation_id": self.conversation_id,
                "note": progress_note,
                "impact_change": impact_change,
                "timestamp": firestore.SERVER_TIMESTAMP,
            }
            events_ref.document(event_id).collection("updates").add(update_entry)

            logger.info(f"✅ Updated exceptional event {event_id}")

            if feeling == "better":
                if new_status == "resolved":
                    return f"That's wonderful! It sounds like {event_title} is behind you now."
                else:
                    return (
                        f"I'm glad to hear you're feeling better about {event_title}!"
                    )
            elif feeling == "worse":
                return f"I'm sorry to hear that {event_title} is still challenging. Take care of yourself."
            else:
                return f"Thanks for the update on {event_title}."

        except Exception as e:
            logger.error(f"❌ Error updating exceptional event: {e}")
            return "Thanks for sharing how you're doing."

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


async def save_message_to_conversation(
    conversation_id: str,
    user_id: str,
    role: str,
    message: str,
    tool_calls: list = None,
) -> None:
    """Save a message to the conversation's messages subcollection in Firestore.

    Args:
        conversation_id: The ID of the conversation document
        user_id: The ID of the user document (can be None)
        role: Either 'user' or 'assistant'
        message: The message text
        tool_calls: Optional list of tool calls associated with this message
    """
    if db is None:
        return

    try:
        # Create message document in conversation's messages subcollection
        # Only include tool_calls if there are actual tool calls
        message_doc = {
            "role": role,
            "message": message,
            "user_id": user_id,
            "timestamp": firestore.SERVER_TIMESTAMP,
        }

        # Add tool_calls field only if we have tool calls (keeps Firebase cleaner)
        if tool_calls and len(tool_calls) > 0:
            message_doc["tool_calls"] = tool_calls

        # Add to the messages subcollection
        message_ref = (
            db.collection("conversations")
            .document(conversation_id)
            .collection("messages")
            .add(message_doc)
        )
        message_id = message_ref[1].id

        # Update the conversation document with latest message info
        db.collection("conversations").document(conversation_id).update(
            {
                "last_message": message,
                "last_message_role": role,
                "last_message_id": message_id,  # Reference to the message in subcollection
                "last_message_at": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
        )

        if tool_calls and len(tool_calls) > 0:
            logger.info(
                f"💬 Saved {role} message with {len(tool_calls)} tool call(s) to conversation {conversation_id}/messages (ID: {message_id})"
            )
            for tc in tool_calls:
                logger.info(f"   🔧 {tc['name']}: {tc.get('arguments', {})}")
        else:
            logger.info(
                f"💬 Saved {role} message to conversation {conversation_id}/messages (ID: {message_id})"
            )
    except Exception as e:
        logger.error(f"❌ Error saving message to conversation: {e}")
        import traceback

        logger.error(traceback.format_exc())


def calculate_current_impact(event: dict) -> float:
    """Calculate the current impact of an exceptional event based on decay.

    Args:
        event: Event dictionary with impact_level, decay_rate, created_at, etc.

    Returns:
        Current impact level (0.0 - 1.0)
    """
    try:
        # Get timestamps
        created_at = event.get("created_at")
        last_mentioned_at = event.get("last_mentioned_at", created_at)

        if not created_at:
            return event.get("impact_level", 0.5)

        # Calculate days elapsed
        now = datetime.now()
        if hasattr(created_at, "timestamp"):
            created_timestamp = created_at
        else:
            created_timestamp = created_at

        days_since_created = (
            (now - created_timestamp).days if hasattr(created_timestamp, "days") else 0
        )

        # Decay rates
        decay_rates = {"fast": 0.1, "medium": 0.05, "slow": 0.02}
        decay_factor = decay_rates.get(event.get("decay_rate", "medium"), 0.05)

        # Calculate decayed impact
        base_impact = event.get("impact_level", 0.5)
        impact = base_impact * ((1 - decay_factor) ** days_since_created)

        # Clamp between 0 and 1
        return max(0.0, min(1.0, impact))
    except Exception as e:
        logger.error(f"Error calculating impact: {e}")
        return event.get("impact_level", 0.5)


async def get_active_exceptional_events(
    user_doc_id: str, lookback_days: int = 30
) -> list:
    """Get exceptional events from the last N days with meaningful impact.

    Args:
        user_doc_id: The user's document ID
        lookback_days: How many days back to look for events

    Returns:
        List of event dictionaries with current_impact calculated
    """
    if db is None or not user_doc_id:
        return []

    try:
        cutoff_date = datetime.now() - timedelta(days=lookback_days)

        events_ref = (
            db.collection("users")
            .document(user_doc_id)
            .collection("exceptional_events")
        )

        # Get active and improving events
        events_docs = events_ref.where("status", "in", ["active", "improving"]).stream()

        events = []
        for doc in events_docs:
            event = doc.to_dict()
            event["id"] = doc.id

            # Calculate current impact with decay
            event["current_impact"] = calculate_current_impact(event)

            # Only include if still has meaningful impact
            if event["current_impact"] > 0.1:
                events.append(event)

        logger.info(
            f"🚨 Loaded {len(events)} active exceptional events for user {user_doc_id}"
        )
        return events
    except Exception as e:
        logger.error(f"❌ Error loading exceptional events: {e}")
        return []


async def get_user_habits(user_doc_id: str) -> list:
    """Get all active habits for a user from Firestore.

    Args:
        user_doc_id: The user's document ID

    Returns:
        List of habit dictionaries
    """
    if db is None or not user_doc_id:
        return []

    try:
        habits_ref = db.collection("users").document(user_doc_id).collection("habits")
        habits_query = habits_ref.where("status", "==", "active")
        habits_docs = habits_query.stream()

        habits = []
        for doc in habits_docs:
            habit_data = doc.to_dict()
            habit_data["id"] = doc.id
            habits.append(habit_data)

        logger.info(f"📋 Loaded {len(habits)} active habits for user {user_doc_id}")
        return habits
    except Exception as e:
        logger.error(f"❌ Error loading user habits: {e}")
        return []


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
    user_doc_id = None
    existing_habits = []
    exceptional_events = []

    if phone_number:
        user_info = await lookup_user_by_phone(phone_number)
        if user_info:
            user_name = user_info.get("name")
            user_doc_id = user_info.get("doc_id")
            logger.info(f"👤 User identified: {user_name}")

            # Load existing habits for this user
            existing_habits = await get_user_habits(user_doc_id)

            # Load active exceptional events
            exceptional_events = await get_active_exceptional_events(user_doc_id)
        else:
            logger.info(f"👤 New user - phone number not in database: {phone_number}")

    # Create conversation document in Firebase
    conversation_id = None
    if db is not None:
        try:
            # Create the conversation document
            conversation_doc = {
                "job_id": ctx.job.id,
                "room_name": ctx.room.name,
                "phone_number": phone_number,
                "user_name": user_name,  # Will be None if user not found
                "user_id": user_doc_id,  # Link to user document for easy queries
                "started_at": firestore.SERVER_TIMESTAMP,
                "ended_at": None,
                "status": "active",
                "last_message": None,
                "last_message_role": None,
                "last_message_id": None,  # Will point to latest message doc
                "last_message_at": None,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
            doc_ref = db.collection("conversations").add(conversation_doc)
            conversation_id = doc_ref[1].id
            logger.info(f"💬 Created conversation in Firestore (ID: {conversation_id})")

            # Also log to call_sessions for tracking
            session_doc = {
                "job_id": ctx.job.id,
                "room_name": ctx.room.name,
                "phone_number": phone_number,
                "user_name": user_name,
                "conversation_id": conversation_id,
                "metadata": ctx.job.metadata or "",
                "started_at": firestore.SERVER_TIMESTAMP,
                "agent_type": "onboarding",
            }
            db.collection("call_sessions").add(session_doc)

        except Exception as e:
            logger.error(f"❌ Error creating conversation: {e}")
    else:
        logger.warning("⚠️  Firebase not initialized - conversation not logged")

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

    # Track recent tool calls to associate with messages
    recent_tool_calls = []

    # Real-time conversation logging
    @session.on("function_tools_executed")
    def _on_tools_executed(ev: FunctionToolsExecutedEvent):
        """Triggered when function tools are executed."""
        nonlocal recent_tool_calls

        try:
            # Capture tool call information
            for func_call, func_output in ev.zipped():
                # Extract tool call data
                tool_call_data = {
                    "name": func_call.name,
                    "arguments": func_call.arguments,
                    "output": str(func_output.output) if func_output.output else None,
                }

                recent_tool_calls.append(tool_call_data)
                logger.info(f"🔧 Tool executed: {func_call.name}")
                logger.info(f"   Arguments: {func_call.arguments}")
                logger.info(
                    f"   Output: {str(func_output.output)[:100] if func_output.output else 'None'}"
                )
                logger.info(
                    f"   Captured in recent_tool_calls (count: {len(recent_tool_calls)})"
                )
        except Exception as e:
            logger.error(f"❌ Error in function_tools_executed handler: {e}")
            import traceback

            logger.error(traceback.format_exc())

    @session.on("conversation_item_added")
    def _on_conversation_item(ev: ConversationItemAddedEvent):
        """Triggered when user or agent message is committed to chat history."""
        nonlocal recent_tool_calls

        if not conversation_id:
            return

        try:
            # ev.item is a ChatMessage with role and content
            role = ev.item.role  # "user" or "assistant"
            message_text = ev.item.text_content  # The message text

            logger.info(
                f"📝 conversation_item_added event: role={role}, recent_tool_calls count={len(recent_tool_calls)}"
            )

            if message_text:
                # Associate tool calls with assistant messages
                tool_calls_to_save = None
                if role == "assistant":
                    if recent_tool_calls:
                        tool_calls_to_save = recent_tool_calls.copy()
                        logger.info(
                            f"🔧 Associating {len(tool_calls_to_save)} tool call(s) with message"
                        )
                        logger.info(
                            f"   Tool calls: {[tc['name'] for tc in tool_calls_to_save]}"
                        )
                        recent_tool_calls.clear()  # Clear for next message
                    else:
                        logger.info(
                            f"💬 No recent tool calls to associate with assistant message"
                        )

                logger.info(f"💬 Saving {role} message: {message_text[:50]}...")
                import asyncio

                asyncio.create_task(
                    save_message_to_conversation(
                        conversation_id,
                        user_doc_id,
                        role,
                        message_text,
                        tool_calls=tool_calls_to_save,
                    )
                )
        except Exception as e:
            logger.error(f"❌ Error in conversation_item_added handler: {e}")
            import traceback

            logger.error(traceback.format_exc())

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    async def end_conversation():
        """Mark conversation as ended in Firebase."""
        if conversation_id and db is not None:
            try:
                db.collection("conversations").document(conversation_id).update(
                    {"ended_at": firestore.SERVER_TIMESTAMP, "status": "completed"}
                )
                logger.info(f"💬 Marked conversation {conversation_id} as completed")
            except Exception as e:
                logger.error(f"❌ Error ending conversation: {e}")

    ctx.add_shutdown_callback(log_usage)
    ctx.add_shutdown_callback(end_conversation)

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
        agent=Assistant(
            user_name=user_name,
            user_phone=phone_number,
            user_doc_id=user_doc_id,
            conversation_id=conversation_id,
            existing_habits=existing_habits,
            exceptional_events=exceptional_events,
        ),
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
