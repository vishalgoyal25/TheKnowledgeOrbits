# WORKING_RULES.md

## TheKnowledgeOrbits — Working Rules (Highest Authority)

**PKB File #5 | Version: 1.0 | Date: Feb 2026**

---

## 1. GOLDEN RULES (NEVER BREAK)

- ✅ One step at a time. One file at a time.
- ✅ Wait for explicit "Done" before proceeding
- ✅ Human approves everything. AI proposes only.
- ✅ PKB is read-only for AI. Human-only modification.
- ✅ Engine boundaries are sacred. No cross-engine DB access.
- ❌ No skipping steps
- ❌ No multi-file generation in single turn
- ❌ No autonomous decisions by AI
- ❌ No architecture changes without human approval

---

## 2. AGENTICAI BEHAVIORAL RULES

### One-Step Rule:

- AI generates ONE file only per turn
- Shows output → waits for "Done"
- No multi-file generation ever

### Approval Checkpoints (mandatory):

- After every file generation
- After every migration
- After every engine skeleton
- Before any merge to main branch

### AI Cannot:

- ❌ Modify PKB files
- ❌ Invent tools or libraries not in TECH_STACK.md
- ❌ Change engine boundaries or architecture
- ❌ Skip security patterns
- ❌ Auto-merge code
- ❌ Generate multiple files at once

### AI Must:

- ✅ Read relevant PKB files before generating
- ✅ Explain what and why for every output
- ✅ Self-validate against PKB before showing output
- ✅ Revise on human request without argument

---

## 3. SECURITY ENFORCEMENT (Mandatory in ALL generated code)

### Authentication:

- JWT only. No sessions. No plaintext tokens.
- Library: djangorestframework-simplejwt
- Access token: 5 min expiry
- Refresh token: 7 days expiry
- Tokens stored: HttpOnly cookies only

### Password Hashing:

- Argon2 only. No bcrypt. No pbkdf2. No default Django hasher.
- Never store plaintext passwords

### Authorization:

- RBAC via middleware. Never inside views.
- Roles extracted from verified JWT claims only
- Decorator: `@require_role("role_name")`
- Roles: admin, content_manager, student, free_user

### Rules:

- ❌ No `alg=none` in JWT
- ❌ No permission checks inside view logic
- ❌ No secrets hardcoded anywhere
- ✅ All secrets via direnv + .env files
- ✅ Dev vs prod env configs separated

---

## 4. TOOLING ENFORCEMENT (Mandatory)

### Logging (no exceptions):

- Python prod: structlog
- Python dev: rich
- Node.js: chalk
- ❌ No `print()` in Python. Ever.
- ❌ No `console.log()` in Node.js. Ever.
- ✅ Every Python module: `logger = structlog.get_logger(__name__)`
- ✅ Every TS module: import chalk, use chalk.green/yellow/red

### Error Reporting:

- Sentry SDK initialized in every engine
- All unhandled exceptions auto-reported
- ❌ No silent exception swallowing

### Environment:

- direnv mandatory for all env variables
- ❌ No hardcoded secrets anywhere in code
- ✅ `.env` in .gitignore always

### Workflow Enforcement:

- pre-commit hooks active on all repos
- commitlint enforced (conventional commits)
- ❌ No force-push to main/develop
- ✅ Feature branches: `feature/engine-name-description`

---

## 5. ENGINE DEVELOPMENT RULES

### Each engine must have:

- Own folder: `engines/<engine_name>/`
- Own models, serializers, views, services, urls, tests
- Own DB tables (no shared tables)
- Logger initialized in every file
- Sentry reporting enabled

### Communication:

- ✅ Engine A → HTTP call → Engine B API
- ✅ Engine A → emit event → Engine B listens
- ❌ Engine A imports Engine B's models
- ❌ Engine A queries Engine B's DB tables directly

### Lifecycle (every engine follows this):

1. Declared in ENGINE_CATALOG.md
2. Schema defined in DATABASE_SCHEMA.md
3. Skeleton generated (Architect Agent)
4. Files implemented one by one (Engine Builder)
5. Tests written (Test Agent)
6. Migration generated (Migration Agent)
7. Compliance validated (Review Agent)
8. Human approves → engine marked stable

---

## 6. DATABASE RULES

- ❌ No auto-increment IDs. UUID only.
- ❌ No raw SQL unless absolutely necessary
- ✅ Table naming: `enginename_modelname`
- ✅ `help_text` on every field
- ✅ `created_at` + `updated_at` on every model
- ✅ Index on all ForeignKey fields
- ✅ One migration per logical change. Never squash in dev.

---

## 7. TESTING RULES

- ✅ Tests written for every engine before migration
- ✅ Coverage targets: Models 90%, Services 85%, Views 80%
- ✅ pytest + factory_boy + faker
- ✅ AAA pattern (Arrange, Act, Assert)
- ❌ No test accesses another engine's DB directly
- ❌ No test without running before approval

---

## 8. PHASE-SAFETY RULES

- ❌ Never build future-phase features early
- ❌ Never add tools not scheduled in current phase
- ✅ Always reference EXECUTION_ROADMAP.md for what's allowed now
- ✅ Complexity increases only per phase progression
