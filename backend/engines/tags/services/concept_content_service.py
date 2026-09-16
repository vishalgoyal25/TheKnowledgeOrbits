"""
engines/tags/services/concept_content_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase G (FEATURES3) — Concept Page full content generation service.
G3.11 (2026-09-16) — quality gate: a draft is saved as ready ONLY when it passes
the same rule the sitemap uses to list a page.

One public method: ConceptContentService.generate_concept_content(concept) → bool

Generates a 500–700 word encyclopaedic article for a ConceptPage stub.
Sets is_content_ready=True and locks the content after generation.

Design rules enforced here:
  - NEVER regenerates a concept where is_content_ready=True unless force=True
    (G3.12 uses force to rewrite thin pages in place)
  - 1 LLM call per concept, plus AT MOST one corrective retry when the draft
    fails the gate — the retry carries the measured failure back to the model
  - GATE (concept_seo_service.quality_issues): >= 400 words, >= 3 `##`
    headings, <= 900 words, real line breaks. A draft that still fails after
    the retry is REJECTED — the row is left exactly as it was (a stub stays a
    stub, a thin page stays thin) and `concept_content_rejected` is logged.
    This is what makes the G0.3 "thin" count unable to grow (G3.11 exit).
  - Over-long drafts are trimmed by PARAGRAPH, never by word — the old
    `" ".join(words[:700])` destroyed every newline and therefore every
    heading, which is one way the zero-heading pages were made (§4.3 d)
  - Context enriched with titles of CA articles that link to this concept (up to 5)
  - No UPSC language, no exam notes, no tables — pure encyclopaedic prose
  - All exceptions captured to Sentry + structlog; never propagated to caller
  - INTER_CALL_SLEEP already applied inside llm_call() — no extra sleep needed here

Three-entity rule (never confuse these):
  Tag          → article label    → /tags/[slug]     → aggregation page
  ConceptPage  → inline deep-link → /concepts/[slug] → concept detail page
  BookContent  → syllabus topic   → /learn/[slug]    → structured article
"""

import re

import sentry_sdk
import structlog

from engines.book_content.services.llm_service import llm_call
from engines.tags.models import ConceptArticleLink, ConceptPage
from engines.tags.services.concept_seo_service import (
    MAX_WORDS,
    MIN_HEADINGS,
    MIN_WORDS,
    quality_issues,
    word_count,
)

logger = structlog.get_logger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────

CONCEPT_CONTENT_PROMPT = """You are an encyclopaedic reference writer creating a permanent knowledge page \
for a premier educational platform. Write for a curious, educated reader — \
not for an exam. Your standard: a high-quality encyclopedia entry that any \
well-read person would find genuinely informative and worth bookmarking.

CONCEPT: {concept_name}

CONTEXT (titles of articles that have referenced this concept — use for relevance cues only):
{linked_article_titles}

EXISTING BRIEF DESCRIPTION (expand on this, do NOT merely repeat it):
{brief_description}

────────────────────────────────────────────────────────────────────────────────
WRITING INSTRUCTIONS:

1. OPENING (1 paragraph):
   What is this? Define it precisely and concisely.
   Lead with what makes this concept specifically significant or unique.
   Do NOT start with "This concept..." or "In India..." — open with the concept itself.

2. BODY (3–5 sections, EACH under its own "## " heading — at least 3 headings):
   Choose headings based on what THIS SPECIFIC CONCEPT requires. Use headings such as:
   - "Origins / Historical Background"  — for constitutional provisions, landmark cases, Acts
   - "How It Works / Mechanism"         — for schemes, policies, technical processes
   - "Key Provisions"                   — for Acts and laws (include actual provision numbers)
   - "India's Journey"                  — for evolving policy or institutional history
   - "International Comparison"         — only where genuinely informative and relevant
   - "Current Status / Implementation"  — for concepts with an ongoing story
   - "Significance"                     — for concepts where the "so what" is non-obvious
   Select only those headings that are GENUINELY relevant — do not force all of them.

3. PARAGRAPH STRUCTURE:
   Each ## section: 2–3 paragraphs. Each paragraph: 3–5 sentences.
   Never write a single dense block for an entire section.
   Leave a blank line between paragraphs and before every heading.

4. FACTUAL DENSITY:
   Include actual numbers, dates, article numbers, named provisions, and named
   officials/institutions where factually accurate.
   Every sentence should contain at least one concrete, specific piece of information.
   Do NOT pad with vague generalisations ("This is very important for national development").

5. DATA INTEGRITY (non-negotiable):
   State only facts you are confident are accurate.
   If uncertain about a specific figure or date, use directional language:
     ✓ "India ranks among the world's top five producers..."
     ✗ "India produces 42.7 million tonnes annually..." (if you are guessing the figure)
   NEVER invent statistics, names, dates, or legal provisions not in your training knowledge.

6. LENGTH: 500 to 700 words. Hard maximum: 800 words. Never fewer than 450.
   Quality over quantity — a tight 500-word entry beats a padded 700-word one.

7. TONE: Factual, precise, intellectually engaging. Not dry. Not exam-note style.
   Write as if explaining to a well-read colleague encountering the topic for the first time.

8. DO NOT INCLUDE:
   - Any mention of UPSC, exam, aspirants, GS paper, Mains, Prelims, or civil services
   - Practice questions, answer hints, or "Important for..." labels
   - Generic closing sentences like "This is a key topic to watch" or "In conclusion..."
   - Markdown tables (prose and bullet lists only — tables break concept page layout)
   - ### sub-headings (use ## only for section headings)
   - Callout boxes or special markdown blocks
   - The title as a heading (start directly with the opening paragraph)

OUTPUT: Return ONLY the article markdown — no preamble, no meta-commentary, \
no "Here is the article:" prefix.
"""

# Appended to the prompt on the single retry, carrying the measured failure.
RETRY_SUFFIX = """

────────────────────────────────────────────────────────────────────────────────
YOUR PREVIOUS DRAFT WAS REJECTED: {issues}.
Rewrite it in full. It MUST have at least {min_words} words and at most {max_words}, \
at least {min_headings} sections each starting with "## " on its own line, and a \
blank line between every paragraph. Real line breaks — never a single line.
"""


# ── Markdown shaping (pure functions) ─────────────────────────────────────────


def normalise_markdown(raw: str) -> str:
    """
    LLMs occasionally return headings with a single \\n before them instead of
    the blank line (\\n\\n) that markdown requires for block rendering.
    Normalise so the stored body_md always renders correctly.
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    # Blank line before ## / ### headings
    text = re.sub(r"([^\n])\n(#{1,3} )", r"\1\n\n\2", text)
    # Blank line after ## / ### headings before body text
    text = re.sub(r"(#{1,3} [^\n]+)\n([^#\n])", r"\1\n\n\2", text)
    # Collapse 3+ blank lines to 2
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def trim_to_paragraphs(text: str, max_words: int = MAX_WORDS) -> str:
    """
    Drop trailing paragraphs until the body fits `max_words`. Paragraph
    boundaries are kept intact, so headings and line breaks survive — the
    property the old word-join trim destroyed.
    """
    if word_count(text) <= max_words:
        return text
    paragraphs = text.split("\n\n")
    while len(paragraphs) > 1 and word_count("\n\n".join(paragraphs)) > max_words:
        paragraphs.pop()
    return "\n\n".join(paragraphs).strip()


# ── Service ────────────────────────────────────────────────────────────────────


class ConceptContentService:
    """
    Generates full body_md content for ConceptPage stubs.

    Designed to be called from the generate_concept_content management command
    (batch mode), the regenerate_concept_content command (G3.12, force=True) or
    directly for a single concept (admin/debug mode).
    """

    @staticmethod
    def generate_concept_content(
        concept: ConceptPage,
        db_alias: str = "default",
        force: bool = False,
    ) -> bool:
        """
        Generates full body_md for a ConceptPage stub.

        Args:
            concept:  The ConceptPage instance to generate content for.
            db_alias: DB alias to query ConceptArticleLink context from.
            force:    If True, regenerate even when is_content_ready=True.
                      G3.12 regeneration and admin override.

        Returns:
            True  — content generated, passed the gate and saved.
            False — skipped (already ready and force=False), rejected by the
                    gate (row untouched), or generation failed.
        """
        if concept.is_content_ready and not force:
            logger.info(
                "concept_content_already_ready",
                slug=concept.slug,
                name=concept.name,
            )
            return False

        # ── Build context: titles of CA articles linking to this concept ─────
        # NOTE: ConceptArticleLink.daily_ca_article_id is a plain UUIDField (not FK).
        # Django cannot traverse it with __ — must do a two-step query.
        try:
            article_ids = list(
                ConceptArticleLink.objects.using(db_alias)
                .filter(concept_page=concept)
                .values_list("daily_ca_article_id", flat=True)[:5]
            )
            linked_titles: list[str] = []
            if article_ids:
                from engines.daily_ca.models import DailyCaArticle

                linked_titles = list(
                    DailyCaArticle.objects.using(db_alias)
                    .filter(id__in=article_ids)
                    .values_list("title", flat=True)
                )
        except Exception as exc:
            # ConceptArticleLink context is best-effort — proceed without it
            sentry_sdk.capture_exception(exc)
            logger.warning(
                "concept_content_context_fetch_failed",
                slug=concept.slug,
                error=str(exc),
            )
            linked_titles = []

        linked_context = (
            "\n".join(f"- {t}" for t in linked_titles if t) or "No linked articles yet."
        )

        prompt = CONCEPT_CONTENT_PROMPT.format(
            concept_name=concept.name,
            linked_article_titles=linked_context,
            brief_description=concept.brief_description or "Not available.",
        )

        # ── Generate, gate, retry once ────────────────────────────────────────
        body = ""
        issues: list[str] = ["no draft"]
        for attempt in (1, 2):
            try:
                # mode="standard" → max_tokens=2048, sufficient for 500–700 words.
                # mode="writer" → 16384 exceeds Groq's per-request cap → HTTP 413.
                raw = llm_call(prompt, mode="standard")
            except Exception as exc:
                sentry_sdk.capture_exception(exc)
                logger.error(
                    "concept_content_llm_call_failed",
                    slug=concept.slug,
                    attempt=attempt,
                    error=str(exc),
                )
                return False

            if not raw or len(raw.strip()) < 200:
                logger.warning(
                    "concept_content_empty_response",
                    slug=concept.slug,
                    attempt=attempt,
                    response_length=len(raw.strip()) if raw else 0,
                )
                return False

            body = trim_to_paragraphs(normalise_markdown(raw))
            issues = quality_issues(body)
            if not issues:
                break

            logger.warning(
                "concept_content_gate_failed",
                slug=concept.slug,
                attempt=attempt,
                issues=issues,
                words=word_count(body),
            )
            prompt = CONCEPT_CONTENT_PROMPT.format(
                concept_name=concept.name,
                linked_article_titles=linked_context,
                brief_description=concept.brief_description or "Not available.",
            ) + RETRY_SUFFIX.format(
                issues="; ".join(issues),
                min_words=MIN_WORDS,
                max_words=MAX_WORDS,
                min_headings=MIN_HEADINGS,
            )

        if issues:
            # G3.11: never save a body that the sitemap would refuse to list.
            logger.warning(
                "concept_content_rejected",
                slug=concept.slug,
                name=concept.name,
                issues=issues,
                was_ready=concept.is_content_ready,
            )
            return False

        # ── Save and lock ─────────────────────────────────────────────────────
        try:
            concept.body_md = body
            concept.is_content_ready = True
            concept.save(update_fields=["body_md", "is_content_ready", "updated_at"])
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "concept_content_save_failed",
                slug=concept.slug,
                error=str(exc),
            )
            return False

        logger.info(
            "concept_content_generated",
            slug=concept.slug,
            name=concept.name,
            word_count=word_count(body),
            regenerated=force,
            had_linked_context=bool(linked_titles),
        )
        return True
