# Exceptional Events System - Implementation Plan

## Overview
Track temporary life events (injuries, illness, travel, stress, etc.) that should influence habit coaching and recommendations over time.

---

## Database Structure

### Collection: `users/{user_id}/exceptional_events`

Each event document:
```javascript
{
  // Identification
  event_id: "auto-generated",
  event_type: "injury" | "illness" | "travel" | "work_stress" | "family_event" | "other",
  
  // Details
  title: "Knee injury from running",
  description: "Twisted knee during morning jog, experiencing pain",
  severity: "low" | "medium" | "high",
  
  // Timing
  created_at: timestamp,
  detected_at: timestamp,  // When first mentioned
  resolved_at: timestamp | null,  // When user says it's better
  
  // Status & Decay
  status: "active" | "improving" | "resolved",
  impact_level: 0.0 - 1.0,  // Current impact (1.0 = full impact, 0.0 = no impact)
  decay_rate: "fast" | "medium" | "slow",  // How quickly impact diminishes
  
  // Context
  affected_habits: ["habit_id_1", "habit_id_2"],  // Which habits are impacted
  conversation_id: "where it was first mentioned",
  
  // Updates tracking
  last_mentioned_at: timestamp,
  mention_count: number,
  
  updates/  // Subcollection
    update_id/
      conversation_id: "conv_xyz",
      note: "Feeling a bit better today",
      impact_change: -0.2,  // Decrease in impact
      timestamp: timestamp
}
```

---

## Impact Decay System

### Decay Strategies

**1. Time-based Decay**
- Events naturally lose impact over time if not mentioned
- Decay rate depends on event type:
  - Fast: Common cold (7-14 days to minimal impact)
  - Medium: Minor injury (2-4 weeks)
  - Slow: Major injury, chronic stress (6-12 weeks)

**2. Mention-based Updates**
- User mentions → reassess impact level
- "Feeling better" → reduce impact
- "Still struggling" → maintain or increase impact
- No mention for X days → automatic slow decay

**3. Resolution Tracking**
- User explicitly says "I'm better" → mark as improving
- Impact drops to near-zero → auto-resolve
- Resolved events kept for 90 days for context

### Decay Formula
```python
def calculate_current_impact(event):
    days_since_created = (now - event.created_at).days
    days_since_mentioned = (now - event.last_mentioned_at).days
    
    # Base decay
    decay_factor = {
        'fast': 0.1,    # 10% per day
        'medium': 0.05, # 5% per day  
        'slow': 0.02    # 2% per day
    }[event.decay_rate]
    
    # Additional decay if not mentioned
    if days_since_mentioned > 7:
        decay_factor *= 1.5
    
    # Calculate decayed impact
    impact = event.impact_level * (1 - decay_factor) ** days_since_created
    
    # User updates can override
    if has_recent_positive_update:
        impact *= 0.7
    elif has_recent_negative_update:
        impact *= 1.2
    
    return max(0.0, min(1.0, impact))
```

---

## Agent Integration

### 1. Load Exceptional Events at Conversation Start

```python
async def get_active_exceptional_events(user_doc_id: str, lookback_days: int = 30):
    """Get exceptional events from the last N days with impact > 0.1"""
    cutoff_date = now - timedelta(days=lookback_days)
    
    events_ref = db.collection("users").document(user_doc_id).collection("exceptional_events")
    query = events_ref.where("created_at", ">=", cutoff_date)
                     .where("status", "in", ["active", "improving"])
    
    events = []
    for doc in query.stream():
        event = doc.to_dict()
        event['id'] = doc.id
        
        # Calculate current impact
        event['current_impact'] = calculate_current_impact(event)
        
        # Only include if still has meaningful impact
        if event['current_impact'] > 0.1:
            events.append(event)
    
    return events
```

### 2. Include in Agent Instructions

```python
# Build exceptional events context
if exceptional_events:
    events_context = "\n".join([
        f"   - {e['title']} (impact: {e['current_impact']:.0%}, affects: {e['affected_habits']})"
        for e in exceptional_events
    ])
    exceptional_context = f"""

EXCEPTIONAL EVENTS:
The user is dealing with these temporary situations:
{events_context}

Take these into account when:
- Asking about habit progress
- Suggesting new activities
- Celebrating achievements (be understanding of setbacks)
- Use the update_exceptional_event tool when they mention progress

For example:
- If injured, don't push hard on exercise habits
- If traveling, acknowledge disrupted routines
- If stressed, be extra supportive
"""
```

### 3. Agent Tools

**Create Event:**
```python
@function_tool
async def create_exceptional_event(
    self,
    context: RunContext,
    event_type: str,
    title: str,
    description: str,
    severity: str = "medium",
    affected_habit_names: list = None
):
    """Record a new exceptional event (injury, illness, travel, etc.)"""
    # Lookup affected habit IDs from names
    # Set initial impact based on severity
    # Determine decay rate from event type
    # Save to Firestore
```

**Update Event:**
```python
@function_tool
async def update_exceptional_event(
    self,
    context: RunContext,
    event_title: str,
    progress_note: str,
    feeling: str  # "better" | "worse" | "same"
):
    """Log an update on an existing exceptional event"""
    # Find event by title
    # Adjust impact_level based on feeling
    # Create update in subcollection
    # Update last_mentioned_at
```

**Auto-resolve Events:**
```python
# Run periodically or at conversation start
async def auto_resolve_events(user_doc_id: str):
    """Auto-resolve events with very low impact"""
    events = get_all_events(user_doc_id)
    
    for event in events:
        if event['current_impact'] < 0.05:
            event_ref.update({
                'status': 'resolved',
                'resolved_at': firestore.SERVER_TIMESTAMP
            })
```

---

## Query Patterns for UI

### Get Active Events
```javascript
// Dashboard: Show current events affecting user
const eventsRef = collection(db, 'users', userId, 'exceptional_events');
const q = query(
  eventsRef,
  where('status', 'in', ['active', 'improving']),
  orderBy('impact_level', 'desc')
);
```

### Event History
```javascript
// User profile: Show resolved events from last 90 days
const cutoff = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000);
const q = query(
  eventsRef,
  where('created_at', '>=', cutoff),
  orderBy('created_at', 'desc')
);
```

### Events Affecting Specific Habit
```javascript
// Habit detail page: Show events impacting this habit
const q = query(
  eventsRef,
  where('affected_habits', 'array-contains', habitId),
  where('status', '!=', 'resolved')
);
```

---

## Use Cases & Examples

### Example 1: Running Injury

**Day 1 - User mentions:**
> "I hurt my knee yesterday while running"

**Agent creates event:**
```javascript
{
  event_type: "injury",
  title: "Knee injury",
  severity: "medium",
  impact_level: 0.8,
  decay_rate: "medium",
  affected_habits: ["running_habit_id"]
}
```

**Day 3 - Agent checks in:**
> "How's your knee feeling? I know that's been limiting your running."

**Day 7 - User update:**
> "It's feeling better, I went for a light walk today"

**Agent updates:**
```javascript
{
  impact_level: 0.5,  // Reduced
  updates: [
    { note: "Feeling better, went for light walk", impact_change: -0.3 }
  ]
}
```

**Day 21 - Auto-decay:**
```javascript
{
  current_impact: 0.12,  // Decayed over time
  status: "improving"
}
```

**Day 30 - Auto-resolve:**
```javascript
{
  current_impact: 0.03,
  status: "resolved",
  resolved_at: timestamp
}
```

### Example 2: Work Stress

**Week 1:**
> "I'm really stressed with this big project at work"

```javascript
{
  event_type: "work_stress",
  title: "Big project stress",
  severity: "high",
  impact_level: 0.9,
  decay_rate: "slow",  // Stress lingers
  affected_habits: ["meditation_habit", "sleep_habit"]
}
```

**Agent adaptation:**
- More understanding about meditation lapses
- Acknowledges sleep disruptions
- Doesn't push too hard on new habits

**Week 4:**
> "The project wrapped up, feeling relieved!"

```javascript
{
  impact_level: 0.3,  // Sharp drop
  status: "improving"
}
```

---

## Implementation Steps

### Phase 1: Core System (Week 1)
1. Create database schema
2. Implement `create_exceptional_event` tool
3. Implement `update_exceptional_event` tool
4. Add event loading to conversation start
5. Basic agent instructions integration

### Phase 2: Decay & Auto-Resolution (Week 2)
1. Implement impact calculation function
2. Auto-decay based on time
3. Auto-resolve low-impact events
4. Scheduled cleanup job

### Phase 3: Smart Features (Week 3)
1. Habit impact analysis
2. Automatic event type detection from conversation
3. Smart suggestions (e.g., suggest recovery habits for injuries)
4. Event-aware progress tracking

### Phase 4: UI Integration (Week 4)
1. Display active events in dashboard
2. Event timeline visualization
3. Habit-event correlation charts
4. Manual event management

---

## Benefits

✅ **Context-Aware Coaching** - Agent understands temporary setbacks
✅ **Realistic Expectations** - Don't punish users for injury/illness-related gaps
✅ **Better Insights** - Track how life events affect habit formation
✅ **Personalized Support** - Adapt recommendations to user's current situation
✅ **Long-term Patterns** - Identify recurring stressors or seasonal issues
✅ **Compassionate AI** - Shows empathy for user's circumstances

---

## Future Enhancements

- **Predictive Events**: Detect patterns (e.g., seasonal allergies, monthly stress)
- **Event Chains**: Track how one event leads to others
- **Habit Resilience Score**: How well habits survive disruptions
- **Recovery Recommendations**: Suggest specific habits to aid recovery
- **Social Events**: Track positive exceptional events (vacation, celebrations)
- **Medical Integration**: Connect with health apps for injury/illness data

