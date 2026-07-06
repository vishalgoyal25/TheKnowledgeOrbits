# 🌍 TheKnowledgeOrbits

**AI-Powered Ed-Tech Platform for UPSC Aspirants**
_Engine-First Django/Next.js Architecture | Built for Scale | Solo-Developed_

---

## 📋 Overview

TheKnowledgeOrbits is an AI-accelerated exam-prep platform for UPSC Civil Services aspirants. It
combines a curated static knowledge base (NCERT/standard-book content) with live current-affairs
ingestion to generate contextual, retrieval-grounded study material — daily current-affairs articles,
public quizzes, evergreen theory content, and an agentic AI research assistant.

### 🎯 Core Design Principles

**Chunk-first content architecture**

- All ingested content (books, current affairs) is split into semantic chunks, embedded, and indexed
  for hybrid (keyword + vector) retrieval — never stored or served as raw, unstructured text.
- Generated content (daily articles, quizzes) is produced by retrieving the most relevant chunks and
  grounding an LLM call in them — a Retrieval-Augmented Generation (RAG) pipeline, not free-form
  generation.

**Engine-first backend**

- The backend is organized into independent Django apps ("engines"), each owning one responsibility
  (content ingestion, current affairs, assessment, authentication, authorization, the AI research
  agent, etc.).
- Engines communicate through APIs/shared infrastructure, not direct cross-engine model imports — the
  `research_agent` engine in particular is fully isolated from the rest of the platform.

---

## ✨ Key Features

### 📚 Content & Knowledge

- PDF/text ingestion with semantic chunking (~1200-character chunks, sentence-boundary aware)
- pgvector-backed embedding storage with HNSW indexing for fast similarity search
- Hybrid retrieval: PostgreSQL full-text search (BM25-style) + vector similarity, fused via
  Reciprocal Rank Fusion
- A syllabus-driven knowledge hierarchy (Subject → Module → Topic) underlying both static content and
  retrieval scoping

### 📰 Current Affairs Automation

- Scheduled RSS scraping, chunking, and embedding of daily news (via a GitHub Actions cron job)
- Cross-linking between current-affairs content and the static syllabus via topic-relation graphs
- A fully automated nightly pipeline: score news → auto-approve → generate daily articles + a public
  quiz → publish — zero manual intervention required

### 🧠 Retrieval-Grounded AI Generation

- A shared RAG "grounding gateway" every content generator calls through — cross-subject theory
  retrieval + recency-scoped current-affairs retrieval, relevance-gated (not subject-gated)
- Multi-provider LLM pool (Groq + Cerebras) with retry/failover
- An agentic AI research assistant (LangGraph-orchestrated, multi-node) with live web search, SSE
  streaming, and LLM-as-judge evaluation — architecturally isolated from the rest of the platform

### 🔐 Authentication & Authorization

- Custom email-based user model, JWT authentication (SimpleJWT)
- Role-based access control (admin / content manager / student / free user)
- Production-hardened settings: HTTPS/HSTS enforcement, secure cookies, CORS/CSRF configured for a
  split frontend/backend deployment

### 📊 Assessment & Progress

- Auto-generated daily public quizzes and topic-wise practice quizzes
- Per-user attempt tracking and mastery scoring

---

## 🏗️ Architecture

### Technology Stack

**Backend**

- Python 3.11, Django 5.0, Django REST Framework 3.15
- PostgreSQL 17 + `pgvector` (hybrid search: HNSW vector index + GIN full-text index)
- Redis (Upstash) — caching, rate limiting, SSE pub/sub, production sessions
- `django-background-tasks` for asynchronous/background work (not Celery)

**AI / ML**

- Groq + Cerebras (LLM generation, pooled with retry/failover)
- `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim embeddings — local or via HuggingFace
  Inference API depending on environment)
- LangGraph, Pydantic v2, Tavily, Exa, Langfuse (the isolated AI research-agent engine)

**Frontend**

- Next.js 16 (App Router), React 19, TypeScript 5
- Tailwind CSS 3, shadcn/ui
- Incremental Static Regeneration (ISR) for CDN-cached, edge-served public content

**Infrastructure**

- Backend hosting: Render
- Frontend hosting: Vercel
- Database: Supabase (managed Postgres + pgvector, PgBouncer connection pooling)
- Media: Cloudinary
- Error tracking: Sentry
- CI/CD: GitHub Actions (lint, sharded test suite, automated deploy gate)
- Containerization: Docker (used for CI/production-style testing only — local development runs
  natively, no containers)

### Engine Overview

The backend is organized as a set of independent Django apps, each with a single responsibility:

| Engine               | Responsibility                                                        |
| -------------------- | --------------------------------------------------------------------- |
| `content`            | Document/chunk/embedding ingestion (the shared content pipeline)      |
| `knowledge`          | The syllabus hierarchy (Subject → Module → Topic) and topic relations |
| `book_content`       | Evergreen, syllabus-driven theory content generation                  |
| `current_affairs`    | Current-affairs scraping, chunking, and cross-linking                 |
| `daily_ca`           | The daily current-affairs pipeline (proposals → articles → publish)   |
| `assessment`         | Quiz generation, attempts, and daily public quizzes                   |
| `tags`               | Concept/tag taxonomy and concept-page content                         |
| `article_generation` | User-facing AI article generation                                     |
| `auth`               | Custom user model, JWT authentication, email verification/reset       |
| `authorization`      | Role-based access control (roles, permissions, middleware)            |
| `userstate`          | Per-user progress and state tracking                                  |
| `analytics`          | Usage aggregation and reporting                                       |
| `social`             | Social/interaction features                                           |
| `support`            | Support/help features                                                 |
| `research_agent`     | The isolated, agentic AI research assistant (LangGraph)               |

---

## 🚀 Local Development Setup

> Local development runs natively (no Docker) on Windows/PowerShell. Docker is used only for CI and
> production-style container testing.

### Prerequisites

```bash
- Python 3.11+
- Node.js 20+
- PostgreSQL 17 (with the pgvector extension available)
- Redis (for caching/rate limiting; optional for basic local dev)
- Git
```

### Backend Setup

```bash
cd backend

python -m venv myvenv
myvenv\Scripts\activate          # Windows
# source myvenv/bin/activate     # Linux/Mac

pip install -r requirements/base.txt -r requirements/dev.txt

copy .env.example .env            # then fill in your local values
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Access

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api/v1/
- Admin panel: http://localhost:8000/admin/

---

## 🧪 Testing & CI/CD

- **699+ backend tests**, sharded across 3 parallel CI jobs (via `pytest-split`) against a real
  `pgvector`-enabled Postgres service container — full suite runs in ~5 minutes.
- **GitHub Actions pipeline**: lint (Ruff) + type-check (mypy) + sharded backend tests + frontend
  build/lint/tests, all gating an automated deploy — a broken build or failing test blocks production
  automatically.
- Run locally: `pytest` (backend, from `backend/`), `npm test` (frontend, from `frontend/`).

---

## 📄 License

This repository is **source-available for viewing and portfolio/reference purposes only**. It is
**not** open source, and no license to use, copy, modify, merge, publish, distribute, sublicense, or
sell any part of this codebase is granted. All rights are reserved by the author.

See [LICENSE](LICENSE) for the full terms.

If you're interested in licensing, collaborating, or discussing this project, please reach out — see
Contact below.

---

## 🔐 Security

If you discover a security vulnerability, please **do not open a public issue**. See
[SECURITY.md](SECURITY.md) for how to report it privately.

---

## 👤 Author

**Vishal Goyal**
Solo-designed and built — backend architecture, RAG pipeline, AI integrations, deployment
infrastructure, and frontend.

---

## 📞 Contact

- **GitHub:** [@vishalgoyal25](https://github.com/vishalgoyal25)
- **Mail** [@vishal25goyal25@gmail.com](mailto:[vishal25goyal25@gmail.com])
- For security reports, see [SECURITY.md](SECURITY.md).

---

**Built for UPSC aspirants — grounded in real content, not generic AI guesses.**
