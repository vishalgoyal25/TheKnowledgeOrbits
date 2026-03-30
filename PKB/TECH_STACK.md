# TECH_STACK.md

## TheKnowledgeOrbits — Authorized Technology Stack

**PKB File #2 | Version: 1.1 | Date: March 2026**

---

## 1. BACKEND

| Layer        | Tool                          | Version | Purpose               |
| ------------ | ----------------------------- | ------- | --------------------- |
| Framework    | Django                        | 5.0     | Core backend          |
| API          | Django REST Framework         | 3.15    | REST APIs             |
| Auth         | djangorestframework-simplejwt | latest  | JWT tokens            |
| Password     | django[argon2]                | latest  | Argon2 hashing only   |
| DB           | PostgreSQL                    | 16      | Primary database      |
| Vector       | pgvector                      | latest  | Embeddings storage    |
| Cache        | Redis                         | 7.0     | Caching + session     |
| Task Queue   | Celery                        | 5.0     | Async background jobs |
| Task Monitor | Flower                        | latest  | Celery dashboard      |
| ORM Extras   | django-environ                | latest  | Env config            |
| CORS         | django-cors-headers           | 4.6+    | Cross-origin headers  |
| DB Adapter   | psycopg2-binary               | 2.9+    | PostgreSQL driver     |
| Cache Layer  | django-redis                  | 5.4+    | Django Redis backend  |
| RSS Scraping | feedparser                    | 6.0+    | RSS/Atom feed parsing |
| HTML Parse   | beautifulsoup4                | 4.12+   | News content parsing  |
| WSGI Server  | gunicorn                      | 23.0+   | Production app server |
| Static Files | whitenoise                    | 6.9+    | Serve static on Render|
| Formatter    | black                         | 24.x    | Code auto-formatting  |
| Imports      | isort                         | 5.13+   | Import sorting        |
| Type Check   | mypy + django-stubs           | latest  | Static type analysis  |
| Linter       | ruff                          | latest  | Fast Python linter    |

---

## 2. FRONTEND

| Layer         | Tool           | Version | Purpose                 |
| ------------- | -------------- | ------- | ----------------------- |
| Framework     | Next.js        | 16      | App Router, SSR         |
| Language      | TypeScript     | 5.x     | Type safety             |
| UI Components | shadcn/ui      | latest  | Base component library  |
| Styling       | Tailwind CSS   | 3.x     | Utility-first CSS       |
| Data Fetching | TanStack Query | 5.x     | Server state management |
| Logging       | chalk          | latest  | Colored Node.js logs    |
| HTTP Client   | axios          | 1.x     | API request handling    |
| Animations    | framer-motion  | 12.x    | Page & UI animations    |
| Forms         | react-hook-form| 7.x     | Controlled form state   |
| Validation    | zod            | 4.x     | Schema validation       |
| Toasts        | sonner         | 2.x     | Toast notifications     |
| Markdown      | react-markdown | 10.x    | Render Markdown content |
| Icons         | lucide-react   | latest  | Icon component library  |
| Cookies       | js-cookie      | 3.x     | Client cookie access    |
| Utilities     | lodash         | 4.x     | General utility helpers |
| Date Utils    | date-fns       | 4.x     | Date formatting         |
| Charts        | recharts       | 3.x     | Analytics/stat charts   |
| Formatter     | prettier       | 3.x     | Code auto-formatting    |
| Linter        | eslint         | 8.x     | JS/TS linting           |

---

## 3. AI / ML

| Tool                  | Purpose                            |
| --------------------- | ---------------------------------- |
| GROQ API              | Article + Quiz generation (LLM)    |
| sentence-transformers | Chunk embeddings (384-dim)         |
| Whisper API           | Video transcription (Phase 8+)     |
| Tesseract + PaddleOCR | PDF OCR                            |
| LangGraph             | AgenticAI dev workflows (Phase 7+) |
| LangChain             | Agent tooling layer (Phase 7+)     |

---

## 4. OBSERVABILITY & LOGGING

| Tool          | Where                | Purpose                       |
| ------------- | -------------------- | ----------------------------- |
| structlog     | Python (production)  | Structured logging            |
| rich          | Python (development) | Formatted output + tracebacks |
| chalk         | Node.js              | Colored terminal logs         |
| Sentry        | Both                 | Error tracking + alerts       |
| OpenTelemetry | Both (Phase 8+)      | Distributed tracing           |
| Grafana       | Infra                | Metrics dashboards            |
| Uptime Kuma   | Infra                | Uptime monitoring             |

**Hard Rules:**

- ❌ `print()` banned — use structlog/rich
- ❌ `console.log()` banned — use chalk
- ✅ Every Python module: `logger = structlog.get_logger(__name__)`
- ✅ Sentry SDK initialized in every engine

---

## 5. DEVELOPER TOOLING

| Tool             | Purpose                          |
| ---------------- | -------------------------------- |
| Conda            | Environment management (myvenv)  |
| direnv           | Per-project env variable loading |
| pre-commit       | Git hook enforcement             |
| commitlint       | Conventional commit validation   |
| just             | Command runner (Justfile)        |
| watchexec        | File-change watcher              |
| fzf              | Fuzzy finder (terminal)          |
| bat              | Syntax-highlighted file viewer   |
| pgcli            | PostgreSQL interactive CLI       |
| DBeaver          | DB GUI client                    |
| tig              | Terminal Git UI                  |
| ngrok            | Local → public URL tunnel        |
| HTTPie           | CLI HTTP client                  |
| Postman/Insomnia | API testing GUI                  |

---

## 6. TESTING

| Tool         | Purpose                             |
| ------------ | ----------------------------------- |
| pytest           | Python test runner                  |
| pytest-django    | Django integration for pytest       |
| pytest-cov       | Test coverage reporting             |
| factory_boy      | Test fixture factories              |
| faker            | Fake data generation                |
| Schemathesis     | API property-based testing          |
| jest             | Frontend JavaScript test runner     |
| @testing-library | React component testing utilities   |
| Locust           | Load/performance testing (Phase 8+) |

---

## 7. SECURITY & SCANNING

| Tool     | Purpose                          |
| -------- | -------------------------------- |
| Bandit   | Python static security analysis  |
| Trivy    | Container vulnerability scanning |
| Fail2Ban | SSH/login brute-force protection |

---

## 8. CI/CD & DEPLOYMENT

| Tool           | Purpose                           |
| -------------- | --------------------------------- |
| Docker         | Containerization                  |
| Docker Compose | Local multi-service orchestration |
| Watchtower     | Auto-update running containers    |
| GitHub Actions | CI/CD pipeline                    |
| Render         | Backend hosting                   |
| Vercel         | Frontend hosting                  |
| Supabase       | Managed PostgreSQL                |
| Cloudinary     | CDN + media storage               |

---

## 9. DOCUMENTATION & REVIEW

| Tool           | Purpose                           |
| -------------- | --------------------------------- |
| MkDocs         | PKB documentation site (optional) |
| Mermaid        | Architecture diagrams (in .md)    |
| Danger.js      | PR validation bot                 |
| CodeRabbit     | AI-powered code review            |
| Cursor / Aider | Context-aware coding assistant    |

---

## 10. RULES

- ❌ No tool outside this list without human approval
- ❌ No library added without updating this file first
- ✅ Agents read this file to validate imports
- ✅ All tools phased per EXECUTION_ROADMAP.md

---

## 11. IMPLEMENTATION & VERIFICATION STATUS

- [x] **Backend Core:** Django, DRF, simplejwt, argon2, CORS, psycopg2 all active.
- [x] **Async:** Celery + Redis configured; `django-redis` cache backend live.
- [x] **AI/ML:** GROQ API, sentence-transformers, feedparser + beautifulsoup4 active.
- [x] **Frontend Core:** Next.js 16, TanStack Query, shadcn/ui, Tailwind active.
- [x] **Frontend UX:** axios, framer-motion, react-hook-form, zod, sonner, recharts active.
- [x] **Markdown Rendering:** react-markdown + remark-gfm verified in article reader.
- [x] **Observability:** structlog (backend) + Sentry (frontend via @sentry/nextjs) active.
- [x] **Testing:** pytest + pytest-django + factory_boy (backend); jest + @testing-library (frontend).
- [x] **Production:** gunicorn + whitenoise (backend); Render + Vercel (deployed).
- [x] **Code Quality:** black, isort, mypy, ruff (backend); prettier, eslint (frontend) enforced via pre-commit.
