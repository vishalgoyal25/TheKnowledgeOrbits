# TECH_STACK.md
## TheKnowledgeOrbits — Authorized Technology Stack
**PKB File #2 | Version: 1.0 | Date: Feb 2026**

---

## 1. BACKEND

| Layer | Tool | Version | Purpose |
|-------|------|---------|---------|
| Framework | Django | 5.0 | Core backend |
| API | Django REST Framework | 3.15 | REST APIs |
| Auth | djangorestframework-simplejwt | latest | JWT tokens |
| Password | django[argon2] | latest | Argon2 hashing only |
| DB | PostgreSQL | 16 | Primary database |
| Vector | pgvector | latest | Embeddings storage |
| Cache | Redis | 7.0 | Caching + session |
| Task Queue | Celery | 5.0 | Async background jobs |
| Task Monitor | Flower | latest | Celery dashboard |
| ORM Extras | django-environ | latest | Env config |

---

## 2. FRONTEND

| Layer | Tool | Version | Purpose |
|-------|------|---------|---------|
| Framework | Next.js | 16 | App Router, SSR |
| Language | TypeScript | 5.x | Type safety |
| UI Components | shadcn/ui | latest | Base component library |
| Styling | Tailwind CSS | 3.x | Utility-first CSS |
| Data Fetching | TanStack Query | 5.x | Server state management |
| Logging | chalk | latest | Colored Node.js logs |

---

## 3. AI / ML

| Tool | Purpose |
|------|---------|
| GROQ API | Article + Quiz generation (LLM) |
| sentence-transformers | Chunk embeddings (384-dim) |
| Whisper API | Video transcription (Phase 8+) |
| Tesseract + PaddleOCR | PDF OCR |
| LangGraph | AgenticAI dev workflows (Phase 7+) |
| LangChain | Agent tooling layer (Phase 7+) |

---

## 4. OBSERVABILITY & LOGGING

| Tool | Where | Purpose |
|------|-------|---------|
| structlog | Python (production) | Structured logging |
| rich | Python (development) | Formatted output + tracebacks |
| chalk | Node.js | Colored terminal logs |
| Sentry | Both | Error tracking + alerts |
| OpenTelemetry | Both (Phase 8+) | Distributed tracing |
| Grafana | Infra | Metrics dashboards |
| Uptime Kuma | Infra | Uptime monitoring |

**Hard Rules:**
- ❌ `print()` banned — use structlog/rich
- ❌ `console.log()` banned — use chalk
- ✅ Every Python module: `logger = structlog.get_logger(__name__)`
- ✅ Sentry SDK initialized in every engine

---

## 5. DEVELOPER TOOLING

| Tool | Purpose |
|------|---------|
| Conda | Environment management (myvenv) |
| direnv | Per-project env variable loading |
| pre-commit | Git hook enforcement |
| commitlint | Conventional commit validation |
| just | Command runner (Justfile) |
| watchexec | File-change watcher |
| fzf | Fuzzy finder (terminal) |
| bat | Syntax-highlighted file viewer |
| pgcli | PostgreSQL interactive CLI |
| DBeaver | DB GUI client |
| tig | Terminal Git UI |
| ngrok | Local → public URL tunnel |
| HTTPie | CLI HTTP client |
| Postman/Insomnia | API testing GUI |

---

## 6. TESTING

| Tool | Purpose |
|------|---------|
| pytest | Python test runner |
| factory_boy | Test fixture factories |
| faker | Fake data generation |
| Schemathesis | API property-based testing |
| Locust | Load/performance testing (Phase 8+) |

---

## 7. SECURITY & SCANNING

| Tool | Purpose |
|------|---------|
| Bandit | Python static security analysis |
| Trivy | Container vulnerability scanning |
| Fail2Ban | SSH/login brute-force protection |

---

## 8. CI/CD & DEPLOYMENT

| Tool | Purpose |
|------|---------|
| Docker | Containerization |
| Docker Compose | Local multi-service orchestration |
| Watchtower | Auto-update running containers |
| GitHub Actions | CI/CD pipeline |
| Render | Backend hosting |
| Vercel | Frontend hosting |
| Supabase | Managed PostgreSQL |
| Cloudinary | CDN + media storage |

---

## 9. DOCUMENTATION & REVIEW

| Tool | Purpose |
|------|---------|
| MkDocs | PKB documentation site (optional) |
| Mermaid | Architecture diagrams (in .md) |
| Danger.js | PR validation bot |
| CodeRabbit | AI-powered code review |
| Cursor / Aider | Context-aware coding assistant |

---

## 10. RULES

- ❌ No tool outside this list without human approval
- ❌ No library added without updating this file first
- ✅ Agents read this file to validate imports
- ✅ All tools phased per EXECUTION_ROADMAP.md
