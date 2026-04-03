"""
src/ingestor.py
━━━━━━━━━━━━━━━
The Core Agent — Orchestrates all 9 steps of the Deep Content Engine.


Two input modes:
  Mode A: ingest_topic(topic_name="Parliament of India")
          → Wikipedia as primary research material
  Mode B: ingest_topic(pdf_path="data/input_pdfs/ch22_parliament.pdf")
          → NCERT as spine, Wikipedia as enricher (THE GOLD STANDARD)

Pipeline:
  Step 1 — Source Extraction (pypdf)
  Step 2 — NCERT Text Cleaning (regex + LLM)
  Step 3 — Hierarchy Classification (LLM Call #1)
  Step 4 — Subtopic Discovery (LLM Call #2)
  Step 5 — Wikipedia Full-Page Fetch (per subtopic)
  Step 6 — NCERT Section Extraction (LLM Call #3 per subtopic)
  Step 7 — Deep Article Synthesis (LLM Call #4 per subtopic)
  Step 8 — Sub-Subtopic Discovery + Articles (LLM Calls #5+ for [DEEP] subtopics)
  Step 9 — Save Everything to DB (single transaction per topic)
"""

import os
from typing import Optional
from dotenv import load_dotenv
from src.database import get_db_connection
from src.llm_client import llm_call, log_info, log_warning, log_error
from src.classifier import classify_hierarchy
from src.subtopic_finder import find_subtopics, find_sub_subtopics
from src.wiki_fetcher import fetch_full_page, extract_relevant_section
from src.quality_engine import generate_quality_article
from src.book_planner import get_previously_covered_concepts, update_concept_registry
from src.coherence_engine import run_coherence_pass

load_dotenv()


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════


def ingest_topic(
    topic_name: Optional[str] = None, pdf_path: Optional[str] = None
) -> dict:
    """
    Main Agent Entry Point.

    Call with either:
      ingest_topic(topic_name="Parliament of India")   ← Mode A
      ingest_topic(pdf_path="data/input_pdfs/ch22.pdf") ← Mode B

    Returns:
      {"nodes_created": int, "edges_created": int, "topic": str}
    """
    _separator()
    if pdf_path:
        mode = "B (NCERT PDF + Wikipedia)"
        log_info(f"📥 INGESTOR — Mode B | PDF: '{os.path.basename(pdf_path)}'")
    else:
        mode = "A (Wikipedia only)"
        log_info(f"📥 INGESTOR — Mode A | Topic: '{topic_name}'")
    log_info(f"   Mode: {mode}")
    _separator()

    # ── Steps 1 & 2: Source Extraction + Cleaning ─────────────────────────────
    clean_ncert_text = ""
    pdf_source_name = None

    if pdf_path:
        from src.pdf_decomposer import extract_raw_text, clean_text

        log_info("\n[Step 1/9] Extracting PDF text...")
        raw_text = extract_raw_text(pdf_path)
        if not raw_text:
            log_error("PDF extraction failed — cannot proceed.")
            return {"nodes_created": 0, "edges_created": 0, "topic": ""}

        log_info("\n[Step 2/9] Cleaning NCERT text...")
        clean_ncert_text = clean_text(raw_text)
        pdf_source_name = os.path.basename(pdf_path)
    else:
        log_info("\n[Step 1-2/9] Mode A — no PDF. Skipping extraction/cleaning.")

    # ── Step 3: Hierarchy Classification ─────────────────────────────────────
    log_info("\n[Step 3/9] Classifying into UPSC hierarchy...")
    hierarchy = classify_hierarchy(
        topic_name=topic_name,
        ncert_text=clean_ncert_text[:1500] if clean_ncert_text else None,
    )
    subject = hierarchy["subject"]
    module = hierarchy["module"]
    topic = hierarchy["confirmed_topic"]

    # ── Step 4: Subtopic Discovery ────────────────────────────────────────────
    log_info(f"\n[Step 4/9] Discovering subtopics for '{topic}'...")
    subtopics = find_subtopics(topic, ncert_text=clean_ncert_text or None)

    if not subtopics:
        log_warning("No subtopics found. Will create topic node only.")

    # ── Steps 5-9: Process each subtopic and save to DB ───────────────────────
    log_info(f"\n[Steps 5-9] Processing {len(subtopics)} subtopics + saving to DB...")

    conn = get_db_connection()
    nodes_created = 0
    edges_created = 0

    try:
        cur = conn.cursor()

        # Create Subject + Module nodes (get_or_create — safe to re-run)
        log_info(f"\n  📚 Subject node: '{subject}'")
        subject_id = _get_or_create_node(
            cur,
            subject,
            "subject",
            level=1,
            content=f"# {subject}\n\nRoot subject in UPSC syllabus.",
            source="system",
        )
        log_info(f"  📂 Module  node: '{module}'")
        module_id = _get_or_create_node(
            cur,
            module,
            "module",
            level=2,
            content=f"# {module}\n\nModule under {subject}.",
            source="system",
        )
        _create_edge(cur, subject_id, module_id, "contains")

        # Generate topic overview (a short intro article, ~400 words)
        log_info("  📄 Topic   node: '" + topic + "' (generating overview...)")
        topic_wiki = fetch_full_page(topic)
        topic_overview = _generate_topic_overview(
            topic, clean_ncert_text, topic_wiki["summary"]
        )
        topic_id = _get_or_create_node(
            cur,
            topic,
            "topic",
            level=3,
            content=topic_overview,
            source="ncert" if clean_ncert_text else "synthesized",
            pdf_source=pdf_source_name or "",
            word_count=len(topic_overview.split()),
            quality_score=75.0,  # Fixed high score for intro overviews
        )
        _create_edge(cur, module_id, topic_id, "contains")
        conn.commit()  # Save topic node immediately
        nodes_created += 1

        # ── Process each subtopic ─────────────────────────────────────────────
        for i, sub in enumerate(subtopics, 1):
            sub_name = sub["name"]
            needs_deep = sub["needs_deep"]
            deep_marker = " [DEEP]" if needs_deep else ""
            log_info(f"\n  [{i}/{len(subtopics)}] Subtopic: '{sub_name}'{deep_marker}")

            # ── Check DB first before burning API tokens
            cur.execute(
                "SELECT id FROM nodes WHERE label = %s AND type = 'subtopic' AND level = 4",
                (sub_name,),
            )
            existing_sub = cur.fetchone()
            if existing_sub:
                log_info(
                    f"     ⏭️  Skipping API call — '{sub_name}' already exists (Node ID: {existing_sub[0]})"
                )
                _create_edge(cur, topic_id, existing_sub[0], "contains")
                # SYNCED SKIPPING: Even if we skip the API call, tell the Book Plan this concept is covered
                update_concept_registry(subject, sub_name, existing_sub[0], sub_name)
                conn.commit()
                # If needs_deep, we still need to process its children (sub-subtopics)
                sub_id = existing_sub[0]
            else:
                # Step 5: Fetch full Wikipedia page for this subtopic
                log_info("  [Step 5] Wikipedia fetch...")
                wiki_data = fetch_full_page(sub_name)
                wiki_section = extract_relevant_section(wiki_data["content"], sub_name)

                # Step 6: Extract NCERT section for this subtopic (Mode B only)
                ncert_section = ""
                if clean_ncert_text:
                    log_info("  [Step 6] NCERT section extract...")
                    from src.pdf_decomposer import extract_section

                    ncert_section = extract_section(clean_ncert_text, sub_name)
                    if ncert_section == "NOT_IN_NCERT":
                        ncert_section = ""  # Will use Wikipedia-only for this subtopic

                # Step 7: Generate the deep article (UPGRADED)
                log_info("  [Step 7] Generating full quality article...")
                previously_covered = get_previously_covered_concepts(subject, sub_name)
                article_md, quality_score = generate_quality_article(
                    subtopic=sub_name,
                    parent_topic=topic,
                    ncert_section=ncert_section,
                    wiki_content=wiki_section,
                    previously_covered=previously_covered,
                    subject=subject,
                )

                # Save subtopic node
                sub_source = "ncert" if ncert_section else "synthesized"
                sub_id = _get_or_create_node(
                    cur,
                    sub_name,
                    "subtopic",
                    level=4,
                    content=article_md,
                    source=sub_source,
                    pdf_source=pdf_source_name or "",
                    word_count=len(article_md.split()),
                    quality_score=quality_score,
                )
                _create_edge(cur, topic_id, sub_id, "contains")

                # After saving subtopic, register in concept registry:
                update_concept_registry(subject, sub_name, sub_id, sub_name)

                conn.commit()  # Save subtopic immediately
                nodes_created += 1
                edges_created += 1

                log_info(
                    f"     ✅ Saved '{sub_name}' (Score: {quality_score:.0f}, {len(article_md.split())} words, Node ID: {sub_id})"
                )

            # ── Step 8: Recursive deep expansion ─────────────────────────────
            if needs_deep:
                log_info(f"\n  [Step 8] Recursive expansion of '{sub_name}'...")
                sub_subtopics = find_sub_subtopics(sub_name, topic)

                for ss_name in sub_subtopics:
                    log_info(f"\n    Sub-subtopic: '{ss_name}'")

                    # ── Check DB first before burning API tokens
                    cur.execute(
                        "SELECT id FROM nodes WHERE label = %s AND type = 'subtopic' AND level = 5",
                        (ss_name,),
                    )
                    existing_ss = cur.fetchone()
                    if existing_ss:
                        log_info(
                            f"     ⏭️  Skipping API call — '{ss_name}' already exists (Node ID: {existing_ss[0]})"
                        )
                        _create_edge(cur, sub_id, existing_ss[0], "contains")
                        # SYNCED SKIPPING for sub-subtopics
                        update_concept_registry(
                            subject, ss_name, existing_ss[0], ss_name
                        )
                        conn.commit()
                        continue

                    ss_wiki = fetch_full_page(ss_name)
                    ss_section = extract_relevant_section(ss_wiki["content"], ss_name)

                    ss_ncert = ""
                    if clean_ncert_text:
                        from src.pdf_decomposer import extract_section

                        ss_ncert = extract_section(clean_ncert_text, ss_name)
                        if ss_ncert == "NOT_IN_NCERT":
                            ss_ncert = ""

                    log_info("    [Step 7] Generating sub-subtopic article...")
                    previously_covered = get_previously_covered_concepts(
                        subject, ss_name
                    )
                    ss_article, ss_quality = generate_quality_article(
                        subtopic=ss_name,
                        parent_topic=sub_name,
                        ncert_section=ss_ncert,
                        wiki_content=ss_section,
                        previously_covered=previously_covered,
                        subject=subject,
                    )

                    ss_source = "ncert" if ss_ncert else "synthesized"
                    ss_id = _get_or_create_node(
                        cur,
                        ss_name,
                        "subtopic",
                        level=5,
                        content=ss_article,
                        source=ss_source,
                        pdf_source=pdf_source_name or "",
                        word_count=len(ss_article.split()),
                        quality_score=ss_quality,
                    )
                    _create_edge(cur, sub_id, ss_id, "contains")

                    # After saving sub-subtopic, register in concept registry:
                    update_concept_registry(subject, ss_name, ss_id, ss_name)

                    conn.commit()  # Save sub-subtopic immediately
                    nodes_created += 1
                    edges_created += 1

                    log_info(
                        f"    ✅ Saved '{ss_name}' (Score: {ss_quality:.0f}, {len(ss_article.split())} words, Node ID: {ss_id})"
                    )

        # ── Step 9: Coherence Pass ────────────────────────────────────────────
        log_info("\n  [Coherence Pass] Running cross-article coherence...")
        run_coherence_pass(topic_id, topic, subject)

        # ── Commit everything ─────────────────────────────────────────────────
        conn.commit()

        # ── Log success ───────────────────────────────────────────────────────
        cur.execute(
            """INSERT INTO ingestion_logs
               (topic_name, status, nodes_created, edges_created)
               VALUES (%s, 'success', %s, %s)""",
            (topic, nodes_created, edges_created),
        )
        conn.commit()

    except Exception as e:
        conn.rollback()
        log_error(f"Ingestion failed mid-run: {e}")
        try:
            cur.execute(
                """INSERT INTO ingestion_logs (topic_name, status, error_msg)
                   VALUES (%s, 'failed', %s)""",
                (topic, str(e)),
            )
            conn.commit()
        except Exception:
            pass
        raise
    finally:
        conn.close()

    _separator()
    log_info(f"✅ INGESTION COMPLETE: '{topic}'")
    log_info(f"   Nodes created : {nodes_created}")
    log_info(f"   Edges created : {edges_created}")
    _separator()

    return {
        "nodes_created": nodes_created,
        "edges_created": edges_created,
        "topic": topic,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ARTICLE GENERATION (Steps 7 — The Core LLM Writing Calls)
# ═══════════════════════════════════════════════════════════════════════════════


def _generate_topic_overview(topic: str, ncert_text: str, wiki_summary: str) -> str:
    """
    Generates a concise topic-level overview article (~400 words).
    This is the intro node that readers see before drilling into subtopics.
    """
    if ncert_text:
        prompt = f"""You are writing an overview introduction for a UPSC study book chapter.

TOPIC: "{topic}"

NCERT CHAPTER CONTEXT (first section):
{ncert_text[:3000]}

WIKIPEDIA SUMMARY:
{wiki_summary[:500]}

Write a concise, engaging OVERVIEW for "{topic}" (~400 words).
  - What this topic is and why it matters for UPSC
  - Key constitutional/legal foundation (1-2 sentences)
  - What subtopics this chapter covers (as a list)
  - Exam relevance (Prelims/Mains)

Use Markdown. Start with: ## {topic}"""
    else:
        prompt = f"""You are writing an overview introduction for a UPSC study book chapter.

TOPIC: "{topic}"

WIKIPEDIA SUMMARY:
{wiki_summary[:800]}

Write a concise, engaging OVERVIEW for "{topic}" (~400 words).
  - What this topic is and why it matters for UPSC
  - Key constitutional/legal foundation (1-2 sentences)
  - What subtopics this chapter covers (as a list)
  - Exam relevance (Prelims/Mains)

Use Markdown. Start with: ## {topic}"""

    result = llm_call(prompt, mode="standard")
    return result or f"## {topic}\n\nOverview coming soon."


def _generate_subtopic_article(
    subtopic: str, parent_topic: str, ncert_section: str, wiki_content: str
) -> str:
    """
    Step 7 — The Gold Standard Article Generation.
    Generates a full-length (2000+ word) UPSC study article.

    Mode B (has NCERT section): NCERT as spine + Wiki as enricher
    Mode A (no NCERT section): Wikipedia as primary research material
    """
    if ncert_section and ncert_section.strip():
        # ── MODE B: NCERT-spined article (THE GOLD STANDARD) ─────────────────
        prompt = f"""You are a senior UPSC educator writing a comprehensive chapter
for a premium UPSC study platform. Your writing is thorough, factual, and exam-focused.

TOPIC TO WRITE: "{subtopic}"
(This is a subtopic under "{parent_topic}")

═══════════════════════════════════════════════════════
PRIMARY SOURCE — NCERT (the factual, exam-verified spine):
───────────────────────────────────────────────────────
{ncert_section}
═══════════════════════════════════════════════════════

═══════════════════════════════════════════════════════
ENRICHMENT SOURCE — Wikipedia (for depth, history, recency):
───────────────────────────────────────────────────────
{wiki_content}
═══════════════════════════════════════════════════════

CONTENT RULES (non-negotiable):
1. START with the NCERT definition/framing if it is precise for this topic.
   If NCERT's phrasing is clear and authoritative — use it verbatim as the opening.
2. EXPAND with Wikipedia: add historical context, case laws, amendments,
   international comparisons, post-NCERT developments.
3. Where both sources cover the same fact — write it ONCE only (no duplication).
   Merge and state it in the most complete way.
4. If Wikipedia has important information NOT in NCERT — include it fully,
   in a clearly marked section "### Recent Developments / Post-NCERT Updates".
5. Proportional scaling: The length of this article must scale proportionally to the source material depth. Do not hallucinate or add fluff to hit artificial word counts. An exhaustive 500-word topic should simply be 500 words. A vast 3000-word topic should be treated comprehensively.
6. Every constitutional article cited must have its exact number (e.g., Article 110).
7. Be specific: years, case names, committee names — no vague generalities.

MANDATORY FORMAT (use these exact section headings):
## {subtopic}

### Definition & Overview
[Precise definition. Start with NCERT phrasing if clear.]

### Constitutional / Legal Framework
[Exact Article numbers, relevant Acts, Schedules, Amendments]

### [Section 3 — choose the most logical title based on topic]

### [Section 4 — choose the most logical title based on topic]

### Historical Evolution & Key Milestones
[Timeline of important changes with years]

### Recent Developments (Post-NCERT) [only if Wikipedia has current info]
[Amendments, court rulings, policy changes after NCERT publication]

### Significance & Critical Analysis
[Why this matters; any debates or criticisms]

### Comparison / Summary Table [if applicable]
| Aspect | Details |
|--------|---------|
| ... | ... |

### UPSC Exam Perspective
| Aspect | Details |
|--------|---------|
| Prelims | [Topics & years asked if known] |
| Mains GS Paper | [Relevant paper and angle] |
| Keywords | [5-7 must-remember terms] |
| Common Mistakes | [What aspirants confuse] |"""

    else:
        # ── MODE A: Wikipedia-based article (no NCERT available) ─────────────
        prompt = f"""You are a senior UPSC educator writing a comprehensive chapter
for a premium UPSC study platform. Your writing is thorough, factual, and exam-focused.

TOPIC TO WRITE: "{subtopic}"
(This is a subtopic under "{parent_topic}")

═══════════════════════════════════════════════════════
RESEARCH MATERIAL — Wikipedia:
───────────────────────────────────────────────────────
{wiki_content}
═══════════════════════════════════════════════════════

CONTENT RULES (non-negotiable):
1. Use the Wikipedia content as your research material to write an ORIGINAL chapter.
2. Do NOT copy-paste Wikipedia text. Write in your expert voice as a UPSC educator.
3. Include everything relevant for UPSC — constitutional basis, historical context,
   examples, significance, current relevance.
4. Proportional scaling: The length of this article must scale proportionally to the source material depth. Do not hallucinate or add fluff to hit artificial word counts. An exhaustive 500-word topic should simply be ~500 words. A vast 3000-word topic should be treated comprehensively.
5. Every constitutional article must have its exact number.
6. Be specific: years, case names, committee names — no vague generalities.

MANDATORY FORMAT (use these exact section headings):
## {subtopic}

### Definition & Overview

### Constitutional / Legal Framework
[Exact Article numbers, relevant Acts, Schedules]

### [Section 3 — choose the most logical title based on topic]

### [Section 4 — choose the most logical title based on topic]

### Historical Evolution & Key Milestones

### Significance & Critical Analysis

### Comparison / Summary Table [if applicable]

### UPSC Exam Perspective
| Aspect | Details |
|--------|---------|
| Prelims | |
| Mains GS Paper | |
| Keywords | |
| Common Mistakes | |"""

    result = llm_call(prompt, mode="writer")
    if not result or len(result.strip()) < 100:
        log_warning(
            f"  ⚠️  Article generation failed for '{subtopic}'. Empty placeholder set."
        )
        return f"## {subtopic}\n\n*Content generation failed. Will retry on next run.*"

    log_info(f"     └─ Article: {len(result.split())} words generated")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# DB HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def _get_or_create_node(
    cur,
    label: str,
    node_type: str,
    level: int,
    content: str = "",
    source: str = "synthesized",
    pdf_source: str = "",
    word_count: int = 0,
    quality_score: float = 0.0,
) -> int:
    """
    Returns the ID of an existing node with this label+type,
    OR creates a new one and returns its ID.
    Safe for re-runs — never creates duplicate nodes.
    """
    cur.execute(
        "SELECT id FROM nodes WHERE label = %s AND type = %s", (label, node_type)
    )
    row = cur.fetchone()
    if row:
        log_info(f"     └─ Reusing existing node: '{label}' (ID: {row[0]})")
        return row[0]

    cur.execute(
        """INSERT INTO nodes
           (label, type, level, content_body, source, pdf_source,
            word_count, quality_score)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING id""",
        (
            label,
            node_type,
            level,
            content,
            source,
            pdf_source,
            word_count,
            quality_score,
        ),
    )
    new_id = cur.fetchone()[0]
    return new_id


def _create_edge(cur, source_id: int, target_id: int, relation: str = "contains"):
    """Creates a directed edge. ON CONFLICT DO NOTHING makes it safe for re-runs."""
    cur.execute(
        """INSERT INTO edges (source_id, target_id, relation)
           VALUES (%s, %s, %s)
           ON CONFLICT (source_id, target_id) DO NOTHING""",
        (source_id, target_id, relation),
    )


def _separator():
    log_info("━" * 55)
