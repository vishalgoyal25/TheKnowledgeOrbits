# PROJECT_VISION.md

## TheKnowledgeOrbits — Engine-First EdTech Platform

**PKB File #1 | Version: 1.0 | Date: Feb 2026**

---

## 1. WHAT WE ARE BUILDING

A UPSC preparation ed-tech platform targeting 10M+ users.
Solo developer project, AgenticAI-accelerated, engine-first architecture.

**Core product loop:**
Raw content (PDFs, news) → Chunks → RAG → AI-generated Articles + Quizzes → User learns → Progress tracked → Personalized path

---

## 2. PLATFORM NAME & IDENTITY

- **Name:** TheKnowledgeOrbits
- **Domain:** UPSC Civil Services Exam Preparation
- **Target Users:** Indian students preparing for UPSC CSE, State PSC exams
- **Scale Target:** 10M+ users
- **Developer Model:** Solo dev + AgenticAI (human-in-the-loop)

---

## 3. CORE PRINCIPLES (NON-NEGOTIABLE)

1. **Content-First** — Content semantics must be clear before any feature is built
2. **Chunk-Based** — All content stored as semantic chunks (~1200 chars). Articles and quizzes are GENERATED from chunks, never stored raw
3. **RAG-First** — All GenAI outputs must be grounded in retrieved chunks. Zero hallucination tolerance
4. **Engine-First** — One engine = one responsibility. No feature-first thinking
5. **Event-Driven** — Engines communicate via events only. No cross-engine DB access
6. **Independent Scaling** — Each engine owns its data, tables, and APIs
7. **Human Authority** — AgenticAI accelerates, never decides. Human approves everything

---

## 4. ARCHITECTURE LAYERS (33 ENGINES)

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

## 5. CONTENT FLOW (CRITICAL PATH)

```
PDF / Web / News
      ↓
  Content Engine          (ingest → OCR → chunk → embed)
      ↓
  Knowledge Engine        (map chunks → topics → syllabus)
      ↓
  Article Gen Engine      (RAG: fetch chunks → GROQ → article)
      ↓
  Assessment Engine       (RAG: fetch chunks → GROQ → MCQs)
      ↓
  User State Engine       (track reads, attempts, progress)
      ↓
  Analytics Engine        (aggregate → insights)
      ↓
  Personalization Engine  (weak areas → learning path)
```

---

## 6. DEVELOPMENT PHASES

```
Phase 0  (Week 1)     → PKB completion + environment setup
Phase 1  (Weeks 2-4)  → Core 5 engines: Content, Knowledge, Assessment, User State, Analytics
Phase 2  (Weeks 5-7)  → Article Generation + Current Affairs (RAG + GenAI)
Phase 3  (Weeks 8-10) → Frontend (Next.js)
Phase 4  (Weeks 11-12)→ Deploy → PUBLIC BETA
Phase 5  (Weeks 13-15)→ Commerce (monetization)
Phase 6  (Weeks 16-19)→ Engagement engines
Phase 7  (Weeks 20-24)→ Intelligence engines
Phase 8  (Weeks 25-28)→ Advanced content engines
Phase 9  (Weeks 29-32)→ Growth engines
Phase 10 (Weeks 33-36)→ Enterprise engines
```

---

## 7. SECURITY STACK (MANDATORY — NO EXCEPTIONS)

| Concern          | Solution                         |
| ---------------- | -------------------------------- |
| Password Hashing | Argon2 only                      |
| Authentication   | JWT (stateless, simplejwt)       |
| Authorization    | RBAC via middleware + JWT claims |
| Token Storage    | HttpOnly cookies                 |
| Secrets          | direnv + .env (never hardcoded)  |

---

## 8. OBSERVABILITY STACK (MANDATORY)

| Concern            | Tool                          |
| ------------------ | ----------------------------- |
| Python Logging     | structlog (prod) + rich (dev) |
| Node.js Logging    | chalk                         |
| Error Tracking     | Sentry                        |
| Tracing (future)   | OpenTelemetry                 |
| Async Task Monitor | Flower (Celery dashboard)     |
| Uptime Monitor     | Uptime Kuma                   |
| Metrics Dashboard  | Grafana                       |

**Hard Rules:**

- ❌ No `print()` anywhere in Python
- ❌ No `console.log()` anywhere in Node.js
- ✅ Every module initializes a logger
- ✅ All unhandled exceptions reported to Sentry

---

## 9. AGENTICAI ROLE IN THIS PROJECT

**Development-time only.** Never runtime.

AgenticAI = controlled code generator that follows PKB rules.

- Generates one file at a time
- Human reviews and approves every output
- PKB is read-only for agents
- Cannot change architecture or invent tools

**Two agent classes (isolated, never mixed):**

1. Dev-time agents → scaffold engines, generate code, run tests
2. Runtime agents → content orchestration, learning path planning (Phase 7+)

---

## 10. WHAT THIS PROJECT IS NOT

- ❌ Not a feature-first app
- ❌ Not autonomous AI
- ❌ Not a monolith
- ❌ Not built all at once
- ❌ Not hallucination-tolerant
