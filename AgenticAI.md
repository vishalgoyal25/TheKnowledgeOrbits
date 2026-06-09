
# Plan: TheKnowledgeOrbits — Research Agent (AgenticAI Feature)

## Context
Building a standalone, production-grade AgenticAI Research Agent integrated into TheKnowledgeOrbits platform.

7-agent LangGraph system. Fully isolated from existing engines. Showcase LLMOps + AgentOps + AgenticAI skills.

---

## LOCKED DESIGN DECISIONS

| Decision | Answer |
|---|---|
| Public or auth-required? | Both: public = 3 queries/day (rate-limited). Logged-in = unlimited + full history saved |
| Save history for logged-in? | Yes — sessions + reports saved. Guests = no DB save, SSE only |
| Free APIs only? | Y — Groq + Cerebras sufficient. Global retry/backoff wrapper on all LLM calls |
| Retry loop API cost? | Limit to MAX 1 retry (not 2). Saves ~30% API calls. Still demonstrates the pattern |
| Langfuse = who sees it? | Developer only (dashboard). User sees derived "Research Confidence %" badge only |
| DeepEval = who sees it? | Developer analysis. User sees confidence badge (derived from scores). Not raw scores |
| Langfuse tier? | Cloud free tier (langfuse.com) |
| DeepEval run? | Local (no cloud cost, no data sent externally) |
| Voice input? | Web Speech API — browser-native, completely free |
| LangGraph checkpointing? | PostgreSQL checkpointer (existing DB, new table) |
| Real-time: SSE or WS? | SSE confirmed |
| Deployment? | Existing Render + Vercel + Supabase — no AWS needed for v1 |
| Docker? | Production deployment only. Never local dev |
| DB sync? | localhost + Supabase simultaneously via existing migrate command |
| Git branch? | feature/research-agent — merge to main only after full verification |
| Project subfolder name? | research_agent (backend + frontend both) |
| Requirements files? | Distribute into existing backend/requirements/*.txt (base, ml, prod, dev) |
| Homepage integration? | New entry point widget on homepage, new /research route. Zero touch to existing sections |

---

## WHAT GETS SAVED IN DB (Per Query)

```
research_session    → created on query submit. stores: query, user_id, status, langfuse_trace_id, timestamps
research_report     → created after Report Generator completes. stores: full markdown, sources, confidence score
agent_execution_log → one row PER AGENT PER SESSION. stores: agent_name, status, duration_ms, tokens, model, output_summary
evaluation_result   → created after DeepEval runs. stores: hallucination, faithfulness, relevance, completeness scores
agent_state_snapshot → NEW 5th table: stores full LangGraph state JSON at each node transition (for LLMOps demo)
```

**5 tables total** (not 4). The `agent_state_snapshot` table is what makes it "Demonstrable LLMOps maturity" —
a recruiter can see the full state evolution across every agent node.

---

## FILES TO UPDATE / CREATE (MD files only, before any code)

### Update (minimal changes only):
- `CLAUDE.md` — current focus, tech stack additions, DO NOT TOUCH additions, new hard rules
- `memory/feature2_progress.md` — stamp COMPLETE
- `memory/MEMORY.md` — update index
- `PKB/ENGINE_CATALOG.md` — add research_agent entry
- `PKB/DATABASE_SCHEMA.md` — add 5 new tables
- `PKB/API_REFERENCE.md` — add research agent endpoints
- (skip: ARCHITECTURE.md, CODING_STANDARDS.md, DATA_FLOW_PATTERNS.md, TESTING_GUIDE.md, EVENT_DRIVEN.md, EXECUTION_ROADMAP.md — not critical, saves tokens)

### Create fresh:
- `FEATURES.md` — brand new, Research Agent only, phases 1–12
- `agentic_ai_roadmap.md` — full architecture: ResearchState schema, routing logic, rate-limit middleware, Langfuse+DeepEval hooks
- `memory/research_agent_progress.md` — new memory file for this feature

---

## EXECUTION PLAN (Sequential)

### PRE-CODING (MD files + setup)
1. Update CLAUDE.md
2. Create fresh FEATURES.md
3. Create agentic_ai_roadmap.md
4. Update memory files
5. Update 3 PKB files (minimal)
6. Approve all new dependencies (list in FEATURES.md)
7. Obtain all free API keys: Tavily (free tier), Langfuse (cloud free), DeepEval (local)
8. Create git branch: feature/research-agent

### PHASE 1 — Full Project Scaffold (both backend + frontend, all ~101 empty files)
### PHASE 2 — LangGraph State + Graph + Checkpointing
### PHASE 3 — Tool Registry + Tools (Tavily, Exa, Wiki, Calculator, Domain Classifier, Circuit Breaker)
### PHASE 4 — All 7 Agent Implementations (incl. Reflection Agent)
### PHASE 5 — Orchestrator + SSE Service + API Endpoints
### PHASE 6 — Model Router + Guardrails + Rate-limit Token Bucket Middleware
### PHASE 7 — Langfuse LLMOps + Prompt Versioning + AgentOps Instrumentation
### PHASE 8 — Redis Caching + Memory Service (short-term + long-term)
### PHASE 9 — DeepEval Evaluation Pipeline + Export Service (PDF + MD)
### PHASE 10 — Frontend: React Flow + SSE Hook + Live Workflow Graph
### PHASE 11 — Frontend: Full Research UI + Voice Input + Report + History
### PHASE 12 — Homepage Integration (entry widget, /research route wired to nav)
### PHASE 13 — Docker + CI/CD Update + Production Deployment Verification
### PHASE 14 — Full localhost verification → merge feature/research-agent → main

---

## VERIFICATION (per phase)
- Each phase: `python manage.py check` + targeted pytest for that phase's files
- SSE: tested via curl before frontend connects
- LangGraph: tested via management command `test_research_agent` before API wired
- React Flow: tested on localhost before any deployment
- Final: full end-to-end run on localhost → then Render/Vercel deploy → live verification → merge to main

<!-- ============================================= -->
