# ARCHITECTURE.md

## TheKnowledgeOrbits — System Architecture

**PKB File #3 | Version: 1.0 | Date: Feb 2026**

---

## 1. ARCHITECTURAL PHILOSOPHY

- **Single Responsibility** — One engine = one job. Clear boundaries.
- **Composition Over Inheritance** — Products compose engines. Engines never inherit from each other.
- **Event-Driven Communication** — Engines talk via events. No direct method calls across engines.
- **Data Ownership** — Each engine owns its tables. No shared tables.
- **Independent Scalability** — Each engine scales separately. Start monolith, microservices-ready.

---

## 2. ENGINE LAYERS

```
L0  Data Ingestion      → Content Engine, Current Affairs Engine
L1  Organization        → Knowledge Engine, Search Engine
L2  Generation          → Article Gen Engine, Assessment Engine, Video Engine
L3  User Tracking       → User State Engine
L4  Analysis            → Analytics Engine
L5  Intelligence        → Personalization, Prediction, AI Tutor Engines
L6  Engagement          → Gamification, Collaboration, Revision Engines
L7  Operations          → Auth, Authorization, Notification, Storage, Cache Engines
L8  Growth              → Commerce, Marketing, Onboarding, Retention Engines
L9  Advanced            → Mock Test, NLP, Computer Vision, Voice Engines
L10 Enterprise          → Marketplace, White-label, Moderation, Privacy, Reporting Engines
```

---

## 3. CORE DATA FLOW

```
[PDF/Web/News]
      ↓
[Content Engine]        → ingest → OCR → chunk (1200 chars) → embed (384-dim)
      ↓
[Knowledge Engine]      → map chunks → topics → syllabus graph
      ↓
[Article Gen Engine]    → RAG: fetch chunks → GROQ → article + source map
      ↓
[Assessment Engine]     → RAG: fetch chunks → GROQ → MCQs
      ↓
[User State Engine]     → event sourcing: reads, attempts, bookmarks
      ↓
[Analytics Engine]      → daily aggregation → insights → signals
      ↓
[Personalization Engine]→ weak areas → learning path → recommendations
```

---

## 4. AUTHENTICATION & AUTHORIZATION ARCHITECTURE

### JWT Flow:

```
Client → POST /auth/login (email + password)
      ↓
Backend validates credentials (Argon2 hash check)
      ↓
Issues: access_token (5 min) + refresh_token (7 days)
      ↓
Tokens stored in HttpOnly cookies
      ↓
Every request → middleware extracts + validates JWT
      ↓
Claims decoded → user_id + roles extracted
      ↓
RBAC middleware checks role against endpoint permission
```

### RBAC Model:

```
User → assigned Role(s) → Role contains Permission(s)
Permission = (resource, action)
Examples: (content, upload), (user, delete), (quiz, create)

Roles: admin, content_manager, student, free_user
```

### Trust Boundaries:

- Each engine trusts JWT claims only
- No engine accesses another engine's DB directly
- Cross-engine calls via internal APIs or events only
- Background workers receive user context via event payload

---

## 5. OBSERVABILITY ARCHITECTURE

### Log Flow:

```
Application Code
      ↓ structlog (prod) / rich (dev)
stdout → Log Aggregator (future: Loki)
      ↓
Grafana Dashboard
```

### Error Flow:

```
Unhandled Exception
      ↓
Sentry SDK captures (auto)
      ↓
Sentry Dashboard → alerts
```

### Trace Flow (Phase 8+):

```
Request arrives → trace_id assigned
      ↓
trace_id propagates through all engines + async workers
      ↓
All logs include trace_id
      ↓
OpenTelemetry → Grafana (full request trace)
```

---

## 6. ASYNC FAILURE MODEL

### Retry Rules:

- Transient failures (network, external API) → retry with exponential backoff (max 3 attempts)
- Fatal failures (validation, auth) → fail immediately, no retry
- Celery task failures → bounded retry → DLQ after max retries

### Backoff Strategy:

```
Attempt 1: immediate
Attempt 2: wait 1s
Attempt 3: wait 5s
After 3 failures: move to Dead Letter Queue → notify admin
```

### Hard-fail vs Soft-fail:

```
Hard-fail (stop immediately):
  - Auth failures (401/403)
  - Validation errors
  - Schema violations

Soft-fail (retry or queue):
  - External API timeouts
  - File processing errors
  - Embedding generation failures
```

---

## 7. ENGINE COMMUNICATION RULES

```
✅ Allowed:
  - Engine A → HTTP call → Engine B API
  - Engine A → emit event → Engine B listens
  - Engine A reads its own DB tables only

❌ Forbidden:
  - Engine A directly queries Engine B's DB tables
  - Engine A imports Engine B's models
  - Shared tables between engines
  - Direct function calls across engine boundaries
```

---

## 8. SCALING STRATEGY

```
Phase 1-4  → Single Django process (monolith)
Phase 5-7  → Celery workers for async tasks
Phase 8+   → Engine-level horizontal scaling
Phase 10+  → Full microservices (if needed)
```

Each engine is isolated enough to extract into a microservice later without refactoring.

- +---
- +## 9. IMPLEMENTATION & VERIFICATION STATUS
- +- [x] **Engine Layer L0-L1:** Content and Knowledge engines fully decoupled with dedicated schemas.
  +- [x] **Data Ownership:** `db_table` naming convention strictly follows `enginename_modelname`.
  +- [x] **JWT Auth Flow:** HttpOnly cookie-based JWT flow implemented and verified in Auth engine.
  +- [x] **RBAC Model:** Role-based access control integrated with JWT claims.
  +- [x] **Core Data Flow:** Document → Chunks → Embeddings → RAG Article Generation verified.
  +- [x] **Observability:** `structlog` and `Sentry` integration verified across core engines.
  +- [x] **Async Processing:** Celery + Redis task queue active for heavy ingestion and generation jobs.
  +- [x] **Communication Rules:** Cross-engine DB access strictly forbidden and verified via code reviews.
  +- [x] **Scaling Readiness:** Architecture verified as monolith-ready for Ph 1-4 with microservices path clear.
-
