# ENGINE_CATALOG.md

## TheKnowledgeOrbits — Engine Catalog

**PKB File #8 | Version: 1.0 | Date: Feb 2026**

---

## 1. ENGINE CONTRACT RULES

Every engine must define:

- Responsibility (single sentence)
- Auth required (Y/N)
- RBAC roles allowed
- Sync or Async operations
- AgenticAI use (what agents can do here)

❌ No engine exists without this entry
❌ No engine skips observability (logging + Sentry)
✅ All engines own their DB tables exclusively

---

## 2. PHASE 1 ENGINES (Core — Build First)

### CONTENT ENGINE

- **Responsibility:** Ingest, process, chunk all raw content (PDF, web, text)
- **Auth:** Upload = YES (admin/content_manager). Read = YES (any authenticated)
- **RBAC:** upload → admin, content_manager | read → all authenticated
- **Sync/Async:** Upload = sync (small) / async via Celery (large). Chunking = always async
- **AgenticAI:** Automate ingestion pipelines, validate chunk quality (human-approved)
- **Tables:** content_document, content_chunk, content_embedding, content_asset, content_ingestion_job

### KNOWLEDGE ENGINE

- **Responsibility:** Organize chunks into syllabus structure (programs, subjects, modules, topics)
- **Auth:** Write = YES (admin/content_manager). Read = YES (any authenticated)
- **RBAC:** create/update → admin, content_manager | read → all authenticated
- **Sync/Async:** All sync
- **AgenticAI:** Suggest concept relationships (never auto-modify without approval)
- **Tables:** knowledge_program, knowledge_subject, knowledge_module, knowledge_topic, knowledge_chunk_topic_map

### ASSESSMENT ENGINE

- **Responsibility:** Generate quizzes/tests from chunks, evaluate responses
- **Auth:** Generate = YES (admin). Take = YES (any authenticated)
- **RBAC:** generate → admin, content_manager | attempt → student, free_user
- **Sync/Async:** Generation = async (Celery). Submission = sync
- **AgenticAI:** Generate question variants, reason over wrong answers
- **Tables:** assessment_quiz, assessment_question, assessment_quiz_attempt, assessment_question_response

### USER STATE ENGINE

- **Responsibility:** Track all user actions via event sourcing, compute progress + mastery
- **Auth:** YES (all operations user-scoped)
- **RBAC:** read/write own data → all authenticated | read others → admin
- **Sync/Async:** Event storage = sync. Progress computation = async (cron)
- **AgenticAI:** Pattern detection over state, insight suggestion (never mutate state)
- **Tables:** userstate_event, userstate_progress, userstate_topic_mastery, userstate_bookmark, userstate_reading_progress

### ANALYTICS ENGINE

- **Responsibility:** Aggregate user events, generate performance insights
- **Auth:** YES (user sees own data, admin sees all)
- **RBAC:** own data → all authenticated | all data → admin
- **Sync/Async:** Aggregation = async (daily cron). Dashboard read = sync
- **AgenticAI:** Insight summarization, trend explanation
- **Tables:** analytics_daily_aggregate, analytics_insight

---

## 3. PHASE 1 OPERATIONAL ENGINES

### AUTH ENGINE

- **Responsibility:** User registration, login, JWT issuance, email verification
- **Auth:** Login/Register = NO auth. All others = YES
- **RBAC:** N/A (this engine issues roles)
- **Sync/Async:** All sync
- **AgenticAI:** ❌ NONE (strictly deterministic)
- **Tables:** auth_user, auth_role, auth_role_assignment

### AUTHORIZATION ENGINE

- **Responsibility:** RBAC enforcement, role management, permission checks
- **Auth:** YES (admin only for role management)
- **RBAC:** role CRUD → admin only
- **Sync/Async:** All sync (middleware)
- **AgenticAI:** ❌ NONE (strictly deterministic)
- **Tables:** Shares auth_role, auth_role_assignment (read-only access)

---

## 4. PHASE 2 ENGINES

### ARTICLE GENERATION ENGINE

- **Responsibility:** Generate articles from chunks using RAG + GROQ
- **Auth:** Generate = YES (admin/content_manager). Read = YES (any authenticated)
- **RBAC:** generate → admin, content_manager | read → all authenticated
- **Sync/Async:** Generation = async (Celery). Read = sync
- **AgenticAI:** Multi-agent orchestration (research → write → review)
- **Tables:** article_article, article_source_map

### CURRENT AFFAIRS ENGINE

- **Responsibility:** Ingest daily news via RSS, chunk, link to syllabus topics
- **Auth:** Read = YES (any authenticated). RSS scrape = system (no user auth)
- **RBAC:** manual topic link → admin, content_manager | read → all authenticated
- **Sync/Async:** Scraping = async (daily cron). Read = sync
- **AgenticAI:** Topic classification assistance
- **Tables:** ca_source, ca_article, ca_chunk, ca_topic_link

---

## 5. PHASE 5+ ENGINES (Summary)

| Engine          | Phase | Auth               | AgenticAI Use                       |
| --------------- | ----- | ------------------ | ----------------------------------- |
| Search          | 5     | Read = any auth    | Query intent interpretation         |
| Notification    | 5     | System-scoped      | Message drafting, priority          |
| Commerce        | 5     | YES                | ❌ NONE (deterministic)             |
| Storage         | 5     | YES (admin upload) | ❌ NONE                             |
| Cache           | 5     | System-only        | ❌ NONE                             |
| Gamification    | 6     | YES (user-scoped)  | Pattern-based reward suggestions    |
| Collaboration   | 6     | YES (user-scoped)  | Thread summarization                |
| Revision        | 6     | YES (user-scoped)  | Schedule optimization               |
| Personalization | 7     | YES (user-scoped)  | Planning + reasoning                |
| AI Tutor        | 7     | YES (user-scoped)  | Multi-step reasoning (RAG-grounded) |
| Prediction      | 7     | YES (user-scoped)  | Probabilistic reasoning             |
| Mock Test       | 8     | YES (user-scoped)  | Performance reasoning (post-test)   |
| Video           | 8     | YES                | Transcript segmentation             |
| NLP             | 8     | YES                | Rubric-based reasoning              |
| Computer Vision | 8     | YES                | CV model orchestration              |
| Voice           | 8     | YES                | Feedback reasoning                  |
| Marketing       | 9     | Admin              | Insight + suggestion only           |
| Onboarding      | 9     | User-scoped        | ❌ NONE                             |
| Retention       | 9     | Admin              | Insight + suggestion only           |
| Marketplace     | 10    | YES                | Insight only, no auto-execute       |
| White-label     | 10    | Admin              | ❌ NONE                             |
| Moderation      | 10    | Admin              | Risk detection (human approval)     |
| Privacy         | 10    | Admin + user       | ❌ NONE (deterministic)             |
| Reporting       | 10    | Admin              | Explanation + reporting             |

---

## 6. AGENT PERMISSIONS PER ENGINE

| Agent           | What it can do across ALL engines                 |
| --------------- | ------------------------------------------------- |
| Architect Agent | Generate skeleton (folders + empty files)         |
| Engine Builder  | Generate ONE file (model/serializer/view/service) |
| Test Agent      | Generate tests for approved code only             |
| Migration Agent | Generate migrations after model approval          |
| Review Agent    | Validate compliance against PKB (report only)     |

❌ No agent writes business logic autonomously
❌ No agent touches another engine's tables
✅ Human approves before any engine is marked stable
