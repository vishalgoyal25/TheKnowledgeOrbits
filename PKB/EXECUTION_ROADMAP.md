# EXECUTION_ROADMAP.md

## TheKnowledgeOrbits — Execution Roadmap

**PKB File #12 | Version: 1.0 | Date: Feb 2026**

---

## 1. PURPOSE

This file is the ONLY source of truth for:

- What gets built when
- Which tools activate at each phase
- What success criteria must pass before the next phase begins
- Go/No-Go gates (mandatory checkpoints)

❌ Never build future-phase features early
❌ Never activate tools before their phase
✅ Always check this file before starting any work

---

## 2. PHASE 0 — SETUP (Week 1)

### Goal

Environment, skeleton, CI. Zero business logic.

### Deliverables

- [x] Mono-repo structure (backend/ + frontend/ + PKB/)
- [x] Django 5 + DRF skeleton (`core/` project, `engines/` package)
- [x] Next.js 16 + TypeScript skeleton (App Router)
- [x] PostgreSQL 16 + pgvector on Supabase
- [x] Redis 7.0 (local via Docker Compose)
- [x] Docker Compose: backend + frontend + postgres + redis
- [x] GitHub Actions CI pipeline (lint + test on PR)
- [x] direnv + .env configured
- [x] pre-commit hooks active (commitlint enforced)
- [x] Justfile with: `just dev`, `just test`, `just migrate`

### Tools Activated This Phase

| Tool                             | Why now                        |
| -------------------------------- | ------------------------------ |
| Django 5 + DRF                   | Core backend                   |
| Next.js 16 + TypeScript          | Core frontend                  |
| PostgreSQL 16 + pgvector         | Database                       |
| Redis 7.0                        | Celery broker (needed Phase 1) |
| Docker + Docker Compose          | Local multi-service            |
| GitHub Actions                   | CI from day one                |
| structlog + rich                 | Logging from day one           |
| chalk                            | Frontend logging from day one  |
| Sentry                           | Error tracking from day one    |
| pytest + factory_boy + faker     | Testing from day one           |
| direnv + pre-commit + commitlint | Workflow from day one          |
| Conda (myvenv)                   | Python env management          |
| pgcli + DBeaver                  | DB interaction                 |
| HTTPie + Postman                 | API testing                    |
| Bandit                           | Python security scan           |

### Success Criteria (all must pass)

- ✅ `python manage.py runserver` → 200 on `/api/v1/health`
- ✅ `npm run dev` → Next.js compiles clean
- ✅ `just test` → pytest finds and runs (0 failures)
- ✅ GitHub Actions green on a dummy PR
- ✅ `.env` never committed (verified by pre-commit)

### Go/No-Go Gate

All 5 criteria pass → Phase 1 begins. If not → fix before proceeding.

---

## 3. PHASE 1 — CORE ENGINES (Weeks 2–4)

### Goal

5 core engines + Auth/Authorization. MVP backend functional. No frontend yet.

### Week 2: Content Engine + Auth Engine

**Content Engine deliverables:**

- [x] PDF upload endpoint
- [x] Text extraction (pdfplumber)
- [x] Chunking service (1200 chars)
- [x] Embedding generation (sentence-transformers, 384-dim)
- [x] Ingestion job tracking (pending → processing → done/failed)
- [x] Tables: content_document, content_chunk, content_embedding, content_asset, content_ingestion_job

**Auth Engine deliverables:**

- [x] Register, login, verify-email, refresh-token
- [x] Argon2 password hashing
- [x] JWT issuance (access 5 min, refresh 7 days)
- [x] HttpOnly cookie setting
- [x] Tables: auth_user, auth_role, auth_role_assignment
- [x] Seed: admin, content_manager, student, free_user roles

**Tools Activated This Phase**
| Tool | Why now |
|------|---------|
| Celery 5.0 + Flower | Async chunking + ingestion jobs |
| sentence-transformers | Chunk embeddings |
| pdfplumber | PDF text extraction |
| Tesseract + PaddleOCR | Scanned PDF OCR |
| djangorestframework-simplejwt | JWT auth |
| django[argon2] | Password hashing |
| Schemathesis | API property-based testing |

**Tests:** 20+ passing (Content) + 15+ passing (Auth)

---

### Week 3: Knowledge Engine

**Deliverables:**

- [x] Program / Subject / Module / Topic CRUD
- [x] Chunk-topic mapping (many-to-many)
- [x] Basic text search across topics + chunks
- [x] Tables: knowledge_program, knowledge_subject, knowledge_module, knowledge_topic, knowledge_chunk_topic_map

**Tests:** 15+ passing

---

### Week 4: Assessment Engine + User State Engine + Analytics Engine

**Assessment Engine deliverables:**

- [x] Quiz generation from chunks (GROQ MCQ generation)
- [x] Quiz start / submit-answer / submit-quiz flow
- [x] Auto-grading + explanation generation
- [x] Tables: assessment_quiz, assessment_question, assessment_quiz_attempt, assessment_question_response

**User State Engine deliverables:**

- [x] Event recording (append-only)
- [x] Progress computation
- [x] Topic mastery tracking
- [x] Bookmarks + reading progress
- [x] Tables: userstate_event, userstate_progress, userstate_topic_mastery, userstate_bookmark, userstate_reading_progress

**Analytics Engine deliverables:**

- [x] Daily aggregation skeleton (cron stub)
- [x] Insight table + basic weak_topic detection logic
- [x] Tables: analytics_daily_aggregate, analytics_insight

**Tools Activated This Phase**
| Tool | Why now |
|------|---------|
| GROQ API | Quiz MCQ generation |

**Tests:** 30+ passing (Assessment + User State + Analytics combined)

### Phase 1 Success Criteria

- ✅ Upload PDF → chunks appear in DB with embeddings
- ✅ Map chunk to topic → query returns linked chunks
- ✅ Generate quiz for topic → quiz + questions created
- ✅ Start → answer → submit quiz → score returned + event fired
- ✅ User State records event → progress updates
- ✅ All auth flows work (register → verify → login → refresh)
- ✅ 65+ tests passing total

### Go/No-Go Gate

All criteria pass → Phase 2 begins. **MVP backend is functional.**

---

## 4. PHASE 2 — ARTICLE GENERATION + CURRENT AFFAIRS (Weeks 5–7)

### Goal

RAG pipeline live. Articles generated from chunks. CA ingestion running.

### Week 5: Article Generation Engine (Static)

- [x] Chunk selection by topic (via Knowledge Engine API)
- [x] RAG: retrieve chunks → GROQ generates narrative
- [x] Source attribution (article_source_map)
- [x] Quality scoring before publish
- [x] Tables: article_article, article_source_map

### Week 6: Current Affairs Engine

- [x] RSS scraping (The Hindu, Indian Express)
- [x] CA chunking + embedding (same 384-dim space)
- [x] Semantic topic classification → ca_topic_link
- [x] Expiry date management
- [x] Tables: ca_source, ca_article, ca_chunk, ca_topic_link
- [x] Cron: RSS scrape 6 AM IST, CA expiry cleanup 6:30 AM IST

### Week 7: Integrated Article Generation

- [x] Merge static chunks + CA chunks for same topic
- [x] Context blending in GROQ prompt
- [x] Integrated article output with source types marked
- [x] Event: `article_generated` emitted on completion
- [x] Event: `ca_chunks_classified` emitted after daily scrape

### Phase 2 Success Criteria

- ✅ Upload NCERT PDF → chunk → map → generate article → article readable
- ✅ RSS scrape runs → CA articles chunked → topics auto-linked
- ✅ Integrated article contains both static theory + CA examples
- ✅ article_source_map correctly traces every chunk used
- ✅ Events fire correctly (article_generated, ca_chunks_classified)

### Go/No-Go Gate

All criteria pass → Phase 3 begins. **Core product value is proven.**

---

## 5. PHASE 3 — FRONTEND (Weeks 8–10)

### Goal

User-facing Next.js app consuming all Phase 1–2 APIs.

### Week 8: Core UI

- [x] Auth pages: login, register, email verify
- [x] Article listing (topic-filtered)
- [x] Article reader (with source attribution toggle)
- [x] Progress dashboard (basic stats)

### Week 9: Quiz UI

- [x] Quiz listing (by topic, difficulty)
- [x] Quiz taking: timed interface, answer selection
- [x] Results page: score, correct/incorrect, explanations
- [x] Frontend fires `article_read` event on article completion

### Week 10: Search + Polish

- [x] Search bar → Knowledge Engine search API
- [x] Mobile responsive layout
- [x] Error boundaries + loading states
- [x] Toast notifications for feedback

### Tools Activated This Phase

| Tool           | Why now                    |
| -------------- | -------------------------- |
| shadcn/ui      | UI components              |
| Tailwind CSS   | Styling                    |
| TanStack Query | Server state + retry logic |

### Phase 3 Success Criteria

- ✅ Full auth flow works in browser (register → verify → login → dashboard)
- ✅ Articles render with source attribution
- ✅ Quiz flow end-to-end in browser (start → answer → submit → results)
- ✅ Progress dashboard reflects quiz scores
- ✅ Search returns relevant results
- ✅ Mobile layout passes basic responsive check

### Go/No-Go Gate

All criteria pass → Phase 4 begins.

---

## 6. PHASE 4 — LAUNCH (Weeks 11–12)

### Goal

Content-populated, production-deployed, monitored. PUBLIC BETA.

### Week 11: Content Population

- [x] Ingest 5 NCERT books (History, Polity, Geography, Economy, Science)
- [x] Map all chunks to syllabus topics
- [x] Generate 100+ articles (static + integrated)
- [x] Generate 50+ quizzes across subjects
- [x] CA scraping live and running

### Week 12: Production Deploy

- [x] E2E test suite passes
- [x] Deploy backend → Render
- [x] Deploy frontend → Vercel
- [x] Supabase production DB configured
- [x] Cloudinary for media CDN
- [x] Sentry production project active
- [x] Uptime Kuma monitoring configured

### Tools Activated This Phase

| Tool        | Why now                                    |
| ----------- | ------------------------------------------ |
| Render      | Backend production hosting                 |
| Vercel      | Frontend production hosting                |
| Cloudinary  | Production CDN                             |
| Uptime Kuma | Production uptime monitoring               |
| Trivy       | Container vulnerability scan before deploy |
| Fail2Ban    | SSH brute-force protection                 |
| Watchtower  | Auto-update containers                     |

### Phase 4 Success Criteria

- ✅ 100+ articles live and readable
- ✅ 50+ quizzes playable
- ✅ CA scraping updates daily
- ✅ Sentry captures test error correctly
- ✅ Uptime Kuma shows green
- ✅ 0 critical security issues in Trivy scan

### Go/No-Go Gate

All criteria pass → **PUBLIC BETA LAUNCHES.** Phase 5 begins post-launch stabilization.

---

## 7. PHASE 5 — MONETIZATION (Weeks 13–15)

### Engines Built

- Commerce Engine (subscriptions, Razorpay, invoicing)
- Search Engine (Elasticsearch full-text + pgvector semantic)
- Notification Engine (email, push, in-app)
- Storage Engine (Cloudinary integration, versioning)
- Cache Engine (Redis query cache, rate limiting)

### Tools Activated

| Tool          | Why now                                       |
| ------------- | --------------------------------------------- |
| Razorpay SDK  | Payment processing                            |
| Elasticsearch | Full-text search (or fallback: pgvector-only) |

---

## 8. PHASE 6 — ENGAGEMENT (Weeks 16–19)

### Engines Built

- Gamification Engine (badges, leaderboards, challenges)
- Revision Engine (SM-2 spaced repetition, flashcards)
- Collaboration Engine (forums, study groups)

### Events Activated

- `streak_broken`, `flashcard_due`, `achievement_unlocked`

---

## 9. PHASE 7 — INTELLIGENCE (Weeks 20–24)

### Engines Built

- Personalization Engine (learning paths, weak area prioritization)
- Prediction Engine (score forecasting, risk alerts)
- AI Tutor Engine (RAG-grounded conversational Q&A)
- Mock Test Engine (full exam simulation, rank prediction)

### Tools Activated

| Tool      | Why now                 |
| --------- | ----------------------- |
| LangGraph | AgenticAI dev workflows |
| LangChain | Agent tooling layer     |

### Events Activated

- `learning_path_updated`, `doubt_resolved`, `mock_test_completed`

---

## 10. PHASE 8 — ADVANCED CONTENT (Weeks 25–28)

### Engines Built

- Video Engine (upload, YouTube, Whisper transcription)
- NLP Engine (descriptive grading, essay scoring)
- Computer Vision Engine (diagram analysis, handwriting)
- Voice Engine (speech-to-text, pronunciation)

### Tools Activated

| Tool          | Why now                            |
| ------------- | ---------------------------------- |
| Whisper API   | Video transcription                |
| OpenTelemetry | Distributed tracing across engines |
| Locust        | Load/performance testing           |
| Grafana       | Metrics dashboards                 |

---

## 11. PHASE 9 — GROWTH (Weeks 29–32)

### Engines Built

- Marketing Engine (referrals, campaigns, A/B tests)
- Onboarding Engine (welcome flow, tutorials)
- Retention Engine (churn prediction, win-back, loyalty)

### Events Activated

- `subscription_activated`, `churn_risk_detected`

---

## 12. PHASE 10 — ENTERPRISE (Weeks 33–36)

### Engines Built

- Marketplace Engine (third-party content, seller portal)
- White-label Engine (multi-tenant, custom branding)
- Content Moderation Engine (screening, plagiarism)
- Privacy Engine (GDPR, data export, deletion)
- Reporting Engine (admin dashboards, financial reports)

### Tools Activated

| Tool       | Why now                  |
| ---------- | ------------------------ |
| MkDocs     | PKB documentation site   |
| Danger.js  | PR validation automation |
| CodeRabbit | AI code review           |

---

## 13. TOOL ACTIVATION SUMMARY

| Tool                                        | Phase Activated | Reason            |
| ------------------------------------------- | --------------- | ----------------- |
| Django 5 + DRF                              | 0               | Core              |
| Next.js 16 + TypeScript                     | 0               | Core              |
| PostgreSQL 16 + pgvector                    | 0               | Core              |
| Redis 7.0                                   | 0               | Celery broker     |
| Docker + Docker Compose                     | 0               | Local infra       |
| GitHub Actions                              | 0               | CI                |
| structlog + rich + chalk                    | 0               | Logging           |
| Sentry                                      | 0               | Error tracking    |
| pytest + factory_boy + faker                | 0               | Testing           |
| direnv + pre-commit + commitlint            | 0               | Workflow          |
| Celery 5.0 + Flower                         | 1               | Async tasks       |
| sentence-transformers                       | 1               | Embeddings        |
| pdfplumber + Tesseract + PaddleOCR          | 1               | PDF processing    |
| simplejwt + argon2                          | 1               | Auth              |
| Schemathesis                                | 1               | API testing       |
| GROQ API                                    | 1               | LLM generation    |
| shadcn/ui + Tailwind + TanStack Query       | 3               | Frontend          |
| Render + Vercel + Supabase + Cloudinary     | 4               | Production        |
| Uptime Kuma + Trivy + Fail2Ban + Watchtower | 4               | Production ops    |
| Razorpay                                    | 5               | Payments          |
| LangGraph + LangChain                       | 7               | AgenticAI         |
| Whisper API                                 | 8               | Transcription     |
| OpenTelemetry + Grafana                     | 8               | Tracing + metrics |
| Locust                                      | 8               | Load testing      |
| MkDocs + Danger.js + CodeRabbit             | 10              | Enterprise docs   |

---

## 14. RULES

- ❌ Never build a future-phase engine early
- ❌ Never activate a tool before its designated phase
- ❌ Never skip a Go/No-Go gate
- ✅ Each phase's success criteria must ALL pass before proceeding
- ✅ Agents check this file to validate whether an engine or tool is in-scope
- ✅ Tool activation table is the master list — TECH_STACK.md defines what exists, this file defines when
