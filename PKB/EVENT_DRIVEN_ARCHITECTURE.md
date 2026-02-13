# EVENT_DRIVEN_ARCHITECTURE.md
## TheKnowledgeOrbits — Event-Driven Architecture
**PKB File #11 | Version: 1.0 | Date: Feb 2026**

---

## 1. PURPOSE

Events are the ONLY sanctioned way engines communicate asynchronously.
This file defines:
- The event bus contract (how events move)
- Every registered event (name, payload, emitter, listeners)
- Event lifecycle (emit → deliver → process → ack)
- Phase 1 implementation (Django signals + Celery)
- Upgrade path for future phases

---

## 2. EVENT BUS CONTRACT

### Core Rules
```
1. Every event has a NAME (snake_case string)
2. Every event has a PAYLOAD (JSON-serializable dict)
3. Every event has exactly ONE emitter
4. Every event has one or more listeners
5. Emitter does NOT wait for listeners (fire-and-forget)
6. Listeners process events independently
7. Failed listener processing → retry per Section 4 rules in DATA_FLOW_PATTERNS
```

### shared/event_bus.py Interface
```python
# Emit — called by the engine that owns the action
event_bus.emit(
    event_name="quiz_completed",
    payload={ ... },
    source_engine="assessment"
)

# Listen — registered by engines that react
@event_bus.on("quiz_completed")
def handle_quiz_completed(payload: dict) -> None:
    ...
```

### Rules
- ❌ No engine calls another engine's listener directly
- ❌ No engine emits events it does not own
- ✅ Payload must be JSON-serializable (no model instances, no ORM objects)
- ✅ Payload must include all data the listener needs (no listener re-fetches from emitter's DB)
- ✅ Every event registered below before use in code

---

## 3. EVENT REGISTRY

### Phase 1 Events

#### quiz_completed
```
Emitter:  Assessment Engine (POST /assessment/submit-quiz)
Payload:  {
            "attempt_id": uuid,
            "user_id": uuid,
            "quiz_id": uuid,
            "topic_id": uuid,
            "score": float,
            "correct": int,
            "total": int,
            "difficulty_level": string,
            "submitted_at": timestamp
          }
Listeners:
  - User State Engine    → updates topic_mastery, increments total_quizzes_taken
  - Analytics Engine     → will aggregate into daily_aggregate (Phase 4+)
```

#### article_read
```
Emitter:  Frontend (POST /user-state/event with event_type="article_read")
Payload:  {
            "user_id": uuid,
            "article_id": uuid,
            "topic_id": uuid,
            "read_time_seconds": int,
            "read_at": timestamp
          }
Listeners:
  - User State Engine    → updates reading_progress, increments total_articles_read
  - Analytics Engine     → will aggregate into daily_aggregate (Phase 4+)
```

#### content_ingested
```
Emitter:  Content Engine (after ingestion_job completes successfully)
Payload:  {
            "document_id": uuid,
            "chunk_count": int,
            "source_type": "static" | "dynamic",
            "subject_id": uuid | null,
            "completed_at": timestamp
          }
Listeners:
  - Knowledge Engine     → signals admin that new chunks are ready for topic mapping
```

#### bookmark_added
```
Emitter:  User State Engine (POST /user-state/bookmark)
Payload:  {
            "user_id": uuid,
            "content_type": string,
            "content_id": uuid,
            "bookmarked_at": timestamp
          }
Listeners:
  - Analytics Engine     → tracks engagement signal (Phase 4+)
```

---

### Phase 2 Events

#### article_generated
```
Emitter:  Article Gen Engine (after async generation completes)
Payload:  {
            "article_id": uuid,
            "topic_id": uuid,
            "quality_score": float,
            "includes_ca": bool,
            "generated_at": timestamp
          }
Listeners:
  - Search Engine        → indexes new article (Phase 5+)
  - Notification Engine  → notifies subscribers of new content (Phase 5+)
```

#### ca_chunks_classified
```
Emitter:  Current Affairs Engine (after daily scrape + embed completes)
Payload:  {
            "ca_chunk_ids": [uuid],
            "topic_ids": [uuid],
            "classified_at": timestamp
          }
Listeners:
  - Article Gen Engine   → signals that new CA context is available for generation
```

---

### Phase 6+ Events (Reserved)

| Event Name | Emitter | Listeners | Phase |
|---|---|---|---|
| streak_broken | User State Engine | Notification, Retention | 6 |
| flashcard_due | Revision Engine | Notification | 6 |
| achievement_unlocked | Gamification Engine | Notification, Analytics | 6 |
| learning_path_updated | Personalization Engine | Notification | 7 |
| doubt_resolved | AI Tutor Engine | Analytics | 7 |
| mock_test_completed | Mock Test Engine | Prediction, Analytics | 8 |
| subscription_activated | Commerce Engine | Onboarding, Analytics | 5 |
| churn_risk_detected | Retention Engine | Notification | 9 |

---

## 4. EVENT LIFECYCLE

```
[Engine A completes action]
      ↓
  event_bus.emit(name, payload)        ← sync call, returns immediately
      ↓
  Event stored in Redis queue          ← durable, survives process restart
      ↓
  Celery worker picks up task          ← routes to correct listener(s)
      ↓
  Listener processes payload           ← writes to its OWN tables only
      ↓
  Success → ack (event removed)
  Failure → retry per backoff schedule
         → DLQ after 3 failures → Sentry alert
```

### Guarantees
- **At-least-once delivery** — event may be processed more than once on retry
- **Listeners must be idempotent** — duplicate processing must not corrupt state
- **Order not guaranteed** — listeners cannot assume event arrival order
- **Payload is immutable** — listener never modifies the event payload

---

## 5. PHASE 1 IMPLEMENTATION

Phase 1 runs as a monolith (single Django process). Full broker not yet needed.

```
shared/event_bus.py:
  - emit() → pushes task to Celery queue
  - @on() decorator → registers Celery task as listener
  - All events routed through a single Celery queue ("events")

Each engine's events.py:
  - Contains ONLY emit calls for events that engine owns
  - Contains ONLY @on handlers for events that engine listens to
  - Imports event_bus from shared — nothing else from shared
```

### Example: Assessment Engine emits, User State listens

```python
# engines/assessment/events.py
from shared.event_bus import emit

def emit_quiz_completed(attempt_id, user_id, quiz_id, topic_id, score, correct, total, difficulty_level):
    """Emit quiz_completed event after successful grading."""
    emit("quiz_completed", {
        "attempt_id": str(attempt_id),
        "user_id": str(user_id),
        "quiz_id": str(quiz_id),
        "topic_id": str(topic_id),
        "score": score,
        "correct": correct,
        "total": total,
        "difficulty_level": difficulty_level,
    })
```

```python
# engines/userstate/events.py
from shared.event_bus import on

@on("quiz_completed")
def handle_quiz_completed(payload: dict) -> None:
    """Update topic mastery when a quiz is completed."""
    from engines.userstate.services import update_mastery
    update_mastery(
        user_id=payload["user_id"],
        topic_id=payload["topic_id"],
        correct=payload["correct"],
        total=payload["total"],
        difficulty_level=payload["difficulty_level"],
    )
```

---

## 6. UPGRADE PATH

```
Phase 1–4:  Celery + Redis (single queue, monolith)
Phase 5–7:  Celery + Redis (multiple queues, per-engine routing)
Phase 8+:   Consider dedicated broker (RabbitMQ / AWS SQS)
            — only if event volume > 10K/min or multi-region needed
            — upgrade is transparent: event_bus.py interface stays the same
```

The `shared/event_bus.py` abstraction layer is the reason this upgrade is painless. No engine ever touches the broker directly.

---

## 7. RULES

- ❌ No event used in code without registration in Section 3
- ❌ No engine emits an event it does not own
- ❌ No listener fetches data from the emitter's DB — payload must be self-contained
- ❌ No listener assumes event order
- ✅ All listeners must be idempotent
- ✅ All payloads JSON-serializable (UUIDs as strings, timestamps as ISO strings)
- ✅ New events require entry in Section 3 BEFORE implementation
- ✅ Agents must read this file before wiring any event emission or listener
