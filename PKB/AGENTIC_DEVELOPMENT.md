# AGENTIC_DEVELOPMENT.md

## TheKnowledgeOrbits — Agentic Development System

**PKB File #15 | Version: 1.0 | Date: Feb 2026**

---

## 1. PURPOSE

This file defines:

- The two-tier agent model (human-in-the-loop vs autonomous)
- When each tier activates
- What each agent does, can do, and cannot do
- The full engine build workflow (plan → scaffold → implement → test → migrate → validate)
- How agents read and respect the PKB
- Runtime agents (Phase 7+) and their boundaries

❌ AgenticAI never decides architecture
❌ AgenticAI never runs without human approval gates
✅ Engines always lead. Agents always follow.
✅ PKB is read-only for all agents, always

---

## 2. TWO-TIER AGENT MODEL

The project uses two distinct modes of AI-assisted development. They are isolated and never mixed.

### Tier 1: Human-in-the-Loop (Phases 0–6)

```
This is the active mode from project start through Phase 6.

How it works:
  → Human describes what needs to be built (one engine, one file)
  → Claude proposes the code (ONE file only)
  → Claude explains WHAT it built and WHY
  → Human reviews → approves or requests changes
  → Human says "Done" → next file begins

Tools used:
  - Claude (conversational AI assistant)
  - PKB files (read by Claude before generating)

What this IS:
  ✅ Controlled code generation
  ✅ Human reviews every line before it ships
  ✅ Pattern-locked against PKB

What this is NOT:
  ❌ Autonomous workflow
  ❌ Multi-file generation
  ❌ Self-executing agents
```

### Tier 2: Autonomous Agent System (Phase 7+)

```
This activates ONLY at Phase 7. Until then, agentic_dev/ is not used.

How it works:
  → Human gives a task (e.g., "scaffold the Personalization Engine")
  → Planner Agent reads PKB, creates step plan
  → Agents execute steps sequentially
  → EVERY step pauses at an approval checkpoint
  → Human approves → next step runs
  → Review Agent validates PKB compliance before any merge

Tools used:
  - LangGraph (workflow orchestration)
  - LangChain (agent tooling layer)
  - 5 specialized agents (see Section 4)
  - 3 tool modules (see Section 5)

What this IS:
  ✅ Faster repetitive scaffolding
  ✅ Stateful across steps (remembers what was done)
  ✅ Self-validates against PKB before showing output

What this is NOT:
  ❌ Fully autonomous "build everything" system
  ❌ Allowed to merge code without human approval
  ❌ Allowed to invent engines or modify PKB
```

### Why Two Tiers?

```
Phases 0–4 establish the patterns.
  → Content Engine is built manually first
  → Knowledge Engine follows, locking the pattern
  → Assessment Engine confirms the pattern is repeatable

By Phase 7, the pattern is proven and locked in PKB.
  → Agents can now safely repeat it for 20+ remaining engines
  → Speed without risk: agents repeat, humans approve
```

---

## 3. PKB READ PROTOCOL

Every agent — in both tiers — must follow this protocol before generating any output.

### What to Read, When

```
ALWAYS read (before any engine work):
  - WORKING_RULES.md          → behavioral constraints
  - CODING_STANDARDS.md       → code shape
  - TECH_STACK.md             → allowed tools only

READ BEFORE specific tasks:
  - DATABASE_SCHEMA.md        → before any model or migration
  - ENGINE_CATALOG.md         → before scaffolding or implementing an engine
  - API_REFERENCE.md          → before any view or serializer
  - DATA_FLOW_PATTERNS.md     → before any cross-engine connection
  - EVENT_DRIVEN_ARCHITECTURE.md → before any event emission or listener
  - EXECUTION_ROADMAP.md      → to validate: is this engine/tool in scope NOW?
  - TESTING_STRATEGY.md       → before any test generation
  - MIGRATION_STRATEGY.md     → before any migration generation
```

### Self-Validation Checklist (before showing output)

```
1. Does this code follow CODING_STANDARDS.md naming + patterns?
2. Does this model use UUID PK + help_text + created_at/updated_at?
3. Does this view use JWT auth + RBAC middleware (never in-view checks)?
4. Does this file initialize structlog logger?
5. Is this engine allowed in the current phase? (check EXECUTION_ROADMAP.md)
6. Does this tool/library exist in TECH_STACK.md?
7. Does this code touch another engine's tables? (if yes → STOP)
8. Is this a single file? (if more than one → STOP, output first only)
```

---

## 4. THE FIVE AGENTS

### 4.1 Planner Agent

```
File:         agentic_dev/agents/planner_agent.py
Responsibility: Reads the task, reads PKB, produces a step-by-step plan
Input:        Human task description
Output:       Ordered list of steps (each step = one file or one action)
Constraints:
  ✅ Must reference EXECUTION_ROADMAP.md to validate scope
  ✅ Must produce steps that map to existing engine lifecycle
  ❌ Cannot invent new engines or modify architecture
  ❌ Cannot skip steps in the engine lifecycle
```

### 4.2 Architect Agent

```
File:         agentic_dev/agents/architect_agent.py
Responsibility: Generates engine skeleton (folder structure + empty files)
Input:        Engine name + ENGINE_CATALOG.md entry
Output:       Empty folder with: models.py, serializers.py, views.py,
              services.py, urls.py, admin.py, events.py, tasks.py,
              apps.py, migrations/__init__.py, tests/ (with factories.py,
              test_models.py, test_serializers.py, test_services.py, test_views.py)
Constraints:
  ✅ Only creates structure — no logic inside any file
  ✅ Every file has logger initialization stub
  ✅ Every file has module docstring
  ❌ Cannot add business logic
  ❌ Cannot create tables or write models
```

### 4.3 Engine Builder (Codegen Agent)

```
File:         agentic_dev/agents/codegen_agent.py
Responsibility: Generates ONE implementation file at a time
Input:        Target file path + relevant PKB context
Output:       One complete file (model OR serializer OR view OR service)
Constraints:
  ✅ Reads DATABASE_SCHEMA.md before models
  ✅ Reads API_REFERENCE.md before views
  ✅ Reads EVENT_DRIVEN_ARCHITECTURE.md before events.py
  ✅ Self-validates against checklist (Section 3) before outputting
  ❌ ONE file per turn. Never two.
  ❌ Cannot write business logic for engines it hasn't scaffolded
  ❌ Cannot modify another engine's files
```

### 4.4 Test Agent

```
File:         agentic_dev/agents/test_agent.py
Responsibility: Generates tests for approved code only
Input:        Approved source file + TESTING_STRATEGY.md
Output:       Corresponding test file (test_models.py / test_views.py / etc.)
Constraints:
  ✅ Only generates tests for code that human has already approved
  ✅ Follows AAA pattern, naming convention, coverage targets
  ✅ Includes idempotency tests if endpoint is in DATA_FLOW_PATTERNS idempotency table
  ✅ Includes event emission tests if endpoint emits events
  ✅ Includes auth matrix tests (401/403/200/expired) for every view
  ❌ Cannot generate tests for unapproved code
  ❌ Cannot import another engine's models in test files
  ❌ Tests must pass before being shown to human
```

### 4.5 Review Agent

```
File:         agentic_dev/agents/review_agent.py
Responsibility: Validates generated code against PKB compliance. Report only.
Input:        Generated file + all relevant PKB files
Output:       Compliance report (pass/fail per rule, with line-level callouts)
Constraints:
  ✅ Checks: naming, types, docstrings, logger init, security patterns, engine isolation
  ✅ Checks: no print(), no console.log(), no hardcoded secrets
  ✅ Checks: UUID PKs, help_text, db_table format, indexes on FKs
  ❌ Cannot modify code — report only
  ❌ Cannot approve or reject — human decides
```

---

## 5. THE THREE TOOLS

### 5.1 Filesystem Tool

```
File:   agentic_dev/tools/filesystem.py
Can do:
  ✅ Read any file in backend/ or frontend/
  ✅ Read any PKB file
  ✅ Write files that an agent has generated (after approval)
  ✅ Create new files in engines/<engine_name>/
Cannot do:
  ❌ Write to PKB/ directory (read-only)
  ❌ Delete files without human confirmation
  ❌ Write outside backend/, frontend/, or agentic_dev/
```

### 5.2 Shell Tool

```
File:   agentic_dev/tools/shell.py
Can do:
  ✅ Run: pytest (test execution)
  ✅ Run: python manage.py makemigrations <engine>
  ✅ Run: python manage.py migrate
  ✅ Run: bandit (security scan)
  ✅ Run: black, flake8 (linting)
Cannot do:
  ❌ Run arbitrary shell commands
  ❌ Access production databases
  ❌ Deploy to any environment
```

### 5.3 Git Tool

```
File:   agentic_dev/tools/git.py
Can do:
  ✅ Create feature branches: feature/<engine-name>-<description>
  ✅ Stage + commit (conventional commit format enforced)
  ✅ Show diff before commit
Cannot do:
  ❌ Merge to main/develop
  ❌ Force-push
  ❌ Push to remote (human does this)
```

---

## 6. ENGINE BUILD WORKFLOW

This is the stateful workflow that runs inside `agentic_dev/workflows/engine_build_graph.py` when Tier 2 is active (Phase 7+). In Phases 0–6, this same sequence is followed manually via human-in-the-loop conversation.

```
┌─────────────────────────────────────────────────────────┐
│                  ENGINE BUILD WORKFLOW                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. PLAN                                                │
│     Planner Agent reads task + PKB                      │
│     Produces step list                                  │
│     ─── CHECKPOINT: Human reviews plan ───              │
│                                                         │
│  2. SCAFFOLD                                            │
│     Architect Agent creates folder + empty files        │
│     ─── CHECKPOINT: Human approves skeleton ───         │
│                                                         │
│  3. IMPLEMENT (loop: one file at a time)                │
│     Engine Builder generates models.py                  │
│     ─── CHECKPOINT ───                                  │
│     Review Agent validates compliance                   │
│     ─── CHECKPOINT: Human approves ───                  │
│     Engine Builder generates serializers.py             │
│     ─── CHECKPOINT ───                                  │
│     Review Agent validates                              │
│     ─── CHECKPOINT: Human approves ───                  │
│     ... (views.py, services.py, events.py, tasks.py)   │
│                                                         │
│  4. TEST                                                │
│     Test Agent generates test file for each approved    │
│     Shell Tool runs pytest — must pass                  │
│     ─── CHECKPOINT: Human reviews test output ───       │
│                                                         │
│  5. MIGRATE                                             │
│     Migration Agent runs makemigrations                 │
│     Shell Tool runs migrate against dev DB              │
│     Smoke test: table exists, FKs resolve               │
│     ─── CHECKPOINT: Human approves migration ───        │
│                                                         │
│  6. VALIDATE                                            │
│     Review Agent runs full PKB compliance scan          │
│     Shell Tool runs bandit (security scan)              │
│     Shell Tool runs full test suite                     │
│     ─── CHECKPOINT: Human marks engine STABLE ───       │
│                                                         │
│  7. COMMIT                                              │
│     Git Tool stages + commits on feature branch         │
│     Human pushes + opens PR                             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### State Persistence

```
agentic_dev/memory/task_state.json tracks:
  - Current engine being built
  - Which step the workflow is on
  - Which files have been approved
  - Which tests have passed
  - Which migrations have run

This survives process restarts. The workflow can resume from where it left off.
```

---

## 7. RUNTIME AGENTS (Phase 7+)

These are product-side agents, NOT development agents. They run inside the platform at runtime to serve users.

### 7.1 Content Orchestration Agent

```
Purpose:     Decides which chunks to retrieve for article/quiz generation
Lives in:    engines/article_gen/services.py (orchestration layer)
Grounding:   RAG — always retrieves from content_chunk via Knowledge Engine
Boundary:    Cannot write articles autonomously. Generates draft → quality check → publish
```

### 7.2 Learning Path Agent

```
Purpose:     Plans daily study path based on mastery + time remaining
Lives in:    engines/personalization/services.py
Grounding:   topic_mastery scores + analytics insights (weak topics)
Boundary:    Cannot modify user data. Produces recommendations only.
             User State Engine applies them via event listener.
```

### Rules (runtime agents)

- ✅ Always RAG-grounded — zero hallucination tolerance
- ✅ Human-curated knowledge structure is the source of truth
- ✅ Agents produce drafts/recommendations — system applies after validation
- ❌ Cannot modify user state directly
- ❌ Cannot bypass quality scoring
- ❌ Cannot generate content outside the syllabus scope

---

## 8. AGENT vs HUMAN RESPONSIBILITY MATRIX

| Decision                            | Who Decides                         |
| ----------------------------------- | ----------------------------------- |
| What engine to build next           | Human (EXECUTION_ROADMAP.md)        |
| What the engine's schema looks like | Human (DATABASE_SCHEMA.md)          |
| What APIs the engine exposes        | Human (API_REFERENCE.md)            |
| How to implement a model            | Agent proposes, Human approves      |
| How to implement a view             | Agent proposes, Human approves      |
| Whether tests pass                  | Shell Tool (automated)              |
| Whether code is PKB-compliant       | Review Agent reports, Human decides |
| Whether to merge to main            | Human only                          |
| Whether an engine is stable         | Human only                          |
| What tools/libraries to use         | Human (TECH_STACK.md)               |
| Whether to add a new engine         | Human only                          |

---

## 9. RULES

- ❌ No agent runs in production (dev-time only, except runtime agents in Section 7)
- ❌ No agent modifies PKB files
- ❌ No agent invents tools, libraries, or engines
- ❌ No agent generates multiple files in one turn
- ❌ No agent merges code to main
- ❌ Tier 2 (autonomous workflow) does not activate before Phase 7
- ✅ Every agent output is reviewed by human before it ships
- ✅ Review Agent runs on every generated file
- ✅ Tests must pass before any file is approved
- ✅ PKB is the single source of truth — agents validate against it, never override it
- ✅ Agents check EXECUTION_ROADMAP.md to confirm engine/tool is in current phase
