"""
src/quality_engine.py
━━━━━━━━━━━━━━━━━━━━━
LAYER 2: Writing Quality Engine

Contains:
  1. The master writing prompt builder (with craft instructions)
  2. Section-by-section generation orchestrator
  3. Self-critique and refinement pass
  4. Quality score calculator

This replaces the simple _generate_subtopic_article() in ingestor.py.
"""

import json
from src.llm_client import llm_call, log_info, log_warning


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
    with self-critique pass.

    Returns:
        (article_markdown: str, quality_score: float)
    """
    log_info(f"  ✍️  Quality Engine: generating article for '{subtopic}'...")

    # Step 1: Generate section by section
    sections = _generate_sections(
        subtopic, parent_topic, ncert_section, wiki_content, previously_covered
    )
    article_draft = _assemble_article(subtopic, sections)

    # Step 2: Self-critique pass
    log_info("     └─ Running self-critique pass...")
    critique_result = _run_critique(subtopic, article_draft)
    quality_score = critique_result.get("score", 0.0)

    # Step 3: If quality < 65, run targeted refinement on weak sections
    if quality_score < 65.0:
        log_info(f"     └─ Quality {quality_score:.0f}/100 — running refinement...")
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

    log_info(
        f"     └─ Final quality: {quality_score:.0f}/100 | "
        f"{len(article_draft.split())} words"
    )

    return article_draft, quality_score


# ── SECTION-BY-SECTION GENERATOR ─────────────────────────────────────────────


def _generate_sections(
    subtopic: str,
    parent_topic: str,
    ncert_section: str,
    wiki_content: str,
    previously_covered: str,
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
        )

        section_content = llm_call(prompt, mode="writer")

        if section_content and len(section_content.strip()) > 50:
            sections[section_id] = f"{heading}\n\n{section_content.strip()}"
            article_so_far += f"\n\n{sections[section_id]}"
        else:
            log_warning(f"     └─ Section '{section_id}' generation failed or empty.")
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

    return f"""You are a senior author writing "{subtopic}" — a chapter in a
comprehensive UPSC study book on "{parent_topic}".
Your writing must match the precision and depth of M. Laxmikanth's Indian Polity.

{MASTER_STYLE_ANCHOR}

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
