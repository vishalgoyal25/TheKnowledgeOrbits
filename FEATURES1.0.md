# FEATURES.md — TheKnowledgeOrbits
## Feature 2: Daily CA Pipeline + Tag Ecosystem

**Git tag at start of this feature**: `v1.0.2-poc-integration`
**Stable baseline**: Book Content Engine live, syllabus seeded (14 subjects, ~290 topics),
Knowledge Graph UI, CA scraping pipeline active, full SaaS auth/RBAC stack operational.

---

## GROUND RULES FOR THIS FEATURE

- ONE file at a time. Stop and wait for human approval before next file.
- NEVER touch existing working engines (current_affairs, book_content, knowledge, auth).
- NEVER cross-engine DB access — new engines communicate via internal API calls only.
- Static BookContent = IMMUTABLE after is_published=True. Never regenerate.
- Daily CA generation = MANUAL (human-controlled) until explicitly automated.
- All GROQ API calls must respect rate limits: 12s sleep, session cap = 25 calls.
- Keyword Tags are permanent assets. Never delete a tag (only set is_active=False).
- Concept Pages are permanent assets. Never delete a concept page.
- Max 8 keyword tags per article. Enforced at DB and service level.
- Max 8 inline concept links per article. Enforced in ConceptPageResolver.
- Article word limit: 450–700 words per Daily CA article. Hard cap: 750 words.
- No UPSC Angle section in any article. No practice questions in CA articles.
- Generation cycle = ATOMIC per CA article: CA article saved immediately after generation. Static BookContent is generated SEPARATELY in background AFTER all CA cycles complete.
- Three entities are DISTINCT and must NEVER be confused or substituted for each other:
    Keyword Tags → article labels → /tags/[slug] → aggregation page
    Concept Pages → inline deep links → /concepts/[slug] → dedicated concept explanation
    Static BookContent → syllabus-mapped articles → /learn/[slug] → structured topic article

---

## THREE-ENTITY CONTENT ARCHITECTURE

Three completely distinct content entities exist on this platform. Each has a different
purpose, different table, different URL, and different generation strategy.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ENTITY         │ KEYWORD TAG         │ CONCEPT PAGE         │ STATIC CONTENT   │
├─────────────────┼─────────────────────┼──────────────────────┼──────────────────┤
│  Model          │ Tag + ArticleTag    │ ConceptPage          │ BookContent       │
│  Table          │ tag, article_tag    │ concept_page         │ knowledge_book_  │
│                 │                     │ concept_article_link │ content           │
│  Engine         │ engines/tags/       │ engines/tags/        │ engines/book_    │
│                 │                     │                       │ content/          │
│  URL            │ /tags/[slug]        │ /concepts/[slug]     │ /learn/[slug]    │
│  Purpose        │ Article labelling   │ Contextual deep-dive │ Syllabus learning │
│                 │ & discovery         │ for high-value terms  │ structured topic  │
│  Examples       │ "federalism"        │ "CLNDA", "SMRs",     │ "Indian Parliament│
│                 │ "gst"               │ "Viksit Bharat 2047" │ Structure"        │
│                 │ "climate-change"    │ "101st Amendment"    │ "GST Framework"  │
│  Location in    │ End of article      │ Inside body [[term]] │ Referenced via   │
│  CA article     │ (chip badges)       │ (hyperlinked inline) │ factual anchor    │
│  Maps to UPSC   │ No                  │ No — standalone      │ Yes — Topic FK   │
│  syllabus?      │                     │                       │                   │
│  Content        │ Label only          │ Brief now, full body │ Full structured  │
│                 │                     │ generated later      │ article           │
│  Used in CA?    │ Yes (end)           │ Yes (inline)         │ As input only    │
│  Used in Static?│ Yes (end)           │ Not yet              │ It IS this        │
│  On creation    │ Instant             │ Stub (brief_desc)    │ Full generation  │
│  click opens    │ Article list page   │ Concept detail page  │ Topic article    │
└─────────────────┴─────────────────────┴──────────────────────┴──────────────────┘
```

### Rules enforced at all times:
- [[double brackets]] in CA article body → ALWAYS Concept Pages. NEVER keyword tags. NEVER static links.
- TAGS: line at end of LLM response → ALWAYS Keyword Tags. NEVER concept pages.
- Static BookContent is NEVER linked inline in CA articles — only used as factual anchor during generation.
- Concept Pages are NEVER seeded manually — created organically by LLM during CA generation.
- Keyword Tags ARE pre-seeded (1000+) and auto-created when not found.

---

## STATIC CONTENT GENERATION + TOPIC GRANULARITY PRINCIPLES

### Demand-Driven Static Generation
Static BookContent is not batch-generated upfront. It is generated ON DEMAND when a Daily CA
proposal needs it and no locked static exists for that topic.

```
Day 1: CA article on "Nuclear Energy Policy" → no static for topic → generate static → lock → use
Day 5: CA article on "Fast Breeder Reactor" → no static → generate static → lock → use
Day 12: CA article on "Nuclear Waste Management" → static exists → use directly, 0 GROQ calls
Day 30: Most high-frequency UPSC topics have static content. Demand-gen rate drops.
```

Over months of daily CA generation, the static BookContent library builds itself organically
around the most news-relevant UPSC topics — without any batch job.

### SUBJECT_TONE_MAP in book_content Engine (Minimal Extension Required)
The existing book_content engine's `SUBJECT_TONE_MAP` was tested primarily for Polity in POC.
It needs entries for all 14 subjects. This is done in Phase A (one dict extension only —
no structural prompt changes, no MASTER_STYLE_ANCHOR changes, no SECTION_PLAN changes).

The same SUBJECT_TONE_MAP is replicated (independently) in the CA prompt builder (Phase I).
The two are separate: book_content owns its version, daily_ca owns its version.

### Topic Granularity — The Correct Balance
Each `knowledge_topic` row = one learnable unit = one BookContent article.

Problem: "Parliament" as one topic → LLM generates 24 sub-subtopics.
Problem: Too many granular seeds → unmanageable maintenance.
Solution: seed_syllabus.py is the HUMAN-DEFINED source of truth for granularity.

```
RULE: LLM never decides topic scope. The topic TITLE defines the scope.
      The prompt says "write about exactly [topic title] in 450–700 words." That's it.

ENFORCEMENT:
  MAX_HEADING_DEPTH = 2  (only ## headings allowed — no ### sub-sub-sections)
  MAX_WORDS = 750        (hard cap — LLM physically cannot expand to 24 sub-sections)

WHEN A TOPIC IS TOO BROAD (detected via poor quality score):
  → Split it in seed_syllabus.py into focused sub-topics:
    "Parliament" → "Parliament — Structure and Composition"
                   "Parliament — Legislative Process"
                   "Parliament — Parliamentary Committees"
                   "Parliament vs State Legislature"
  → This is a seed_syllabus.py edit, not a model change.
  → Done incrementally as quality issues surface, not all upfront.

CURRENT STATE: ~290 topics across 14 subjects. Sufficient to start.
               Will be refined over time as generation reveals gaps.
```

---

## ARCHITECTURE OVERVIEW

```
THREE NEW CONTENT ENTITIES:
  engines/daily_ca/   — Owns proposal + generated CA article tables
  engines/tags/       — Owns keyword tags + concept pages (cross-cutting)
  (book_content extended) — SUBJECT_TONE_MAP extended for all 14 subjects

TWO NEW MANAGEMENT COMMANDS:
  generate_ca_proposals   — Lightweight: score + group + propose titles
  generate_daily_ca       — Full generation: triggered AFTER human approval only

HUMAN-IN-THE-LOOP FLOW:
  Step 1 → Run generate_ca_proposals → creates 20-50 CaDailyProposal rows
  Step 2 → Admin visits /admin/daily-ca/proposals/ → selects exactly 10
  Step 3 → Clicks "Approve & Generate" → triggers full article generation
  Step 4 → Admin reviews generated articles → clicks "Publish All"
  Step 5 → Articles appear live on /daily-ca/

GENERATION = CYCLE-BASED (CA-first, static-background):
  Each proposal = one complete CA generation cycle (fast — ~15-20 seconds per cycle)
  Cycle completes → CA article saved immediately → move to next cycle
  If static exists for topic → used as factual anchor in that cycle
  If static missing → cycle proceeds with wiki enrichment only → topic queued for background static
  After ALL cycles complete → fire background static generation for topics without static
  If session cap hit mid-run → remaining proposals marked 'queued_next_run' → stop gracefully
  If individual cycle fails → mark proposal 'failed' → continue to next cycle (not catastrophic)
  6 complete articles from 10 proposals = valid and acceptable output
  Static content available for NEXT day's CA articles (organic library growth over time)

NO AUTOMATION YET. Everything manual at localhost stage.
```

---

## DATA FLOW (Full Pipeline)

```
LAYER 0 — RAW INGESTION (Existing + Extended in Phase A)
══════════════════════════════════════════════════════════
Sources (5 total — RSS only):
  TheHindu RSS        (existing, keep)
  IndianExpress RSS   (existing, keep)
  PIB RSS             (new — official govt press releases)
  DownToEarth RSS     (new — environment/ecology focus)
  MyGov RSS           (new — official scheme/policy announcements)

Schedule: GitHub Actions "🤖 Current Affairs Ghost Worker" → 24hrs (once/day)
          Was: every 12hrs. Changed to preserve GitHub Actions free minutes.

All → ca_article → ca_chunk → (UPSC Relevance Scorer applied)

LAYER 1 — PROPOSAL GENERATION (Phase F)
══════════════════════════════════════════
generate_ca_proposals command:
  → Fetch ca_articles from last 24hrs
  → Apply UPSC Relevance Scorer (0–10 score, threshold = 5)
  → Group by topic (deduplicate: 3 sources on same topic = 1 proposal)
  → For each unique topic: generate title + 3-line description (1 GROQ call)
  → Save as CaDailyProposal (status='pending')
  → Total cost: ~5-10 lightweight GROQ calls

LAYER 2 — HUMAN APPROVAL (Phase N)
═════════════════════════════════════
Admin page /admin/daily-ca/proposals/[date]/:
  → Shows 20-50 proposal cards with checkboxes
  → Admin selects exactly 10 (others auto-disable)
  → Clicks "Approve & Generate"
  → Backend marks selected proposals status='approved'
  → Triggers Layer 3

LAYER 3 — FULL ARTICLE GENERATION, CYCLE-BY-CYCLE (Phase J–K)
════════════════════════════════════════════════════════════════
For each approved proposal (one complete atomic cycle):

  PRE-CHECK: groq_calls_used >= 25? → mark remaining 'queued_next_run' → STOP

  STEP 1: Static Background Check (internal API, no direct DB cross-access)
    → GET /api/v1/book-content/?topic_id=X&is_published=true
    → Case A: EXISTS + is_published=True
        → Extract key facts (dates, article numbers, statistics) as factual_anchor
        → 0 GROQ calls here
    → Case B: NOT EXISTS (no static content for this topic yet)
        → Return None IMMEDIATELY (do NOT trigger generation here — do NOT block)
        → Record topic_id in pending_static_generation list for post-cycle processing
        → Proceed with wiki_enrichment only as factual context
    → Case C: EXISTS but is_published=False (draft, incomplete)
        → Return None (do not use unlocked/unpublished content as factual anchor)
    → RULE: NEVER regenerate published static. NEVER block CA cycle waiting for static.
    → All static generation happens AFTER all CA cycles complete (see POST-CYCLE step below).

  STEP 2: Wiki Enrichment (conditional)
    → Only if ca_chunk total text < 300 words (thin source)
    → Reuses existing wiki_service.py (no GROQ — Wikipedia API)
    → Returns: intro paragraph + key facts + related terms

  STEP 3: Generate Daily CA Article (1 GROQ call)
    → Inputs: ca_chunks (top 3) + factual_anchor (or None) + wiki_enrichment + subject_tone
    → Prompt: CA_DAILY_PROMPT (subject-tone-aware, flexible headings)
    → LLM wraps 5-8 HIGH-VALUE terms in [[double brackets]] → these become Concept Page links
    → LLM inserts :::callout::: boxes ("Did You Know?") mid-article
    → LLM ends response with: TAGS: [keywords] and SOURCE: [url]
    → Output: title + markdown body (450-700 words)

  STEP 4: Concept Page Resolution ([[term]] → /concepts/slug)
    → ConceptPageResolver.process_and_replace(body_md, article.id)
    → For each [[term]]:
        a. Fuzzy match ConceptPage table (similarity > 0.85) → reuse if found
        b. No match → 1 GROQ call → generate name + brief_description → save stub
        c. Replace [[term]] → [term](/concepts/slug) in body_md_processed
        d. Create ConceptArticleLink record
    → Max 8 concept links per article enforced

  STEP 5: Keyword Tag Processing (TAGS: line → ArticleTag records)
    → TagService.extract_and_link_tags(article_text, overrides=tags_raw)  ← 1 GROQ call
    → Fuzzy match existing Tag table (similarity > 0.85)
    → No match → auto-create new Tag with description
    → Max 8 keyword tags per article enforced

  STEP 6: ATOMIC SAVE (transaction.atomic())
    → Save DailyCaArticle (body_md raw + body_md_processed with links)
    → Save ArticleTag records (keyword tags)

  STEP 2: Wiki Enrichment (conditional)
    → Only if ca_chunk total text < 300 words (thin source)
    → Reuses existing wiki_service.py (no GROQ — Wikipedia API)
    → Returns: intro paragraph + key facts + related terms

  STEP 3: Generate Daily CA Article (1 GROQ call)
    → Inputs: ca_chunks (top 3) + factual_anchor + wiki_enrichment + subject_tone
    → Prompt: CA_DAILY_PROMPT (subject-tone-aware, flexible headings)
    → LLM wraps 5-8 HIGH-VALUE terms in [[double brackets]] → these become Concept Page links
    → LLM inserts :::callout::: boxes ("Did You Know?") mid-article
    → LLM ends response with: TAGS: [keywords] and SOURCE: [url]
    → Output: title + markdown body (450-700 words)

  STEP 4: Concept Page Resolution ([[term]] → /concepts/slug)
    → ConceptPageResolver.process_and_replace(body_md, article.id)
    → For each [[term]]:
        a. Fuzzy match ConceptPage table (similarity > 0.85) → reuse if found
        b. No match → 1 GROQ call → generate name + brief_description → save stub
        c. Replace [[term]] → [term](/concepts/slug) in body_md_processed
        d. Create ConceptArticleLink record
    → Max 8 concept links per article enforced

  STEP 5: Keyword Tag Processing (TAGS: line → ArticleTag records)
    → TagService.extract_and_link_tags(article_text, overrides=tags_raw)  ← 1 GROQ call
    → Fuzzy match existing Tag table (similarity > 0.85)
    → No match → auto-create new Tag with description
    → Max 8 keyword tags per article enforced

  STEP 6: ATOMIC SAVE (transaction.atomic())
    → Save DailyCaArticle (body_md raw + body_md_processed with links)
    → Save ArticleTag records (keyword tags)
    → Save ConceptArticleLink records (concept page links)
    → Save DailyCaStaticLink if static already existed (Case A only)
    → Update proposal: status='generated', generated_article=article
    → Redis: update daily_ca_progress:{date} cache
    → LOG: "Cycle N/10 complete: [title] | GROQ calls this session: X"

  ON EXCEPTION IN ANY CYCLE:
    → Full exception logged with structlog
    → proposal.status = 'failed'
    → DO NOT stop the loop — move to next proposal
    → Partial run (6/10) is valid output

  POST-CYCLE (after ALL 10 cycles complete):
    → StaticBackgroundService.trigger_pending_static_generation(pending_topic_ids)
    → For each topic_id that had no static: POST /api/v1/book/internal/generate/{topic_id}/
    → Non-blocking: fires-and-forgets (202 Accepted), does NOT wait for completion
    → Static generates in background → eventually becomes available for NEXT day's CA articles
    → LOG: "Triggered background static generation for N topics: [topic names]"

LAYER 4 — PUBLISH (Phase N)
═════════════════════════════
Admin reviews generated articles → "Publish All" → is_published=True
→ Redis cache: daily_ca:{date} = list of published article slugs
→ Articles appear live on /daily-ca/

LAYER 5 — MONTHLY CLEANUP (Phase K)
══════════════════════════════════════
Run manually: python manage.py cleanup_raw_ca --months-old 1
→ Deletes: ca_article, ca_chunk, ca_topic_link older than 30 days
→ KEEPS: DailyCaArticle FOREVER (our generated asset)
→ KEEPS: Tag + ArticleTag FOREVER
→ KEEPS: ConceptPage + ConceptArticleLink FOREVER
→ KEEPS: DailyCaStaticLink FOREVER
```

---

## PHASE A — CA Sources Extension + Relevance Scorer + Tone Map Extension
**Depends on**: Nothing (extends existing engines cautiously)
**Engines touched**: `engines/current_affairs/` (scrape_ca.py edited) + `engines/book_content/` (quality_engine_service.py extended)
**GitHub Actions**: Manually update `🤖 Current Affairs Ghost Worker` schedule from `0 */12 * * *` to `0 0 * * *` (once/day at midnight). Do this BEFORE running Phase A commands.

---

### ✅ A1 — Extend SUBJECT_PROFILES in book_content Engine
**File edited**: `backend/engines/book_content/services/quality_engine_service.py`

**Done:**
- `SUBJECT_PROFILES` extended from 5 → all 14 UPSC subjects (matches `seed_syllabus.py` names exactly)
- Each profile has 10 keys: `tone`, `emphasis`, `structure`, `avoid`, `example_voice`,
  `key_sources`, `critical_vocab`, `comparison_pairs`, `data_types`, `section_renames`
- `MASTER_STYLE_ANCHOR` rewritten to be subject-agnostic with multi-subject examples
- `SECTION_PLAN` upgraded: `upsc_angle` section removed; fixed headings replaced with
  `heading_directive` per section — LLM picks topic-specific `###` heading each time;
  `_generate_sections()` tracks `used_headings` and injects anti-duplication fence per prompt
- `_build_section_prompt()` injects all 10 profile keys into every generation prompt

---

### ⚠️ A2 — Add New RSS Sources — DROPPED (TH + IE sufficient)
**Decision**: PIB, DownToEarth, and MyGov RSS URLs are broken or return 403/404.
All three require custom HTML scrapers — out of scope for Phase A.
`scrape_ca.py` is untouched — already fully functional with TH + IE.

TH + IE yield ~300-400 articles/day → ~90-160 after relevance scoring → sufficient for 10 proposals/day.

**Future**: Add new sources directly via Django admin (`/admin/current_affairs/casource/`).
No code change needed — `scrape_all_active()` picks up any active DB row automatically.

---

### ✅ A3 — UPSC Relevance Scorer
**File created**: `backend/engines/current_affairs/services/relevance_scorer.py`

**Done:**
- `RelevanceScorerService.score_article(article)` → float 0.0–10.0 (clamped)
- `RelevanceScorerService.is_relevant(article)` → bool (threshold >= 5.0)
- `RelevanceScorerService.filter_relevant(articles)` → sorted list of (article, score) tuples

```
Scoring breakdown:
  +3.0  title contains a UPSC keyword (200+ terms across all 14 subjects)
  +3.0  article embeds close to a knowledge_topic (cosine similarity > 0.7)
  +1.0  published_at within last 12 hours (recency bonus)
  -5.0  title matches BLOCKED_NOISE pattern AND no cancel term present
        — "monsoon", "cyclone", "flood" → NOT blocked (Environment/Disaster)
        — "strike", "protest"           → NOT blocked (Governance/Labour)
        — only pure noise (zero UPSC mapping) gets -5.0

Threshold: >= 5.0 → keep | < 5.0 → discard (logged at DEBUG)
Note: +2.0 html source_type bonus dropped — all active sources are RSS.
```

**Phase A success criteria**:
- ✅ `quality_engine_service.py` — SUBJECT_PROFILES has all 14 subjects, dynamic headings active
- ⚠️ A2 dropped — TH + IE are the active sources; PIB/DTE/MyGov deferred
- ✅ `relevance_scorer.py` — RelevanceScorerService scores CAArticle 0.0–10.0
- ✅ GitHub Actions `🤖 Current Affairs Ghost Worker` schedule updated to `0 0 * * *`
- ✅ `SELECT COUNT(*) FROM ca_source;` shows ≥ 2 active sources (TH + IE)
- ✅ RelevanceScorerService manually verified on 10 real articles (run in Django shell)

---

## ✅ PHASE B — New Engine Skeletons
**Depends on**: Phase A complete
**Files to create (one at a time, wait for approval between files)**:

```
backend/engines/daily_ca/
  __init__.py
  apps.py          ← DailyCaConfig, label='daily_ca'
  admin.py
  urls.py
  models.py        ← empty placeholder
  serializers.py   ← empty placeholder
  views.py         ← empty placeholder
  services/
    __init__.py
  management/
    __init__.py
    commands/
      __init__.py
  tests/
    __init__.py
  migrations/
    __init__.py

backend/engines/tags/
  __init__.py
  apps.py          ← TagsConfig, label='tags'
  admin.py
  urls.py
  models.py        ← empty placeholder
  serializers.py   ← empty placeholder
  views.py         ← empty placeholder
  services/
    __init__.py
  management/
    __init__.py
    commands/
      __init__.py
  tests/
    __init__.py
  migrations/
    __init__.py
```

**Register both in `core/settings/base.py` INSTALLED_APPS**:
```python
'engines.daily_ca',
'engines.tags',
```

**Add URL routing in `core/urls.py`**:
```python
path('api/v1/daily-ca/', include('engines.daily_ca.urls')),
path('api/v1/tags/', include('engines.tags.urls')),
path('api/v1/concepts/', include('engines.tags.urls')),  # concepts served via tags engine
```

**Phase B success criteria**:
- ✅ `python manage.py check` passes with no errors
- ✅ Both engines appear in INSTALLED_APPS
- ✅ No import errors on runserver

---

## ✅ PHASE C — Tags Engine: DB Models + Migration
**Depends on**: Phase B complete
**File**: `backend/engines/tags/models.py`

### Model 1: Tag (Keyword Tags — article labels)
```python
class Tag(models.Model):
    id           = UUIDField(primary_key=True, default=uuid4, editable=False)
    name         = CharField(max_length=100, unique=True)  # lowercase-hyphenated
    slug         = SlugField(max_length=120, unique=True)
    description  = TextField(blank=True, default='')  # 1-2 sentence explanation
    tag_type     = CharField(max_length=20, choices=[
                     ('topic', 'UPSC Topic'),
                     ('subtopic', 'Subtopic'),
                     ('scheme', 'Government Scheme'),
                     ('person', 'Person/Figure'),
                     ('place', 'Place/Geography'),
                     ('organisation', 'Organisation/Body'),
                     ('concept', 'Concept/Term'),
                     ('law', 'Law/Act/Treaty'),
                     ('event', 'Event'),
                     ('other', 'Other'),
                   ], default='concept')
    usage_count  = PositiveIntegerField(default=0)
    is_active    = BooleanField(default=True)
    created_at   = DateTimeField(auto_now_add=True)
    updated_at   = DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tag'
        ordering = ['-usage_count', 'name']
        indexes = [Index(fields=['slug']), Index(fields=['tag_type']),
                   Index(fields=['-usage_count'])]
```

### Model 2: ArticleTag (Keyword Tag ↔ Article junction)
```python
class ArticleTag(models.Model):
    id           = UUIDField(primary_key=True, default=uuid4, editable=False)
    tag          = ForeignKey(Tag, on_delete=CASCADE, related_name='article_tags')
    content_type = CharField(max_length=20, choices=[
                     ('daily_ca', 'Daily CA Article'),
                     ('book_content', 'Static Book Content'),
                   ])
    object_id    = UUIDField()  # ID of the linked article
    relevance    = FloatField(default=1.0)  # 0.0–1.0
    created_at   = DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'article_tag'
        unique_together = ['tag', 'content_type', 'object_id']
        indexes = [Index(fields=['content_type', 'object_id']),
                   Index(fields=['tag', 'content_type'])]
```

### Model 3: ConceptPage (Inline Concept Deep Links — standalone knowledge units)
```python
class ConceptPage(models.Model):
    """
    Standalone concept explanation pages. Created organically during CA generation
    when LLM writes [[term]] for a high-value conceptual term.
    NOT linked to syllabus. NOT a keyword tag. NOT a static book content article.
    brief_description is generated at creation time (1 GROQ call).
    body_md is EMPTY initially — full content generated in a separate future phase.
    """
    id                = UUIDField(primary_key=True, default=uuid4, editable=False)
    name              = CharField(max_length=300)   # "Civil Liability for Nuclear Damage Act"
    slug              = SlugField(max_length=350, unique=True)
    brief_description = TextField(blank=True, default='')  # 2-3 lines, LLM-generated on creation
    body_md           = TextField(blank=True, default='')  # Full content — EMPTY initially
    is_content_ready  = BooleanField(default=False, db_index=True)  # True = full page live
    usage_count       = PositiveIntegerField(default=0)  # incremented each time linked
    created_at        = DateTimeField(auto_now_add=True)
    updated_at        = DateTimeField(auto_now=True)

    class Meta:
        db_table = 'concept_page'
        ordering = ['-usage_count', 'name']
        indexes = [Index(fields=['slug']),
                   Index(fields=['-usage_count']),
                   Index(fields=['is_content_ready'])]
```

### Model 4: ConceptArticleLink (ConceptPage ↔ DailyCaArticle junction)
```python
class ConceptArticleLink(models.Model):
    id                = UUIDField(primary_key=True, default=uuid4, editable=False)
    concept_page      = ForeignKey(ConceptPage, on_delete=CASCADE,
                                   related_name='article_links')
    daily_ca_article  = ForeignKey('daily_ca.DailyCaArticle', on_delete=CASCADE,
                                    related_name='concept_links')
    created_at        = DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'concept_article_link'
        unique_together = ['concept_page', 'daily_ca_article']
        indexes = [Index(fields=['concept_page']),
                   Index(fields=['daily_ca_article'])]
```

**Migration**: `python manage.py makemigrations tags --name initial`

**Phase C implementation notes**:
- `ConceptArticleLink.daily_ca_article_id` is a plain `UUIDField` (no FK constraint yet)
  because `DailyCaArticle` doesn't exist until Phase E. FK + CASCADE migration added in Phase E.
- `ArticleTag` uses generic FK pattern (`content_type` + `object_id`) to support both
  `daily_ca` and `book_content` articles from a single table.
- Max 8 tags / 8 concept links per article enforced at service layer, not DB level.

**Phase C success criteria**:
- ✅ models.py written with all 4 models
- ✅ `python manage.py makemigrations tags --name initial` — generates migration file
- ✅ `python manage.py migrate` — tables created on local postgres
- ✅ Tables visible in pgAdmin: `tag`, `article_tag`, `concept_page`, `concept_article_link`
- ✅ Supabase: migration applied via `python manage.py migrate --database=supabase`

---

## ✅ PHASE D — Tags Engine: seed_tags Management Command
**Depends on**: Phase C complete
**File**: `backend/engines/tags/management/commands/seed_tags.py`

Structure mirrors `seed_syllabus.py` exactly (idempotent, human-defined source of truth):
```python
TAGS: dict = {
    # Format: "tag-slug": ("Short description 1-2 sentences.", "tag_type")

    # === CONSTITUTIONAL ===
    "preamble": ("Opening statement of the Indian Constitution declaring India sovereign, socialist, secular, democratic and republic.", "topic"),
    "fundamental-rights": ("Articles 12-35 of Indian Constitution guaranteeing enforceable rights against state action.", "topic"),
    "dpsp": ("Directive Principles of State Policy under Articles 36-51, non-justiciable guidelines for governance.", "topic"),
    "fundamental-duties": ("Article 51A lists 11 duties for citizens, added by 42nd Amendment 1976.", "topic"),
    "basic-structure": ("Doctrine established in Kesavananda Bharati (1973) that Parliament cannot amend Constitution's core features.", "concept"),
    "judicial-review": ("Power of courts to examine laws and government actions for constitutional validity.", "concept"),
    "judicial-activism": ("Pro-active role of judiciary in protecting rights, especially via PIL, beyond traditional adjudication.", "concept"),
    "pil": ("Public Interest Litigation allowing any citizen to approach courts for public welfare matters.", "concept"),
    "federalism": ("Division of powers between Centre and States as enshrined in Indian Constitution.", "concept"),
    "centre-state-relations": ("Legislative, administrative and financial relations between Union and State governments.", "topic"),
    "emergency-provisions": ("Articles 352-360 covering National Emergency, President's Rule and Financial Emergency.", "topic"),
    "article-370": ("Special provision for Jammu and Kashmir, abrogated in August 2019.", "law"),
    "anti-defection": ("Tenth Schedule of Constitution disqualifying legislators who switch party allegiance.", "law"),
    "election-commission": ("Constitutional body under Article 324 responsible for superintendence of elections in India.", "organisation"),
    "upsc-body": ("Union Public Service Commission under Article 315 conducting civil services examinations.", "organisation"),
    "finance-commission": ("Constitutional body under Article 280 recommending Centre-State tax devolution.", "organisation"),
    "cag": ("Comptroller and Auditor General under Article 148 auditing government accounts.", "organisation"),
    "lokpal": ("Anti-corruption ombudsman body established under Lokpal and Lokayuktas Act 2013.", "organisation"),
    "niti-aayog": ("Policy think tank replacing Planning Commission in 2015, promotes cooperative federalism.", "organisation"),
    "separation-of-powers": ("Doctrine distributing legislative, executive and judicial powers among separate organs.", "concept"),

    # === POLITY — LEGISLATURE ===
    "parliament": ("Bicameral legislature of India comprising Lok Sabha, Rajya Sabha and President.", "topic"),
    "lok-sabha": ("Lower house of Parliament, directly elected, maximum 552 members.", "topic"),
    "rajya-sabha": ("Upper house of Parliament representing states, 245 members, permanent house.", "topic"),
    "money-bill": ("Bill certified by Speaker under Article 110 dealing exclusively with financial matters.", "concept"),
    "joint-sitting": ("Article 108 provision for simultaneous sitting of both Houses to resolve deadlock.", "concept"),
    "parliamentary-committees": ("Committees of Parliament scrutinising legislation, estimates and public accounts.", "topic"),
    "delimitation": ("Redrawing of constituency boundaries by Delimitation Commission based on census data.", "concept"),

    # === POLITY — EXECUTIVE ===
    "president": ("Constitutional head of India under Article 52, elected by electoral college.", "topic"),
    "prime-minister": ("Head of government and Council of Ministers, leader of majority in Lok Sabha.", "topic"),
    "governor": ("Constitutional head of state government, appointed by President under Article 155.", "topic"),
    "council-of-ministers": ("Cabinet collectively responsible to Lok Sabha under Article 75.", "topic"),
    "ordinance": ("Article 123 power of President to promulgate laws when Parliament not in session.", "concept"),

    # === JUDICIARY ===
    "supreme-court": ("Apex court of India under Article 124, final interpreter of Constitution.", "organisation"),
    "high-court": ("Article 214 courts at state level with original and appellate jurisdiction.", "organisation"),
    "suo-motu": ("Courts taking cognizance of matter on own motion without formal petition.", "concept"),
    "contempt-of-court": ("Disobedience of court orders or act lowering court's authority.", "concept"),

    # === ECONOMY ===
    "gdp": ("Gross Domestic Product measuring total value of goods and services produced in a country.", "concept"),
    "inflation": ("Sustained increase in general price levels measured by CPI or WPI in India.", "concept"),
    "repo-rate": ("Rate at which RBI lends money to commercial banks against government securities.", "concept"),
    "monetary-policy": ("RBI's management of money supply and interest rates to achieve macroeconomic goals.", "concept"),
    "fiscal-policy": ("Government's use of taxation and expenditure to influence economy.", "concept"),
    "gst": ("Goods and Services Tax, unified indirect tax replacing multiple levies since July 2017.", "scheme"),
    "frbm-act": ("Fiscal Responsibility and Budget Management Act 2003 mandating fiscal deficit targets.", "law"),
    "direct-tax": ("Tax levied directly on income or wealth of individuals and corporations.", "concept"),
    "indirect-tax": ("Tax on goods and services collected by intermediaries and passed to government.", "concept"),
    "fdi": ("Foreign Direct Investment — investment by foreign entities in Indian businesses.", "concept"),
    "fpi": ("Foreign Portfolio Investment — foreign investment in Indian stocks and bonds.", "concept"),
    "current-account-deficit": ("Excess of imports over exports of goods, services and income.", "concept"),
    "balance-of-payments": ("Record of all economic transactions between India and the world.", "concept"),
    "msme": ("Micro, Small and Medium Enterprises — backbone of Indian manufacturing and employment.", "concept"),
    "ppp": ("Public Private Partnership model for infrastructure development.", "concept"),
    "npa": ("Non-Performing Assets — bank loans overdue beyond 90 days.", "concept"),
    "rbi": ("Reserve Bank of India — central bank managing monetary policy and banking regulation.", "organisation"),
    "sebi": ("Securities and Exchange Board of India regulating securities markets.", "organisation"),
    "make-in-india": ("Government initiative to boost domestic manufacturing and attract investment.", "scheme"),
    "pli-scheme": ("Production Linked Incentive Scheme providing financial incentives for domestic manufacturing.", "scheme"),
    "one-nation-one-ration": ("Scheme allowing PDS beneficiaries to access rations from any fair price shop in India.", "scheme"),
    "pm-kisan": ("PM Kisan Samman Nidhi providing income support of Rs 6000/year to farmers.", "scheme"),
    "mgnrega": ("Mahatma Gandhi National Rural Employment Guarantee Act providing 100 days work guarantee.", "scheme"),
    "jan-dhan": ("Pradhan Mantri Jan Dhan Yojana for universal banking and financial inclusion.", "scheme"),
    "ayushman-bharat": ("PM Jan Arogya Yojana providing health cover of Rs 5 lakh per family.", "scheme"),
    "smart-cities": ("Government mission to develop 100 smart cities with sustainable infrastructure.", "scheme"),

    # === AGRICULTURE ===
    "msp": ("Minimum Support Price announced by government for agricultural crops.", "concept"),
    "green-revolution": ("1960s-70s agricultural transformation through high-yield seeds, irrigation and fertilisers.", "event"),
    "apmc": ("Agricultural Produce Market Committee — state-run mandis for agricultural trade.", "organisation"),
    "land-reforms": ("Policy measures redistributing agricultural land and abolishing zamindari system.", "topic"),
    "food-security": ("Ensuring availability, access and absorption of adequate food for all citizens.", "concept"),
    "pds": ("Public Distribution System delivering subsidised food grains through fair price shops.", "scheme"),
    "crop-insurance": ("PM Fasal Bima Yojana providing insurance coverage for crop losses.", "scheme"),

    # === ENVIRONMENT ===
    "climate-change": ("Long-term shifts in global temperatures and weather patterns, accelerated by human activity.", "concept"),
    "paris-agreement": ("2015 international accord under UNFCCC to limit global warming to 1.5-2°C.", "law"),
    "unfccc": ("UN Framework Convention on Climate Change — global treaty on climate action.", "organisation"),
    "cop": ("Conference of Parties — annual UN climate summit reviewing Paris Agreement progress.", "event"),
    "ndc": ("Nationally Determined Contribution — India's climate action pledges under Paris Agreement.", "concept"),
    "biodiversity": ("Variety of life on Earth measured at genetic, species and ecosystem levels.", "concept"),
    "cbd": ("Convention on Biological Diversity — international treaty for biodiversity conservation.", "law"),
    "cites": ("Convention on International Trade in Endangered Species protecting wildlife from over-exploitation.", "law"),
    "ramsar": ("International convention for conservation of wetlands of international importance.", "law"),
    "project-tiger": ("Government initiative for tiger conservation under Wildlife Protection Act.", "scheme"),
    "project-elephant": ("Government programme for elephant conservation and conflict mitigation.", "scheme"),
    "eia": ("Environmental Impact Assessment — mandatory review of environmental consequences of projects.", "concept"),
    "carbon-credit": ("Tradeable certificate representing reduction of one tonne of CO2 equivalent emissions.", "concept"),
    "renewable-energy": ("Energy from naturally replenishing sources: solar, wind, hydro, geothermal.", "concept"),
    "solar-energy": ("Energy harnessed from sunlight via photovoltaic cells or solar thermal systems.", "concept"),
    "national-park": ("Protected area under Wildlife Protection Act 1972 with highest level of protection.", "concept"),
    "biosphere-reserve": ("UNESCO-designated areas for conservation and sustainable use of biodiversity.", "concept"),
    "wetlands": ("Land areas saturated with water supporting unique ecosystems and biodiversity.", "concept"),
    "coral-reef": ("Underwater ecosystems built by coral organisms, highly sensitive to temperature changes.", "concept"),
    "deforestation": ("Permanent removal of forests for agriculture, infrastructure or settlements.", "concept"),
    "desertification": ("Degradation of dryland ecosystems due to climate change and human activities.", "concept"),
    "ozone-layer": ("Stratospheric layer absorbing UV radiation, protected under Montreal Protocol.", "concept"),
    "plastic-pollution": ("Accumulation of plastic waste in environment, particularly oceans.", "concept"),

    # === SCIENCE & TECHNOLOGY ===
    "isro": ("Indian Space Research Organisation conducting India's space programme since 1969.", "organisation"),
    "chandrayaan": ("India's lunar exploration mission, Chandrayaan-3 successfully landed in 2023.", "event"),
    "gaganyaan": ("India's first crewed spaceflight mission planned by ISRO.", "event"),
    "drdo": ("Defence Research and Development Organisation developing defence technologies.", "organisation"),
    "artificial-intelligence": ("Simulation of human intelligence by machines for decision-making and learning.", "concept"),
    "quantum-computing": ("Computing using quantum mechanical phenomena for exponentially faster processing.", "concept"),
    "5g": ("Fifth generation mobile network technology with ultra-fast speeds and low latency.", "concept"),
    "semiconductor": ("Material used in electronic devices; India's semiconductor mission targets domestic production.", "concept"),
    "nuclear-energy": ("Energy released by nuclear fission or fusion reactions.", "concept"),
    "fast-breeder-reactor": ("Nuclear reactor producing more fissile material than it consumes, part of India's thorium programme.", "concept"),
    "biotechnology": ("Use of biological systems and organisms for industrial and medical applications.", "concept"),
    "gmo": ("Genetically Modified Organisms whose DNA has been altered using genetic engineering.", "concept"),
    "cybersecurity": ("Protection of computer systems and networks from digital attacks and breaches.", "concept"),
    "data-protection": ("Legal and technical frameworks safeguarding personal data from misuse.", "concept"),
    "upi": ("Unified Payments Interface enabling real-time inter-bank transactions via mobile.", "scheme"),
    "digital-india": ("Government programme for digital infrastructure, services and empowerment.", "scheme"),
    "drone-technology": ("Unmanned aerial vehicles with applications in agriculture, defence and logistics.", "concept"),
    "space-economy": ("Commercial and governmental activities related to space exploration and utilisation.", "concept"),

    # === INTERNATIONAL RELATIONS ===
    "non-alignment": ("India's Cold War foreign policy of not joining either US or Soviet blocs.", "concept"),
    "act-east-policy": ("India's engagement with Southeast and East Asian nations for strategic and economic ties.", "concept"),
    "neighbourhood-first": ("India's foreign policy prioritising relations with South Asian neighbours.", "concept"),
    "brics": ("Brazil, Russia, India, China, South Africa — emerging economy grouping.", "organisation"),
    "sco": ("Shanghai Cooperation Organisation — Eurasian political, security and economic organisation.", "organisation"),
    "g20": ("Group of 20 major economies coordinating on global economic governance.", "organisation"),
    "g7": ("Group of 7 advanced economies: USA, UK, France, Germany, Italy, Canada, Japan.", "organisation"),
    "saarc": ("South Asian Association for Regional Cooperation — regional bloc of 8 nations.", "organisation"),
    "bimstec": ("Bay of Bengal Initiative for Multi-Sectoral Technical and Economic Cooperation.", "organisation"),
    "asean": ("Association of Southeast Asian Nations — 10-member regional bloc.", "organisation"),
    "un-security-council": ("15-member UN body with primary responsibility for international peace and security.", "organisation"),
    "wto": ("World Trade Organisation governing international trade rules and dispute settlement.", "organisation"),
    "imf": ("International Monetary Fund providing financial stability and economic surveillance.", "organisation"),
    "world-bank": ("International financial institution providing loans for development projects.", "organisation"),
    "quad": ("Quadrilateral Security Dialogue comprising India, USA, Japan and Australia.", "organisation"),
    "india-china": ("Bilateral relations between India and China marked by border disputes and trade.", "topic"),
    "india-pakistan": ("Bilateral relations with Pakistan, complicated by Kashmir and cross-border terrorism.", "topic"),
    "india-usa": ("Strategic partnership between India and USA covering defence, trade and technology.", "topic"),
    "border-dispute": ("Territorial disagreements between India and neighbouring countries.", "topic"),
    "belt-and-road": ("China's global infrastructure investment initiative spanning Asia, Europe and Africa.", "concept"),
    "nuclear-non-proliferation": ("International regime preventing spread of nuclear weapons.", "concept"),
    "diaspora": ("Indian community living abroad, contributing remittances and cultural diplomacy.", "concept"),

    # === HISTORY & CULTURE ===
    "freedom-struggle": ("India's movement for independence from British colonial rule (1857-1947).", "topic"),
    "constituent-assembly": ("Body that drafted the Indian Constitution between 1946-1949.", "event"),
    "partition": ("Division of British India into India and Pakistan in August 1947.", "event"),
    "emergency-1975": ("Period of 1975-77 when civil liberties were suspended under Indira Gandhi.", "event"),
    "bhakti-movement": ("Medieval devotional movement emphasising direct connection with God, led by saint-poets.", "topic"),
    "sufi-movement": ("Islamic mystical movement in India promoting love, tolerance and spiritual practice.", "topic"),
    "tribal-rights": ("Constitutional and legal protections for Scheduled Tribes including Forest Rights Act.", "topic"),
    "dalits": ("Communities at lowest rung of caste hierarchy; Constitution mandates their upliftment.", "topic"),

    # === SOCIAL ISSUES ===
    "poverty": ("State of lacking basic necessities; measured by Multidimensional Poverty Index in India.", "concept"),
    "inequality": ("Unequal distribution of income, wealth and opportunities in society.", "concept"),
    "urbanisation": ("Shift of population from rural to urban areas with associated social changes.", "concept"),
    "migration": ("Movement of people within or across national boundaries for livelihood or safety.", "concept"),
    "gender-equality": ("Equal rights and opportunities for people of all genders in society.", "concept"),
    "women-empowerment": ("Policies and processes strengthening women's agency, rights and opportunities.", "concept"),
    "child-rights": ("Rights of children to education, health, protection and participation.", "topic"),
    "education-policy": ("National Education Policy 2020 and other frameworks governing India's education system.", "topic"),
    "healthcare": ("Medical services, public health infrastructure and health policy in India.", "topic"),
    "communalism": ("Politics based on religious identity leading to inter-community conflicts.", "concept"),
    "secularism": ("Constitutional principle of state neutrality towards all religions.", "concept"),
    "regionalism": ("Political mobilisation based on regional identity and demands for autonomy.", "concept"),
    "caste-discrimination": ("Social and economic disadvantage faced due to birth in lower caste groups.", "topic"),

    # === DISASTER MANAGEMENT ===
    "ndma": ("National Disaster Management Authority — apex body for disaster management in India.", "organisation"),
    "sendai-framework": ("2015-2030 international framework for disaster risk reduction.", "law"),
    "floods": ("Overflow of water inundating normally dry land, frequent in India's river basins.", "concept"),
    "drought": ("Prolonged shortage of water affecting agriculture and livelihoods.", "concept"),
    "cyclone": ("Tropical storm system with strong rotating winds, frequent in Bay of Bengal.", "concept"),
    "earthquake": ("Sudden ground shaking caused by movement of tectonic plates.", "concept"),
    "heatwave": ("Extended period of abnormally high temperatures causing health emergencies.", "concept"),

    # === GOVERNANCE ===
    "rti": ("Right to Information Act 2005 enabling citizens to seek government records.", "law"),
    "e-governance": ("Delivery of government services through digital platforms.", "concept"),
    "decentralisation": ("Transfer of power to local self-government under 73rd and 74th Amendments.", "concept"),
    "panchayati-raj": ("Three-tier rural local government system under 73rd Amendment.", "concept"),
    "urban-local-bodies": ("Municipal corporations, councils and nagar panchayats under 74th Amendment.", "concept"),
    "civil-services": ("All India Services and Central Services recruited through UPSC examinations.", "topic"),
    "good-governance": ("Transparent, accountable, participatory and rule-based administration.", "concept"),
    "corruption": ("Abuse of entrusted power for private gain, addressed by Prevention of Corruption Act.", "concept"),
    "social-audit": ("Community verification of government programme implementation at grassroots level.", "concept"),

    # === ETHICS ===
    "integrity": ("Adherence to moral and ethical principles even under pressure.", "concept"),
    "probity": ("Strong moral principles and complete honesty in conduct of public duties.", "concept"),
    "conflict-of-interest": ("Situation where personal interests may improperly influence official duties.", "concept"),
    "emotional-intelligence": ("Ability to understand and manage one's emotions and those of others.", "concept"),
    "utilitarianism": ("Ethical theory holding that the best action maximises overall happiness.", "concept"),
    "virtue-ethics": ("Ethical framework focusing on character and virtues rather than rules or consequences.", "concept"),
    "whistleblower": ("Person who exposes wrongdoing within an organisation in public interest.", "concept"),
}
```

Command logic:
- Idempotent: `get_or_create` on `name` field
- Auto-generates `slug` from `name` using Django's `slugify`
- Prints summary: total tags seeded, new vs existing
- Usage: `python manage.py seed_tags`

**Phase D success criteria**:
- ✅ `python manage.py seed_tags` runs without error — 556 tags created on local
- ✅ `python manage.py seed_tags --database=supabase` — 556 tags created on Supabase
- ✅ Tags visible in Django admin

---

## ✅ PHASE E — Tags Engine: Services
**Depends on**: Phase D complete

Two separate services. Each handles one of the two tag types.

---

### E1 — TagService (Keyword Tags)
**File**: `backend/engines/tags/services/tag_service.py`

**`extract_and_link_tags(article_text, content_type, object_id, overrides=None)`**
```
Input: full article markdown text, content_type ('daily_ca'|'book_content'),
       object UUID, optional list of LLM-suggested keyword strings (from TAGS: line)
Process:
  1. If overrides provided (from LLM TAGS: line): use those as primary candidates
     Else: 1 GROQ call — "Extract 5-8 key UPSC-relevant keywords from this article.
            Prefer: topic, scheme, law, concept types. Return JSON list: [{name, type}]"
  2. For each keyword:
     a. Normalize: lowercase, replace spaces with hyphens
     b. Fuzzy search Tag table (pg_trgm similarity OR Python difflib, threshold 0.85)
     c. Match found → reuse existing Tag, increment usage_count
     d. No match → 1 GROQ call → generate description → create new Tag → log creation
  3. Create ArticleTag records (max 8 enforced — discard lowest relevance if >8)
  4. Return: list of Tag objects linked
```

**`get_articles_by_tag(tag_slug, content_type=None, limit=20)`**
```
Input: tag slug, optional content_type filter
Returns: list of article IDs for that tag, sorted by created_at desc
Used by: tag page API endpoint
```

---

### E2 — ConceptPageResolver (Inline Concept Links)
**File**: `backend/engines/tags/services/concept_resolver.py`

```python
class ConceptPageResolver:
    SIMILARITY_THRESHOLD = 0.85
    MAX_CONCEPT_LINKS = 8  # per article hard limit
    last_new_concept_calls = 0  # class-level, reset per article

    @classmethod
    def process_and_replace(cls, body_md: str, article_id: UUID) -> str:
        """
        Scans body_md for [[term]] patterns.
        Resolves each to a ConceptPage (reuse or create).
        Replaces [[term]] → [term](/concepts/slug).
        Creates ConceptArticleLink records.
        Enforces max 8 concept links per article.
        Returns processed markdown string.
        """
        cls.last_new_concept_calls = 0
        pattern = r'\[\[([^\]]+)\]\]'
        links_added = 0

        def replace_match(match):
            nonlocal links_added
            term = match.group(1).strip()
            if links_added >= cls.MAX_CONCEPT_LINKS:
                return term  # over limit — just the plain text, no link
            concept = cls._resolve_or_create(term)
            ConceptArticleLink.objects.get_or_create(
                concept_page=concept,
                daily_ca_article_id=article_id,
            )
            ConceptPage.objects.filter(pk=concept.pk).update(
                usage_count=F('usage_count') + 1
            )
            links_added += 1
            return f"[{term}](/concepts/{concept.slug})"

        return re.sub(pattern, replace_match, body_md)

    @classmethod
    def _resolve_or_create(cls, term: str) -> ConceptPage:
        """
        Finds existing ConceptPage (exact slug or fuzzy match).
        If no match: creates stub with brief_description (1 GROQ call).
        NEVER creates duplicate or near-duplicate concept pages.
        """
        slug = slugify(term)

        # Exact match first
        existing = ConceptPage.objects.filter(slug=slug).first()
        if existing:
            return existing

        # Fuzzy match against all slugs
        all_slugs = list(ConceptPage.objects.values_list('slug', flat=True))
        matches = difflib.get_close_matches(slug, all_slugs, n=1, cutoff=cls.SIMILARITY_THRESHOLD)
        if matches:
            return ConceptPage.objects.get(slug=matches[0])

        # No match: create new stub
        brief = cls._generate_brief(term)  # 1 GROQ call
        cls.last_new_concept_calls += 1
        time.sleep(12)  # GROQ rate limit
        concept = ConceptPage.objects.create(
            name=term,
            slug=slug,
            brief_description=brief,
            is_content_ready=False,
        )
        logger.info("concept_page_created", name=term, slug=slug)
        return concept
```

**What makes a good concept page term (enforced in CA_DAILY_PROMPT instructions):**
- Specific Acts/laws: `[[Civil Liability for Nuclear Damage Act]]`, `[[Forest Conservation Act 1980]]`
- Major government schemes with specific mandates: `[[PM-KUSUM]]`, `[[Viksit Bharat 2047]]`
- Technical/scientific terms: `[[Small Modular Reactors]]`, `[[HALEU]]`, `[[Thorium Cladding]]`
- Landmark constitutional events: `[[101st Constitutional Amendment]]`, `[[42nd Amendment]]`
- Key organisations with specific mandates: `[[Nuclear Power Corporation of India]]`

**What is NOT a concept page (enforced in prompt):**
- Generic topic names: "federalism", "parliament", "judiciary" → these are keyword tags
- Terms the article itself fully explains
- Casual or colloquial phrases

**Phase E success criteria**:
- ✅ `TagService.extract_and_link_tags()` implemented — fuzzy match + GROQ fallback + max 8 enforced
- ✅ `ConceptPageResolver.process_and_replace()` implemented — [[term]] → /concepts/slug links
- ✅ New concept page stub created + saved when [[term]] has no match (1 GROQ call)
- ✅ Fuzzy match (difflib 0.85) prevents duplicate concept pages
- ✅ Max 8 concept links per article enforced — over-limit terms render as plain text
- ✅ usage_count incremented atomically via F() on both Tag and ConceptPage

---

## ✅ PHASE F — Proposal Generation
**Depends on**: Phase E complete

### F1 — CaDailyProposal Model
**File**: `backend/engines/daily_ca/models.py`

```python
class CaDailyProposal(models.Model):
    id               = UUIDField(primary_key=True, default=uuid4, editable=False)
    date             = DateField(db_index=True)
    title            = CharField(max_length=500)
    description      = TextField()  # 3-line news summary for admin review
    topic            = ForeignKey('knowledge.Topic', null=True, blank=True,
                                  on_delete=SET_NULL, related_name='ca_proposals')
    subject_name     = CharField(max_length=200, blank=True)
    gs_paper         = CharField(max_length=10, blank=True)  # "GS2", "GS3" etc.
    source_urls      = JSONField(default=list)  # [{source_name, url, title}]
    ca_chunk_ids     = JSONField(default=list)  # UUIDs of top 3 ca_chunks
    relevance_score  = FloatField(default=0.0)
    status           = CharField(max_length=20, choices=[
                          ('pending', 'Pending Review'),
                          ('approved', 'Approved'),
                          ('rejected', 'Rejected'),
                          ('generated', 'Article Generated'),
                          ('failed', 'Generation Failed'),
                          ('queued_next_run', 'Queued for Next Run'),
                       ], default='pending')
    approved_at      = DateTimeField(null=True, blank=True)
    generated_article = ForeignKey('daily_ca.DailyCaArticle', null=True, blank=True,
                                    on_delete=SET_NULL, related_name='proposal')
    created_at       = DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'daily_ca_proposal'
        ordering = ['-relevance_score']
        unique_together = ['date', 'topic']  # one proposal per topic per day
```

**Migration**: `python manage.py makemigrations daily_ca`

### F2 — generate_ca_proposals Command
**File**: `backend/engines/daily_ca/management/commands/generate_ca_proposals.py`

```
Usage: python manage.py generate_ca_proposals --date today

Process:
  1. Fetch all CAArticle WHERE published_at >= yesterday AND processing_status='completed'
  2. Apply RelevanceScorerService → filter score >= 5.0
  3. Group by knowledge_topic (via ca_topic_link) → deduplicate
     (3 sources on same topic = 1 proposal, not 3 proposals)
  4. For each unique topic (top 30 max):
     a. Collect top 3 ca_chunks by relevance_score
     b. 1 GROQ call (lightweight):
        "Given this news context, write:
         1. A sharp 10-15 word article title
         2. A 3-sentence description of why this is in news today
         3. Which GS paper: GS1/GS2/GS3/GS4
         Return JSON only."
     c. Save CaDailyProposal (status='pending')
  5. Log: "X proposals created for date Y"
  6. Rate limit: 12s sleep between calls
  7. Session cap: max 30 GROQ calls (safeguard — proposals are cheap)
```

**Phase F success criteria**:
- ✅ `python manage.py generate_ca_proposals --date today` — 30 proposals created locally
- ✅ `python manage.py generate_ca_proposals --database=supabase` — 30 proposals on Supabase
- ✅ Proposals visible in Django admin with correct status='pending'
- ✅ No duplicate proposals per topic per date (unique_together enforced)
- ✅ GROQ session cap (30 calls) respected — key rotation working (key_idx alternating)
- ✅ RelevanceScorerService fixed: CATopicLink used as primary signal (embedding threshold was too high)

---

## ✅ PHASE G — Static Background Check Service
**Depends on**: Phase F complete
**File**: `backend/engines/daily_ca/services/static_background_service.py`

### Architecture: CA-First, Static-Background Pattern

CA article generation must be FAST (10 articles in one session). Static BookContent generation is
SLOW (~3-4 GROQ calls per topic). These two must NEVER run sequentially inside the same cycle.

**The pattern:**
1. CA cycles run first — each cycle checks if static exists, uses it if available, skips if not
2. After ALL CA cycles finish → fire background static generation for topics that had no static
3. Next day's CA articles will have static available for these topics

This means:
- Day 1: Nuclear Energy → no static → CA article generated with wiki only → static triggered in background
- Day 2: Any new Nuclear Energy CA article → static now exists → used as factual anchor

### Two Methods in StaticBackgroundService:

**Method 1 — `get_background_facts()` — called INSIDE each CA generation cycle:**
```python
class StaticBackgroundService:

    @staticmethod
    def get_background_facts(topic_id: UUID) -> dict | None:
        """
        Checks if published static content exists for a topic.
        Returns structured facts INSTANTLY — NEVER blocks, NEVER generates, NEVER waits.

        Case A: GET /api/v1/book-content/?topic_id={topic_id}&is_published=true
                → 200 with data → extract key facts via regex → return dict
                → dict = {title, key_provisions: list[str], key_facts: list[str], book_content_id: UUID}
                → Extraction: pure Python regex — 0 GROQ calls

        Case B: GET returns 404 or empty (no published static exists)
                → Return None IMMEDIATELY
                → Caller records topic_id in pending_static_generation list

        Case C: GET returns data but is_published=False
                → Return None IMMEDIATELY
                → Do not use incomplete/unpublished content as anchor

        NEVER triggers generation. NEVER polls. NEVER sleeps.
        Zero Django ORM calls to book_content tables (all via internal API).
        """
```

**Method 2 — `trigger_pending_static_generation()` — called AFTER all CA cycles finish:**
```python
    @staticmethod
    def trigger_pending_static_generation(topic_ids: list[UUID]) -> int:
        """
        Fires background static generation for topics that had no published static.
        Called ONCE after all CA cycles complete — NOT inside individual cycles.

        For each topic_id:
          → POST /api/v1/book/internal/generate/{topic_id}/
          → 202 Accepted: book_content engine starts generating in background thread
          → Does NOT wait for completion (fire-and-forget)
          → 12s sleep between each POST to respect book_content's GROQ rate limits

        Returns: count of successfully triggered topics.

        NOTE: This endpoint must be created in book_content engine (Phase G Step 1 below).
        NOTE: is_published=True on static content = "locked and ready to use".
              The book_content generation pipeline sets is_published=True when done.
        """
```

### Pre-requisite: Internal Generate Endpoint in book_content Engine
**BEFORE implementing StaticBackgroundService, create this endpoint:**
**File**: `backend/engines/book_content/views.py` — add InternalGenerateView
```
POST /api/v1/book/internal/generate/{topic_id}/
  → Accepts: topic_id (UUID) in URL
  → Auth: internal service call only (RBAC: service_internal role or no-auth for localhost)
  → Response: 202 Accepted + {"status": "triggered", "topic_id": "..."}
  → Action: Calls ingest_topic(topic_id) in a background thread (threading.Thread)
  → Non-blocking: returns 202 immediately, generation runs in background
  → If topic already has is_published=True: return 200 {"status": "already_exists"}
  → If topic not found: return 404
```

### Factual Anchor Extraction (Case A — regex, 0 GROQ calls):
```python
def _extract_facts_from_content(content_markdown: str, book_content_id: UUID) -> dict:
    """
    Extracts bullet facts from published BookContent markdown.
    Pure regex — zero GROQ calls, instant.
    Looks for: dates (2024, 1950, etc.), article numbers (Article 21, Article 370),
               statistics (percentages, amounts), numbered provisions.
    """
```

**Phase G implementation order (strictly one at a time)**:
1. `book_content/views.py` → add InternalGenerateView + URL in book_content/urls.py
2. `daily_ca/services/static_background_service.py` → both methods

**Phase G success criteria**:
- `get_background_facts(topic_id)` returns structured dict for a topic that has published static
- `get_background_facts(topic_id)` returns None INSTANTLY for a topic with no static (no wait, no sleep)
- `trigger_pending_static_generation([topic_id])` calls POST endpoint and returns 1
- POST /api/v1/book/internal/generate/{topic_id}/ returns 202 and triggers background generation
- Zero Django ORM calls to book_content tables inside StaticBackgroundService (all via API)

---

## ✅ PHASE H — Wiki Enrichment Wrapper
**Depends on**: Phase G complete
**File**: `backend/engines/daily_ca/services/wiki_enrichment_service.py`

Thin wrapper around existing `engines/book_content/services/wiki_service.py`.
No changes to wiki_service.py itself.

```python
class WikiEnrichmentService:
    @staticmethod
    def get_enrichment(topic_name: str) -> dict:
        """
        Returns supplementary facts for thin CA source articles (< 300 words).
        Uses Wikipedia API — zero GROQ calls.

        Returns:
          {
            'intro': str,          # Wikipedia intro paragraph
            'key_facts': list,     # Bullet facts extracted from infobox
            'related_terms': list  # Related Wikipedia page titles
          }
        OR empty dict if Wikipedia page not found.
        """
        # Calls wiki_service.search(topic_name) — existing, unchanged
        # Extracts intro + infobox data
        # Returns structured dict (NOT raw wiki text)
```

**When used**: Only when ca_chunk total text < 300 words.
**NOT used**: When ca_chunks are already substantial (300+ words).

**Phase H success criteria**:
- Returns structured dict for "Fast Breeder Reactor"
- Returns empty dict gracefully if Wikipedia page not found
- wiki_service.py file is untouched

---

## ✅ PHASE I — CA_DAILY_PROMPT Builder
**Depends on**: Phase H complete
**File**: `backend/engines/daily_ca/services/prompt_builder.py`

### Subject Tone Map (Daily CA version — independent of book_content's copy):
```python
SUBJECT_TONE_MAP = {
    "Indian Polity & Constitution": "constitutional, legal, institutional tone — reference specific Articles, Acts, landmark judgements where relevant",
    "Indian Economy": "analytical, data-driven tone — include statistics, policy implications, trade/fiscal figures",
    "Environment & Ecology": "scientific, conservation-oriented tone — reference international frameworks, India's targets, biodiversity data",
    "International Relations": "diplomatic, strategic tone — reference bilateral frameworks, India's stated positions, multilateral forums",
    "Science & Technology": "technical but accessible tone — explain concepts clearly, highlight India's achievements and gaps",
    "Indian Society": "sociological, ground-level tone — focus on vulnerable groups, data-backed, constitutional provisions on equality",
    "Indian Heritage & Culture": "cultural, art-historical tone — reference dynasties, movements, specific artefacts, UNESCO designations",
    "Modern Indian History": "narrative-historical tone — specific dates, leaders, cause-effect chains, colonial-nationalist framing",
    "World History": "global-comparative tone — relate international events to India's contemporary context where applicable",
    "Governance & Social Justice": "policy-implementation tone — scheme details, RTI/DPSP framing, gaps between intent and ground reality",
    "Disaster Management": "preparedness-focused tone — reference NDMA mandate, Sendai Framework, India's DRR progress",
    "Internal Security": "factual, neutral tone — legal framework, threat classification, avoid sensationalism",
    "Ethics, Integrity & Aptitude": "philosophical-reflective tone — values-based, dilemma-aware, case-scenario framing",
    "default": "factual, analytical, accessible to a general educated reader",
}
```

### Critical distinction embedded in the prompt:
- `[[double brackets]]` = high-value conceptual term → becomes Concept Page link → `/concepts/slug`
- `TAGS:` line at end = discovery keyword labels → becomes Keyword Tags → `/tags/slug`
These are two completely different systems. The LLM must be instructed clearly on both.

### CA_DAILY_PROMPT Template:
```
SYSTEM:
You are a senior editorial writer for a premier knowledge platform read by
curious citizens, students, researchers and civil service aspirants.
Write content that is informative, factual and genuinely valuable to ALL readers —
not exclusively for exam preparation.

SUBJECT: {subject_name}
TONE GUIDE: {subject_tone}

TODAY'S NEWS CONTEXT:
{ca_chunks_text}

FACTUAL ANCHOR (verified facts about this topic — use only for accuracy, do NOT copy prose):
{static_key_facts}

SUPPLEMENTARY REFERENCE:
{wiki_enrichment}

WRITING INSTRUCTIONS:
1. Title: Sharp, newsworthy, 10-15 words. Reflects today's specific development.
2. Opening: 1-2 sentences — what happened today and why it matters.
3. Sections: Decide headings based on what THIS SPECIFIC TOPIC requires.
   Good section heading examples (choose what fits, do not use all):
   - "What is [X]?" for concepts unfamiliar to general readers
   - "India's Current Status" for ongoing situations
   - "Key Provisions / Legal Framework" for constitutional/legal topics
   - "Recent Development" for the specific news trigger
   - "Significance / Impact" for policy or economic topics
   - "Challenges" where genuinely relevant
   - "Way Forward" where meaningful
   FORBIDDEN section headings: "UPSC Angle", "Exam Relevance", "Prelims Focus",
   "Mains Value", "Practice Questions", "Important for UPSC"
4. INLINE CONCEPT LINKS — use [[double brackets]] for 5-8 HIGH-VALUE terms:
   These create dedicated concept explanation pages for specific, important terms.
   USE [[brackets]] for:
     - Specific Acts/laws: [[Civil Liability for Nuclear Damage Act]], [[Forest Rights Act 2006]]
     - Major schemes with specific mandates: [[PM-KUSUM]], [[Viksit Bharat 2047]]
     - Technical/scientific terms: [[Small Modular Reactors]], [[HALEU]], [[Thorium Cladding]]
     - Landmark constitutional events: [[101st Constitutional Amendment]]
     - Specific bodies with specific mandates: [[Nuclear Power Corporation of India]]
   DO NOT use [[brackets]] for:
     - Generic topic names like "federalism", "parliament", "judiciary" (those go in TAGS)
     - Terms already fully explained in this article
     - Every technical noun — only genuinely high-value terms
     - More than 8 terms total
5. Insert exactly 1 callout box mid-article:
   :::callout
   **Did You Know?** [One surprising, engaging fact about this topic.]
   :::
6. Length: 450–700 words. Quality over quantity. No padding.
7. End your response with these two lines:
   TAGS: [comma-separated 5-8 keywords — short, generic, UPSC-relevant labels]
   SOURCE: [source name] — [URL]
   Note: TAGS are discovery labels (e.g., "nuclear-energy, environment, science-tech").
         They are DIFFERENT from the [[inline brackets]] above.

DO NOT include:
- Any mention of "UPSC", "GS paper", "exam", "aspirants" inside the article body
- Practice questions or answer hints
- Generic lines like "This is important for UPSC Mains"
- More than ## level headings (no ### sub-sub-sections)
- More than 700 words
```

### Prompt Builder Function:
```python
def build_ca_prompt(ca_chunks_text, static_key_facts, wiki_enrichment,
                    subject_name, topic_name) -> str:
    tone = SUBJECT_TONE_MAP.get(subject_name, SUBJECT_TONE_MAP["default"])
    return CA_DAILY_PROMPT_TEMPLATE.format(
        subject_name=subject_name,
        subject_tone=tone,
        ca_chunks_text=ca_chunks_text[:2000],   # hard cap on input tokens
        static_key_facts=static_key_facts or "Not available.",
        wiki_enrichment=wiki_enrichment or "Not available.",
    )
```

**Phase I success criteria**:
- `build_ca_prompt()` returns correctly formatted prompt string for each of the 14 subjects
- Subject tone correctly injected for all subjects
- Fallback "default" tone used when subject_name is unrecognised
- Input text hard-capped at 2000 chars to prevent token overflow

---

## ✅ PHASE J — Daily CA Generator Service + DailyCaArticle Model
**Depends on**: Phases G, H, I complete

### J1 — DailyCaArticle Model
**File**: `backend/engines/daily_ca/models.py` — add to existing file

```python
class DailyCaArticle(models.Model):
    id                   = UUIDField(primary_key=True, default=uuid4, editable=False)
    title                = CharField(max_length=500)
    slug                 = SlugField(max_length=550, unique=True)
    topic                = ForeignKey('knowledge.Topic', null=True, blank=True,
                                      on_delete=SET_NULL, related_name='daily_ca_articles')
    subject_name         = CharField(max_length=200)
    gs_paper             = CharField(max_length=10, blank=True)
    published_date       = DateField(db_index=True)
    body_md              = TextField()      # raw markdown with [[terms]] (for audit)
    body_md_processed    = TextField()      # markdown with [[terms]] → /concepts/ links
    news_context         = TextField()      # 3-line summary: what triggered this article
    sources_used         = JSONField(default=list)   # [{name, url, title}]
    static_background    = ForeignKey('book_content.BookContent', null=True, blank=True,
                                       on_delete=SET_NULL, related_name='ca_articles')
    hero_image_url       = CharField(max_length=1000, blank=True, default='')
    ca_chunk_ids         = JSONField(default=list)   # audit trail of source chunks
    quality_score        = FloatField(default=0.0)
    is_published         = BooleanField(default=False, db_index=True)
    generation_metadata  = JSONField(default=dict)   # groq_model, word_count, subject etc.
    order_on_date        = PositiveSmallIntegerField(default=0)   # 1-10 per day
    created_at           = DateTimeField(auto_now_add=True)
    updated_at           = DateTimeField(auto_now=True)

    class Meta:
        db_table = 'daily_ca_article'
        ordering = ['published_date', 'order_on_date']
        indexes = [Index(fields=['-published_date']),
                   Index(fields=['published_date', 'is_published']),
                   Index(fields=['slug'])]
```

### J2 — DailyCaStaticLink Model
```python
class DailyCaStaticLink(models.Model):
    id             = UUIDField(primary_key=True, default=uuid4, editable=False)
    daily_article  = ForeignKey(DailyCaArticle, on_delete=CASCADE,
                                related_name='static_links')
    book_content   = ForeignKey('book_content.BookContent', on_delete=CASCADE,
                                related_name='ca_links')
    link_reason    = CharField(max_length=50, choices=[
                        ('same_topic', 'Same Topic'),
                        ('background', 'Background Context'),
                        ('related_concept', 'Related Concept'),
                    ], default='same_topic')
    created_at     = DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'daily_ca_static_link'
        unique_together = ['daily_article', 'book_content']
```

**Migration**: `python manage.py makemigrations daily_ca`

### J3 — DailyCaGeneratorService (Cycle-Based Orchestrator)
**File**: `backend/engines/daily_ca/services/generator_service.py`

**Architecture: CA-First, Static-Background**
- `_run_single_cycle()` handles CA generation ONLY — no static generation inside cycles
- `run_generation_cycle()` collects topic_ids that had no static, triggers static AFTER all cycles

```python
class DailyCaGeneratorService:
    MAX_WORDS = 750
    MAX_GROQ_CALLS = 25  # session safety cap across all cycles

    @classmethod
    def run_generation_cycle(cls, proposals: list, groq_calls_used: int = 0) -> dict:
        """
        Main entry point. Processes each approved proposal as one complete atomic cycle.
        Stops gracefully when session cap is reached.
        Failed cycles do not stop the run — marked 'failed' and skipped.

        AFTER all cycles: triggers background static generation for topics without static.

        Returns summary: {generated, failed, capped, static_triggered, total}
        """
        results = {'generated': 0, 'failed': 0, 'capped': 0, 'static_triggered': 0,
                   'total': len(proposals)}
        pending_static_topic_ids = []  # topics that had no static — trigger after all cycles

        for i, proposal in enumerate(proposals, 1):
            logger.info("starting_cycle", cycle=i, total=len(proposals),
                        title=proposal.title, groq_calls_so_far=groq_calls_used)

            # Pre-check session cap before starting new cycle
            if groq_calls_used >= cls.MAX_GROQ_CALLS:
                logger.warning("session_cap_reached_pre_cycle", cap=cls.MAX_GROQ_CALLS,
                               at_cycle=i, remaining=len(proposals) - i + 1)
                for p in proposals[i - 1:]:
                    p.status = 'queued_next_run'
                    p.save(update_fields=['status'])
                results['capped'] = len(proposals) - i + 1
                break

            try:
                article, calls_this_cycle, needs_static = cls._run_single_cycle(proposal)
                groq_calls_used += calls_this_cycle
                results['generated'] += 1
                if needs_static and proposal.topic_id:
                    pending_static_topic_ids.append(proposal.topic_id)
                logger.info("cycle_complete", cycle=i, article_id=str(article.id),
                            title=article.title, groq_calls_total=groq_calls_used,
                            needs_static=needs_static)

            except Exception as e:
                logger.error("cycle_failed", cycle=i, proposal_id=str(proposal.id),
                             error=str(e), exc_info=True)
                proposal.status = 'failed'
                proposal.save(update_fields=['status'])
                results['failed'] += 1
                # DO NOT break — a failed cycle is not catastrophic — continue to next

        # POST-CYCLE: Trigger background static generation for topics without static
        if pending_static_topic_ids:
            triggered = StaticBackgroundService.trigger_pending_static_generation(
                pending_static_topic_ids
            )
            results['static_triggered'] = triggered
            logger.info("post_cycle_static_triggered", topic_count=triggered,
                        topic_ids=[str(t) for t in pending_static_topic_ids])

        logger.info("generation_run_complete", **results)
        return results

    @classmethod
    def _run_single_cycle(cls, proposal) -> tuple:
        """
        One complete, atomic CA article generation cycle for a single proposal.
        ONLY generates the CA article — does NOT generate static content.

        Returns: (DailyCaArticle, int groq_calls_used_this_cycle, bool needs_static)
          - needs_static=True means no published static existed for this topic
          - Caller collects these topic_ids and triggers static AFTER all cycles complete
        """
        calls_used = 0
        needs_static = False

        with transaction.atomic():
            # STEP 1: Static background facts (instant check — no blocking, no generation)
            static_facts = StaticBackgroundService.get_background_facts(proposal.topic_id)
            book_content_id = static_facts.get('book_content_id') if static_facts else None
            if static_facts is None:
                needs_static = True  # No published static exists — flag for post-cycle trigger

            # STEP 2: Wiki enrichment (conditional — 0 GROQ calls)
            ca_text = cls._fetch_ca_chunks_text(proposal.ca_chunk_ids)
            wiki_data = {}
            if len(ca_text.split()) < 300:
                wiki_data = WikiEnrichmentService.get_enrichment(
                    proposal.topic.name if proposal.topic else proposal.title
                )

            # STEP 3: Build and send prompt (1 GROQ call)
            prompt = build_ca_prompt(
                ca_chunks_text=ca_text,
                static_key_facts=cls._format_static_facts(static_facts),
                wiki_enrichment=cls._format_wiki(wiki_data),
                subject_name=proposal.subject_name,
                topic_name=proposal.topic.name if proposal.topic else '',
            )
            raw_response = llm_service.generate(prompt)
            calls_used += 1
            time.sleep(12)  # GROQ rate limit

            # STEP 4: Parse LLM response
            title, body_md, tags_raw, source_attr = cls._parse_response(raw_response)

            # STEP 5: Word count enforcement
            word_count = len(body_md.split())
            if word_count > cls.MAX_WORDS:
                body_md = ' '.join(body_md.split()[:cls.MAX_WORDS])
                word_count = cls.MAX_WORDS

            # STEP 6: Save article (need article.id before linking)
            slug = cls._generate_slug(title, proposal.date)
            hero_url = cls._fetch_hero_image(proposal)
            article = DailyCaArticle.objects.create(
                title=title, slug=slug,
                topic=proposal.topic,
                subject_name=proposal.subject_name,
                gs_paper=proposal.gs_paper,
                published_date=proposal.date,
                body_md=body_md,
                body_md_processed='',  # filled in step 7
                news_context=proposal.description,
                sources_used=proposal.source_urls,
                static_background_id=book_content_id,  # None if no static yet
                hero_image_url=hero_url,
                ca_chunk_ids=proposal.ca_chunk_ids,
                quality_score=cls._score_quality(body_md),
                is_published=False,
                generation_metadata={
                    'groq_model': 'llama-3.3-70b-versatile',
                    'word_count': word_count,
                    'subject': proposal.subject_name,
                    'had_static_anchor': static_facts is not None,
                },
            )

            # STEP 7: Concept Page resolution — [[term]] → /concepts/slug
            body_md_processed = ConceptPageResolver.process_and_replace(body_md, article.id)
            calls_used += ConceptPageResolver.last_new_concept_calls  # new concept stubs
            article.body_md_processed = body_md_processed
            article.save(update_fields=['body_md_processed'])

            # STEP 8: Keyword tag processing — TAGS: line → ArticleTag records (1 GROQ call)
            TagService.extract_and_link_tags(
                article_text=body_md,
                content_type='daily_ca',
                object_id=article.id,
                overrides=tags_raw,
            )
            calls_used += 1
            time.sleep(12)

            # STEP 9: Static link (only if static already existed — Case A)
            if book_content_id:
                DailyCaStaticLink.objects.create(
                    daily_article=article,
                    book_content_id=book_content_id,
                    link_reason='same_topic',
                )

            # STEP 10: Update proposal status
            proposal.status = 'generated'
            proposal.generated_article = article
            proposal.save(update_fields=['status', 'generated_article'])

            return article, calls_used, needs_static
```

**Phase J success criteria**:
- `_run_single_cycle(proposal)` generates a complete DailyCaArticle for one test proposal
- `_run_single_cycle()` returns `(article, calls, needs_static=True)` when no static exists
- `run_generation_cycle()` calls `trigger_pending_static_generation()` after all cycles
- `body_md` contains raw [[terms]], `body_md_processed` has /concepts/ links
- Keyword tags (from TAGS: line) saved as ArticleTag records
- Concept page stubs created for [[terms]] not found in ConceptPage table
- Word count enforced (≤750)
- transaction.atomic() verified: if tag saving fails, article is also rolled back
- No blocking/polling inside any cycle — each cycle completes in ~15-20 seconds

---

## ✅ PHASE K — Management Commands
**Depends on**: Phase J complete

### K1 — generate_daily_ca Command
**File**: `backend/engines/daily_ca/management/commands/generate_daily_ca.py`

```
Usage:
  python manage.py generate_daily_ca --date 2026-04-08
  python manage.py generate_daily_ca --date 2026-04-08 --database=supabase

Process:
  1. Fetch all CaDailyProposal WHERE date=X AND status='approved'
     (also picks up status='queued_next_run' from previous day's capped run)
  2. Order by relevance_score DESC
  3. Call DailyCaGeneratorService.run_generation_cycle(proposals)
  4. Print live progress per cycle:
     "Cycle 1/10 starting: [title]..."
     "Cycle 1/10 DONE: [title] | Word count: 542 | GROQ calls used: 3/25 | static: YES"
     "Cycle 2/10 starting: [title]..."
     "Cycle 3/10 FAILED: [error summary] — continuing..."
  5. On session cap:
     "Session cap reached at cycle 7/10. Remaining 3 marked as queued_next_run."
     "Run again tomorrow to complete generation."
  6. After all cycles — static background trigger (automatic, no user action needed):
     "Triggering background static generation for 4 topics without static content..."
     "→ Triggered: Nuclear Energy, Fiscal Federalism, Forest Rights Act, ISRO Missions"
     "→ Static will be ready for tomorrow's CA generation."
  7. Final summary:
     "Generation complete: 7 generated | 1 failed | 2 queued | GROQ calls: 23/25"
     "Background static triggered for: 4 topics"
  8. Does NOT auto-publish — admin reviews before publishing

Notes:
  - Re-running next day picks up status='queued_next_run' proposals automatically
  - Re-running with same date skips already 'generated' proposals
  - Static background trigger is automatic — no separate command needed
  - Static content generates in background (book_content engine) while admin reviews CA articles
```

### K2 — cleanup_raw_ca Command
**File**: `backend/engines/daily_ca/management/commands/cleanup_raw_ca.py`

```
Usage:
  python manage.py cleanup_raw_ca --months-old 1 --confirm

Process:
  → Deletes: ca_article, ca_chunk, ca_topic_link older than N months
  → KEEPS FOREVER: DailyCaArticle, Tag, ArticleTag, ConceptPage,
                   ConceptArticleLink, DailyCaStaticLink
  → Prints: rows deleted per table, estimated space freed
  → Requires --confirm flag to execute (without it: dry-run only)
```

**Phase K success criteria**:
- `generate_daily_ca --date today` processes all approved proposals with live progress output
- Re-running skips already 'generated' proposals (also picks up queued_next_run)
- After all cycles, command prints "Triggering background static for N topics" automatically
- Static generation POST call fires for each topic_id that had no published static
- `cleanup_raw_ca --months-old 1` (no --confirm) runs dry-run only, prints what would be deleted
- `cleanup_raw_ca --months-old 1 --confirm` deletes correct rows, keeps permanent assets

---

## ✅ PHASE L — DRF Serializers + API Views + URLs
**Depends on**: Phase K complete

### L1 — Tags Engine API
**File**: `backend/engines/tags/serializers.py`
```python
TagSerializer: id, name, slug, description, tag_type, usage_count
TagDetailSerializer: all fields + list of recent article titles using this tag

ConceptPageSerializer: id, name, slug, brief_description, is_content_ready, usage_count
ConceptPageDetailSerializer: all fields + body_md (if is_content_ready=True)
                              + list of CA article titles that link to this concept
```

**File**: `backend/engines/tags/views.py`
```python
# Keyword Tags
GET /api/v1/tags/                          → list all tags (paginated, filterable by type)
GET /api/v1/tags/{slug}/                   → tag detail + recent articles
GET /api/v1/tags/{slug}/articles/          → all DailyCaArticles for this tag (paginated)

# Concept Pages
GET /api/v1/concepts/                      → list all concept pages (paginated, filter by is_content_ready)
GET /api/v1/concepts/{slug}/               → concept detail (brief + body if ready + linked articles)
```

### L2 — Daily CA Public API
**File**: `backend/engines/daily_ca/serializers.py`
```python
DailyCaArticleListSerializer:  id, slug, title, subject_name, gs_paper,
                                published_date, news_context, hero_image_url,
                                tags (nested TagSerializer list), order_on_date

DailyCaArticleDetailSerializer: all fields + body_md_processed + static_background
                                  (nested) + related_articles (5 items)
                                  + concept_links (nested ConceptPageSerializer list)

DailyCaProposalSerializer: id, title, description, topic_name, gs_paper,
                            relevance_score, source_count, status
```

**File**: `backend/engines/daily_ca/views.py`
```python
GET /api/v1/daily-ca/today/                → today's published articles (Redis-cached)
GET /api/v1/daily-ca/{date}/               → articles for specific date (YYYY-MM-DD)
GET /api/v1/daily-ca/article/{slug}/       → full article detail + related + concept links
GET /api/v1/daily-ca/archive/              → last 30 days, date-grouped summary
```

### L3 — Admin API (no auth — solo developer, direct access from frontend UI)
```python
GET  /api/v1/admin/daily-ca/proposals/{date}/     → list proposals for review
POST /api/v1/admin/daily-ca/proposals/approve/    → approve selected IDs
                                                     body: {proposal_ids: [uuid, ...]}
                                                     validates: max 10 proposals
GET  /api/v1/admin/daily-ca/generate/status/      → cycle-by-cycle generation progress
POST /api/v1/admin/daily-ca/publish/{date}/       → set all generated articles is_published=True
GET  /api/v1/admin/daily-ca/articles/{date}/      → list generated (unpublished) articles for review
```

**Phase L success criteria**:
- All public endpoints return correct data with proper serialization
- `/api/v1/daily-ca/today/` returns cached response on second call
- `/api/v1/concepts/{slug}/` returns brief_description when is_content_ready=False

---

## ✅ PHASE M — Tests
**Depends on**: Phase L complete

### M1 — Tags Engine Tests
**File**: `backend/engines/tags/tests/test_models.py`
- Tag creation with all 10 tag_types
- Slug auto-generation from name
- usage_count increment
- Unique constraint on name
- ConceptPage creation with is_content_ready=False
- ConceptArticleLink unique constraint

**File**: `backend/engines/tags/tests/test_services.py`
- `TagService.extract_and_link_tags()` with mocked GROQ
- Max 8 keyword tags enforced (test with 12 suggested)
- Fuzzy match reuses existing tag (test with near-duplicate input)
- `ConceptPageResolver.process_and_replace()` with known [[term]] inputs
- Fuzzy match prevents duplicate concept pages (CLNDA vs "Civil Liability Act")
- Max 8 concept links enforced (test with 12 [[terms]] in body_md)
- New concept page stub created when no match found

### M2 — Daily CA Engine Tests
**File**: `backend/engines/daily_ca/tests/test_models.py`
- CaDailyProposal status transitions (pending → approved → generated)
- CaDailyProposal queued_next_run status
- DailyCaArticle creation with all fields
- DailyCaStaticLink unique constraint

**File**: `backend/engines/daily_ca/tests/test_services.py`
- `StaticBackgroundService.get_background_facts()` — Case A returns dict, Case B returns None instantly, Case C returns None instantly (all 3 cases mocked)
- `StaticBackgroundService.trigger_pending_static_generation([topic_id])` calls POST endpoint
- `WikiEnrichmentService.get_enrichment()` with mocked wiki_service
- `build_ca_prompt()` output contains correct subject tone for each of 14 subjects
- `_run_single_cycle()` returns `needs_static=True` when no published static exists
- `_run_single_cycle()` with fully mocked GROQ (no real API calls)
- `run_generation_cycle()` calls `trigger_pending_static_generation()` after all cycles complete
- Word count enforcement (>750 words gets truncated)
- GROQ session cap: cycle N+1 not started when cap reached at cycle N
- Failed cycle: marks proposal 'failed', continues to next proposal
- `body_md` contains raw [[terms]], `body_md_processed` contains /concepts/ links

**File**: `backend/engines/daily_ca/tests/test_views.py`
- `/api/v1/daily-ca/today/` returns 200 with articles
- `/api/v1/daily-ca/article/{slug}/` returns full detail with concept_links
- Admin approval endpoint validates max 10 proposals
- Admin endpoints return 403 for non-admin users
- Generation progress endpoint reflects cycle-by-cycle status

**Phase M success criteria**:
- `pytest engines/daily_ca/ engines/tags/ -v` all pass
- Zero real GROQ API calls in test suite (all mocked)
- Coverage > 80% on all service files

---

## ✅ PHASE N — Frontend: Admin Proposal Approval + Review Pages
**Depends on**: Phase L + M complete

### N1 — Proposal Approval Page
**Route**: `/admin/daily-ca/proposals/` (admin only)

```
Page Layout:
  Header: "Daily CA Proposals — [Date]"
  Date selector: navigate between dates

  Proposal Cards Grid (2-3 columns):
    Each card:
      - Numbered badge
      - GS Paper badge (GS2, GS3 etc.) — colour-coded
      - Subject tag chip
      - Title (bold, 2 lines max)
      - Description (3 lines, grey text)
      - Relevance score bar (visual)
      - Source count badge ("3 sources")
      - Checkbox (top-right of card)

  Selection counter: "8/10 selected" — live update
  When 10 selected: all unchecked cards grey out + checkbox disabled
  When < 10: "Select 2 more"

  Bottom action bar (sticky):
    "Approve & Generate Selected (10)" button — disabled until exactly 10 checked
    On click: POST to admin approve API → opens Generation Progress Modal

  Generation Progress Modal:
    "Generating articles... 3/10 complete"
    Per-cycle status: pending / generating / done / failed / capped
    When all done/capped: "Review & Publish" button → navigates to review page
```

### N2 — Article Review + Publish Page
**Route**: `/admin/daily-ca/review/[date]/`

```
Lists all generated (unpublished) articles for the date:
  Each row: title, word count, quality score, tags count, concept links count
  "Preview" → opens article in read-only preview modal
  "Publish All" → POST /api/v1/admin/daily-ca/publish/{date}/ → all become is_published=True
```

**Files**:
- `frontend/src/app/admin/daily-ca/proposals/page.tsx`
- `frontend/src/app/admin/daily-ca/review/[date]/page.tsx`
- `frontend/src/components/admin/proposal-card.tsx`
- `frontend/src/components/admin/generation-progress-modal.tsx`
- `frontend/src/lib/api/daily-ca-admin.ts`

**Phase N success criteria**:
- Admin can see proposal cards, select 10, trigger generation
- Progress modal shows per-cycle status live
- Review page lists generated articles with quality metadata
- "Publish All" makes articles live
- Non-admin users redirected

---

## ✅ PHASE O — Frontend: /daily-ca/ Main Feed Page
**Depends on**: Phase N complete (can test with seeded data)
**Route**: `/daily-ca/`

### Layout (VisionIAS-inspired, 3-column):
```
FULL PAGE:
┌────────────────────────────────────────────────────────────────────┐
│ [Eye/collapse icon — top right of content area]                     │
├──────────────┬──────────────────────────────┬──────────────────────┤
│  LEFT PANEL  │      MAIN CONTENT            │   RIGHT PANEL        │
│ (collapsible)│                              │ (article-level)      │
│              │  Article 1 ─────────────     │                      │
│ NEWS TODAY   │  [Title large bold]          │  RELATED ARTICLES    │
│ [logo area]  │  Posted: 08 Apr 2026 | 4min  │  (5 cards,           │
│              │  ┌────────────────────┐      │   same tags)         │
│ 📅 08 Apr 26 │  │ ℹ In Summary  ▼   │      │                      │
│ [Calendar]   │  └────────────────────┘      │  ──────────────      │
│              │  [Article body markdown]     │                      │
│ Table of     │  [:::callout Did You Know:::] │  EXPLORE SYLLABUS   │
│ Contents:    │  [Concept links in body]      │  (3 static cards)   │
│              │  [Tags: chip chip chip]      │                      │
│ 1. Article 1 │  [Sources ▼ accordion]       │  ──────────────      │
│ 2. Article 2 │  ← Prev | Next →             │                      │
│ ...          │                              │  CONCEPTS MENTIONED  │
│ 10. Article  │  Article 2 ─────────────     │  (concept page cards)│
│              │  ...                         │                      │
└──────────────┴──────────────────────────────┴──────────────────────┘
```

### Key Behaviours:
- **Left panel collapse**: Eye icon → hides left panel → main content full width
- **Date navigation**: Calendar → `/daily-ca/[date]/`
- **ToC navigation**: Click article in ToC → smooth scroll + blue dot highlight
- **In Summary box**: Collapsible (▼/▲) — 3 AI-generated bullet points
- **Keyword Tags**: Clickable chips → `/tags/[slug]/`
- **Inline Concept Links**: Already hyperlinked in body_md_processed → `/concepts/[slug]/`
- **Source attribution**: Collapsed accordion below tags
- **Right panel — "Concepts Mentioned"**: Shows ConceptPage cards linked from this article

### Markdown Rendering:
- Library: `react-markdown` + `remark-gfm`
- Custom renderer for `:::callout:::` → styled callout card component
- Inline concept links already in standard markdown format → renders as links
- Keyword tag chips rendered separately from body (not in markdown)

**Files**:
- `frontend/src/app/daily-ca/page.tsx`
- `frontend/src/app/daily-ca/[date]/page.tsx`
- `frontend/src/components/daily-ca/daily-ca-feed.tsx`
- `frontend/src/components/daily-ca/daily-ca-article.tsx`
- `frontend/src/components/daily-ca/in-summary-box.tsx`
- `frontend/src/components/daily-ca/callout-block.tsx`
- `frontend/src/components/daily-ca/tag-chips.tsx`
- `frontend/src/components/daily-ca/source-accordion.tsx`
- `frontend/src/components/daily-ca/concept-card.tsx`
- `frontend/src/components/daily-ca/left-panel.tsx`
- `frontend/src/components/daily-ca/right-panel.tsx`
- `frontend/src/lib/api/daily-ca.ts`

**Phase O success criteria**:
- `/daily-ca/` shows today's articles
- Left panel collapses, content expands
- Calendar navigates to correct date
- Tags are clickable chips linking to /tags/[slug]
- Inline concept links in body render as hyperlinks to /concepts/[slug]
- Callout blocks render as styled cards

---

## ✅ PHASE P — Frontend: Article Detail + Tag Pages + Concept Pages
**Depends on**: Phase O complete

### P1 — /daily-ca/article/[slug]/ (Full Article Reader)
Same layout as feed page but:
- Shows only 1 article (full width)
- Right panel always visible
- ToC shows article section headings (from ## headings)
- Share button (copy link)
- Bookmark button (future — userstate engine)

**Files**:
- `frontend/src/app/daily-ca/article/[slug]/page.tsx`
- Reuses all components from Phase O

### P2 — /tags/[slug]/ (Keyword Tag Page)
```
Layout:
  Header: "[Tag Name]" — large title
           Tag description (from Tag.description)
           Tag type badge (colour-coded by type)
           Usage count: "47 articles"

  Article Cards Grid (2 columns):
    Each card: Date | Subject | Title | 2-line description | Hero image | "Read →"

  Pagination (20 per page), Sort: newest first
```

**Files**:
- `frontend/src/app/tags/[slug]/page.tsx`
- `frontend/src/components/daily-ca/article-card.tsx`

### P3 — /concepts/[slug]/ (Concept Page)
```
Layout:
  Header: "[Concept Name]" — large title
           Brief description (always shown — generated at concept creation time)

  IF is_content_ready=False:
    → Banner: "Full article in progress. Check back soon."
    → Show: brief_description (2-3 lines) in a styled info card
    → Show: "Articles that reference this concept:" → list of CA article cards
    → No empty page — always has at minimum the brief description + linked articles

  IF is_content_ready=True:
    → Full body_md rendered (same as article reader)
    → "Articles that reference this concept:" section below

  Sidebar: usage_count, related concept pages (same articles), back link
```

**Files**:
- `frontend/src/app/concepts/[slug]/page.tsx`
- `frontend/src/components/concepts/concept-detail.tsx`
- `frontend/src/components/concepts/concept-stub-card.tsx`  (for is_content_ready=False state)

**Phase P success criteria**:
- `/daily-ca/article/[slug]` renders full article with concept links clickable
- `/tags/federalism` shows all articles tagged with "federalism"
- `/concepts/small-modular-reactors` shows brief description even when is_content_ready=False
- `/concepts/[slug]` shows full article when is_content_ready=True
- Concept pages list linked CA articles correctly

---

## ✅ PHASE Q — Frontend: Homepage DailyCaTeaser Widget
**Depends on**: Phase P complete
**File to modify**: `frontend/src/app/page.tsx`

### Widget Design:
```
Section heading: "Today's Current Affairs"
Subtitle: "10 articles | Updated daily"

Grid layout (responsive):
  Desktop: 5 columns × 2 rows = 10 mini-cards
  Tablet:  3 columns × 4 rows
  Mobile:  1 column × 10 cards (scrollable)

Each mini-card:
  - Number badge (1-10) — top left
  - Subject tag chip (GS2/Polity, GS3/Economy etc.) — colour-coded
  - Title (2 lines max, bold)
  - 1-line news context (grey, italic)
  - "2 min read" micro-badge

CTA row below grid:
  "Read All Today's Current Affairs →" (links to /daily-ca/)
```

**Phase Q success criteria**:
- Homepage shows DailyCaTeaser with 10 mini-cards
- Each card links to correct article slug
- "Read All" links to /daily-ca/
- Responsive on mobile/tablet/desktop
- No layout break with existing homepage sections

---

## ✅ PHASE R — Production Verification
**Depends on**: All phases A-Q complete and tested locally

### R1 — Local Verification Checklist
```
✅ python manage.py setup_ca_sources → all 4 sources present, existing unchanged
✅ python manage.py seed_tags → ~180 tags seeded without error
✅ python manage.py generate_ca_proposals --date today → 15-30 proposals created
✅ Admin proposal page shows cards correctly, 10-selection limit enforced
✅ Approve 10 → "Approve & Generate" → generation progress modal works
✅ generate_daily_ca runs cycle-by-cycle with live console output
✅ Failed cycle does NOT stop the run
✅ Session cap stops run gracefully, remaining marked 'queued_next_run'
✅ /daily-ca/ shows all 10 published articles
✅ Inline concept links in article body are clickable → /concepts/[slug]
✅ Concept pages show brief description when is_content_ready=False
✅ Keyword tag chips are clickable → /tags/[slug]
✅ Tag pages list correct articles
✅ Related articles sidebar shows relevant articles
✅ Explore Syllabus section shows static content links if static exists for topic
✅ Calendar navigation works, left panel collapse works
✅ Homepage DailyCaTeaser shows 10 mini-cards
✅ Mobile responsive layout verified
✅ Admin endpoints open (no auth — solo developer)
✅ Concept pages created organically — no duplicate concept pages (fuzzy match working)
```

### R2 — Git Tag
After all phases verified locally:
```powershell
git add .
git commit -m "Feature 2: Daily CA Pipeline + Tags + Concept Pages complete"
git tag -a v2.0.0-daily-ca -m "Daily CA pipeline, keyword tags, concept pages, human-approval workflow, cycle-based atomic generation"
git push origin main
git push origin v2.0.0-daily-ca
```

---

## UPDATED FUTURE FEATURES ROADMAP

All phases A–R of Feature 2 complete the Daily CA Pipeline.
The following are post-Feature-2 roadmap items.

| Feature | Category | Priority | Notes |
|---------|----------|----------|-------|
| Concept Page Content Generation | AI Content | HIGH | `generate_concept_content` management command. Generates full body_md for top N ConceptPages by usage_count. Sets is_content_ready=True. Same GROQ pipeline as static, but lighter (concepts are narrower scope). Run on-demand after Feature 2 stable. |
| Daily Quiz Engine | AI Feature | HIGH | 10 MCQs per day linked to daily CA articles. Uses existing assessment engine + daily_ca articles as source. `generate_daily_quiz` command. |
| Theme Series Engine | AI Content | HIGH | Episodic articles on running themes ("India's Water Crisis" — 5-episode series). Uses same daily_ca + tags infrastructure. New ThemeSeries + ThemeEpisode models. |
| Opinionated Articles | AI Content | HIGH | Admin-triggered opinion/editorial pieces. Different prompt: first-person expert voice. Separate OpinionArticle model. |
| RAG Chatbot ("Ask the Map") | AI Feature | HIGH | Query static book content via BookRetrievalService.get_rag_context(). Tags + concept pages provide richer retrieval context. Infrastructure ready. |
| CA ↔ Book Dynamic Linking UI | UX | HIGH | PARTIALLY BUILT in Feature 2 (DailyCaStaticLink + Explore Syllabus section). Full version: show CA articles panel inside book_content reader too. |
| Related Articles in Book Content Reader | UX | HIGH | PARTIALLY BUILT in Feature 2 (right panel pattern). Extend to /knowledge page article reader. |
| Mains Answer Evaluation | AI Feature | HIGH | Submit handwritten answer → AI scores on UPSC parameters. Separate evaluation engine needed. |
| Semantic Search Bar | Search | MEDIUM | Unified search: static + daily CA + tags + concepts. Input → embedding → hybrid_search. Tags + concept pages provide keyword index. |
| Concept Pages in Static Book Content | Content | MEDIUM | Extend inline [[term]] concept linking to static BookContent articles too (currently CA only). Requires post-processing static body_md. |
| Prelims Quiz from Book Content | AI Feature | MEDIUM | Auto-generate MCQs from BookContent. Assessment engine already built. Just needs trigger command. |
| Themes Clustering on /knowledge | Discovery | MEDIUM | Cluster book_content vectors by cosine similarity → auto-generate theme pages. Tags engine provides foundation. |
| Cloudinary Image Admin Upload | Admin | MEDIUM | Django Admin inline to upload hero images per daily CA article. |
| seed_syllabus.py Granularity Pass | Data | MEDIUM | Audit broad topics (Parliament, Economy, Environment) → split into focused sub-topics in seed_syllabus.py. Triggered by quality score analysis after 30 days of generation. |
| Bookmarks / Study Progress | UX | LOW | Save article read state per user. userstate engine models already exist. Frontend only. |
| Monthly CA Digest PDF | Content | LOW | Auto-generate monthly PDF compiling all Daily CA articles, organised by tag/subject. |
| Tag-based Unified Search Page | Search | LOW | /search?tag=federalism → shows static + CA + quiz + concepts all in one page with tabs. |
| Offline PWA Mode | Performance | LOW | Service worker caches last 20 read articles. After stable production only. |
