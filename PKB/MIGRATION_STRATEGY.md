# MIGRATION_STRATEGY.md
## TheKnowledgeOrbits — Migration Strategy
**PKB File #14 | Version: 1.0 | Date: Feb 2026**

---

## 1. PURPOSE

Two distinct concerns governed here:

1. **Schema Migration Discipline** — how the Django database schema evolves safely as engines are built phase by phase
2. **Data Migration Plan** — how user data moves from the old LearningHub system into the new engine-first schema

Both are critical. Schema discipline keeps the live system stable during development. Data migration keeps users when we switch.

---

## 2. SCHEMA MIGRATION DISCIPLINE

### Core Rules (from WORKING_RULES.md — non-negotiable)
```
✅ One migration per logical change. Never squash in dev.
✅ Tests written and passing BEFORE migration runs.
✅ Each engine owns its migrations exclusively.
❌ No migration touches another engine's tables.
❌ No raw SQL in migrations unless absolutely necessary.
❌ No migration without human approval.
```

### Migration Lifecycle (every engine follows this)
```
1. Model code written + reviewed
2. Model tests written + passing (90% coverage)
3. Human approves model + tests
4. `python manage.py makemigrations <engine_name>` runs
5. Migration file reviewed (diff checked — no surprises)
6. `python manage.py migrate` runs against dev DB
7. Smoke test: verify table exists, indexes created, FKs resolve
8. Migration committed to feature branch
9. PR merge → CI runs migration against test DB
```

### What "One Logical Change" Means
```
✅ GOOD — one migration per:
  - Adding a new model
  - Adding a field to an existing model
  - Adding an index
  - Changing a field constraint (e.g., adding NOT NULL)
  - Creating a UNIQUE constraint

❌ BAD — never combine:
  - New model + new field on another model
  - Schema change + data backfill
  - Two unrelated field additions
```

### Naming Convention
```
Django auto-generates: 0001_initial.py, 0002_add_quality_flag.py
Each engine starts at 0001. Never renumber.

engines/content/migrations/
  0001_initial.py              → content_document + content_chunk
  0002_add_content_embedding.py → content_embedding table
  0003_add_content_asset.py    → content_asset table
  0004_add_ingestion_job.py    → content_ingestion_job table

engines/knowledge/migrations/
  0001_initial.py              → knowledge_program + knowledge_subject
  0002_add_module_topic.py     → knowledge_module + knowledge_topic
  0003_add_chunk_topic_map.py  → knowledge_chunk_topic_map
```

---

## 3. MIGRATION ORDERING — FK DEPENDENCY GRAPH

Migrations must run in an order that satisfies FK dependencies. This graph is derived from DATABASE_SCHEMA.md Section 3 (Relationship Summary).

### Tier 0 — No dependencies (run first)
```
auth_user
auth_role
knowledge_program
```

### Tier 1 — Depends on Tier 0
```
auth_role_assignment    → auth_user, auth_role
knowledge_subject       → knowledge_program
content_document        → knowledge_subject (optional FK)
```

### Tier 2 — Depends on Tier 1
```
knowledge_module        → knowledge_subject
content_embedding       → (standalone, but referenced by Tier 3)
content_chunk           → content_document, content_embedding
```

### Tier 3 — Depends on Tier 2
```
knowledge_topic         → knowledge_module, knowledge_subject, knowledge_topic (self-ref)
content_asset           → content_chunk
content_ingestion_job   → content_document
```

### Tier 4 — Depends on Tier 3
```
knowledge_chunk_topic_map   → content_chunk, knowledge_topic
assessment_quiz             → knowledge_topic
assessment_question         → knowledge_topic, content_chunk
userstate_topic_mastery     → auth_user, knowledge_topic
```

### Tier 5 — Depends on Tier 4
```
assessment_quiz_attempt     → assessment_quiz, auth_user
assessment_question_response → assessment_quiz_attempt, assessment_question
userstate_event             → auth_user
userstate_progress          → auth_user
userstate_bookmark          → auth_user
userstate_reading_progress  → auth_user
analytics_daily_aggregate   → auth_user
analytics_insight           → auth_user
```

### Tier 6 — Phase 2 tables (depend on Tier 3–4)
```
article_article             → knowledge_topic
article_source_map          → article_article, content_chunk
ca_source                   → (standalone)
ca_article                  → ca_source
ca_chunk                    → ca_article, content_embedding
ca_topic_link               → ca_chunk, knowledge_topic
```

### Rule
```
Never run a Tier N migration before all Tier N-1 migrations are complete.
Django handles this via dependencies[] in migration files — but humans must verify.
```

---

## 4. DESTRUCTIVE MIGRATION RULES

Some migrations are destructive (drop column, rename table, change type). These require extra care.

### Allowed Destructive Operations
| Operation | Allowed? | Guard |
|---|---|---|
| Add column (nullable) | ✅ Yes | No guard needed — nullable is safe |
| Add column (NOT NULL + default) | ✅ Yes | Default must be a valid sentinel |
| Add index | ✅ Yes | Use `CONCURRENTLY` in production |
| Drop column | ⚠️ Conditional | Only if zero code references it. Verified by grep + test run |
| Rename column | ❌ Never | Use add-new + backfill + drop-old pattern instead |
| Rename table | ❌ Never | Use new table + data copy + drop old pattern |
| Change column type | ❌ Never in-place | Use add-new-type column + backfill + drop old |

### The Add-Backfill-Drop Pattern (for renames / type changes)
```
Migration 0001: Add new column/table (nullable)
Migration 0002: Backfill data from old → new (data migration, not schema)
Migration 0003: Drop old column/table (after verifying new is populated)

Each is a separate migration. Each is reviewed separately. Each can be rolled back independently.
```

### Production Index Creation
```
# NEVER do this in production (locks table):
# CREATE INDEX idx_name ON table(column);

# ALWAYS do this in production:
# CREATE INDEX CONCURRENTLY idx_name ON table(column);

# In Django: use RunSQL with CONCURRENTLY, outside of a transaction
```

---

## 5. ROLLBACK CONTRACTS

Every migration must be rollback-safe. Django supports this natively for most operations, but some require manual attention.

### Auto-Rollback Safe (Django handles)
- Add model → rollback drops table
- Add field → rollback drops column
- Add index → rollback drops index
- Add constraint → rollback drops constraint

### Manual Rollback Required
- Data migrations (RunPython) → must provide reverse function
- RunSQL → must provide reverse SQL
- If reverse is impossible → migration must be marked `atomic = False` and documented

### Rollback Pattern for Data Migrations
```python
from django.db import migrations

def backfill_forward(apps, schema_editor):
    """Forward: populate new_field from old_field."""
    Model = apps.get_model("engine", "ModelName")
    for obj in Model.objects.filter(new_field__isnull=True):
        obj.new_field = obj.old_field
        obj.save()

def backfill_reverse(apps, schema_editor):
    """Reverse: clear new_field (old_field still exists)."""
    Model = apps.get_model("engine", "ModelName")
    Model.objects.update(new_field=None)

class Migration(migrations.Migration):
    dependencies = [("engine", "0001_initial")]

    operations = [
        migrations.RunPython(backfill_forward, backfill_reverse),
    ]
```

---

## 6. DATA MIGRATION PLAN (Old LearningHub → TheKnowledgeOrbits)

This is a one-time migration at launch. It does NOT apply to ongoing schema evolution (that's Sections 2–5).

### Phase A: Data Audit (During Development Week 1)
```
What to export from old system:
  ✅ Users (email, name, password_hash — if compatible)
  ✅ User progress (articles read, quizzes taken)
  ✅ Bookmarks
  ✅ Quiz attempt history (scores, answers)

What to DISCARD (re-ingest fresh):
  ❌ Raw content (re-ingest all NCERTs from source PDFs)
  ❌ Generated articles (regenerate via new RAG pipeline)
  ❌ Old quiz questions (regenerate from new chunks)
  ❌ Any data tied to old ingestion services (38 services → gone)

Why discard content:
  - Old chunking was inconsistent (38 services)
  - New chunks are 1200-char semantic units — incompatible shape
  - Embeddings must be regenerated for pgvector anyway
  - Fresh content = clean foundation
```

### Phase B: Transformation Mapping
```
Old Table          →  New Table                    →  Transform
─────────────────────────────────────────────────────────────────
old_users          →  auth_user                    →  Map email, name. Re-hash password if algo differs
old_progress       →  userstate_progress           →  Map article counts, quiz counts. Streak resets to 0
old_bookmarks      →  userstate_bookmark           →  Map content_type + content_id (articles only — quizzes regenerated)
old_quiz_history   →  (discard)                    →  Old questions don't exist in new system
old_content        →  (discard)                    →  Re-ingest from source PDFs
```

### Phase C: Migration Execution (Week 13 — after MVP launches)
```
Step 1: Export
  → Dump old DB tables identified in Phase A
  → Validate row counts

Step 2: Transform
  → Run transformation scripts (Python, not SQL)
  → Validate: every old user maps to exactly one new user
  → Validate: no orphaned FKs

Step 3: Load
  → Insert into new DB in FK-dependency order (Tier 0 → Tier 5)
  → auth_user first (everything else references it)
  → userstate_progress, userstate_bookmark after user

Step 4: Verify
  → Row count check: old users == new auth_user rows
  → Spot-check 10 users: login works, progress visible
  → Run full test suite against migrated data
```

### Phase D: Soft Launch (Weeks 14–15)
```
- 100 migrated users invited to beta
- Both old and new systems running in parallel
- Users can flag discrepancies
- Fix any data integrity issues found
- Old system stays READ-ONLY (no new writes)
```

### Phase E: Full Cutover (Week 16)
```
1. Freeze old database (set read-only)
2. Final incremental sync (any writes since Phase C)
3. Run full migration verification suite
4. Switch DNS: old domain → new system
5. Monitor error rates for 24 hours
6. If stable → archive old DB (keep 30-day backup)
7. If not stable → DNS rollback to old system (< 5 min)
```

---

## 7. SEED DATA STRATEGY

Production seed data is separate from migration data. It populates the knowledge structure before any user content exists.

### What Gets Seeded (before any user signs up)
```
knowledge_program:   UPSC CSE, State PSC (Karnataka, Maharashtra, Tamil Nadu)
knowledge_subject:   Polity, History, Geography, Economy, Environment, Science & Tech
knowledge_module:    Fundamental Rights, Indian History, Physical Geography, ...
knowledge_topic:     Right to Equality, Mughal Period, Monsoons, ...
auth_role:           admin, content_manager, student, free_user
```

### Seed Script Location
```
scripts/seed_data.py   →  Populates knowledge hierarchy + roles
scripts/ingest_ncert.py →  Ingests NCERT PDFs → chunks → embeddings → topic mapping
```

### Rules
- Seed data runs ONCE at initial deploy (Phase 4, Week 11)
- Seed script is idempotent — safe to run multiple times
- Knowledge hierarchy is the FIRST thing seeded — everything else depends on it
- Roles are seeded before any user registration is possible

---

## 8. RULES

- ❌ Never squash migrations in development
- ❌ Never run a migration without model tests passing first
- ❌ Never touch another engine's migration files
- ❌ Never do destructive operations in-place — use Add-Backfill-Drop
- ❌ Never create indexes without CONCURRENTLY in production
- ✅ Every migration is rollback-safe (or documented why not)
- ✅ FK dependency ordering must be respected (Section 3 tiers)
- ✅ Data migrations are separate files from schema migrations
- ✅ Seed data script is idempotent and runs knowledge hierarchy first
- ✅ Agents must read DATABASE_SCHEMA.md before generating any migration
