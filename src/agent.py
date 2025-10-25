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


google_sched = """
{
    "events": [
        {
            "id": "0a8fjthpeb1uibr8h83ldmvd37",
            "summary": "Meal Prep",
            "start": "2025-10-26T11:00:00+09:00",
            "end": "2025-10-26T13:00:00+09:00",
            "description": "<ul><li>Prep meals for the week</li><li>   •        •    <b>Note:</b> Good intention, rarely happens</li></ul>"
        },
        {
            "id": "6q3fai2bcc3732fct3l3uij9og",
            "summary": "Flowers for mom",
            "start": "2025-10-26T15:00:00+09:00",
            "end": "2025-10-26T16:00:00+09:00",
            "description": "My monthly gift for mom"
        },
        {
            "id": "0d9j4sjh73ehcr8q6o6joa5jut",
            "summary": "Church",
            "start": "2025-10-26T18:00:00+09:00",
            "end": "2025-10-26T20:00:00+09:00",
            "description": "Pastor Tim will be doing service today"
        },
        {
            "id": "79fanh7vghbqgs08et7grjkn5k",
            "summary": "Weekly Team Standup",
            "start": "2025-10-27T09:00:00+09:00",
            "end": "2025-10-27T09:30:00+09:00",
            "description": "<ul><li>Weekly sync on sprint progress</li></ul>"
        },
        {
            "id": "0opsa53q7cui9288qt21ciaqbk",
            "summary": "Product Roadmap Review",
            "start": "2025-10-27T10:00:00+09:00",
            "end": "2025-10-27T11:00:00+09:00",
            "description": "<ul><li>Q4 roadmap priorities and resource allocation</li></ul><p>    •        •    <b>Notes:</b> ⚠️ Need to finalize slides and review Q3 metrics</p>"
        },
        {
            "id": "49e68q1fg903mu7l40nr4slk9o",
            "summary": "1:1 with Jordan (Designer)",
            "start": "2025-10-27T11:30:00+09:00",
            "end": "2025-10-27T12:00:00+09:00",
            "description": "<ul><li>Weekly 1:1 - design feedback and career development</li></ul>"
        },
        {
            "id": "2f2jsok45th3gds9892pecqckl",
            "summary": "User Research Debrief",
            "start": "2025-10-27T14:00:00+09:00",
            "end": "2025-10-27T15:00:00+09:00",
            "description": "<ul><li>Review findings from last week's user interviews</li></ul>"
        },
        {
            "id": "361qf4sal3qk7svdf5um52jsb0",
            "summary": "Sprint Planning",
            "start": "2025-10-27T15:30:00+09:00",
            "end": "2025-10-27T17:00:00+09:00",
            "description": "<ul><li>Sprint 23 planning - story estimation and commitment</li></ul>"
        },
        {
            "id": "0j354i68u5kkrejklq6vtjfl8j",
            "summary": "Gym - Olympic Lifts",
            "start": "2025-10-27T20:00:00+09:00",
            "end": "2025-10-27T22:00:00+09:00",
            "description": "I need to eat a lot of fruit before this session"
        },
        {
            "id": "7lseqohq3mr02j1h2ltbme6odd",
            "summary": "Marketing Sync",
            "start": "2025-10-28T09:30:00+09:00",
            "end": "2025-10-28T10:00:00+09:00",
            "description": "<ul><li>Product marketing alignment for upcoming launch</li></ul>"
        },
        {
            "id": "2na5tq7q1e44667d0s0lon09es",
            "summary": "Customer Call - Acme Corp",
            "start": "2025-10-28T10:30:00+09:00",
            "end": "2025-10-28T11:30:00+09:00",
            "description": "<ul><li>Enterprise customer feedback session - integration pain points</li></ul><p>    •        •    <b>Notes:</b> ⚠️ Review their support tickets and feature requests</p>"
        },
        {
            "id": "4bjiv531th998tl2etronp4u59",
            "summary": "LUNCH - blocked",
            "start": "2025-10-28T12:00:00+09:00",
            "end": "2025-10-28T12:30:00+09:00",
            "description": "<ul><li>Personal - lunch break</li><li>   •        •    <b>Note:</b> You historically cancel this for meetings</li></ul>"
        },
        {
            "id": "2tl15naju1u8ochmu9o92k6kga",
            "summary": "Engineering Architecture Discussion",
            "start": "2025-10-28T13:00:00+09:00",
            "end": "2025-10-28T14:00:00+09:00",
            "description": "<ul><li><b>Description:</b> Technical approach for notification system redesign</li></ul>"
        },
        {
            "id": "3o7vdumikssm61ufee6td5gb7k",
            "summary": "Competitive Analysis Workshop",
            "start": "2025-10-28T14:30:00+09:00",
            "end": "2025-10-28T16:00:00+09:00",
            "description": "<ul><li>Deep dive on competitor features and market positioning</li></ul>"
        },
        {
            "id": "5kco1hkeokhbo5gujspr4llnjd",
            "summary": "Leadership Coffee Chat",
            "start": "2025-10-28T16:00:00+09:00",
            "end": "2025-10-28T17:00:00+09:00",
            "description": "<ul><li>Informal check-in</li></ul>"
        },
        {
            "id": "27ua9ure01dub8cp97ccg4ag8o",
            "summary": "Drop dog off at groomer",
            "start": "2025-10-28T19:00:00+09:00",
            "end": "2025-10-28T20:00:00+09:00",
            "description": "Missy's hair is getting too long"
        },
        {
            "id": "617l34o4ms6reqf6gv4nl7qkap",
            "summary": "Meditation",
            "start": "2025-10-28T21:00:00+09:00",
            "end": "2025-10-28T21:30:00+09:00",
            "description": "My weekly re-sync"
        },
        {
            "id": "3n2ekq1kcagb7q8kgiqdb6do0p",
            "summary": "Weekly Team Standup",
            "start": "2025-10-29T09:00:00+09:00",
            "end": "2025-10-29T09:30:00+09:00",
            "description": "<ul><li>Weekly sync on sprint progress</li></ul>"
        },
        {
            "id": "3d7uhin55ujf3s44khrm4t1d7r",
            "summary": "Product Strategy Session",
            "start": "2025-10-29T10:00:00+09:00",
            "end": "2025-10-29T12:00:00+09:00",
            "description": "<ul><li>2026 vision and long-term strategy planning</li></ul><p>    •        •    <b>Notes:</b> ⚠️ Bring ideas for new verticals</p>"
        },
        {
            "id": "7d1lii8oauua68i3ll0962encj",
            "summary": "FOCUS TIME - Product Spec",
            "start": "2025-10-29T13:00:00+09:00",
            "end": "2025-10-29T15:00:00+09:00",
            "description": "<ul><li>Deep work: finish notification system spec</li><li>   •        •    <b>Note:</b> Protected time - created 2 weeks ago but keep getting meeting requests</li></ul>"
        },
        {
            "id": "69l9ancb7m9p8h65bd394ordvm",
            "summary": "Design Review",
            "start": "2025-10-29T15:00:00+09:00",
            "end": "2025-10-29T16:30:00+09:00",
            "description": "<ul><li>Weekly design critique and feedback</li></ul>"
        },
        {
            "id": "7g6tdhj4l18hl5mn3v0ie5mi5r",
            "summary": "Dinner Date",
            "start": "2025-10-29T18:00:00+09:00",
            "end": "2025-10-29T19:00:00+09:00",
            "description": "Third time meeting up with Stacy"
        },
        {
            "id": "7s1to8fmv3ev3crhafh6r5cumm",
            "summary": "All-Hands Meeting",
            "start": "2025-10-30T09:00:00+09:00",
            "end": "2025-10-30T10:00:00+09:00",
            "description": "<ul><li>Monthly company-wide update from CEO</li></ul>"
        },
        {
            "id": "0du8k9rkh8o2crp1ch8tlkqvve",
            "summary": "Vendor Demo - Analytics Tool",
            "start": "2025-10-30T10:30:00+09:00",
            "end": "2025-10-30T11:30:00+09:00",
            "description": "<ul><li>Evaluating new product analytics platform</li></ul>"
        },
        {
            "id": "0o9qk6v7j8thgidcrcotampch7",
            "summary": "Budget Planning Q1",
            "start": "2025-10-30T13:00:00+09:00",
            "end": "2025-10-30T14:00:00+09:00",
            "description": "<ul><li>2026 Q1 budget allocation and headcount planning</li></ul><p>    •        •    <b>Notes:</b> ⚠️ Need to submit team priorities by end of week</p>"
        },
        {
            "id": "5s28clodfivonhaes1j44tbts5",
            "summary": "User Testing Observation",
            "start": "2025-10-30T15:00:00+09:00",
            "end": "2025-10-30T16:00:00+09:00",
            "description": "<ul><li>Watch users test new onboarding flow</li></ul>"
        },
        {
            "id": "6172aeuabc3plo5oftjn7995at",
            "summary": "URGENT: Bug Triage",
            "start": "2025-10-30T16:30:00+09:00",
            "end": "2025-10-30T17:30:00+09:00",
            "description": "<ul><li>Critical production bug affecting enterprise customers</li><li>   •        •    <b>Note:</b> Last-minute addition - added at 3:45 PM same day</li></ul>"
        },
        {
            "id": "7747deq5hmlbn8t5netuhhifu3",
            "summary": "Movie with the guys",
            "start": "2025-10-30T20:00:00+09:00",
            "end": "2025-10-30T22:00:00+09:00",
            "description": "Our weekly catch up and unwind"
        },
        {
            "id": "3ltfmro11s44c1nh2d1b5q9u2u",
            "summary": "Weekly Team Standup",
            "start": "2025-10-31T09:00:00+09:00",
            "end": "2025-10-31T09:30:00+09:00",
            "description": "<ul><li>Weekly sync on sprint progress</li></ul>"
        },
        {
            "id": "77p27eiabqgnck4gt35c8612dt",
            "summary": "Sprint Retro",
            "start": "2025-10-31T10:00:00+09:00",
            "end": "2025-10-31T11:00:00+09:00",
            "description": "<ul><li>Sprint 22 retrospective - what went well, what to improve</li></ul>"
        },
        {
            "id": "40sea5k2tqhfgciai8980r4tg4",
            "summary": "1:1 with Manager",
            "start": "2025-10-31T11:30:00+09:00",
            "end": "2025-10-31T12:00:00+09:00",
            "description": "<ul><li>Weekly 1:1 - projects, blockers, career development</li></ul>"
        },
        {
            "id": "43om9cvpp6mqi64rb9ftb0pi8i",
            "summary": "Product Demo - Internal",
            "start": "2025-10-31T14:00:00+09:00",
            "end": "2025-10-31T15:00:00+09:00",
            "description": "<ul><li>Show recent features to internal stakeholders</li></ul>"
        },
        {
            "id": "0vcnb3jds4ecnmoqc57q1j57n3",
            "summary": "FOCUS TIME - Catch up",
            "start": "2025-10-31T15:30:00+09:00",
            "end": "2025-10-31T17:00:00+09:00",
            "description": "<ul><li>Finish anything that slipped this week</li><li>   •        •    <b>Note:</b> Optimistically created but usually given up</li></ul>"
        },
        {
            "id": "5lj6vcmkdbpqugvbb7t8j0amn3",
            "summary": "Dentist Appointment",
            "start": "2025-11-01T10:00:00+09:00",
            "end": "2025-11-01T11:00:00+09:00",
            "description": "<ul><li>Regular checkup - overdue by 3 months</li><li>   •        •    <b>Note:</b> Rescheduled twice already</li></ul>"
        },
        {
            "id": "601m8acmfddehu912agngp1lb3",
            "summary": "Gym - blocked",
            "start": "2025-11-01T14:00:00+09:00",
            "end": "2025-11-01T15:00:00+09:00",
            "description": "<ul><li>Weekend workout</li></ul>"
        }
    ]
}
"""

google_tasks = """
{
    "tasks": [
        {
            "id": "U3pBbUo4MVVpby1vdGRyYQ",
            "title": "10. Competitive analysis doc",
            "listName": "My Tasks",
            "listId": "MDI4NTUyMTU1MzcwODQ3MjUzNjc6MDow",
            "status": "needsAction",
            "due": "2025-10-29T00:00:00.000Z",
            "notes": "* Notes: Started research but haven't written anything up yet\n",
            "updated": "2025-10-25T06:46:48.695Z"
        },
        {
            "id": "blAzb1l4RkpWSTdDeU96Mw",
            "title": "9. Update PRD for mobile app redesign",
            "listName": "My Tasks",
            "listId": "MDI4NTUyMTU1MzcwODQ3MjUzNjc6MDow",
            "status": "needsAction",
            "due": "2025-10-30T00:00:00.000Z",
            "notes": "* Notes: Half done but lost momentum\n",
            "updated": "2025-10-25T06:46:32.279Z"
        },
        {
            "id": "cllpU2hTUlJEMkZHSk5FWg",
            "title": "8. Review sprint 23 tickets ⚠️",
            "listName": "My Tasks",
            "listId": "MDI4NTUyMTU1MzcwODQ3MjUzNjc6MDow",
            "status": "needsAction",
            "due": "2025-10-29T00:00:00.000Z",
            "notes": "* Notes: Need to groom backlog before Monday planning\n",
            "updated": "2025-10-25T06:46:17.720Z"
        },
        {
            "id": "YXZfX2F3aWQ1OEJTVS1BNg",
            "title": "7. Respond to Acme Corp feature requests",
            "listName": "My Tasks",
            "listId": "MDI4NTUyMTU1MzcwODQ3MjUzNjc6MDow",
            "status": "needsAction",
            "due": "2025-10-29T00:00:00.000Z",
            "notes": "* Notes: They sent 8 feature requests. Need to prioritize and respond diplomatically.\n",
            "updated": "2025-10-25T06:46:02.734Z"
        },
        {
            "id": "V281cHBCUWNLWjFyemp6Mg",
            "title": "6. Write performance reviews for direct reports 🔥",
            "listName": "My Tasks",
            "listId": "MDI4NTUyMTU1MzcwODQ3MjUzNjc6MDow",
            "status": "needsAction",
            "due": "2025-10-31T00:00:00.000Z",
            "notes": "* Notes: Dreading this. Have notes scattered everywhere.\n",
            "updated": "2025-10-25T06:45:49.182Z"
        },
        {
            "id": "Y0ZDYlVMRVFOWUY2akM3bQ",
            "title": "5. Submit budget headcount plan 🔥",
            "listName": "My Tasks",
            "listId": "MDI4NTUyMTU1MzcwODQ3MjUzNjc6MDow",
            "status": "needsAction",
            "due": "2025-10-28T00:00:00.000Z",
            "notes": "* Notes: Finance needs this by EOW. No idea what to ask for yet.\n",
            "updated": "2025-10-25T06:45:32.383Z"
        },
        {
            "id": "RDNoeFdNZXVHc18yRVpFYg",
            "title": "4. Write Q4 team goals 🔥",
            "listName": "My Tasks",
            "listId": "MDI4NTUyMTU1MzcwODQ3MjUzNjc6MDow",
            "status": "needsAction",
            "due": "2025-10-27T00:00:00.000Z",
            "notes": "* Notes: Manager has asked 3 times. This is getting embarrassing.\n",
            "updated": "2025-10-25T06:45:12.889Z"
        },
        {
            "id": "RGlCR2tBZjFwZFBmUWZpZw",
            "title": "3. Update roadmap deck for exec review 🔥",
            "listName": "My Tasks",
            "listId": "MDI4NTUyMTU1MzcwODQ3MjUzNjc6MDow",
            "status": "needsAction",
            "due": "2025-10-28T00:00:00.000Z",
            "notes": "* Notes: VP wants to see this before Thursday's all-hands\n",
            "updated": "2025-10-25T06:44:57.540Z"
        },
        {
            "id": "bGRqOS1iUEJQaU9YSGlpXw",
            "title": "Review Jordan's design mockups 🔥⚠️",
            "listName": "My Tasks",
            "listId": "MDI4NTUyMTU1MzcwODQ3MjUzNjc6MDow",
            "status": "needsAction",
            "due": "2025-10-28T00:00:00.000Z",
            "notes": "* Notes: Jordan needs feedback before Thursday. They're blocked.\n",
            "updated": "2025-10-25T06:44:32.668Z"
        },
        {
            "id": "X1I0c0dKMUZCWDVIQWRuWQ",
            "title": "1. Finish notification system product spec 🔥",
            "listName": "My Tasks",
            "listId": "MDI4NTUyMTU1MzcwODQ3MjUzNjc6MDow",
            "status": "needsAction",
            "due": "2025-10-27T00:00:00.000Z",
            "notes": "* Notes: Started but keep getting interrupted. Need 3-4 focused hours.\n* Subtasks:\n    * ✅ Define user stories (DONE)\n    * ⏳ Technical requirements doc (IN PROGRESS)\n    * ⏳ Get engineering review (NOT STARTED)",
            "updated": "2025-10-25T06:44:03.177Z"
        }
    ]
}
"""

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
        is_outbound: bool = True,
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

        # Different instructions for outbound (check-in) vs inbound (open) calls
        if is_outbound and has_habits:
            # Outbound call - directive check-in mode
            instructions = f"""You are a personal growth coach checking in with {user_name}. The user is interacting with you via voice.
            
            IMPORTANT: You must always speak in English, regardless of what language the user speaks to you in.
            
            YOU CALLED THEM for their daily check-in. Be direct and focused.{habits_context}{events_context}
            
            Your check-in flow (keep it tight and focused):
            
            1. FIRST: Call get_user_schedule and get_user_tasks to understand their calendar and to-do list
            
            2. Greet {user_name} warmly and briefly explain you're calling for their daily check-in
            
            3. IMMEDIATELY ask about their habits:
               - Go through each habit one by one
               - Ask: "How did you do with [habit name] today?"
               - Use log_habit_progress for each update they share
               - Keep questions direct and specific
            
            4. Check on exceptional events (if any):
               - Ask how they're feeling about each event
               - Use update_exceptional_event when they share updates
            
            5. Use context from their schedule and tasks to provide relevant coaching:
               - Reference upcoming deadlines or busy periods
               - Acknowledge workload when discussing habit challenges
               - Suggest time slots for habits based on their calendar
            
            6. Wrap up efficiently:
               - Encourage them briefly
               - Ask if there's anything else they need
               - Don't prolong the call unnecessarily
            
            Keep your responses:
            - Direct and focused (this is a check-in, not a long conversation)
            - Concise (1 sentence at a time)
            - Without complex formatting, emojis, or asterisks
            - Warm but efficient
            
            Move quickly through the check-in - respect their time."""
        else:
            # Inbound call or first-time user - open conversation mode
            instructions = f"""You are a personal growth coach helping users build better habits. The user is interacting with you via voice.
            
            IMPORTANT: You must always speak in English, regardless of what language the user speaks to you in.
            
            {"This is the user's first call with you." if is_new_user else "This user has called before."}{habits_context}{events_context}
            
            Your conversation flow:
            
            1. FIRST: Call get_user_schedule and get_user_tasks to understand their calendar and to-do list
            
            2. {name_instruction}
            
            3. {"Ask what habits they want to build or improve." if not has_habits else "Check in on their existing habits and see if they want to add new ones."}
               - Be curious and encouraging. Ask follow-up questions to understand their "why"
               - When they mention a specific habit they want to work on, use the create_or_update_habit tool to save it
               - When they share progress on an existing habit, use the log_habit_progress tool
               - If they mention an injury, illness, stress, or other temporary disruption, use create_exceptional_event tool
            
            4. Use context from their schedule and tasks to provide relevant coaching:
               - Reference upcoming deadlines or busy periods
               - Acknowledge workload when discussing habit challenges
               - Suggest time slots for habits based on their calendar
               - Help them prioritize and be realistic given their commitments
            
            5. Plan for today
               - Ask what they plan to do today to work toward their goals
               - Help them be specific and realistic
            
            Keep your responses:
            - Conversational and warm, not robotic  
            - Concise (1-2 sentences at a time)
            - Without complex formatting, emojis, or asterisks
            - Encouraging and supportive
            
            Move through the conversation naturally - don't rush, but don't linger too long on one topic."""

        super().__init__(instructions=instructions)
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
        self.is_outbound = is_outbound

    @function_tool
    async def get_user_schedule(self, context: RunContext):
        """Retrieve the user's Google Calendar schedule.

        Call this at the beginning of the conversation to understand what events
        the user has coming up. This helps provide context-aware coaching.

        Returns:
            JSON string containing the user's calendar events
        """
        logger.info("📅 Retrieving user's Google Calendar schedule")
        return google_sched

    @function_tool
    async def get_user_tasks(self, context: RunContext):
        """Retrieve the user's Google Tasks list.

        Call this at the beginning of the conversation to understand what tasks
        the user needs to complete. This helps provide context-aware coaching.

        Returns:
            JSON string containing the user's tasks
        """
        logger.info("✅ Retrieving user's Google Tasks")
        return google_tasks

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
    is_outbound_call = True

    # For testing in console mode: check for TEST_PHONE_NUMBER env var
    test_phone = os.getenv("TEST_PHONE_NUMBER")
    test_outbound = os.getenv("TEST_OUTBOUND_MODE", "").lower() in ("true", "1", "yes")

    if test_phone:
        phone_number = test_phone
        is_outbound_call = test_outbound
        logger.info(
            f"🧪 TEST MODE: Using phone number from environment: {phone_number}"
        )
        if test_outbound:
            logger.info(f"🧪 TEST MODE: Simulating outbound call (check-in mode)")

    # Otherwise get from metadata (production/real calls)
    if not test_phone:
        try:
            if ctx.job.metadata:
                metadata = json.loads(ctx.job.metadata)
                phone_number = metadata.get("phone_number")
                if phone_number:
                    is_outbound_call = (
                        True  # If phone_number in metadata, it's an outbound call
                    )
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
                "call_type": "outbound" if is_outbound_call else "inbound",
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
                "call_type": "outbound" if is_outbound_call else "inbound",
                "metadata": ctx.job.metadata or "",
                "started_at": firestore.SERVER_TIMESTAMP,
                "agent_type": "check_in" if is_outbound_call else "onboarding",
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
    logger.info(
        f"📋 Mode: {'Outbound check-in' if is_outbound_call else 'Inbound open conversation'}"
    )

    await session.start(
        agent=Assistant(
            user_name=user_name,
            user_phone=phone_number,
            user_doc_id=user_doc_id,
            conversation_id=conversation_id,
            existing_habits=existing_habits,
            exceptional_events=exceptional_events,
            is_outbound=is_outbound_call,
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

        # Greet based on call type
        if is_outbound_call and user_name and len(existing_habits) > 0:
            # Outbound check-in call - directive greeting
            await session.generate_reply(
                instructions=f"You're calling {user_name} for their daily check-in. Start immediately: Greet them warmly and say you're calling to check in on their habits. Then immediately ask about their first habit. Be direct and focused - this is a check-in, not a long chat."
            )
        elif user_name:
            # Inbound call with known user - warm greeting
            await session.generate_reply(
                instructions=f"Warmly greet {user_name} by name and start the conversation. Ask about their habits and goals. Keep it brief, friendly, and natural - like a coach starting a conversation."
            )
        else:
            # New user - onboarding
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
