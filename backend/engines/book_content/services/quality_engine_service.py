"""
engines/book_content/services/quality_engine_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAYER 2: Writing Quality Engine

Contains:
  1. The master writing prompt builder (with craft instructions)
  2. Section-by-section generation orchestrator
  3. Self-critique and refinement pass
  4. Quality score calculator
  5. Phase 4.5B: Formatting pass (tables, callouts, infographic markers)
  6. Phase 4.5C: Adaptive subject personas (SUBJECT_PROFILES)

This replaces the simple _generate_subtopic_article() in ingestor.py.
Ported from: upsc-agent-lab/src/quality_engine.py
Changes: logging (structlog), imports, added SUBJECT_PROFILES, added
         _run_formatting_pass(), subject param injected into _build_section_prompt().
Preserved exactly: MASTER_STYLE_ANCHOR, SECTION_PLAN (all 6 sections),
                   _generate_sections(), _run_critique(), _refine_weak_sections(),
                   _assemble_article(), _parse_critique_json().
"""

import json
import re

import structlog

from .llm_service import llm_call

logger = structlog.get_logger(__name__)


# ── MASTER STYLE ANCHOR ───────────────────────────────────────────────────────
# This is injected into every single generation prompt.
# It is the most important change in the entire upgrade.

MASTER_STYLE_ANCHOR = """
WRITING STYLE — NON-NEGOTIABLE RULES:

PRECISION OVER PADDING:
  ✅ "The President is elected by an electoral college consisting of elected members
      of both Houses of Parliament and elected members of Legislative Assemblies
      of all States and UTs of Delhi and Puducherry." (Article 54)
  ❌ "The President is elected through a special process involving Parliament members
      and state representatives."
  Rule: Every sentence must carry maximum information. Zero filler words.

SPECIFICITY IS MANDATORY:
  ✅ Name exact Articles (Article 110, Article 368, Article 356)
  ✅ Name exact Acts (Representation of the People Act 1951)
  ✅ Name exact committees (Swaran Singh Committee, 1976)
  ✅ Name exact case laws (Kesavananda Bharati v State of Kerala, 1973)
  ✅ Name exact years (42nd Amendment, 1976; 44th Amendment, 1978)
  ❌ "Constitutional amendments have changed this over time"
  ❌ "Many committees have examined this issue"
  ❌ "Several landmark judgments have shaped this area"

WRITING FOR PREPARED ASPIRANTS (not beginners):
  - Assume the reader knows basic civics
  - Do NOT explain what a constitution is, what democracy means
  - DO explain nuances, exceptions, controversies, and comparisons
  - Write at the level of a Class 12 student who has read NCERT once

ACTIVE, DIRECT SENTENCES:
  ✅ "Parliament exercises sovereign legislative authority over the Union List."
  ❌ "It can be seen that Parliament has been given the authority to make laws
      in relation to subjects that are there in the Union List."

NO HEDGING:
  ❌ "It may be noted that...", "It is important to understand that..."
  ❌ "As we know...", "Needless to say...", "Of course..."
  ✅ Just state the fact directly.

TABLES: Use only when comparison genuinely adds value.
  Good table: Lok Sabha vs Rajya Sabha (direct comparison, same attributes)
  Bad table: Single-column list disguised as a table
"""


# ── SECTION TEMPLATES ─────────────────────────────────────────────────────────
# Each subtopic article has these sections.
# Generated ONE BY ONE (not all at once) for deeper content per section.

SECTION_PLAN = [
    {
        "id": "definition",
        "heading": "### Definition & Constitutional Basis",
        "instruction": """Write the precise definition of {subtopic}.
Start with the exact NCERT definition if available (verbatim).
Then state the exact constitutional basis: Article number, Schedule, or Act.
Length: 150-250 words. No padding. Every sentence = information.""",
    },
    {
        "id": "framework",
        "heading": "### Constitutional & Legal Framework",
        "instruction": """List and explain ALL constitutional provisions, Articles,
Acts, and Schedules relevant to {subtopic}.
For EACH Article: state the number, what it says, and its practical significance.
Include any relevant Constitutional Amendments with year and effect.
Format as a structured explanation, NOT a bullet dump.
Length: 200-400 words depending on complexity.""",
    },
    {
        "id": "composition_powers",  # Renamed per topic by LLM
        "heading": "### [Composition / Powers / Structure — choose most logical heading]",
        "instruction": """Write the core substantive section on {subtopic}.
This is the main content section — the most detailed part.
Cover: composition OR powers OR structure OR process (whichever applies).
Use numbered lists only when order matters. Use prose for explanations.
Be exhaustive — a serious aspirant must find everything they need here.
Length: 300-600 words.""",
    },
    {
        "id": "evolution",
        "heading": "### Historical Evolution & Key Milestones",
        "instruction": """Write a chronological account of how {subtopic} evolved.
Include:
  - Pre-constitutional background (if relevant)
  - Original constitutional provision at 1950
  - Each significant amendment with year and effect
  - Key Supreme Court judgments with case name, year, and ruling
  - Recent developments (post-2015 if any)
Format: Flowing prose with years clearly embedded. Not a bare bullet list.
Length: 200-350 words.""",
    },
    {
        "id": "significance",
        "heading": "### Significance, Debates & Critical Analysis",
        "instruction": """Analyze {subtopic} critically.
Cover:
  - Why this institution/provision/concept matters constitutionally
  - Any ongoing debates or controversies (anti-defection loopholes, etc.)
  - Comparison with similar systems in other democracies IF relevant
  - Committee recommendations that were accepted or rejected
  - Any reform proposals (Law Commission reports, etc.)
Do NOT be neutral to the point of vagueness. Present real debates.
Length: 200-300 words.""",
    },
    {
        "id": "upsc_angle",
        "heading": "### UPSC Exam Perspective",
        "instruction": """Write the UPSC-specific exam guide for {subtopic}.
Format as a table:
| Aspect | Details |
|--------|---------|
| Prelims Focus | [Specific facts, numbers, years asked in Prelims] |
| Mains GS Paper | [Which paper, which question type, what angle] |
| Previous Year Questions | [At least 2-3 actual PYQ phrasings if known] |
| High-Yield Keywords | [5-8 exact terms aspirants must know] |
| Common Mistakes | [What aspirants confuse or get wrong] |
| Related Topics | [2-3 other topics to link for integrated answers] |""",
    },
]


# ── SUBJECT PROFILES (Phase 4.5C — Adaptive Subject Personas) ────────────────
# Injected after MASTER_STYLE_ANCHOR when subject matches.
# Gives each subject a distinct voice and emphasis pattern.

SUBJECT_PROFILES = {
    "Indian Constitution & Polity": {
        "tone": "authoritative, precise, legislative",
        "emphasis": "exact Article numbers, landmark judgments, constitutional provisions",
        "structure": "definition → framework → evolution → criticism → UPSC angle",
        "avoid": "narrative storytelling, emotional language",
        "example_voice": "Article 352 empowers the President to proclaim...",
    },
    "History": {
        "tone": "narrative, chronological, personality-driven",
        "emphasis": "cause-effect chains, key personalities, turning points",
        "structure": "context → events → key figures → impact → legacy",
        "avoid": "dry legalistic tone, bullet-point overload",
        "example_voice": "The fateful year of 1857 saw the first major...",
    },
    "Ethics, Integrity & Aptitude": {
        "tone": "reflective, philosophical, case-study driven",
        "emphasis": "ethical dilemmas, thinker quotes, real-world cases",
        "structure": "concept → thinkers → case study → application → UPSC angle",
        "avoid": "purely factual recitation, legalistic tone",
        "example_voice": "Consider the ethical implications when a civil servant...",
    },
    "Economy & Finance": {
        "tone": "analytical, data-aware, policy-focused",
        "emphasis": "statistics, policy comparisons, budget references",
        "structure": "concept → data → policy → impact → reform → UPSC angle",
        "avoid": "abstract philosophy, narrative-heavy prose",
        "example_voice": "India's GDP growth rate of 7.2% in FY24 reflects...",
    },
    "Geography": {
        "tone": "spatial, descriptive, pattern-focused",
        "emphasis": "maps (conceptual), regional patterns, physical processes",
        "structure": "phenomenon → process → distribution → India-specific → UPSC angle",
        "avoid": "purely historical narrative, excessive legal citations",
        "example_voice": "The Western Ghats, running 1600 km along the coast...",
    },
}


# ── MAIN GENERATION FUNCTION ──────────────────────────────────────────────────


def generate_quality_article(
    subtopic: str,
    parent_topic: str,
    ncert_section: str,
    wiki_content: str,
    previously_covered: str = "",
    subject: str = "",
) -> tuple[str, float]:
    """
    LAYER 2 MAIN FUNCTION.
    Generates a high-quality article using section-by-section approach
    with self-critique pass, then formatting pass.

    Returns:
        (article_markdown: str, quality_score: float)
    """
    logger.info("quality_engine_start", subtopic=subtopic, subject=subject)

    # Step 1: Generate section by section
    sections = _generate_sections(
        subtopic, parent_topic, ncert_section, wiki_content, previously_covered, subject
    )
    article_draft = _assemble_article(subtopic, sections)

    # Step 2: Self-critique pass
    logger.info("quality_engine_critique_start", subtopic=subtopic)
    critique_result = _run_critique(subtopic, article_draft)
    quality_score = critique_result.get("score", 0.0)

    # Step 3: If quality < 65, run targeted refinement on weak sections
    if quality_score < 65.0:
        logger.info(
            "quality_engine_refinement_start",
            subtopic=subtopic,
            score=quality_score,
        )
        article_draft = _refine_weak_sections(
            subtopic,
            article_draft,
            critique_result.get("weak_sections", []),
            ncert_section,
            wiki_content,
        )
        # Re-score after refinement
        critique_result = _run_critique(subtopic, article_draft)
        quality_score = critique_result.get("score", 0.0)

    # Step 4: Phase 4.5B — Formatting pass (tables, callouts, infographic markers)
    article_draft = _run_formatting_pass(subtopic, article_draft)

    logger.info(
        "quality_engine_done",
        subtopic=subtopic,
        quality_score=quality_score,
        word_count=len(article_draft.split()),
    )

    return article_draft, quality_score


# ── SECTION-BY-SECTION GENERATOR ─────────────────────────────────────────────


def _generate_sections(
    subtopic: str,
    parent_topic: str,
    ncert_section: str,
    wiki_content: str,
    previously_covered: str,
    subject: str = "",
) -> dict:
    """Generates each section independently for deeper content."""
    sections = {}
    article_so_far = ""

    for section_def in SECTION_PLAN:
        section_id = section_def["id"]
        heading = section_def["heading"]
        instruction = section_def["instruction"].format(subtopic=subtopic)

        prompt = _build_section_prompt(
            subtopic=subtopic,
            parent_topic=parent_topic,
            ncert_section=ncert_section,
            wiki_content=wiki_content,
            previously_covered=previously_covered,
            section_heading=heading,
            section_instruction=instruction,
            article_so_far=article_so_far,
            subject=subject,
        )

        section_content = llm_call(prompt, mode="writer")

        if section_content and len(section_content.strip()) > 50:
            sections[section_id] = f"{heading}\n\n{section_content.strip()}"
            article_so_far += f"\n\n{sections[section_id]}"
        else:
            logger.warning(
                "quality_engine_section_failed",
                section_id=section_id,
                subtopic=subtopic,
            )
            sections[section_id] = f"{heading}\n\n*Content pending.*"

    return sections


def _build_section_prompt(
    subtopic: str,
    parent_topic: str,
    ncert_section: str,
    wiki_content: str,
    previously_covered: str,
    section_heading: str,
    section_instruction: str,
    article_so_far: str,
    subject: str = "",
) -> str:
    """Builds the prompt for a single section."""

    sources_block = ""
    if ncert_section and ncert_section.strip():
        sources_block += f"""
PRIMARY SOURCE — NCERT (use this as your factual spine):
{ncert_section[:3000]}
"""
    if wiki_content and wiki_content.strip():
        sources_block += f"""
ENRICHMENT SOURCE — Wikipedia (add depth, history, recent developments):
{wiki_content[:3000]}
"""
    if not sources_block:
        sources_block = "(No source material available — use your expert knowledge.)"

    context_block = ""
    if previously_covered:
        context_block = f"\n{previously_covered}\n"

    continuity_block = ""
    if article_so_far.strip():
        # Only show last 500 chars of what's written so far to save tokens
        continuity_block = f"""
WHAT HAS BEEN WRITTEN SO FAR (maintain continuity, do NOT repeat):
...{article_so_far[-500:]}
"""

    # Phase 4.5C — inject subject persona after MASTER_STYLE_ANCHOR if available
    subject_persona_block = ""
    if subject and subject in SUBJECT_PROFILES:
        profile = SUBJECT_PROFILES[subject]
        subject_persona_block = f"""
SUBJECT PERSONA — {subject}:
  Tone:     {profile["tone"]}
  Emphasis: {profile["emphasis"]}
  Structure: {profile["structure"]}
  Avoid:    {profile["avoid"]}
  Voice example: "{profile["example_voice"]}"
"""

    return f"""You are a senior author writing "{subtopic}" — a chapter in a
comprehensive UPSC study book on "{parent_topic}".
Your writing must match the precision and depth of M. Laxmikanth's Indian Polity.

{MASTER_STYLE_ANCHOR}
{subject_persona_block}
{sources_block}
{context_block}
{continuity_block}

YOUR CURRENT TASK — Write this specific section:
{section_heading}

SECTION INSTRUCTIONS:
{section_instruction}

Write ONLY this section now. Do NOT write other sections.
Begin directly with the content (no preamble like "Here is the section..."):"""


def _assemble_article(subtopic: str, sections: dict) -> str:
    """Assembles all sections into the final article."""
    header = f"## {subtopic}\n"
    body = "\n\n".join(sections.values())
    return f"{header}\n{body}"


# ── SELF-CRITIQUE PASS ────────────────────────────────────────────────────────


def _run_critique(subtopic: str, article: str) -> dict:
    """
    Runs a self-critique on the generated article.
    Returns critique dict with score and weak sections.
    """
    prompt = f"""You are a strict UPSC content quality reviewer.
Review this article on "{subtopic}" and score it.

ARTICLE TO REVIEW:
{article[:4000]}

Rate on these criteria (0-20 each, total 100):
1. SPECIFICITY: Are Articles, Acts, case names, years all cited precisely?
2. DEPTH: Does it go beyond surface-level explanation?
3. UPSC RELEVANCE: Is exam angle clearly addressed?
4. NO VAGUENESS: Zero hedging phrases, zero filler sentences?
5. ACCURACY: Is constitutional information factually correct?

Return ONLY valid JSON:
{{
  "scores": {{
    "specificity": 0-20,
    "depth": 0-20,
    "upsc_relevance": 0-20,
    "no_vagueness": 0-20,
    "accuracy": 0-20
  }},
  "total_score": 0-100,
  "weak_sections": ["section heading that needs improvement"],
  "specific_gaps": ["specific missing fact or concept"],
  "verdict": "one sentence summary"
}}"""

    response = llm_call(prompt, mode="standard")
    result = _parse_critique_json(response)
    return result


def _refine_weak_sections(
    subtopic: str,
    article: str,
    weak_sections: list,
    ncert_section: str,
    wiki_content: str,
) -> str:
    """Rewrites identified weak sections with targeted prompts."""
    if not weak_sections:
        return article

    for section_heading in weak_sections[:2]:  # Max 2 refinements to save API calls
        prompt = f"""This section of a UPSC article on "{subtopic}" is weak.
Rewrite it to be more specific, precise, and exam-relevant.

{MASTER_STYLE_ANCHOR}

SECTION TO IMPROVE:
{section_heading}

SOURCE MATERIAL:
NCERT: {ncert_section[:2000] if ncert_section else "Not available"}
Wikipedia: {wiki_content[:2000] if wiki_content else "Not available"}

Rewrite ONLY this section. Begin directly with improved content:"""

        improved = llm_call(prompt, mode="writer")
        if improved and len(improved.strip()) > 100:
            # Replace the weak section in the article
            if section_heading in article:
                # Find and replace just this section
                idx = article.find(section_heading)
                next_heading_idx = article.find("\n###", idx + 1)
                if next_heading_idx == -1:
                    next_heading_idx = len(article)
                article = (
                    article[:idx]
                    + section_heading
                    + "\n\n"
                    + improved.strip()
                    + "\n\n"
                    + article[next_heading_idx:]
                )

    return article


# ── PHASE 4.5B: FORMATTING PASS ───────────────────────────────────────────────


def _run_formatting_pass(subtopic: str, article_md: str) -> str:
    """
    Phase 4.5B: Post-critique formatting pass.
    Runs SECTION BY SECTION — mirrors the SECTION_PLAN loop in _generate_sections()
    to keep each LLM call within API payload limits.

    Per-section calls (Criteria 2 & 3):
      Each call receives only that one section (capped at 2500 chars).
      CRITERION 2 — Comparison Potential: inline comparison table if ≥2 entities compared.
      CRITERION 3 — Logical Grouping: inline classification table if content groups cleanly.
      Infographic placeholders and UPSC callout boxes also injected per section.

    Final single call (Criterion 1):
      CRITERION 1 — Factual Density: generates ONLY the summary table from the
      first 4000 chars of the assembled article, then appends it ourselves.
      This mirrors _run_critique()'s article[:4000] cap.

    IF NO CRITERIA MET → section returned unchanged. No tables added.
    DATA SAFETY: Every table cell must trace to a sentence in the source section.
    """
    # Split article into header (## line) + individual ### sections
    parts = re.split(r"(?=\n### )", article_md)
    header = parts[0]
    section_parts = parts[1:]

    if not section_parts:
        # No ### sections found — fall back gracefully, skip formatting
        logger.info(
            "formatting_pass_skipped", subtopic=subtopic, reason="no_sections_found"
        )
        return article_md

    # ── Pass 1: per-section (Criteria 2 & 3 + infographics + callouts) ──────
    enhanced_sections = []
    for section_text in section_parts:
        enhanced = _format_single_section(subtopic, section_text.strip())
        enhanced_sections.append(enhanced)

    assembled = header + "\n" + "\n\n".join(enhanced_sections)

    # ── Pass 2: summary table (Criterion 1) — capped single call ────────────
    assembled = _add_summary_table(subtopic, assembled)

    if assembled and len(assembled.strip()) > len(article_md) * 0.5:
        logger.info("formatting_pass_done", subtopic=subtopic, enhanced=True)
        return assembled.strip()

    logger.info("formatting_pass_skipped", subtopic=subtopic, reason="output_too_short")
    return article_md


def _format_single_section(subtopic: str, section_text: str) -> str:
    """
    Checks a single ### section for Criterion 2 (comparison tables),
    Criterion 3 (classification tables), infographic placeholders, and
    UPSC callout boxes. Each call is bounded to section_text[:2500] —
    same bounding philosophy as ncert[:3000] / wiki[:3000] in _build_section_prompt().
    Returns the enhanced section, or original if no criteria met.
    """
    prompt = f"""You are a UPSC study material formatter.
Analyze the single section below from an article on "{subtopic}" and enhance it WHERE JUSTIFIED.

SECTION:
{section_text[:2500]}

EVALUATE THESE 2 CRITERIA FOR THIS SECTION ONLY:

CRITERION 2 — Comparison Potential:
  Does this section discuss ≥2 distinct entities on the same attributes
  (e.g., Lok Sabha vs Rajya Sabha, Fundamental Rights vs DPSP)?
  → If YES: Add a comparison table INLINE after both entities are discussed.
  Format:
  ### ⚖️ Comparative Analysis: [Entity A] vs [Entity B]
  | Feature | [Entity A] | [Entity B] |
  |---------|-----------|-----------|
  (Fill ONLY with facts present in the section above — no hallucination)

CRITERION 3 — Logical Grouping:
  Can this section's content be better presented as a classification table
  (e.g., types of emergencies, categories of bills, types of amendments)?
  → If YES: Add a categorization table INLINE within this section.
  Format:
  ### 📋 Classification: [Category Name]
  | Category | Description |
  |----------|-------------|
  (Fill ONLY with facts present in the section above — no hallucination)

ALSO — detect Visual Moments in this section and inject infographic placeholders:
  Use this syntax inline where a diagram/map/timeline would genuinely help:
  >[!infographic: "Description of what the image should show"]<

ALSO — inject UPSC callout boxes for critical exam-facing facts:
  > **💡 UPSC High-Yield Focus:** [Critical exam takeaway in 1-2 sentences]

RULES:
  - If NEITHER criterion is met → return the section UNCHANGED.
  - Do NOT add tables for the sake of adding them.
  - Every table cell must trace to a sentence in the section above.
  - Do NOT add any new facts, names, or data not present in the section.

Return the complete enhanced section (or unchanged section if no criteria met):"""

    result = llm_call(prompt, mode="writer")
    if result and len(result.strip()) > len(section_text) * 0.4:
        return result.strip()
    return section_text


def _add_summary_table(subtopic: str, article_md: str) -> str:
    """
    Criterion 1: Factual Density check.
    Asks the LLM to generate ONLY the summary table (or reply NO_TABLE).
    Uses article[:4000] as input — same cap as _run_critique().
    The table is appended to the full article by this function, not by the LLM,
    so the LLM never needs to echo back a large payload.
    """
    prompt = f"""You are a UPSC study material formatter.
Analyze the article excerpt below on "{subtopic}".

ARTICLE EXCERPT:
{article_md[:4000]}

TASK — Criterion 1: Does this article contain ≥5 dates, names, or specific powers/provisions?

→ If YES: Generate ONLY the summary revision table (nothing else, no preamble):
### 📊 Quick Revision: {subtopic}
| Aspect | Detail |
|--------|--------|
(8–12 rows of key facts ONLY from the excerpt above — no hallucination, no new data)

→ If NO: Reply with exactly the word: NO_TABLE

Rules: Every row must trace to a fact in the excerpt. Zero hallucination."""

    result = llm_call(prompt, mode="standard")

    if result and result.strip() and result.strip() != "NO_TABLE" and "|" in result:
        return article_md.rstrip() + "\n\n" + result.strip()

    return article_md


# ── JSON PARSER ───────────────────────────────────────────────────────────────


def _parse_critique_json(text: str) -> dict:
    """Parses critique JSON from LLM response."""
    for attempt in [
        text,
        text[text.find("{") : text.rfind("}") + 1] if "{" in text else "",
    ]:
        try:
            result = json.loads(attempt)
            if isinstance(result, dict):
                # Normalize score
                score = result.get("total_score", 0)
                if not score and "scores" in result:
                    score = sum(result["scores"].values())
                result["score"] = float(score)
                return result
        except Exception:
            pass
    return {"score": 60.0, "weak_sections": [], "specific_gaps": []}
