# DATA_FLOW_PATTERNS.md
## TheKnowledgeOrbits — Data Flow Patterns
**PKB File #10 | Version: 1.0 | Date: Feb 2026**

---

## 1. PURPOSE

This file defines reusable patterns for how data moves between engines.
Every new engine or cross-engine integration must follow one of these patterns exactly.

Three concerns governed here:
1. **Flow Patterns** — how engines connect end-to-end
2. **Retry & Failure** — what happens when things break
3. **Idempotency** — how duplicate calls are handled safely

---

## 2. CANONICAL FLOWS

### Flow A: Ingest → Organize → Generate (Content Pipeline)

```
[Admin uploads PDF]
      ↓
Content Engine                  ← ingest, OCR, chunk (1200 chars), embed
      ↓ (chunk_id)
Knowledge Engine                ← admin maps chunk → topic
      ↓ (topic has chunks)
Article Gen Engine              ← RAG: fetch chunks by topic → GROQ → article
      ↓
Assessment Engine               ← RAG: fetch chunks by topic → GROQ → MCQs
```

**Rules:**
- Content Engine owns all chunks. No other engine stores raw text
- Knowledge Engine is the ONLY engine that maps chunks to topics
- Article Gen and Assessment both READ chunks via Knowledge Engine's topic mapping
- Neither Article Gen nor Assessment stores chunks themselves

---

### Flow B: User Action → Event → State Update (Tracking Pipeline)

```
[User reads article / takes quiz / bookmarks]
      ↓
Frontend fires POST /api/v1/user-state/event
      ↓
User State Engine               ← records event (append-only)
      ↓ emits event
Analytics Engine                ← listens, updates daily_aggregate
      ↓
Personalization Engine          ← listens, recalculates recommendations (Phase 7)
```

**Rules:**
- ALL user actions must flow through User State Engine first
- User State Engine is the single source of truth for what a user has done
- Downstream engines (Analytics, Personalization) LISTEN to events — they never poll User State
- Events are fire-and-forget from the caller's perspective (sync record, async propagation)

---

### Flow C: News Ingestion → Context Merge (Current Affairs Pipeline)

```
[Daily 6 AM cron]
      ↓
Current Affairs Engine          ← scrape RSS → chunk → embed
      ↓ (ca_chunk_ids)
Knowledge Engine                ← semantic match → ca_topic_link
      ↓
Article Gen Engine              ← fetch static chunks + CA chunks for topic
                                ← merge contexts → GROQ → integrated article
```

**Rules:**
- CA chunks share the same embedding space as static chunks (384-dim, same model)
- Knowledge Engine classifies CA chunks automatically via semantic similarity
- Article Gen Engine is the ONLY place where static + CA contexts merge
- CA chunks have `expiry_date` — cleanup cron runs daily to soft-delete stale chunks

---

### Flow D: Assessment → Mastery → Insight (Learning Loop)

```
[User submits quiz]
      ↓
Assessment Engine               ← auto-grade, return score + explanations
      ↓ emits quiz_completed event
User State Engine               ← updates topic_mastery score
      ↓ (mastery data)
Analytics Engine                ← daily aggregation → weak_topic insight
      ↓ (insights)
Personalization Engine          ← reprioritizes learning path (Phase 7)
```

**Rules:**
- Mastery score is COMPUTED, never manually set
- Formula: `mastery = (questions_correct / questions_attempted) * 100`, weighted by difficulty
- Analytics Engine generates `weak_topic` insights when mastery < 40 for 3+ consecutive days
- Learning path reorder happens async — user sees updated path on next app open

---

## 3. VALIDATION RULES

### Input Validation (every endpoint)
```
1. Schema validation (DRF serializer) — runs first
2. Business validation (service layer) — runs second
3. Fail immediately on either — never proceed with bad data
```

### Cross-Engine Call Validation
```
Engine A calls Engine B API:
  1. Engine A validates its OWN input before calling
  2. Engine B validates the incoming payload independently
  3. Neither trusts the other's validation
```

### UUID Validation
```
All resource IDs in request bodies must be:
  - Valid UUID format (reject at serializer level)
  - Verified to exist in the target engine's DB (reject with NOT_FOUND)
  - Checked for ownership where applicable (reject with FORBIDDEN)
```

---

## 4. RETRY & FAILURE MODEL

### Classification

| Failure Type | Examples | Action |
|---|---|---|
| Hard-fail | Auth 401/403, validation error, schema violation | Stop immediately. No retry. Return error |
| Soft-fail | External API timeout, file processing error, embedding failure | Retry with backoff. DLQ after max |

### Backoff Schedule (Celery tasks only)
```
Attempt 1: immediate
Attempt 2: wait 1s
Attempt 3: wait 5s
After 3 failures: move to Dead Letter Queue (DLQ) → notify admin via Sentry alert
```

### DLQ Rules
- Failed tasks land in a dedicated DLQ (Redis list)
- Admin sees DLQ count in Flower dashboard
- DLQ items are NOT auto-retried — admin must manually replay or discard
- DLQ items expire after 7 days if not actioned

### Sync Endpoint Failures
- Sync endpoints do NOT retry internally
- Client receives error response immediately
- Client is responsible for retry logic (if applicable)
- Frontend uses TanStack Query's built-in retry (max 2, exponential backoff)

---

## 5. IDEMPOTENCY CONTRACTS

### Which operations MUST be idempotent

| Endpoint | Idempotency Key | How |
|---|---|---|
| POST /content/upload | document title + source_edition | Return existing if duplicate key found |
| POST /knowledge/map-chunk | (chunk_id, topic_id) | UNIQUE constraint → return existing on conflict |
| POST /user-state/bookmark | (user_id, content_type, content_id) | UNIQUE constraint → return existing on conflict |
| POST /user-state/event | None — append-only | Events always appended. Dedup at aggregation layer |
| POST /assessment/submit-quiz | attempt_id | Once submitted, status = submitted. Subsequent calls return cached result |
| POST /ca/link-topic | (ca_chunk_id, topic_id) | UNIQUE constraint → return existing on conflict |

### Which operations are NOT idempotent (and why)

| Endpoint | Why not |
|---|---|
| POST /auth/register | Email unique — second call returns CONFLICT |
| POST /assessment/start-quiz | Creates new attempt each time. Guard: check no active attempt exists first |
| POST /articles/generate | Each call triggers a new generation job. Client must check status before re-calling |

---

## 6. CROSS-ENGINE CALL CONVENTIONS

### Pattern 1: Synchronous HTTP Call
```
When: Engine A needs data from Engine B at request time
How:
  → Engine A calls Engine B's API endpoint
  → Waits for response
  → Uses data in its own logic
  → Never stores Engine B's raw data — only what it needs

Example: Article Gen Engine fetches chunks via Content Engine API
```

### Pattern 2: Event Emission (Async)
```
When: Engine A completed an action, downstream engines need to react
How:
  → Engine A emits named event with payload
  → Engine B (listener) receives event async
  → Engine B acts on payload independently
  → Engine A does NOT wait for Engine B

Example: Assessment Engine emits quiz_completed → User State Engine updates mastery
```

### Forbidden Patterns
```
❌ Engine A imports Engine B's Django models
❌ Engine A writes to Engine B's tables
❌ Engine A queries Engine B's tables via raw SQL or ORM
❌ Shared database tables owned by two engines
❌ Engine A passes internal DB IDs to Engine B expecting them to mean the same thing
     (each engine resolves IDs via its own API only)
```

---

## 7. CRON JOBS REGISTRY

All scheduled jobs must be documented here. No undocumented crons.

| Job | Engine | Schedule | What it does |
|---|---|---|---|
| RSS Scrape | Current Affairs | Daily 6:00 AM IST | Fetch new news, chunk, embed |
| CA Expiry Cleanup | Current Affairs | Daily 6:30 AM IST | Soft-delete ca_chunks past expiry_date |
| Daily Aggregation | Analytics | Daily 12:00 AM IST | Roll up user_events into daily_aggregate |
| Insight Generation | Analytics | Daily 12:30 AM IST | Compute weak_topic, streak_risk insights |
| Mastery Recompute | User State | Daily 1:00 AM IST | Recompute topic_mastery from event history |

---

## 8. RULES

- ❌ No new cross-engine flow without a pattern entry here
- ❌ No undocumented cron job
- ❌ No retry logic that doesn't follow Section 4
- ✅ Every idempotent endpoint must have its key documented in Section 5
- ✅ Agents must read this file before wiring any engine-to-engine connection
