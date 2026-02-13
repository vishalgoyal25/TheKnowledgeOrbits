# TheKnowledgeOrbits — PKB Explained + What Next
## Your Complete Understanding Guide

---

## 🔴 REDFLAG FIX FIRST — Knowledge Base Feature

### What the error means:
The 15 .md files you generated need to be uploaded into the
**Project Knowledge Base** inside your Claude Project so that
every future chat in that project automatically has access to them.
Without this, every new chat starts blank — no PKB context.

### Step-by-step fix (takes 2 minutes):

```
1. Open claude.ai
2. Click "Projects" in the left sidebar
3. Open your TheKnowledgeOrbits project
4. You will see the project main page
5. On the RIGHT SIDE → look for "Project knowledge" panel
6. Click the "+" button in that panel
7. Upload all 15 .md files one by one
   (or select all 15 at once if your OS allows multi-select)
8. Wait for each file to show "uploaded" confirmation
9. Done — every future chat in this project now sees all 15 files
```

### If the "Project knowledge" panel is missing entirely:
- You need a PAID plan (Pro, Max, Team, or Enterprise)
- Free plans do not get the Knowledge Base upload panel
- Check: Settings → Plan → upgrade if needed
- After upgrading, re-open the project → the panel appears

### Important note:
- Continue this project work IN THE SAME PROJECT
- Do NOT open a new tab outside the project
- Context stays only inside the project where files are uploaded

---

## 📂 WHAT ARE THESE 15 FILES? (The Big Picture)

Think of the 15 .md files as a BLUEPRINT for a 33-engine
ed-tech platform. Each file is one page of that blueprint.
Together they form the **PKB (Project Knowledge Base)** —
the single source of truth that governs everything.

```
┌─────────────────────────────────────────────────────┐
│              THE PKB = YOUR BLUEPRINT                │
│                                                     │
│  VISION          → WHY we build this                │
│  RULES           → HOW we work                      │
│  ARCHITECTURE    → WHAT the system looks like       │
│  DATABASE        → WHERE data lives                 │
│  ENGINES         → WHAT each piece does             │
│  APIs            → HOW frontend talks to backend    │
│  DATA FLOWS      → HOW data moves between engines   │
│  EVENTS          → HOW engines talk to each other   │
│  ROADMAP         → WHEN each piece gets built       │
│  TESTING         → HOW we prove it works            │
│  MIGRATION       → HOW schema evolves safely        │
│  AGENTS          → HOW AI accelerates development   │
└─────────────────────────────────────────────────────┘
```

---

## 📖 EACH FILE EXPLAINED — PLAIN ENGLISH

### FILE #1 — PROJECT_VISION.md
**"What are we building and why?"**

This is the north star. One sentence summary:
  Raw content (PDFs, news) → Chunks → RAG → AI articles + Quizzes
  → User learns → Progress tracked → Personalized path

It defines:
- Platform name: TheKnowledgeOrbits
- Target: Indian students preparing for UPSC CSE
- Scale: 10 million+ users
- Developer model: Solo developer + AI acceleration
- 7 non-negotiable principles (Content-First, Chunk-Based, RAG-First, etc.)

---

### FILE #2 — TECH_STACK.md
**"What tools are we allowed to use?"**

Every single library, framework, and service used in the project
is listed here. Nothing outside this list gets added without approval.

Key tools:
- Backend: Django 5 + PostgreSQL 16
- Frontend: Next.js 16 + TypeScript + Tailwind
- AI: GROQ (article/quiz generation), sentence-transformers (embeddings)
- Testing: pytest + factory_boy
- Logging: structlog (Python), chalk (Node.js) — no print(), no console.log()

---

### FILE #3 — ARCHITECTURE.md
**"What does the system look like structurally?"**

The 33 engines organized in 11 layers (L0 through L10):

```
L0  → Data comes IN        (Content Engine, Current Affairs Engine)
L1  → Data gets ORGANIZED  (Knowledge Engine, Search Engine)
L2  → Content gets MADE    (Article Gen, Assessment, Video)
L3  → Users get TRACKED    (User State Engine)
L4  → Data gets ANALYZED   (Analytics Engine)
L5  → AI gets SMART        (Personalization, Prediction, AI Tutor)
L6  → Users stay ENGAGED   (Gamification, Collaboration, Revision)
L7  → System OPERATES      (Auth, Notifications, Storage, Cache)
L8  → Money comes IN       (Commerce, Marketing, Onboarding, Retention)
L9  → Advanced CONTENT     (Mock Test, NLP, Computer Vision, Voice)
L10 → Enterprise FEATURES  (Marketplace, White-label, Compliance)
```

Golden rule: Engines never talk directly. They use APIs or events.

---

### FILE #4 — CODING_STANDARDS.md
**"How do we write code?"**

The style guide. Every line of code must follow these rules:
- Python: snake_case, type hints required, docstrings required
- Django Models: UUID primary keys ONLY, help_text on every field
- Database tables named: enginename_modelname (e.g. content_chunk)
- No print() anywhere. Ever. Use structlog logger instead.
- Git commits follow conventional format: feat(content): add PDF chunking

---

### FILE #5 — WORKING_RULES.md
**"The rules that CANNOT be broken."**

This is the highest authority file. If any other file conflicts
with this one, this one wins.

Critical rules:
- One file at a time. One step at a time.
- Human approves everything. AI proposes only.
- Engine boundaries are sacred — no cross-engine database access
- Security patterns (JWT, Argon2, RBAC) are mandatory in all code

---

### FILE #6 — DATABASE_SCHEMA.md
**"What tables exist and how do they connect?"**

The complete SQL schema for all engines. Every table, every column,
every index, every foreign key. This is the source of truth for
"what data does the system store?"

Key relationships:
- auth_user is the ROOT — everything references it
- knowledge_topic is the SHARED HUB — articles, quizzes, mastery all point here
- content_chunk is the FOUNDATION — articles and quizzes are generated FROM chunks

---

### FILE #7 — COMPLETE_FOLDER_STRUCTURE.md
**"Where does every file live on disk?"**

The exact directory tree for backend/, frontend/, agentic_dev/, PKB/.
Every engine has the same internal structure:
  models.py → serializers.py → views.py → services.py → tests/

---

### FILE #8 — ENGINE_CATALOG.md
**"What does each engine do? Who can use it?"**

Each of the 33 engines has a one-line responsibility, its allowed
roles (admin, student, etc.), whether it's sync or async, and
what the AI agent is allowed to do inside it.

Example: Assessment Engine
  → Responsibility: Generate quizzes from chunks, evaluate responses
  → Who generates: admin, content_manager
  → Who takes quizzes: student, free_user

---

### FILE #9 — API_REFERENCE.md
**"How does the frontend talk to the backend?"**

Every single endpoint. Method, URL, auth requirement, request body,
response shape, error codes, side effects.

Example:
  POST /api/v1/assessment/submit-quiz
  → Returns score + explanations
  → Side effect: fires quiz_completed event → User State updates mastery

---

### FILE #10 — DATA_FLOW_PATTERNS.md
**"How does data move between engines?"**

4 canonical flows that everything else follows:

  Flow A: Ingest → Organize → Generate  (Content Pipeline)
  Flow B: User Action → Event → State   (Tracking Pipeline)
  Flow C: News → Context Merge          (Current Affairs Pipeline)
  Flow D: Assessment → Mastery → Insight (Learning Loop)

Also defines: retry rules, failure handling, idempotency contracts,
and which operations are safe to call twice without breaking things.

---

### FILE #11 — EVENT_DRIVEN_ARCHITECTURE.md
**"How do engines communicate asynchronously?"**

Engines don't call each other directly. They emit EVENTS.
Other engines LISTEN to those events and react.

Example:
  Assessment Engine finishes grading → emits "quiz_completed"
  User State Engine hears it → updates mastery score
  Analytics Engine hears it → updates daily aggregate

Events go through Redis → Celery workers → listeners process independently.
If a listener fails, it retries 3 times, then goes to a Dead Letter Queue.

---

### FILE #12 — EXECUTION_ROADMAP.md
**"What gets built when?"**

The 36-week plan broken into 11 phases. Each phase has:
- Exact deliverables
- Which tools activate
- Success criteria (all must pass)
- Go/No-Go gate (mandatory checkpoint before next phase)

```
Phase 0  (Week 1)     → Setup environment
Phase 1  (Weeks 2-4)  → 5 core engines (MVP backend)
Phase 2  (Weeks 5-7)  → Article generation + Current Affairs
Phase 3  (Weeks 8-10) → Frontend (Next.js app)
Phase 4  (Weeks 11-12)→ Deploy → PUBLIC BETA LAUNCH
Phase 5-10            → Monetization → Enterprise (Weeks 13-36)
```

---

### FILE #13 — TESTING_STRATEGY.md
**"How do we prove the code works?"**

Coverage targets that cannot be skipped:
  Models: 90% | Services: 85% | Views: 80%

Every endpoint gets tested for:
  - No token → 401
  - Wrong role → 403
  - Correct role → 200
  - Expired token → 401

Idempotency tests prove that calling an endpoint twice doesn't
create duplicates. Event emission tests prove events actually fire.

---

### FILE #14 — MIGRATION_STRATEGY.md
**"How does the database change safely over time?"**

Two concerns:
1. Schema discipline — one migration per logical change, never squash,
   tests must pass before migration runs, rollback-safe always.
2. Data migration — how user data moves from old LearningHub to new
   system. Users + progress migrate. Content gets re-ingested fresh.

FK dependency ordering (Tier 0 → Tier 6) ensures migrations run
in the right sequence. auth_user first. Everything else after.

---

### FILE #15 — AGENTIC_DEVELOPMENT.md
**"How does AI help build this platform?"**

Two tiers:
- Phases 0-6: Human-in-the-loop. Claude proposes one file. You approve.
- Phase 7+:   Autonomous agent system (LangGraph). 5 agents work together.
              But EVERY step still pauses for human approval.

5 agents: Planner, Architect, Engine Builder, Test, Review
3 tools:  Filesystem, Shell (pytest/migrations), Git

Runtime agents (Phase 7+) also exist INSIDE the product:
  - Content Orchestration Agent → picks chunks for RAG
  - Learning Path Agent → plans daily study schedules

---

## 🗺️ HOW THE 15 FILES CONNECT TO EACH OTHER

```
PROJECT_VISION ──────→ defines WHY
      │
      ▼
WORKING_RULES ───────→ highest authority (overrides everything)
      │
      ├──→ TECH_STACK          (what tools exist)
      ├──→ CODING_STANDARDS    (how to write code)
      ├──→ ARCHITECTURE        (system shape)
      │         │
      │         ├──→ ENGINE_CATALOG      (per-engine contracts)
      │         ├──→ DATABASE_SCHEMA     (tables + relationships)
      │         ├──→ API_REFERENCE       (endpoints)
      │         ├──→ DATA_FLOW_PATTERNS  (how data moves)
      │         ├──→ EVENT_DRIVEN_ARCH   (async communication)
      │         └──→ FOLDER_STRUCTURE    (where files live)
      │
      ├──→ EXECUTION_ROADMAP    (when things get built)
      ├──→ TESTING_STRATEGY     (how we prove it works)
      ├──→ MIGRATION_STRATEGY   (how schema evolves)
      └──→ AGENTIC_DEVELOPMENT  (how AI helps build)
```

---

## ⏭️ WHAT HAPPENS NEXT — THE EXACT SEQUENCE

```
RIGHT NOW (today):
  1. Upload all 15 .md files into Project Knowledge Base (fix redflag)
  2. Stay in this same Project from now on

PHASE 0 — SETUP (Week 1):
  3. Create the mono-repo folder structure on your machine
     D:\AI_Projects\TheKnowledgeOrbits\
       ├── backend/     (Django)
       ├── frontend/    (Next.js)
       ├── PKB/         (your 15 .md files)
       └── docker/      (Docker configs)

  4. Initialize Django 5 + DRF skeleton
  5. Initialize Next.js 16 + TypeScript skeleton
  6. Set up PostgreSQL 16 + pgvector (via Supabase or local Docker)
  7. Set up Redis 7.0 (Docker Compose)
  8. Set up GitHub Actions CI
  9. Health check endpoint: GET /api/v1/health → 200

  ✅ Gate: All 5 success criteria pass → Phase 0 complete

PHASE 1 — CORE ENGINES (Weeks 2-4):
  10. Week 2: Content Engine + Auth Engine
  11. Week 3: Knowledge Engine
  12. Week 4: Assessment + User State + Analytics Engines
  13. 65+ tests passing

  ✅ Gate: MVP backend is functional

PHASE 2 — ARTICLE GENERATION (Weeks 5-7):
  14. RAG pipeline: chunks → GROQ → articles
  15. Current Affairs scraping
  16. Integrated articles (theory + news)

  ✅ Gate: Core product value is proven

PHASE 3 — FRONTEND (Weeks 8-10):
  17. Next.js app consuming all APIs
  18. Article reader, quiz taker, progress dashboard

PHASE 4 — LAUNCH (Weeks 11-12):
  19. Ingest 5 NCERT books → 100+ articles → 50+ quizzes
  20. Deploy to Render (backend) + Vercel (frontend)

  🚀 PUBLIC BETA LAUNCHES
```

---

## 💬 SAME CHAT OR NEW TAB?

Answer: **Stay in this Project. New chats within it are fine.**

- Every new chat INSIDE this Project will automatically see all 15 PKB files
  (once you upload them to Project Knowledge)
- You do NOT need to stay in the same chat thread forever
- You CAN start a fresh chat inside the same Project for each new task
  (e.g., "Phase 0 setup", "Content Engine models", etc.)
- Do NOT leave the Project to work on this — context lives in the Project

The workflow from here:
  → Say "Done" to this explanation
  → Say "Start Phase 0 setup"
  → We build the mono-repo skeleton, one file at a time
