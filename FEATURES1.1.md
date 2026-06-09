# FEATURES.md — TheKnowledgeOrbits
## Book Content Engine: POC Integration Roadmap

**Purpose:** This file is the ONLY instruction source for Claude Code.
Work through PARTS in strict order. ONE task at a time.
Stop after each task and wait for human approval before proceeding.

---

## CRITICAL CONTEXT — READ BEFORE ANYTHING ELSE

### What This Feature Is
We are integrating a proven Proof-of-Concept (POC) content generation system
into the main Django project as a brand new engine: `engines/book_content/`.

The POC lives at: `upsc-agent-lab/` (root of this project).
It is VERIFIED, STABLE, and produces 86/100 quality UPSC study articles.
DO NOT rewrite its logic. PORT it with minimal Django adaptations.

### What This Feature Is NOT
- This is NOT a replacement for any existing feature.
- This is NOT connected to `article_article` table (that is a separate marketing tool).
- This is NOT connected to `assessment_*` tables (quiz system, untouched).
- This does NOT modify any existing engine.

### The Core Concept
The POC generates Laxmikanth-quality static UPSC book chapters using:
  - Wikipedia as the research source (no PDFs for now)
  - GROQ API (llama-3.3-70b-versatile) for generation
  - 3-Layer Quality Architecture:
      Layer 1 (Book Intelligence): TOC + concept registry per subject
      Layer 2 (Quality Engine): section-by-section generation + self-critique
      Layer 3 (Coherence Engine): cross-references + dedup across articles
  - Rate limit reality: ~20-22 articles/day on GROQ free tier (12s delay per call)
  - Smart resumption: crash-safe, picks up exactly where it stopped

### The DB Mapping (POC → Main Project)
  POC `nodes` (subject/module/topic/subtopic)
    → knowledge_subject, knowledge_module, knowledge_topic (EXISTING, reused as-is)

  POC `nodes.content_body` (the generated article markdown)
    → knowledge_book_content (NEW table — owns all book-quality article text)

  POC `book_plans` (TOC + concept registry)
    → knowledge_book_plan (NEW table)

  POC `cross_references` (article ↔ article links)
    → knowledge_cross_reference (NEW table)

  POC `edges` relation='related_to' (topic ↔ topic semantic links)
    → knowledge_topic_relation (NEW table)

  POC `ingestion_logs` (per-run tracking)
    → knowledge_generation_log (NEW table)

### POC Files to Reference (upsc-agent-lab/src/)
| POC File | Port Into |
|---|---|
| llm_client.py | engines/book_content/services/llm_service.py |
| wiki_fetcher.py | engines/book_content/services/wiki_service.py |
| classifier.py | engines/book_content/services/classifier_service.py |
| cross_subject_map.py | engines/book_content/services/cross_subject_map.py |
| subtopic_finder.py | engines/book_content/services/subtopic_service.py |
| book_planner.py | engines/book_content/services/book_planner_service.py |
| quality_engine.py | engines/book_content/services/quality_engine_service.py |
| coherence_engine.py | engines/book_content/services/coherence_service.py |
| ingestor.py | engines/book_content/services/ingestor_service.py |
| src/templates/index.html | frontend reference only (port to React component) |

### Porting Rules (MANDATORY)
When porting any POC file:
  PRESERVE EXACTLY:
    - All prompt strings (MASTER_STYLE_ANCHOR, SECTION_PLAN, subject personas)
    - All rate-limit values (INTER_CALL_SLEEP=12.0, RETRY_WAIT_TIMES=[15,30,45])
    - All algorithm logic (wiki section scoring, critique loop, coherence dedup)
    - All JSON parsing fallback logic
    - All LLM pool configuration (writer=16384 tokens, standard=2048, critique=2048)

  CHANGE ONLY:
    - Imports (from src.x → from engines.book_content.services.x)
    - DB access (psycopg2 direct → Django ORM via models)
    - Logging (log.info/warning → structlog logger.info/logger.warning)
    - Node integer IDs → UUID foreign keys to knowledge_topic
    - get_db_connection() → Django ORM QuerySets

---

## SYSTEM ARCHITECTURE — THE FULL LAYER MODEL

```
LAYER 0 — STRUCTURE (skeleton, existing, never touch)
  knowledge_program
  knowledge_subject      ← subject-level graph nodes
  knowledge_module       ← module-level graph nodes
  knowledge_topic        ← topic/subtopic/sub-subtopic nodes
                           (self-referencing via parent_topic_id)

LAYER 1 — BOOK CONTENT (flesh, NEW — this entire feature)
  knowledge_book_plan    ← AI-generated TOC + concept registry per subject
  knowledge_book_content ← generated markdown articles (one per topic node)
  knowledge_content_media← images/infographics placeholders (Cloudinary-ready)

LAYER 2 — CONNECTIONS (nervous system, NEW tables + existing)
  knowledge_topic_relation  ← NEW: topic ↔ topic semantic edges (graph)
  knowledge_cross_reference ← NEW: article ↔ article See Also links
  knowledge_chunk_topic_map ← EXISTING: chunk ↔ topic (untouched)
  ca_topic_link             ← EXISTING: CA event ↔ topic (untouched)

LAYER 3 — INTELLIGENCE (brain, NEW + existing)
  knowledge_book_plan    ← concept registry + prerequisite chains
  knowledge_generation_log ← NEW: per-run generation tracking
  content_embedding      ← EXISTING: pgvector (untouched)

LAYER 4 — EVENTS (living layer, existing, untouched)
  ca_article, ca_chunk   ← daily news (untouched)
  knowledge_theme        ← themes (untouched for now)

LAYER 5 — STUDENT INTERACTION (experience, existing, untouched)
  userstate_*, analytics_*, assessment_*
```

---

## PART 1 — DATABASE MIGRATION
**Goal:** Add all new tables and columns. Zero data loss. Zero existing table modification except additive columns.
**Constraint:** All changes are additive only. No DROP, no ALTER existing columns.

### Task 1.1 — Create new Django engine scaffold (empty)

Create the following empty files. Do not add any logic yet:

```
backend/engines/book_content/__init__.py
backend/engines/book_content/apps.py
backend/engines/book_content/models.py          ← will fill in Task 1.2
backend/engines/book_content/admin.py
backend/engines/book_content/urls.py
backend/engines/book_content/views.py
backend/engines/book_content/serializers.py
backend/engines/book_content/services/__init__.py
backend/engines/book_content/management/__init__.py
backend/engines/book_content/management/commands/__init__.py
backend/engines/book_content/migrations/__init__.py
backend/engines/book_content/migrations/0001_initial.py  ← will fill in Task 1.3
backend/engines/book_content/tests/__init__.py
backend/engines/book_content/tests/test_models.py
backend/engines/book_content/tests/test_services.py
```

apps.py content:
```python
from django.apps import AppConfig

class BookContentConfig(AppConfig):
    """Book Content Engine — static UPSC syllabus generation."""
    default_auto_field = "django.db.models.UUIDField"
    name = "engines.book_content"
    label = "book_content"
```

Register in core/settings/base.py under INSTALLED_APPS:
```python
"engines.book_content",
```

---

### Task 1.2 — Write models.py

File: `backend/engines/book_content/models.py`

Write ALL models below. Follow coding standards strictly:
- UUID PKs using `default=uuid.uuid4`
- `help_text` on every field
- `Meta.db_table`, `Meta.ordering`, `Meta.indexes` on every model
- structlog logger at top of file
- Full docstrings on every class

```python
import uuid
import structlog
from django.db import models

logger = structlog.get_logger(__name__)


class BookPlan(models.Model):
    """
    Layer 1: Book Intelligence Plan.
    One plan per subject. Generated ONCE before article generation begins.
    Stores the AI-generated Table of Contents, concept registry,
    prerequisite chains, and reading order for the entire subject.
    Equivalent to POC's book_plans table.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
        help_text="Unique identifier for this book plan.")
    subject = models.OneToOneField(
        "knowledge.Subject",
        on_delete=models.CASCADE,
        related_name="book_plan",
        help_text="The subject this book plan belongs to."
    )
    toc_json = models.JSONField(default=list,
        help_text="AI-generated complete Table of Contents. "
                  "Structure: [{module, order, topics: [{name, subtopics, prerequisites}]}]")
    concept_registry = models.JSONField(default=dict,
        help_text="Maps concept_name_lower → {topic_id (uuid), topic_label}. "
                  "Updated after each article is generated. Powers Layer 3 cross-references.")
    prerequisite_chains = models.JSONField(default=dict,
        help_text="Maps topic_name → [prerequisite topic names]. "
                  "Defines reading order for students.")
    reading_order = models.JSONField(default=list,
        help_text="Flat ordered list of topics for linear book-reading mode.")
    generation_status = models.CharField(max_length=20, default="planned",
        help_text="Status of content generation for this subject. "
                  "Values: planned | generating | partial | complete")
    topics_planned = models.IntegerField(default=0,
        help_text="Total number of topic nodes planned in this subject's TOC.")
    topics_completed = models.IntegerField(default=0,
        help_text="Number of topic nodes with generated book content.")
    avg_quality_score = models.FloatField(default=0.0,
        help_text="Rolling average quality score across all generated articles in this subject.")
    created_at = models.DateTimeField(auto_now_add=True,
        help_text="When this book plan was first created.")
    updated_at = models.DateTimeField(auto_now=True,
        help_text="Last time this book plan was updated.")

    class Meta:
        db_table = "knowledge_book_plan"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["generation_status"],
                name="book_plan_status_idx"),
        ]

    def __str__(self) -> str:
        return f"BookPlan: {self.subject.name} ({self.generation_status})"


class BookContent(models.Model):
    """
    Layer 1: Generated book-quality article for a single topic node.
    One record per knowledge_topic node that has been generated.
    Stores the full Markdown article produced by the 3-Layer Quality Engine.
    This is the CORE output of the entire POC integration.
    Equivalent to POC's nodes.content_body field (but separated cleanly).
    DO NOT confuse with article_article — that is a separate marketing tool.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
        help_text="Unique identifier for this book content entry.")
    topic = models.OneToOneField(
        "knowledge.Topic",
        on_delete=models.CASCADE,
        related_name="book_content",
        help_text="The knowledge topic node this content belongs to."
    )
    subject = models.ForeignKey(
        "knowledge.Subject",
        on_delete=models.CASCADE,
        related_name="book_contents",
        help_text="Denormalized subject FK for fast filtering without JOIN chain."
    )
    content_markdown = models.TextField(
        help_text="Full generated Markdown article. "
                  "Produced by Layer 2 Quality Engine (section-by-section generation).")
    formatted_content = models.TextField(blank=True, default="",
        help_text="Phase 4.5B output: content WITH tables + callouts injected. "
                  "Frontend renders this if available, falls back to content_markdown.")
    word_count = models.IntegerField(default=0,
        help_text="Word count of content_markdown. Computed on save.")
    quality_score = models.FloatField(default=0.0,
        help_text="Self-critique quality score (0-100) from Layer 2. "
                  "Articles below 65 are auto-refined before saving.")
    critique_log = models.TextField(blank=True, default="",
        help_text="Full JSON output of the self-critique pass. Audit trail.")
    generation_pass = models.IntegerField(default=1,
        help_text="How many refinement passes the article took. 1=first pass passed.")
    source_mode = models.CharField(max_length=30, default="wiki_only",
        help_text="Which sources were used. Values: wiki_only | ncert_wiki")
    has_tables = models.BooleanField(default=False,
        help_text="Whether this article contains generated comparison/summary tables.")
    has_media = models.BooleanField(default=False,
        help_text="Whether this article has image/infographic placeholders.")
    is_published = models.BooleanField(default=False,
        help_text="Whether this content is visible to students.")
    created_at = models.DateTimeField(auto_now_add=True,
        help_text="When this article was first generated.")
    updated_at = models.DateTimeField(auto_now=True,
        help_text="Last time this article was updated or refined.")

    class Meta:
        db_table = "knowledge_book_content"
        ordering = ["-quality_score", "-created_at"]
        indexes = [
            models.Index(fields=["subject", "is_published"],
                name="book_content_subject_pub_idx"),
            models.Index(fields=["quality_score"],
                name="book_content_quality_idx"),
            models.Index(fields=["topic"],
                name="book_content_topic_idx"),
            models.Index(fields=["source_mode"],
                name="book_content_source_idx"),
        ]

    def __str__(self) -> str:
        return f"BookContent: {self.topic.name} (score={self.quality_score:.0f})"

    def save(self, *args, **kwargs) -> None:
        """Auto-compute word count on save."""
        if self.content_markdown:
            self.word_count = len(self.content_markdown.split())
        super().save(*args, **kwargs)


class TopicRelation(models.Model):
    """
    Layer 2: Semantic relationship between two topic nodes.
    Powers the knowledge graph UI edges (related_to, cross_subject, prerequisite).
    Also powers the 'Related Topics' sidebar on article reader pages.
    Equivalent to POC's edges table WHERE relation='related_to'.
    The 'contains' hierarchy is already encoded in knowledge_topic.parent_topic_id FK.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
        help_text="Unique identifier for this topic relation.")
    source_topic = models.ForeignKey(
        "knowledge.Topic",
        on_delete=models.CASCADE,
        related_name="outgoing_relations",
        help_text="The source topic in this directional relationship."
    )
    target_topic = models.ForeignKey(
        "knowledge.Topic",
        on_delete=models.CASCADE,
        related_name="incoming_relations",
        help_text="The target topic this relation points to."
    )
    relation_type = models.CharField(max_length=30, default="related_to",
        help_text="Type of relationship. "
                  "Values: related_to | prerequisite | cross_subject | contrast | applies_to")
    similarity_score = models.FloatField(default=0.0,
        help_text="pgvector cosine similarity score (0.0-1.0). "
                  "Populated by cross-linker after embeddings exist.")
    is_auto_detected = models.BooleanField(default=True,
        help_text="True=auto-detected by similarity engine. False=manually added.")
    created_at = models.DateTimeField(auto_now_add=True,
        help_text="When this relation was created.")

    class Meta:
        db_table = "knowledge_topic_relation"
        unique_together = [("source_topic", "target_topic")]
        ordering = ["-similarity_score"]
        indexes = [
            models.Index(fields=["source_topic", "relation_type"],
                name="topic_rel_source_type_idx"),
            models.Index(fields=["target_topic"],
                name="topic_rel_target_idx"),
            models.Index(fields=["relation_type"],
                name="topic_rel_type_idx"),
            models.Index(
                fields=["relation_type"],
                name="topic_rel_cross_subject_idx",
                condition=models.Q(relation_type="cross_subject")
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source_topic.name} →[{self.relation_type}]→ {self.target_topic.name}"


class CrossReference(models.Model):
    """
    Layer 2: Article-to-article cross-reference link.
    Injected by Layer 3 Coherence Engine after article generation.
    Powers the 'See Also' section at the bottom of every book article.
    Also powers the 'Related Articles' sidebar in the frontend reader.
    Equivalent to POC's cross_references table.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
        help_text="Unique identifier for this cross-reference.")
    source_content = models.ForeignKey(
        BookContent,
        on_delete=models.CASCADE,
        related_name="outgoing_references",
        help_text="The article that contains the reference."
    )
    target_content = models.ForeignKey(
        BookContent,
        on_delete=models.CASCADE,
        related_name="incoming_references",
        help_text="The article being referenced."
    )
    ref_type = models.CharField(max_length=30, default="see_also",
        help_text="Type of reference. "
                  "Values: see_also | prerequisite | continuation | contrast")
    ref_text = models.CharField(max_length=300, blank=True, default="",
        help_text="The concept phrase in the source article that triggered this reference.")
    display_label = models.CharField(max_length=300, blank=True, default="",
        help_text="Human-readable link text shown to student. "
                  "Example: 'Anti-Defection Law → Tenth Schedule'")
    created_at = models.DateTimeField(auto_now_add=True,
        help_text="When this cross-reference was injected.")

    class Meta:
        db_table = "knowledge_cross_reference"
        unique_together = [("source_content", "target_content")]
        ordering = ["ref_type"]
        indexes = [
            models.Index(fields=["source_content"],
                name="crossref_source_idx"),
            models.Index(fields=["target_content"],
                name="crossref_target_idx"),
        ]

    def __str__(self) -> str:
        return f"CrossRef: {self.source_content.topic.name} → {self.target_content.topic.name}"


class ContentMedia(models.Model):
    """
    Layer 1: Media asset linked to a book content article.
    Stores images, diagrams, infographic placeholders, and videos.
    Cloudinary-ready: cloudinary_url populated when asset is uploaded.
    Initially populated with placeholders from Phase 4.5B formatting pass.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
        help_text="Unique identifier for this media asset.")
    content = models.ForeignKey(
        BookContent,
        on_delete=models.CASCADE,
        related_name="media_assets",
        help_text="The book content article this media belongs to."
    )
    media_type = models.CharField(max_length=30,
        help_text="Type of media. "
                  "Values: image | diagram | table_image | infographic | video | placeholder")
    cloudinary_url = models.TextField(blank=True, default="",
        help_text="Cloudinary CDN URL. Empty if placeholder not yet fulfilled.")
    youtube_url = models.TextField(blank=True, default="",
        help_text="YouTube embed URL for video content.")
    position = models.CharField(max_length=20, default="inline",
        help_text="Where in the article this media appears. Values: hero | inline | end")
    position_marker = models.TextField(blank=True, default="",
        help_text="The exact marker string in content_markdown where this media is inserted. "
                  "Example: '>[!infographic: Map of British India 1773]<' "
                  "Frontend replaces this marker with the rendered component.")
    caption = models.TextField(blank=True, default="",
        help_text="Caption text displayed below the media.")
    alt_text = models.CharField(max_length=500, blank=True, default="",
        help_text="Accessibility alt text for images.")
    display_order = models.IntegerField(default=0,
        help_text="Order of this media within the article.")
    created_at = models.DateTimeField(auto_now_add=True,
        help_text="When this media asset was created.")

    class Meta:
        db_table = "knowledge_content_media"
        ordering = ["display_order"]
        indexes = [
            models.Index(fields=["content", "display_order"],
                name="content_media_order_idx"),
            models.Index(fields=["media_type"],
                name="content_media_type_idx"),
        ]

    def __str__(self) -> str:
        return f"Media[{self.media_type}]: {self.content.topic.name}"


class GenerationLog(models.Model):
    """
    Layer 3: Tracks every book content generation run.
    Equivalent to POC's ingestion_logs table.
    Used for crash recovery, admin monitoring, and resumption logic.
    The management command reads this to implement Smart Skip.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False,
        help_text="Unique identifier for this generation log entry.")
    topic_name = models.CharField(max_length=500,
        help_text="Name of the topic being generated.")
    subject_name = models.CharField(max_length=300,
        help_text="Name of the subject this topic belongs to.")
    status = models.CharField(max_length=20,
        help_text="Outcome of this generation run. Values: success | failed | skipped")
    nodes_created = models.IntegerField(default=0,
        help_text="Number of new BookContent records created in this run.")
    relations_created = models.IntegerField(default=0,
        help_text="Number of new TopicRelation records created in this run.")
    cross_refs_created = models.IntegerField(default=0,
        help_text="Number of CrossReference records injected in this run.")
    quality_score = models.FloatField(default=0.0,
        help_text="Quality score of the generated article (0-100).")
    word_count = models.IntegerField(default=0,
        help_text="Word count of the generated article.")
    error_message = models.TextField(blank=True, default="",
        help_text="Full error message if status=failed.")
    generation_time_seconds = models.IntegerField(default=0,
        help_text="Total wall-clock seconds taken for this generation run.")
    created_at = models.DateTimeField(auto_now_add=True,
        help_text="When this log entry was created (= when generation ran).")

    class Meta:
        db_table = "knowledge_generation_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"],
                name="gen_log_status_time_idx"),
            models.Index(fields=["subject_name"],
                name="gen_log_subject_idx"),
            models.Index(fields=["topic_name"],
                name="gen_log_topic_idx"),
        ]

    def __str__(self) -> str:
        return f"GenLog: {self.topic_name} [{self.status}] score={self.quality_score:.0f}"


# ── Additive columns on existing knowledge_topic table ───────────────────────
# These are added via migration only — DO NOT redefine knowledge_topic model here.
# The migration (Task 1.3) adds these columns using RunSQL.
#
# knowledge_topic gets:
#   node_type VARCHAR(30) DEFAULT 'topic'
#     → 'subject_root'|'module'|'topic'|'subtopic'|'sub_subtopic'
#     → Drives graph node visual type and navbar depth
#   graph_position JSONB DEFAULT '{}'
#     → {"x": 120, "y": 340, "cluster": "union_legislature"}
#     → Graph UI reads for stable node layout. Navbar UI ignores.
#   content_status VARCHAR(20) DEFAULT 'empty'
#     → 'empty'|'generating'|'draft'|'book_quality'|'verified'
#     → Admin dashboard: "320/800 topics have book-quality content"
```

---

### Task 1.3 — Write migration 0001_initial.py

File: `backend/engines/book_content/migrations/0001_initial.py`

This migration must:
1. Create all 6 new tables (BookPlan, BookContent, TopicRelation, CrossReference, ContentMedia, GenerationLog)
2. Add 3 columns to existing `knowledge_topic` table using `migrations.RunSQL`
3. Create all performance indexes

The RunSQL for knowledge_topic additions:
```sql
ALTER TABLE knowledge_topic ADD COLUMN IF NOT EXISTS node_type VARCHAR(30) DEFAULT 'topic';
ALTER TABLE knowledge_topic ADD COLUMN IF NOT EXISTS graph_position JSONB DEFAULT '{}';
ALTER TABLE knowledge_topic ADD COLUMN IF NOT EXISTS content_status VARCHAR(20) DEFAULT 'empty';

CREATE INDEX IF NOT EXISTS topic_node_type_idx ON knowledge_topic(node_type);
CREATE INDEX IF NOT EXISTS topic_content_status_idx ON knowledge_topic(content_status);
CREATE INDEX IF NOT EXISTS topic_parent_idx ON knowledge_topic(parent_topic_id) WHERE parent_topic_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS topic_subject_idx ON knowledge_topic(subject_id, is_active);
CREATE INDEX IF NOT EXISTS topic_module_idx ON knowledge_topic(module_id, order_index);
```

---

### Task 1.4 — Apply and verify migration

Run:
```
python manage.py migrate book_content
```

Verify in psql or pgAdmin:
- All 6 new tables exist with correct columns
- `knowledge_topic` has 3 new columns: node_type, graph_position, content_status
- All indexes are created
- No existing table was dropped or modified beyond the 3 new columns

✅ STOP. Show human the migration output. Wait for approval.

---

## PART 2 — NEW ENGINE: SERVICES (POC PORT)

**Goal:** Port all POC logic into Django services. Preserve all prompts and algorithms exactly.
**One file at a time. Stop after each file for approval.**

---

### Task 2.1 — Port llm_client.py → llm_service.py

File: `backend/engines/book_content/services/llm_service.py`

Source: `upsc-agent-lab/src/llm_client.py`

Adaptations:
- Replace `import logging` + basicConfig → `import structlog; logger = structlog.get_logger(__name__)`
- Replace `log.info/warning/error` → `logger.info/warning/error` with keyword args
- Replace `logging.FileHandler("logs/agent.log")` → structlog handles this
- All LLM pool config (temperature, max_tokens, key rotation) → PRESERVE EXACTLY
- INTER_CALL_SLEEP = 12.0 → PRESERVE EXACTLY
- RETRY_WAIT_TIMES = [15, 30, 45] → PRESERVE EXACTLY
- Read GROQ_API_KEY and GROQ_MODEL from Django settings (os.environ via settings)
- Add sentry_sdk.capture_exception(e) in the permanent failure branch
- Export: `llm_call(prompt: str, mode: str = "standard") -> str`

✅ STOP. Wait for approval.

---

### Task 2.2 — Port wiki_fetcher.py → wiki_service.py

File: `backend/engines/book_content/services/wiki_service.py`

Source: `upsc-agent-lab/src/wiki_fetcher.py`

Adaptations:
- Replace logging → structlog
- All section-scoring algorithm → PRESERVE EXACTLY
- _split_into_sections() → PRESERVE EXACTLY
- _keyword_window() fallback → PRESERVE EXACTLY
- Export: `fetch_full_page(term: str, fallback_suffix: str = "India") -> dict`
- Export: `extract_relevant_section(wiki_content: str, subtopic: str, max_chars: int = 6000) -> str`

✅ STOP. Wait for approval.

---

### Task 2.3 — Copy cross_subject_map.py

File: `backend/engines/book_content/services/cross_subject_map.py`

Source: `upsc-agent-lab/src/cross_subject_map.py`

Adaptations:
- Replace logging → structlog
- All SUBJECTS dict, TOPIC_MAP dict, fuzzy_lookup() → PRESERVE EXACTLY
- No other changes needed

✅ STOP. Wait for approval.

---

### Task 2.4 — Port classifier.py → classifier_service.py

File: `backend/engines/book_content/services/classifier_service.py`

Source: `upsc-agent-lab/src/classifier.py`

Adaptations:
- Replace logging → structlog
- Import cross_subject_map from `.cross_subject_map` (not `src.cross_subject_map`)
- Import llm_call from `.llm_service`
- All prompt builders → PRESERVE EXACTLY
- All JSON parsing fallback → PRESERVE EXACTLY
- Export: `classify_hierarchy(topic_name: str = None, ncert_text: str = None) -> dict`

✅ STOP. Wait for approval.

---

### Task 2.5 — Port subtopic_finder.py → subtopic_service.py

File: `backend/engines/book_content/services/subtopic_service.py`

Source: `upsc-agent-lab/src/subtopic_finder.py`

Adaptations:
- Replace logging → structlog
- Import llm_call from `.llm_service`
- All prompt builders → PRESERVE EXACTLY
- All JSON parsers (_parse_subtopic_list, _parse_string_list, _extract_json_array) → PRESERVE EXACTLY
- Export: `find_subtopics(topic_name: str, ncert_text: str = None) -> list`
- Export: `find_sub_subtopics(subtopic_name: str, parent_topic: str) -> list`

✅ STOP. Wait for approval.

---

### Task 2.6 — Port book_planner.py → book_planner_service.py

File: `backend/engines/book_content/services/book_planner_service.py`

Source: `upsc-agent-lab/src/book_planner.py`

Adaptations:
- Replace logging → structlog
- Import llm_call from `.llm_service`
- Replace ALL psycopg2 DB operations → Django ORM using BookPlan model:
    - `get_book_plan(subject_name)` → `BookPlan.objects.filter(subject__name=subject_name).first()`
    - `_save_book_plan()` → `BookPlan.objects.update_or_create(subject=subject_obj, ...)`
    - `update_concept_registry()` → fetch BookPlan, update concept_registry field, save()
    - `get_concept_registry()` → fetch BookPlan.concept_registry
- All TOC generation prompts → PRESERVE EXACTLY
- All prerequisite chain logic → PRESERVE EXACTLY
- Export: `generate_book_plan(subject_name: str, modules: list) -> dict`
- Export: `get_book_plan(subject_name: str) -> dict | None`
- Export: `update_concept_registry(subject_name: str, concept_name: str, topic_id: str, topic_label: str) -> None`
- Export: `get_concept_registry(subject_name: str) -> dict`
- Export: `get_previously_covered_concepts(subject_name: str, current_topic: str) -> str`

✅ STOP. Wait for approval.

---

### Task 2.7 — Port quality_engine.py → quality_engine_service.py

File: `backend/engines/book_content/services/quality_engine_service.py`

Source: `upsc-agent-lab/src/quality_engine.py`

This is the MOST CRITICAL file. Preserve everything.

Adaptations:
- Replace logging → structlog
- Import llm_call from `.llm_service`
- MASTER_STYLE_ANCHOR string → PRESERVE CHARACTER FOR CHARACTER
- SECTION_PLAN list → PRESERVE EXACTLY (all 6 sections, all instructions)
- Add SUBJECT_PROFILES dict (Phase 4.5C — Adaptive Subject Personas):
  ```python
  SUBJECT_PROFILES = {
      "Indian Constitution & Polity": {
          "tone": "authoritative, precise, legislative",
          "emphasis": "exact Article numbers, landmark judgments, constitutional provisions",
          "structure": "definition → framework → evolution → criticism → UPSC angle",
          "avoid": "narrative storytelling, emotional language",
          "example_voice": "Article 352 empowers the President to proclaim..."
      },
      "History": {
          "tone": "narrative, chronological, personality-driven",
          "emphasis": "cause-effect chains, key personalities, turning points",
          "structure": "context → events → key figures → impact → legacy",
          "avoid": "dry legalistic tone, bullet-point overload",
          "example_voice": "The fateful year of 1857 saw the first major..."
      },
      "Ethics, Integrity & Aptitude": {
          "tone": "reflective, philosophical, case-study driven",
          "emphasis": "ethical dilemmas, thinker quotes, real-world cases",
          "structure": "concept → thinkers → case study → application → UPSC angle",
          "avoid": "purely factual recitation, legalistic tone",
          "example_voice": "Consider the ethical implications when a civil servant..."
      },
      "Economy & Finance": {
          "tone": "analytical, data-aware, policy-focused",
          "emphasis": "statistics, policy comparisons, budget references",
          "structure": "concept → data → policy → impact → reform → UPSC angle",
          "avoid": "abstract philosophy, narrative-heavy prose",
          "example_voice": "India's GDP growth rate of 7.2% in FY24 reflects..."
      },
      "Geography": {
          "tone": "spatial, descriptive, pattern-focused",
          "emphasis": "maps (conceptual), regional patterns, physical processes",
          "structure": "phenomenon → process → distribution → India-specific → UPSC angle",
          "avoid": "purely historical narrative, excessive legal citations",
          "example_voice": "The Western Ghats, running 1600 km along the coast..."
      },
  }
  ```
- Modify `_build_section_prompt()` to accept `subject: str` and inject SUBJECT_PROFILES[subject] after MASTER_STYLE_ANCHOR if subject is in SUBJECT_PROFILES
- Add `_run_formatting_pass(subtopic: str, article_md: str) -> str` (Phase 4.5B):
  This function runs AFTER self-critique. It evaluates 3 criteria:
  ```
  CRITERION 1 — Factual Density:
    Does the article contain ≥5 dates, names, or specific powers?
    → If YES: generate a Summary Table at the END of article
    Table format: "### 📊 Quick Revision: {subtopic}"
    | Aspect | Detail |

  CRITERION 2 — Comparison Potential:
    Does the article discuss ≥2 distinct entities on same attributes?
    → If YES: generate Comparison Table INLINE after both entities discussed
    Table format: "### ⚖️ Comparative Analysis: {Entity A} vs {Entity B}"

  CRITERION 3 — Logical Grouping:
    Can sections be categorized into classification table?
    → If YES: generate Categorization Table INLINE within relevant section
    Table format: "### 📋 Classification: {Category Name}"

  IF NONE MET → return article unchanged. No tables added.

  DATA SAFETY: Formatter receives ONLY the generated article as input.
  It CANNOT hallucinate. Every cell must trace to a sentence in the article.
  Prompt the LLM explicitly: "Only use facts present in the article below."

  Also detect "Visual Moments" and inject infographic placeholders:
    Syntax: >[!infographic: "Description of what image should show"]<
    Used for highly spatial, structural, or timeline-based data.

  Inject UPSC callout boxes:
    Syntax: > **💡 UPSC High-Yield Focus:** {Critical Exam Takeaway}
  ```
- `generate_quality_article()` → call `_run_formatting_pass()` after self-critique
- Export: `generate_quality_article(subtopic, parent_topic, ncert_section, wiki_content, previously_covered, subject) -> tuple[str, float]`

✅ STOP. Wait for approval.

---

### Task 2.8 — Port coherence_engine.py → coherence_service.py

File: `backend/engines/book_content/services/coherence_service.py`

Source: `upsc-agent-lab/src/coherence_engine.py`

Adaptations:
- Replace logging → structlog
- Import llm_call from `.llm_service`
- Import BookContent, CrossReference, TopicRelation from `..models`
- Replace psycopg2 DB operations → Django ORM:
    - `_fetch_subtopics(topic_id)` → `BookContent.objects.filter(topic__parent_topic_id=topic_id)`
    - `_inject_cross_references()` → `CrossReference.objects.get_or_create(...)`
    - `UPDATE nodes SET content_body` → `content_obj.content_markdown = ...; content_obj.save()`
- All duplicate detection prompts → PRESERVE EXACTLY
- All consistency validation prompts → PRESERVE EXACTLY
- Export: `run_coherence_pass(topic_id: str, topic_name: str, subject_name: str) -> None`

✅ STOP. Wait for approval.

---

### Task 2.9 — Port ingestor.py → ingestor_service.py

File: `backend/engines/book_content/services/ingestor_service.py`

Source: `upsc-agent-lab/src/ingestor.py`

This is the MASTER ORCHESTRATOR. It calls all other services.

Adaptations:
- Replace logging → structlog
- Import all services from their new locations
- Replace psycopg2 DB operations → Django ORM:
    - `_get_or_create_node()` → `knowledge_topic.objects.get_or_create(name=label, ...)`
      NOTE: For subject/module/topic nodes — check if they ALREADY EXIST in
      knowledge_subject, knowledge_module, knowledge_topic tables.
      DO NOT create duplicates. Use get_or_create with name matching.
    - `_create_edge()` → `TopicRelation.objects.get_or_create(...)`
    - Article save → `BookContent.objects.update_or_create(topic=topic_obj, ...)`
    - Log → `GenerationLog.objects.create(...)`
- Smart Skip logic → PRESERVE EXACTLY:
    Check `BookContent.objects.filter(topic__name=subtopic_name).exists()`
    If exists → skip LLM call, but still call `update_concept_registry()`
- Atomic commits → Django's `transaction.atomic()` per subtopic save
- topic_overview generation → PRESERVE prompt EXACTLY
- _generate_subtopic_article() → REPLACED by `generate_quality_article()` from quality_engine_service
- After all subtopics complete → call `run_coherence_pass()`
- Update `knowledge_topic.content_status = 'book_quality'` after successful generation
- Export: `ingest_topic(topic_name: str = None, subject_name: str = None) -> dict`

IMPORTANT: The ingestor must use `knowledge_topic.parent_topic_id` to build
the hierarchy instead of POC's integer-based edges table.
When a subtopic is created → set `parent_topic_id = parent_topic.id`
When a sub-subtopic is created → set `parent_topic_id = subtopic.id`
The `knowledge_topic.node_type` column drives the depth:
  subject → 'subject_root' (level 1)
  module  → 'module' (level 2)
  topic   → 'topic' (level 3)
  subtopic → 'subtopic' (level 4)
  sub-subtopic → 'sub_subtopic' (level 5)

✅ STOP. Wait for approval.

---

## PART 3 — MANAGEMENT COMMAND

**Goal:** Create a Django management command that runs the full generation pipeline.
This replaces `run_lab.py` from the POC.

### Task 3.1 — Write generate_book_content.py command

File: `backend/engines/book_content/management/commands/generate_book_content.py`

```python
"""
Management command: generate_book_content
Equivalent to POC's run_lab.py — the "Play" button for the 3-Layer pipeline.

Usage:
  python manage.py generate_book_content --subject "Indian Constitution & Polity"
  python manage.py generate_book_content --topic "Parliament of India"
  python manage.py generate_book_content --subject "Indian Constitution & Polity" --dry-run

What it does:
  1. Verifies DB state (all required tables exist)
  2. Generates/retrieves Book Intelligence Plan (Layer 1)
  3. Runs 3-Layer Quality Engine for each topic (Layer 2 + 3)
  4. Prints full generation summary with quality metrics
  5. Handles GROQ rate limits gracefully (12s delay built into llm_service)
  6. Smart resumption: skips already-generated content (crash-safe)
"""
import structlog
import sentry_sdk
from django.core.management.base import BaseCommand, CommandError
from engines.book_content.services.book_planner_service import generate_book_plan, get_book_plan
from engines.book_content.services.ingestor_service import ingest_topic
from engines.book_content.models import BookContent, GenerationLog
from engines.knowledge.models import Subject, Topic

logger = structlog.get_logger(__name__)

# ── SUBJECT CONFIGURATION ────────────────────────────────────────────────────
# Mirrors run_lab.py MODULES config from POC.
# Add more subjects here as content generation expands.

SUBJECT_MODULES = {
    "Indian Constitution & Polity": [
        "Union Legislature",
        "Union Executive",
        "Union Judiciary",
        "State Government",
        "Fundamental Rights & Duties",
        "Directive Principles",
        "Constitutional Amendments",
        "Emergency Provisions",
        "Federalism & Centre-State Relations",
        "Constitutional Bodies",
    ],
}

# ── TOPIC QUEUE ──────────────────────────────────────────────────────────────
# Topics to generate. Add one topic at a time to control rate limits.
# Comment/uncomment topics as generation progresses.

TOPICS_TO_GENERATE = [
    "Parliament of India",
    # "President of India",
    # "Prime Minister of India",
    # "Fundamental Rights",
    # "Directive Principles of State Policy",
    # "Supreme Court of India",
    # "Election Commission of India",
    # "Federalism & Centre-State Relations",
    # "Emergency Provisions",
    # "Constitutional Amendments",
]


class Command(BaseCommand):
    """Generate book-quality UPSC study content using the 3-Layer Quality Engine."""
    help = "Generate static book-quality UPSC articles using the 3-Layer Quality Engine."

    def add_arguments(self, parser):
        parser.add_argument("--subject", type=str, default=None,
            help="Subject name to generate book plan for. "
                 "Example: 'Indian Constitution & Polity'")
        parser.add_argument("--topic", type=str, default=None,
            help="Single topic name to generate. Overrides TOPICS_TO_GENERATE list.")
        parser.add_argument("--dry-run", action="store_true", default=False,
            help="Show what would be generated without making any LLM calls.")

    def handle(self, *args, **options):
        """Main entry point."""
        logger.info("book_content_generation_started",
                    subject=options.get("subject"),
                    topic=options.get("topic"),
                    dry_run=options.get("dry_run"))

        try:
            self._run(options)
        except KeyboardInterrupt:
            self.stdout.write("\n⚠️  Interrupted. All completed articles are safely saved.")
            logger.warning("generation_interrupted_by_user")
        except Exception as e:
            logger.error("generation_failed", error=str(e))
            sentry_sdk.capture_exception(e)
            raise CommandError(f"Generation failed: {e}")

    def _run(self, options):
        subject_name = options.get("subject") or "Indian Constitution & Polity"
        single_topic = options.get("topic")
        dry_run = options.get("dry_run", False)

        self.stdout.write(self.style.SUCCESS(
            "\n╔══════════════════════════════════════════════════╗"
            "\n║   TheKnowledgeOrbits — Book Content Engine       ║"
            "\n║   3-Layer Quality Engine (GROQ free tier)        ║"
            "\n╚══════════════════════════════════════════════════╝\n"
        ))

        # Step 1: Book Intelligence Plan
        self.stdout.write("STEP 1: Book Intelligence Plan...")
        existing_plan = get_book_plan(subject_name)
        if not existing_plan:
            if not dry_run:
                modules = SUBJECT_MODULES.get(subject_name, [])
                generate_book_plan(subject_name, modules)
                self.stdout.write(self.style.SUCCESS(f"  ✅ Book plan created for '{subject_name}'"))
            else:
                self.stdout.write(f"  [DRY RUN] Would create book plan for '{subject_name}'")
        else:
            self.stdout.write(f"  ✅ Book plan exists for '{subject_name}' — skipping")

        # Step 2: Generate topics
        topics = [single_topic] if single_topic else TOPICS_TO_GENERATE
        self.stdout.write(f"\nSTEP 2: Generating {len(topics)} topic(s)...")

        for topic_name in topics:
            already_done = BookContent.objects.filter(
                topic__name=topic_name
            ).exists()

            if already_done:
                self.stdout.write(f"  ⏭️  Skipping '{topic_name}' — already generated")
                continue

            if dry_run:
                self.stdout.write(f"  [DRY RUN] Would generate: '{topic_name}'")
                continue

            self.stdout.write(f"\n  🔄 Generating: '{topic_name}'...")
            result = ingest_topic(topic_name=topic_name, subject_name=subject_name)
            self.stdout.write(self.style.SUCCESS(
                f"  ✅ '{topic_name}' done — "
                f"{result.get('nodes_created', 0)} articles, "
                f"avg quality: {result.get('avg_quality', 0):.0f}/100"
            ))

        # Step 3: Summary
        self._print_summary(subject_name)

    def _print_summary(self, subject_name: str):
        """Print generation summary."""
        total_content = BookContent.objects.filter(
            subject__name=subject_name
        ).count()
        total_words = sum(
            bc.word_count for bc in
            BookContent.objects.filter(subject__name=subject_name)
        )
        avg_quality = BookContent.objects.filter(
            subject__name=subject_name,
            quality_score__gt=0
        ).values_list("quality_score", flat=True)
        avg_q = sum(avg_quality) / len(avg_quality) if avg_quality else 0

        self.stdout.write(self.style.SUCCESS(
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 GENERATION SUMMARY: {subject_name}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  Total Articles : {total_content}\n"
            f"  Total Words    : {total_words:,}\n"
            f"  Est. Pages     : ~{total_words // 300} (at 300 words/page)\n"
            f"  Avg Quality    : {avg_q:.1f} / 100\n"
        ))
```

### Task 3.2 — End-to-end local test

Run on local with ONE topic only:
```
python manage.py generate_book_content --topic "Parliament of India" --dry-run
```
Then if dry-run passes:
```
python manage.py generate_book_content --topic "Parliament of India"
```

Verify:
- BookContent record created in local PostgreSQL
- quality_score > 0
- word_count > 1000
- knowledge_topic.content_status = 'book_quality'
- GenerationLog record created with status='success'

✅ STOP. Show human the output. Wait for approval.

---

## PART 4 — GITHUB ACTIONS AUTOMATION

**Goal:** Automate daily content generation via GitHub Actions.
Rate limit reality: ~20-22 deep articles/day. Let it run overnight.
Smart Skip ensures no wasted API calls on restart.

### Task 4.1 — Create daily generation workflow

IMPORTANT: DO NOT touch any existing file in .github/workflows/.
Create a new file ONLY:

File: `.github/workflows/daily_book_content.yml`

```yaml
name: Daily Book Content Generation

on:
  schedule:
    # Runs at 11:30 PM IST (18:00 UTC) every day
    - cron: "0 18 * * *"
  workflow_dispatch:
    # Allow manual trigger from GitHub UI
    inputs:
      topic:
        description: "Specific topic to generate (optional)"
        required: false
        default: ""
      subject:
        description: "Subject name"
        required: false
        default: "Indian Constitution & Polity"

jobs:
  generate-book-content:
    name: Generate Static Book Content
    runs-on: ubuntu-latest
    timeout-minutes: 360  # 6 hours max — GROQ rate limits mean this runs slow

    env:
      DJANGO_SETTINGS_MODULE: core.settings.production
      DATABASE_URL: ${{ secrets.DATABASE_URL }}
      GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
      GROQ_MODEL: llama-3.3-70b-versatile
      SECRET_KEY: ${{ secrets.SECRET_KEY }}

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        working-directory: backend
        run: pip install -r requirements.txt

      - name: Run database migrations
        working-directory: backend
        run: python manage.py migrate --run-syncdb

      - name: Generate book content
        working-directory: backend
        run: |
          if [ -n "${{ github.event.inputs.topic }}" ]; then
            python manage.py generate_book_content \
              --subject "${{ github.event.inputs.subject }}" \
              --topic "${{ github.event.inputs.topic }}"
          else
            python manage.py generate_book_content \
              --subject "${{ github.event.inputs.subject || 'Indian Constitution & Polity' }}"
          fi

      - name: Report summary
        if: always()
        working-directory: backend
        run: |
          python manage.py shell -c "
          from engines.book_content.models import BookContent, GenerationLog
          total = BookContent.objects.count()
          recent = GenerationLog.objects.filter(status='success').count()
          print(f'Total book articles: {total}')
          print(f'Successful runs today: {recent}')
          "
```

✅ STOP. Wait for human approval before creating this file.
Human must add GROQ_API_KEY to GitHub Secrets before this workflow runs.

---

## PART 5 — API ENDPOINTS

**Goal:** Expose book content data via DRF endpoints.
Navbar UI reads the tree structure. Knowledge Graph UI reads nodes + edges.
Both read from the SAME tables.

### Task 5.1 — Write serializers.py

File: `backend/engines/book_content/serializers.py`

Write serializers for:
- `BookContentSerializer` — full article content for reader
- `BookContentListSerializer` — lightweight list (no content_markdown)
- `TopicNodeSerializer` — for graph/tree rendering (id, name, node_type, content_status, graph_position, parent_topic_id, quality_score)
- `TopicRelationSerializer` — for graph edges
- `CrossReferenceSerializer` — for See Also section
- `BookPlanSerializer` — for subject overview
- `GenerationLogSerializer` — for admin monitoring

---

### Task 5.2 — Write views.py

File: `backend/engines/book_content/views.py`

Write these DRF ViewSets/APIViews:

```
GET /api/v1/book/subjects/
  → Returns all knowledge_subject records with book_plan status
  → Shows: subject name, topics_planned, topics_completed, avg_quality_score
  → Used by: subject selector in frontend

GET /api/v1/book/tree/{subject_id}/
  → Returns full hierarchy tree for navbar renderer
  → Structure: subject → modules → topics → subtopics (recursive)
  → Includes: content_status per node (empty/book_quality/etc)
  → Used by: hamburger/navbar UI

GET /api/v1/book/graph/{subject_id}/
  → Returns ALL topic nodes + edges for graph renderer
  → Nodes: {id, name, node_type, graph_position, content_status, quality_score}
  → Hierarchical edges: derived from parent_topic_id FK structure
  → Semantic edges: from knowledge_topic_relation table
  → Used by: Knowledge Graph UI (eye toggle)

GET /api/v1/book/graph/{subject_id}/node/{topic_id}/children/
  → Returns ONLY direct children of a topic node
  → Used by: progressive disclosure in Knowledge Graph (lazy load on click)

GET /api/v1/book/content/{topic_id}/
  → Returns full BookContent for a topic
  → Includes: content_markdown, formatted_content, quality_score, cross_references
  → Used by: article reader panel in both navbar and graph UI

GET /api/v1/book/content/{topic_id}/cross-references/
  → Returns all CrossReference records for an article
  → Used by: See Also section in article reader

GET /api/v1/book/generation-log/
  → Returns recent GenerationLog records
  → Used by: admin monitoring dashboard
  → Requires: is_staff permission
```

All views:
- Use `@require_auth` decorator (existing RBAC pattern)
- Use structlog for all logging
- Return proper DRF Response objects
- Handle 404 gracefully

---

### Task 5.3 — Write urls.py

File: `backend/engines/book_content/urls.py`

Register all endpoints from Task 5.2.
Then register in `core/urls.py`:
```python
path("api/v1/book/", include("engines.book_content.urls")),
```

✅ STOP. Test all endpoints with HTTPie or Postman. Wait for approval.

---

## PART 6 — FRONTEND: KNOWLEDGE GRAPH UI

**Goal:** Add knowledge graph as a toggleable view alongside the existing hamburger/navbar.
The "eye" button toggles between two renderers of the same data.
No existing page is modified structurally — only additions.

### Task 6.1 — Add API client functions

File: `frontend/src/lib/api/book-content.ts`

Write TypeScript API functions for all endpoints from Part 5:
```typescript
export async function getBookSubjects(): Promise<Subject[]>
export async function getBookTree(subjectId: string): Promise<TreeNode[]>
export async function getBookGraph(subjectId: string): Promise<GraphData>
export async function getGraphNodeChildren(subjectId: string, topicId: string): Promise<GraphNode[]>
export async function getBookContent(topicId: string): Promise<BookContent>
export async function getCrossReferences(topicId: string): Promise<CrossReference[]>
```

Add TypeScript types for all responses in `frontend/src/types/book-content.ts`

---

### Task 6.2 — Create KnowledgeGraph component

File: `frontend/src/components/book-content/knowledge-graph.tsx`

Port the D3.js graph logic from `upsc-agent-lab/src/templates/index.html`.

Key behaviours (from POC's index.html — study it carefully):
- Progressive disclosure: initially shows only subject-level nodes
- Single click on node with children (collapsed) → fetch children → animate into view
- Single click on expanded node → collapse children
- Single click on leaf node → open article reader panel
- Double click on any node → open article reader panel
- Node visual types: subject=large orange, module=medium blue, topic=small green, subtopic=tiny grey
- Edge types: contains=solid line, related_to=dashed orange line
- Node label shows child count: "Parliament ▼ (22 subtopics)"

Use D3.js (already available via CDN or install):
```
npm install d3 @types/d3
```
Only add this package — no others.

Colour scheme matches existing shadcn/ui theme (use CSS variables).

---

### Task 6.3 — Create BookContentReader component

File: `frontend/src/components/book-content/book-content-reader.tsx`

Renders the markdown article in a right-side panel when a graph node is clicked.

Features:
- Render `formatted_content` (if available) else `content_markdown`
- Markdown renderer: use existing `lib/utils/markdown.ts` patterns
- Render tables with proper styling (Tailwind prose classes)
- Render callout boxes:
    `>[!infographic: "..."]<` → placeholder component with dashed border + icon
    `> **💡 UPSC High-Yield Focus:** ...` → highlighted glassmorphism callout box
- Render `### See Also` section as clickable links that navigate to referenced node in graph
- Show quality_score badge (colour: green >80, yellow 65-80, red <65)
- Show word_count and read_time estimates

---

### Task 6.4 — Create the eye toggle button and page

File: `frontend/src/components/book-content/graph-toggle-button.tsx`

A button component with an eye icon (use lucide-react `Eye` icon, already installed).
When clicked, toggles between:
  - `navbar` mode: existing hamburger/sidebar navigation (default)
  - `graph` mode: Knowledge Graph UI

Store toggle state in localStorage key: `"tko_view_mode"` (persists across sessions).

File: `frontend/src/app/knowledge/page.tsx`

New page at `/knowledge` route.
Layout:
```
Left panel (40%):   Subject selector dropdown
                    Toggle button [📋 Outline] ↔ [🕸️ Graph]

                    IF outline mode:
                      Tree view (collapsible, same data as navbar)
                    IF graph mode:
                      KnowledgeGraph component

Right panel (60%):  BookContentReader component
                    (empty state until a node is clicked)
```

This is a NEW standalone page. It does NOT modify any existing page.
Add it to the main navigation header as: "Knowledge Map" link.

---

### Task 6.5 — Add "Knowledge Map" link to header

File: `frontend/src/components/layout/header.tsx`

ADD (do not replace anything):
```tsx
<Link href="/knowledge">Knowledge Map</Link>
```

This is the only modification to an existing file in Part 6.

✅ STOP. Test full flow:
- Open /knowledge page
- Select a subject
- Toggle to graph view
- Click a node → see children expand
- Click a leaf node → see article in right panel
- Toggle back to outline view → same data, different renderer
- Verify "See Also" links navigate correctly

Wait for human approval.

---

## COMPLETION CHECKLIST

Before marking any part complete, verify:

**Part 1 (DB):**
- [ ] 6 new tables exist in local PostgreSQL
- [ ] knowledge_topic has 3 new columns
- [ ] All indexes created
- [ ] No existing table dropped or destructively modified
- [ ] Migration runs cleanly on fresh DB

**Part 2 (Services):**
- [ ] All 9 service files created
- [ ] MASTER_STYLE_ANCHOR preserved character-for-character
- [ ] INTER_CALL_SLEEP = 12.0 (not changed)
- [ ] SUBJECT_PROFILES dict included (Phase 4.5C)
- [ ] _run_formatting_pass() implemented (Phase 4.5B)
- [ ] Smart Skip logic working (check BookContent before LLM call)
- [ ] No print() anywhere — structlog only

**Part 3 (Command):**
- [ ] `python manage.py generate_book_content --dry-run` works
- [ ] Full generation produces BookContent record with quality_score > 65
- [ ] GenerationLog record created
- [ ] knowledge_topic.content_status updated to 'book_quality'

**Part 4 (GitHub Actions):**
- [ ] New workflow file created (.github/workflows/daily_book_content.yml)
- [ ] No existing workflow files modified
- [ ] Human has added GROQ_API_KEY to GitHub Secrets

**Part 5 (API):**
- [ ] All 7 endpoints return correct data
- [ ] Tree endpoint returns full hierarchy without graph_position
- [ ] Graph endpoint returns nodes with graph_position + edges
- [ ] Content endpoint returns markdown + cross_references

**Part 6 (Frontend):**
- [ ] /knowledge page loads without errors
- [ ] Graph toggle works
- [ ] Progressive disclosure works (children load on click)
- [ ] Article reader renders markdown + tables + callouts correctly
- [ ] "Knowledge Map" link appears in header
- [ ] No existing page broken

---

## WHAT NOT TO BUILD (Explicit Prohibitions)

❌ Do NOT modify article_article table or its engine
❌ Do NOT modify assessment_* tables or quiz engine
❌ Do NOT modify auth engine or JWT flow
❌ Do NOT modify CA scraper or current_affairs engine
❌ Do NOT modify any existing .github/workflows/ file
❌ Do NOT add NCERT PDF processing (wiki only for now)
❌ Do NOT add RAG/embedding pipeline (future phase)
❌ Do NOT add Daily CA article generation (future phase — needs Part 1-6 stable first)
❌ Do NOT add Theme Series engine (future phase)
❌ Do NOT use Docker or docker-compose commands
❌ Do NOT use print() anywhere
❌ Do NOT install any npm/pip packages not listed in this file

---

## FUTURE PHASES (Do Not Build Now)

These are listed here only so Claude Code understands the direction.
Build them ONLY after Parts 1-6 are complete and human-approved.

**Phase 7 (future): Daily CA Article Generation**
  Uses: book content (static) + ca_chunk (live) → integrated daily article
  New table: knowledge_daily_article
  New command: generate_daily_article

**Phase 8 (future): Theme Series Engine**
  Uses: knowledge_theme + knowledge_theme_episode
  Episodic articles with series_context memory
  New command: generate_theme_episode

**Phase 9 (future): RAG Enhancement**
  Chunk book_content into content_chunk
  Add embeddings to content_embedding
  Enable semantic search across book content

**Phase 10 (future): Cross-Subject Linking**
  Use pgvector to auto-detect topic similarity
  Populate knowledge_topic_relation automatically
  Threshold: similarity_score > 0.75
