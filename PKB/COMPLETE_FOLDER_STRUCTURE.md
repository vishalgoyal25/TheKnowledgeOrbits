# COMPLETE_FOLDER_STRUCTURE.md

## TheKnowledgeOrbits — Project Folder Structure

**PKB File #7 | Version: 1.0 | Date: Feb 2026**

---

## 1. ROOT STRUCTURE

```
TheKnowledgeOrbits/
├── backend/                    # Django 5 backend
├── frontend/                   # Next.js 16 frontend
├── agentic_dev/                # AgenticAI dev system (Phase 7+)
├── PKB/                        # Project Knowledge Base (15 .md files)
├── docker/                     # Docker configs
├── scripts/                    # Utility scripts
├── .env                        # Environment variables (gitignored)
├── .env.example                # Env template (committed)
├── docker-compose.yml          # Local multi-service orchestration
├── Justfile                    # Command runner (just)
├── .gitignore
├── .pre-commit-config.yaml     # Pre-commit hooks
└── README.md
```

---

## 2. BACKEND (Django)

```
backend/
├── manage.py
├── requirements.txt
├── pyproject.toml              # Bandit, black, mypy config
├── setup.cfg                   # Flake8, pytest config
├── .env
├── .env.example
│
├── core/                       # Django project root
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py             # Common settings
│   │   ├── dev.py              # Development overrides
│   │   └── prod.py             # Production overrides
│   ├── urls.py                 # Root URL config
│   ├── wsgi.py
│   ├── asgi.py
│   └── celery.py               # Celery app init
│
├── engines/                    # All 33 engines live here
│   ├── __init__.py
│   ├── content/                # Content Engine
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── services.py         # Business logic
│   │   ├── urls.py
│   │   ├── admin.py
│   │   ├── events.py           # Event emission
│   │   ├── tasks.py            # Celery tasks
│   │   ├── migrations/
│   │   │   ├── __init__.py
│   │   │   └── 0001_initial.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── factories.py    # factory_boy fixtures
│   │       ├── test_models.py
│   │       ├── test_serializers.py
│   │       ├── test_views.py
│   │       └── test_services.py
│   │
│   ├── knowledge/              # Knowledge Engine (same structure)
│   ├── assessment/             # Assessment Engine
│   ├── userstate/              # User State Engine
│   ├── analytics/              # Analytics Engine
│   ├── auth/                   # Authentication Engine
│   ├── authorization/          # Authorization Engine
│   ├── article_gen/            # Article Generation Engine (Phase 2)
│   ├── current_affairs/        # Current Affairs Engine (Phase 2)
│   ├── notification/           # Notification Engine (Phase 5+)
│   ├── search/                 # Search Engine (Phase 5+)
│   ├── personalization/        # Personalization Engine (Phase 7+)
│   ├── prediction/             # Prediction Engine (Phase 7+)
│   ├── ai_tutor/               # AI Tutor Engine (Phase 7+)
│   ├── gamification/           # Gamification Engine (Phase 6+)
│   ├── collaboration/          # Collaboration Engine (Phase 6+)
│   ├── revision/               # Revision Engine (Phase 6+)
│   ├── commerce/               # Commerce Engine (Phase 5+)
│   ├── marketing/              # Marketing Engine (Phase 9+)
│   ├── onboarding/             # Onboarding Engine (Phase 9+)
│   ├── retention/              # Retention Engine (Phase 9+)
│   ├── mock_test/              # Mock Test Engine (Phase 8+)
│   ├── nlp/                    # NLP Engine (Phase 8+)
│   ├── computer_vision/        # Computer Vision Engine (Phase 8+)
│   ├── voice/                  # Voice Engine (Phase 8+)
│   ├── video/                  # Video Engine (Phase 8+)
│   ├── storage/                # Storage Engine (Phase 5+)
│   ├── cache/                  # Cache Engine (Phase 5+)
│   ├── marketplace/            # Marketplace Engine (Phase 10+)
│   ├── whitelabel/             # White-label Engine (Phase 10+)
│   ├── moderation/             # Content Moderation Engine (Phase 10+)
│   ├── privacy/                # Privacy Engine (Phase 10+)
│   └── reporting/              # Reporting Engine (Phase 10+)
│
├── shared/                     # Shared utilities (NO engine logic here)
│   ├── __init__.py
│   ├── base_models.py          # Abstract base model (UUID, timestamps)
│   ├── exceptions.py           # Custom exception hierarchy
│   ├── permissions.py          # RBAC permission classes
│   ├── decorators.py           # @require_role etc.
│   ├── event_bus.py            # Event emission/listening
│   └── utils.py                # Pure utility functions
│
└── conftest.py                 # Global pytest fixtures
```

---

## 3. FRONTEND (Next.js)

```
frontend/
├── package.json
├── tsconfig.json
├── next.config.ts
├── tailwind.config.ts
├── .env.local
├── .env.local.example
│
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx          # Root layout
│   │   ├── page.tsx            # Home page
│   │   ├── auth/
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── dashboard/page.tsx
│   │   ├── articles/
│   │   │   ├── page.tsx        # Article listing
│   │   │   └── [slug]/page.tsx # Article detail
│   │   ├── quizzes/
│   │   │   ├── page.tsx
│   │   │   └── [id]/page.tsx
│   │   └── progress/page.tsx
│   │
│   ├── components/             # Reusable UI components
│   │   ├── layout/             # Header, Sidebar, Footer
│   │   ├── auth/               # Login, Register forms
│   │   ├── article/            # Article card, reader
│   │   ├── quiz/               # Quiz UI, timer, results
│   │   └── shared/             # Buttons, inputs, modals
│   │
│   ├── hooks/                  # Custom React hooks
│   ├── lib/                    # API client, utils
│   │   ├── api.ts              # Axios/fetch wrapper
│   │   └── utils.ts
│   ├── types/                  # Global TypeScript types
│   └── styles/                 # Global CSS
│       └── globals.css
│
└── public/                     # Static assets
```

---

## 4. AGENTIC DEV SYSTEM (Phase 7+)

```
agentic_dev/
├── main.py                     # Entry point
├── graph.py                    # LangGraph workflow definition
├── state.py                    # Task state model
├── agents/
│   ├── __init__.py
│   ├── planner_agent.py        # Decides next engine/step
│   ├── architect_agent.py      # Generates engine skeletons
│   ├── codegen_agent.py        # Writes boilerplate code
│   ├── test_agent.py           # Generates + runs tests
│   └── review_agent.py         # PKB compliance check
├── tools/
│   ├── __init__.py
│   ├── filesystem.py           # File read/write/create
│   ├── shell.py                # Run pytest, migrations, linters
│   └── git.py                  # Branch, commit, rollback
├── memory/
│   └── task_state.json         # Persistent task state
└── workflows/
    └── engine_build_graph.py   # Full engine build workflow
```

---

## 5. PKB (Project Knowledge Base)

```
PKB/
├── PROJECT_VISION.md           # #1  — What & why
├── TECH_STACK.md               # #2  — All tools & versions
├── ARCHITECTURE.md             # #3  — System structure
├── CODING_STANDARDS.md         # #4  — How to write code
├── WORKING_RULES.md            # #5  — Highest authority rules
├── DATABASE_SCHEMA.md          # #6  — All table definitions
├── COMPLETE_FOLDER_STRUCTURE.md# #7  — This file
├── ENGINE_CATALOG.md           # #8  — Per-engine contracts
├── API_REFERENCE.md            # #9  — All endpoints
├── DATA_FLOW_PATTERNS.md       # #10 — Validation, retry, idempotency
├── EVENT_DRIVEN_ARCHITECTURE.md# #11 — Async patterns
├── EXECUTION_ROADMAP.md        # #12 — Phase-wise plan + tool rollout
├── TESTING_STRATEGY.md         # #13 — Test patterns & coverage
├── MIGRATION_STRATEGY.md       # #14 — Safe schema evolution
└── AGENTIC_DEVELOPMENT.md      # #15 — Agent roles & workflow
```

---

## 6. DOCKER & SCRIPTS

```
docker/
├── backend.Dockerfile
├── frontend.Dockerfile
└── nginx.conf                  # Reverse proxy (prod)

scripts/
├── setup.sh                    # One-time project setup
├── seed_data.py                # Seed DB with test data
└── ingest_ncert.py             # NCERT PDF ingestion script

docker-compose.yml              # Local: backend + frontend + postgres + redis
Justfile                        # just dev, just test, just migrate, etc.
```

---

## 7. RULES

- Every engine folder follows the SAME internal structure
- Only `shared/` contains reusable code — no engine imports another engine
- `agentic_dev/` is development-only. Never deployed to production
- Phase markers in engine comments indicate when that engine is built
- New engines are added to `engines/` only when their phase begins
