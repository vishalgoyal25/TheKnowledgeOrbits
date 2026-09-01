# FEATURES_SUPABASE_CLEANUP.md — Database Quota Recovery + Infra Hardening

**Status:** ✅ **ALL CLOSED** — SUPABASE · RENDER · VERCEL all shipped & deployed. Blueprint
IaC live (3 services adopted, crons auto-deploy wired). Only passive metric-watching remains.
**Opened:** 2026-08-29 · **Closed:** 2026-09-01 · **Supabase:** `S0`–`S8` ✅ · **Render:** `R0`–`R2` ✅ (774c7f8), `R4`/`R5` ✅ (43f9e84 + Blueprint synced), `R3` metric-watch · **Vercel:** `V0`–`V3` ✅ (774c7f8), `V4` metric-watch
**Result:** database **1214 MB → 282 MB**, `402` restrictions lifted, leak fixed, retention live.
**Next single commit to `main`:** Render + Vercel code changes bundled together (Part D/E), one push.

> This document is both the incident record **and** a learning log. Part A is the
> Supabase cleanup. Parts B and C reproduce **every SQL query** (annotated for
> PostgreSQL learning) and **every local command** used to execute and verify each
> phase. Part D/E carry the still-pending Render + Vercel work (merged in from the
> former `FEATURES_RENDER_FIVE_SEC.md`, now deleted).
>
> **No secrets:** no connection strings, service IDs, org/project IDs, or keys appear
> anywhere below — only SQL, table names, and commands.

---

---

# PART A — SUPABASE QUOTA RECOVERY ✅

## A1. The incident ✅

```
Supabase Free Plan · 26 Aug 2026 – 26 Sep 2026
Database Size: 1.302 / 0.5 GB (260%)
"All services are restricted. Your projects are not able to serve requests
 and will respond with a 402 status code."
```

Every other quota was idle: Egress 9%, Storage 0%, MAU 0/50,000. **Purely a
database-size problem** — so egress-side fixes (caching, ISR tuning) were irrelevant.

## A2. Measured state ✅ (2026-08-29, Supabase SQL Editor)

`pg_database_size` = **1214 MB**. Three tables were **84%** of it:

| Table                    | Total      | Data | Index/TOAST | Live rows | Verdict                   |
| ------------------------ | ---------- | ---- | ----------- | --------- | ------------------------- |
| `content_embedding`      | **610 MB** | 458  | 151         | 232,116   | 🔴 primary target         |
| `ca_chunk`               | **244 MB** | 200  | 43          | 7,128     | 🔴 delete                 |
| `ca_article`             | **171 MB** | 34   | 137         | 1,435     | 🔴 delete                 |
| `knowledge_book_chunk`   | 80 MB      | 37   | 43          | 25,764    | ✅ **KEEP — untouchable** |
| `daily_ca_article`       | 14 MB      | 2.6  | 11          | 1,259     | ✅ **KEEP — all of it**   |
| `ca_topic_link`          | 13 MB      |      |             | 19,198    | 🔴 cascades away          |
| `knowledge_book_content` | 12 MB      |      |             | 1,150     | ✅ KEEP                   |
| `daily_ca_proposal`      | 8.2 MB     |      |             | 4,162     | 🟡 delete (consumed)      |
| everything else          | ~62 MB     |      |             |           | ✅ keep                   |

**`content_embedding` by `content_type`** (ground truth from the DB, NOT the model):

| `content_type`     | Rows        | Oldest     | Newest     | Verdict   |
| ------------------ | ----------- | ---------- | ---------- | --------- |
| `ca_chunk`         | **204,065** | 2026-04-01 | 2026-08-29 | 🔴 delete |
| `book_chunk`       | 25,764      | 2026-04-29 | 2026-08-29 | ✅ keep   |
| `daily_ca_article` | 1,255       | 2026-04-21 | 2026-08-29 | ✅ keep   |
| `book_article`     | 1,150       | 2026-04-29 | 2026-08-29 | ✅ keep   |

> ⚠️ The `Embedding` model declared `choices = [chunk, article, question]` — **none of
> which exist in the DB**. Django `choices` is validation metadata, not a DB constraint.
> The four labels above are the real ones. Fixed in S6.

## A3. Root cause — a missing cascade ✅

```python
class Embedding(models.Model):
    content_type = models.CharField(...)   # string label
    content_id   = models.UUIDField(...)   # ← NOT a ForeignKey → NO CASCADE
```

`content_id` is a bare UUID with no FK, so deleting content never deletes its
embedding. `cleanup_expired.py` ran `expired_chunks.delete()` for months; the chunks
vanished, the 384-dim vectors stayed forever.

```
ca_chunk embeddings : 204,065
ca_chunk rows       :   7,128
inferred orphans    : 196,937   ← 96.5%, ~518 MB, ~43% of the whole DB
```

`unique_together = [content_type, content_id]` ⇒ one embedding per chunk, so 204,065
embeddings cannot legitimately serve 7,128 chunks. These orphans reference nothing —
deleting them has **zero RAG impact**. (Verified by anti-join in S1, not assumed.)

## A4. FK cascade map — VERIFIED in code ✅

```
ca_article ──CASCADE──> ca_chunk ──CASCADE──> ca_topic_link
                            └──M2M──> assessment_question_source_ca_chunks
content_embedding ──── NO FK AT ALL ────  (orphans; must be deleted explicitly)
```

No `PROTECT` anywhere → nothing aborts mid-operation. Accepted effect: old quiz
questions survive but lose CA source attribution (`has_ca_sources` → `False`).

> ⚠️ **The lesson that bit us (S4):** Django's `on_delete=CASCADE` is enforced by the
> **ORM in Python, not the database**. Django creates FKs as `NO ACTION` at the DB
> level and simulates the cascade by deleting children first. So **raw SQL `DELETE`
> does NOT cascade** — it raises `23503 foreign key violation`. Raw SQL must delete
> **children before parents**; ORM `.delete()` handles order itself.

## A5. Three facts that decided success ✅

1. **`DELETE` does not shrink PostgreSQL.** Deleted rows become _dead tuples_ — space
   reusable by Postgres but **not returned to the OS**. Supabase bills physical disk,
   so **`VACUUM FULL` is mandatory** or the dashboard stays at ~1.2 GB.
2. **Dead tuples were only 1%** (`last_vacuum` was `null` on every table — autovacuum
   reclaims _within_ Postgres, never to disk). So the 610 MB was **genuinely live** —
   vacuuming alone frees nothing; rows had to actually be deleted.
3. **`VACUUM FULL` rebuilds all indexes**, including the pgvector HNSW index, at the
   new smaller size — so a separate `REINDEX` was unnecessary.

## A6. Phases ✅ (all executed 2026-08-29 → 08-30)

### S0 — Measure ✅

Captured DB size, per-table sizes, real `content_type` labels, dead-tuple ratio, FK map.

### S1 — Verify orphans (read-only gate) ✅

Anti-join returned **exactly 196,937 orphans / 7,128 live** — the inferred figure to the
row. Invariant `book_chunk` embeddings = `knowledge_book_chunk` rows = 25,764 (clean 1:1).

### S2 — Backup (irreversible-step insurance) ✅

Free-tier Supabase has **no PITR, no restore**. Exported all 16 KEEP tables to CSV via
`scripts/dev/supabase_backup.py` → **88,144 rows / 237 MB** in `backups/` (gitignored).
Gate passed before any deletion.

### S3 — Delete orphaned embeddings ✅

196,937 orphans deleted, **50k/batch × 4**, oldest-first. `total_emb` 232,116 → 35,297.
`book_chunk` held at 25,764 through every batch.

### S4 — Delete CA content ✅

`daily_ca_proposal` cleared; live `ca_chunk` embeddings deleted (7,128); CA tables
emptied **children-first** (the raw-SQL cascade lesson above). `total_emb` = **28,169**
(= backup keep-count exactly). Invariants held: 25,764 / 1,259.

### S5 — Reclaim disk ✅

`VACUUM FULL` on the six affected tables → `pg_database_size` **282 MB**. Restrictions
lifted; `/daily-ca/archive/` served JSON again (was `402`).

### S6 — Fix the leak ✅ (6 files, code)

- `EmbeddingService.delete_embeddings_for()` — one shared delete API.
- `cleanup_expired.py` — deletes chunks **and** embeddings in one `transaction.atomic`.
- `relevance_scorer.py` — `object_id`→`content_id`, and both functions routed through
  `EmbeddingService` (API-first). Live Sentry `AttributeError` gone; **1,017 topic
  embeddings load via HF API** (was crashing → 0). _Side effect (intended):_ semantic
  topic scoring, dead for months, is reactivated — CA proposal ranking improves.
- `content/models.py` — `choices` corrected to the real labels + migration `0004`.
- `test_embedding_cleanup.py` — 4 regression tests locking the helper contract.

### S7 — Retention (1 file, NO new cron) ✅

Root of the _size_: `CAChunk.expiry_date = published_at + 180 days` — nothing expired for
six months. `_prune_old_ca()` added to `run_daily_pipeline.py`: prunes CA + embeddings
older than **`_CA_RETENTION_DAYS = 30`**, via the ORM (so CASCADE fires) + the S6 helper.
Runs inside the existing daily pipeline. `daily_ca_article` never touched. Steady state
≈ **277 MB** → indefinitely under quota. The separate `check_db_size` guard was
**deliberately dropped** — Supabase already emails at quota (over-engineering avoided).

### S8 — Verify ✅

Site functional (`/daily-ca/today/` → 10 articles); 95 affected-engine tests + 4 new
pool tests pass; mypy + ruff clean.

## A7. End state ✅

|                        | Before                 | After                                          |
| ---------------------- | ---------------------- | ---------------------------------------------- |
| Database size          | 1214 MB (260%)         | **282 MB (~56%)**                              |
| `402` restrictions     | 🔴 active              | ✅ lifted                                      |
| Static syllabus corpus | 25,764 chunks          | **25,764 — intact**                            |
| Daily CA articles      | 1,259                  | **1,259 — intact**                             |
| Durability             | ~2.4 months (one-time) | **indefinite** (leak fixed + 30-day retention) |

---

---

# PART B — SQL / PostgreSQL LEARNING LOG 📚

Every query run in the Supabase SQL Editor, with what each PostgreSQL construct does.

## B1. Measuring size (S0)

**Whole-database size.** `pg_database_size()` returns bytes; `pg_size_pretty()` formats
them (`1214 MB`). `current_database()` = the DB you're connected to.

```sql
SELECT pg_size_pretty(pg_database_size(current_database())) AS total_db_size;
```

**Per-table sizes.** `pg_stat_user_tables` is a system view with one row per table
(`relid` = table OID, `relname` = name, `n_live_tup`/`n_dead_tup` = row estimates).

- `pg_total_relation_size(relid)` = table + all its indexes + TOAST (out-of-line big values)
- `pg_relation_size(relid)` = just the main table heap (no indexes/TOAST)
- their difference = indexes + TOAST

```sql
SELECT
  relname                                                              AS table_name,
  pg_size_pretty(pg_total_relation_size(relid))                        AS total,
  pg_size_pretty(pg_relation_size(relid))                              AS data_only,
  pg_size_pretty(pg_total_relation_size(relid) - pg_relation_size(relid)) AS indexes,
  n_live_tup                                                           AS live_rows,
  n_dead_tup                                                           AS dead_rows
FROM pg_catalog.pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 30;
```

**Category breakdown + rough byte estimate.** `GROUP BY` aggregates; `COUNT(*)` per
group; `MIN/MAX(created_at)::date` casts a timestamp to a date. `(COUNT(*) * 1700)` is a
hand estimate of bytes per 384-dim vector row.

```sql
SELECT
  content_type,
  COUNT(*)                                  AS row_count,
  MIN(created_at)::date                     AS oldest,
  MAX(created_at)::date                     AS newest,
  pg_size_pretty((COUNT(*) * 1700)::bigint) AS approx_raw_vector_bytes
FROM content_embedding
GROUP BY content_type
ORDER BY COUNT(*) DESC;
```

**Dead-tuple / bloat check.** How much a plain `VACUUM` could reclaim, and when
autovacuum last ran. `NULLIF(x,0)` avoids divide-by-zero. `ROUND(…,1)` = 1 decimal.

```sql
SELECT
  relname, n_live_tup, n_dead_tup,
  ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 1) AS pct_dead,
  last_vacuum, last_autovacuum
FROM pg_catalog.pg_stat_user_tables
WHERE n_dead_tup > 0
ORDER BY n_dead_tup DESC
LIMIT 15;
```

## B2. Finding orphans — the anti-join (S1)

**`LEFT JOIN … WHERE right IS NULL`** is the canonical "rows in A with no match in B".
Here: embeddings whose `content_id` matches no live `ca_chunk`. `FILTER (WHERE …)` is a
per-aggregate condition (cleaner than `SUM(CASE WHEN …)`).

```sql
SELECT
  COUNT(*) FILTER (WHERE c.id IS NULL)     AS orphaned_embeddings,
  COUNT(*) FILTER (WHERE c.id IS NOT NULL) AS live_embeddings,
  COUNT(*)                                 AS total_ca_chunk_embeddings
FROM content_embedding e
LEFT JOIN ca_chunk c ON c.id = e.content_id
WHERE e.content_type = 'ca_chunk';
```

**Invariant probe with `UNION ALL`** (stacks result rows; `ALL` keeps duplicates, no
dedupe cost). Used to confirm nothing unexpected appeared and the KEEP counts matched.

```sql
SELECT content_type, COUNT(*) AS rows FROM content_embedding GROUP BY content_type
UNION ALL
SELECT 'INVARIANT knowledge_book_chunk', COUNT(*) FROM knowledge_book_chunk
UNION ALL
SELECT 'INVARIANT daily_ca_article', COUNT(*) FROM daily_ca_article
ORDER BY 2 DESC;   -- ORDER BY ordinal: sort by the 2nd column
```

**Age distribution with `DATE_TRUNC`** (buckets a timestamp to month start). `SUM(
pg_column_size(t.*))` sums the on-row byte size across all columns of table alias `t`.

```sql
SELECT
  DATE_TRUNC('month', created_at)::date AS month,
  COUNT(*)                              AS ca_articles,
  pg_size_pretty(SUM(pg_column_size(t.*))::bigint) AS approx_size
FROM ca_article t
GROUP BY 1 ORDER BY 1;
```

## B3. Batched deletes (S3)

**Delete in bounded batches** so a single statement never locks 200k rows or times out.
`ctid` is Postgres's physical row address (fast to target). The subquery picks 50k
oldest orphans; the outer `DELETE` removes exactly those. Re-run until it reports
`DELETE 0`.

```sql
DELETE FROM content_embedding
WHERE ctid IN (
  SELECT e.ctid
  FROM content_embedding e
  LEFT JOIN ca_chunk c ON c.id = e.content_id
  WHERE e.content_type = 'ca_chunk' AND c.id IS NULL
  ORDER BY e.created_at
  LIMIT 50000
);
```

**Invariant check after every batch** — nested scalar subqueries each return one number.
The book-chunk pair MUST stay 25,764/25,764 or STOP.

```sql
SELECT
  (SELECT COUNT(*) FROM content_embedding WHERE content_type='book_chunk') AS book_chunk_emb,
  (SELECT COUNT(*) FROM knowledge_book_chunk)                              AS book_chunks,
  (SELECT COUNT(*) FROM content_embedding WHERE content_type='ca_chunk')   AS ca_chunk_emb_left,
  (SELECT COUNT(*) FROM ca_chunk)                                          AS ca_chunks,
  (SELECT COUNT(*) FROM content_embedding)                                 AS total_emb;
```

## B4. Deleting CA content — children first (S4)

Because Django FKs are `NO ACTION` at the DB level, raw SQL had to remove children
before parents (order matters). Each was preceded by its `SELECT COUNT(*)`.

```sql
-- 1. quiz-source M2M (references ca_chunk; the questions themselves survive)
DELETE FROM assessment_question_source_ca_chunks;
-- 2. topic links (references ca_chunk; knowledge_topic untouched)
DELETE FROM ca_topic_link;
-- 3. the live CA chunk embeddings (no FK → must be explicit)
DELETE FROM content_embedding WHERE content_type = 'ca_chunk';
-- 4. chunks (now unreferenced)
DELETE FROM ca_chunk;
-- 5. articles (now unreferenced)
DELETE FROM ca_article;
-- and the consumed proposals
DELETE FROM daily_ca_proposal;
```

The first attempt was `DELETE FROM ca_article` _before_ the children — it raised:

```
ERROR: 23503: update or delete on table "ca_article" violates foreign key
constraint "..._fk_ca_article_id" on table "ca_chunk"
```

That error is the whole lesson of §A4.

## B5. Reclaiming disk (S5)

**`VACUUM FULL`** rewrites each table into a fresh, compact file and returns freed space
to the OS — and rebuilds every index (incl. HNSW). It takes an `ACCESS EXCLUSIVE` lock
and **cannot run inside a transaction block**, so each ran as its own statement.

```sql
VACUUM FULL content_embedding;
VACUUM FULL ca_chunk;
VACUUM FULL ca_article;
VACUUM FULL ca_topic_link;
VACUUM FULL daily_ca_proposal;
VACUUM FULL assessment_question_source_ca_chunks;
```

Then re-measured with the B1 queries → **282 MB**.

> **Mental model:** `DELETE` marks rows dead → `VACUUM` makes that space reusable _inside_
> Postgres → `VACUUM FULL` physically rewrites the table and hands space _back to the OS_
> (what a disk-quota meter actually sees).

---

---

# PART C — LOCAL TERMINAL COMMAND LOG 🖥️

Every command run from the local Windows PowerShell terminal, per phase. (Backend cwd.)

**S2 — backup (before any deletion):**

```bash
git check-ignore -v backups/test.csv          # prove backups/ is ignored
python scripts/dev/supabase_backup.py         # → 88,144 rows / 237 MB, gate passed
```

**S6 — leak fix, one file at a time (mypy after each):**

```bash
mypy engines/content/services/embedding_service.py
mypy engines/current_affairs/management/commands/cleanup_expired.py
python manage.py cleanup_expired              # mark-only (no --delete) smoke test
mypy engines/current_affairs/services/relevance_scorer.py
```

```bash
# proof the Sentry crash is fixed — loads topic embeddings via the HF API:
python -c "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings.dev');django.setup();from engines.current_affairs.services import relevance_scorer as r;r._topic_embeddings_cache=None;print(len(r._get_topic_embeddings()))"
# → generating_embeddings_via_api count=1024 → 1017  (was crashing → 0)
```

```bash
python manage.py makemigrations content       # → 0004_alter_embedding_content_type
python manage.py migrate content              # local
python manage.py migrate content --database=supabase   # BOTH DBs, always
pytest engines/content/tests/test_embedding_cleanup.py -q --tb=short   # 4 passed
```

**S7 — retention dry-count (safe, deletes nothing):**

```bash
python -c "import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','core.settings.dev');django.setup();from datetime import timedelta;from django.utils import timezone;from engines.current_affairs.models import CAArticle;print(CAArticle.objects.using('supabase').filter(created_at__lt=timezone.now()-timedelta(days=30)).count())"
# → 0  (all CA < 30 days; retention would prune nothing today)
```

**S8 — full verification gate:**

```bash
mypy <all changed .py files>                  # Success, EXIT 0
pytest engines/content engines/current_affairs -q --tb=short   # 95 passed
ruff format --check <changed files>; ruff check engines/content engines/current_affairs engines/daily_ca scripts/dev   # all passed
```

**Migration safety pattern used throughout:** every schema change is applied to BOTH the
local DB and `--database=supabase`; migrations are additive only; `choices` changes emit
no data-touching DDL.

---

---

# PART D — RENDER "health-check timed out after 5 s" 🟡 PENDING

Merged from the former `FEATURES_RENDER_FIVE_SEC.md`. **Constraint: the fix must NOT
increase the Render bill (~$9–10/mo total).**

## D1. Symptom

Render emails roughly **every second day since February 2026** (from first deploy):

```
Server failure detected on theknowledgeorbits-backend
HTTP health check failed (timed out after 5 seconds)
```

The site keeps working — Render restarts the instance itself. Noisy, not user-facing.

## D2. Ruled out (do NOT re-derive)

- **NOT the health endpoint** — `/api/v1/health/` is DB-free and ultra-light; it is being
  _starved_, not slow.
- **NOT the LLM outage** — that was 2026-08-19→21 only; these span six months.
- **NOT (originally) research_agent** — a tempting theory, but the alerts predate that
  code by four months (built June, alerts since February). It may _contribute_ since June.

## D3. Leading cause — CONFIRMED root, matches the timeline

`render.yaml` runs the worker **inside the web container**, single gunicorn worker:

```
startCommand: (python manage.py process_tasks & gunicorn ... --workers 1 --threads 8 ...)
```

The background task `auto_scrape_and_process_ca` (current*affairs, `@background`, runs in
`process_tasks`) calls `TopicLinkerService.link_unlinked_chunks()`, which loaded
**`SentenceTransformer("all-MiniLM-L6-v2")`** — hundreds of MB of torch + weights — into
a **512 MB** container already running gunicorn. → OOM → auto-restart → the health probe
during restart fails → "timed out after 5 s". This is \_also* the source of the separate
"exceeded its memory limit" emails: **same event, two alerts.** CA scraping cadence
explains "every second day."

Crucially, `USE_EMBEDDING_API=True` (set to keep the model out of memory) is **only
honored by `content/services/embedding_service.py`**. Two CA call sites bypassed it and
loaded the model directly — **both now routed through `EmbeddingService` (API-first):**

- `current_affairs/services/relevance_scorer.py` → fixed in **R1** (was S6).
- `current_affairs/services/topic_linker.py` → fixed in **R2** (this session).

## D4. Phases

### R0 — Diagnose ✅

Confirmed root cause above: SentenceTransformer loaded into the 512 MB web dyno by two CA
call sites that bypassed `USE_EMBEDDING_API`. Ruled out the health endpoint, the LLM
outage, and (as originator) research_agent — see D2. Timeline (Feb 2026 →) matches the CA
scrape cadence, not any June-built code.

### R1 — Route `relevance_scorer.py` through `EmbeddingService` ✅

Both callers routed through `EmbeddingService.generate_embeddings_batch()` (API-first).
Removed the dead `_get_embedding_model()`, `_embedding_model`, `_embedding_model_unavailable`;
replaced with a comment pointing here. mypy green, ruff clean. (Landed with the S6 leak fix.)

### R2 — Route `topic_linker.py` through `EmbeddingService` + remove dead loader ✅

Cold-start topic encoding (`_get_topic_embeddings`) now calls
`EmbeddingService.generate_embeddings_batch()` — same 384-dim `all-MiniLM-L6-v2` model, so
vectors stay in the stored embedding space. Removed the module-level `_embedding_model`
global and `get_embedding_model()`; replaced with the explanatory comment at the top of the
file. mypy `Success`, ruff clean, 7 topic-linker tests pass. **No local SentenceTransformer
can now load in the web dyno — the OOM/crash mechanism is deleted (deterministic).**

> **Note — `knowledge_chunk_topic_map` is empty (0 rows).** So every scrape hits the
> cold-start branch and API-encodes **~1,462 active topics per run**. Safe (fails soft via
> HF API, no crash) but HF-heavy. Caching topic vectors is a **follow-up optimization**, not
> a blocker for the crash fix. Tracked as R-later below.

### R3 — Deploy + watch (pending)

R1+R2 shipped in commit `774c7f8` (with the Vercel V1-V3 work). Watch Render memory
metrics + alert frequency for ~2 weeks to confirm the OOM is gone.

### R4 — Cron jobs + env under IaC (Blueprint) ✅

The two cron jobs (`tko-generate-daily-ca` 02:00 UTC, `generate-static-content` 03:30 UTC)
were dashboard-only, so a push auto-deployed the web service but never them. Added both to
`render.yaml` as `type: cron` (deps-only build, no `render-build.sh`; DB writes at runtime
via `--database=supabase`). Also reconciled the web service to remove drift:

- **`buildCommand`/`preDeployCommand`:** yaml is the source of truth — collectstatic runs
  with the `IS_BUILD_PHASE` shield, migrations run in `preDeployCommand` on direct port 5432
  (safer than the pooler). The drifted dashboard `buildCommand` will be overwritten on sync.
- **`SECRET_KEY` landmine removed:** dropped `generateValue: true` — the real key comes from
  the env group; a sync could otherwise regenerate it and log every user out.
- **`fromGroup: TheKnowledgeOrbits`** on all three services — single source of truth for
  secrets; only the group NAME is in git, never values.

**DONE (2026-09-01):** created the Blueprint instance `TheKnowledgeOrbits` (repo + `main`) and
chose **"Associate existing services"** — Render adopted all **3** services by name, **no
duplicates**. The plan applied exactly as designed: crons' auto-deploy-trigger → `commit`,
build filters removed, web `buildCommand`/`preDeployCommand` reconciled, config env vars
created, **no `SECRET_KEY` regeneration** (landmine confirmed gone). Web redeployed healthy;
both crons manually deployed once to the latest commit (green) so the daily pipeline now runs
the Supabase-retention code. **Future pushes auto-deploy all three** — the automation is live.

### R5 — `.env.example` hygiene + relocation ✅

Rewrote every tracked example file to the real variable names (verified against
`core/settings/*` and frontend `process.env.*`), placeholders only, and moved them to a
symmetric per-service layout:

- `backend/.env.example` — local backend (the file the README copies to `backend/.env`)
- `backend/.env.production.example` — Render/prod backend (mirrors the env group)
- `frontend/.env.local.example` — local frontend
- `frontend/.env.production.example` — Vercel frontend

The two **root** files (`.env.example`, `.env.production.example`) were misplaced (backend
vars at repo root) and unreferenced except here — **removed**. Scanned all files: zero
real-secret fragments.

**Deliberately NOT doing** (costs money): a separate Render Background Worker or a bigger
instance — the architecturally-correct fix, but ruled out by the no-extra-bill constraint.
The free fix above removes the memory OOMs, which is the actual root.

## D5. Exit criteria

- [x] `relevance_scorer.py` API-routed; dead loaders removed (R1)
- [x] `topic_linker.py` API-routed; dead loader removed (R2)
- [x] mypy green, ruff clean, topic-linker tests pass
- [x] Deployed to `main` (774c7f8) + crons under Blueprint (43f9e84 + sync)
- [x] Both DBs unaffected; CI green; 3 services adopted, no duplicates
- [x] Render bill unchanged (associated existing services — no new billable resource)
- [ ] `R3` metric-watch — **PASSIVE, owner-observed.** The developer is watching Render
      alert frequency over the next month. No action, no reporting, no follow-up needed
      unless they raise it.

**R-later (follow-up, non-blocking):** cache topic embeddings so scrapes stop re-encoding
~1,462 topics every run — the single biggest lever on HF API load.

---

# PART E — VERCEL "Exceeded free resources" ✅ FIXED (V1–V3 shipped 774c7f8)

Different system from everything above — the **Next.js frontend on Vercel** (`frontend/`),
not the Django backend. Warning emails **weekly since May 2026**. **Constraint: fix must
stay on the Vercel free (Hobby) tier — no Pro upgrade, no new bill.**

## E1. Measured state (dashboard, 2026-08-30)

| Metric                                 | Usage    | Limit  | Status             |
| -------------------------------------- | -------- | ------ | ------------------ |
| **ISR Writes**                         | **417K** | 200K   | 🔴 **208% — OVER** |
| Fast Origin Transfer                   | 9.42 GB  | 10 GB  | 🟠 94%             |
| **Image Optimization Transformations** | ~3.7K    | 5K     | 🟡 75%             |
| Edge Requests                          | 435K     | 1M     | 🟢 44%             |
| Function Invocations                   | 181K     | 1M     | 🟢 18%             |
| Fast Data Transfer                     | 6.05 GB  | 100 GB | 🟢 6%              |

Plus a sidebar warning: **Node.js 20 is deprecated — builds fail after 2026-10-01** (must
move to Node 24).

## E2. Root cause

- **ISR Writes (the serious one).** Incremental Static Regeneration re-generates static
  pages on a schedule (`revalidate`) or on-demand; **each regeneration = one ISR Write.**
  With **~2,161 concept pages + ~1,259 daily-CA articles + news pages** and short
  `revalidate` intervals (or frequent on-demand revalidation), writes explode into the
  hundreds of thousands/month. **If exceeded, Vercel auto-pauses the project → site down.**
  This recurs weekly (a standing config issue, not a spike) despite a past
  _"reduce Vercel ISR write amplification"_ commit — intervals are still too aggressive for
  the page count.
- **Image Optimization Transformations.** Next.js `<Image>` transforms each image+size on
  first request. Daily-CA hero images come from **Cloudinary, which already optimizes them**
  — so Vercel is paying quota to re-optimize already-optimized images (double work).
- **Node.js 20 deprecation.** Unrelated build-config item; one-line bump.

## E3. Phases

### V0 — Diagnose ✅

Measured state (E1) + root cause (E2) confirmed from the dashboard and the weekly emails.
ISR Writes is the site-pause risk and the priority.

### V1 — Cut ISR Writes (the big lever) ✅ code-complete

Lengthened `revalidate` on the high-cardinality dynamic routes (the real amplifier). On-demand
revalidation (`/api/revalidate` → `revalidatePath`) already exists, so new content still appears
**instantly on publish** — the longer window is only a fallback. Edits (6 files):

| File                                                   | Before | After                     |
| ------------------------------------------------------ | ------ | ------------------------- |
| `topics/[id]/page.tsx` (~1,462 pages)                  | 3600   | **86400**                 |
| `daily-ca/article/[slug]/page.tsx` (~1,259, immutable) | 3600   | **86400**                 |
| `subjects/[id]/page.tsx`                               | 3600   | **86400**                 |
| `modules/[id]/page.tsx`                                | 3600   | **86400**                 |
| `current-affairs/page.tsx` (list)                      | 600    | **3600**                  |
| `page.tsx` (home inner fetches)                        | 300    | **1800**                  |
| `current-affairs/[id]/page.tsx`                        | 86400  | unchanged (already right) |

Also fixed the stale "Render free tier cold-starts" comments (plan is paid Starter).
Expected ~24x fewer dynamic-route writes, back well under 200K/cycle.

### V2 — Stop double image optimization ✅ code-complete

**Verified first (not assumed):** `backend/engines/daily_ca/services/image_service.py:285`
uploads every hero image with `fetch_format="auto"`, `quality="auto:good"`, `width=1200,
crop="limit"` — so Cloudinary already delivers f_auto/q_auto/≤1200px assets. Vercel's
`<Image>` optimizer was re-optimizing an already-optimized image.

Chose a **custom Cloudinary loader** over a blunt `unoptimized` flag because (a) Fast Origin
Transfer sits at 94% and dropping responsive `srcset` would send full 1200px images to phones,
and (b) some hero images are Wikipedia fallbacks (`upload.wikimedia.org`), not Cloudinary.

Files (2):

- `frontend/src/lib/cloudinary-loader.ts` (new) — injects `f_auto,q_auto,w_<width>,c_limit`
  into Cloudinary `/upload/` URLs; passes non-Cloudinary URLs through untouched.
- `frontend/next.config.ts` — `images.loader = "custom"` + `loaderFile`.

Effect: Vercel Image-Optimization Transformations → ~0, images served straight from
Cloudinary's CDN (also relieves the 94% Fast-Origin-Transfer meter), responsive srcset kept.

### V3 — Node.js 20 → 24 ✅ code-complete

`frontend/package.json` had **no `engines` field**, so Vercel fell back to its default
(Node 20, deprecated — builds fail after 2026-10-01). Pinned it in code (IaC, not the
dashboard):

```json
"engines": { "node": "24.x" }
```

Next.js 16 supports Node 24. `@types/node` left at 20 — it types the local dev runtime, is
unrelated to the Vercel deprecation, and bumping it risks new `tsc` errors for zero benefit
here. (Optional future alignment, non-blocking.)

### V4 — Deploy + watch ✅ shipped, metric-watch ongoing

V1–V3 shipped in `774c7f8`; Vercel auto-deploys the frontend on push. Remaining is passive:
watch the Vercel usage dashboard for one full cycle to confirm ISR Writes fall back under
200K and Image Optimization stops climbing.

## E4. Exit criteria

- [x] V1–V3 shipped (774c7f8) and auto-deployed by Vercel
- [x] Node 24 pinned; builds green
- [x] Still on the free (Hobby) tier — no new bill
- [ ] Metric-watch — **PASSIVE, owner-observed.** ISR Writes back under 200K/cycle,
      Image Optimization flat, no "Exceeded free resources" email. The developer is
      watching this over the next month; no action or reporting needed unless raised.

---

## Appendix — misc observations (not blocking)

- `ca_chunk` averaged ~28 KB/row (chunks should be 1–2 KB) — near-full article text likely
  stored per chunk. Worth trimming CA chunk size later to slow regrowth further.
- Index/TOAST dwarfs data on several small tables — a periodic `REINDEX`/`VACUUM FULL`
  pass on the whole DB would reclaim a little more, but is not needed at 282 MB.
