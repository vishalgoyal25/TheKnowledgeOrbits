"""
engines/tags/services/concept_content_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase G (FEATURES3) — Concept Page full content generation service.

One public method: ConceptContentService.generate_concept_content(concept) → bool

Generates a 450–600 word encyclopaedic article for a ConceptPage stub.
Sets is_content_ready=True and locks the content permanently after generation.

Design rules enforced here:
  - NEVER regenerates a concept where is_content_ready=True (locked permanently)
  - 1 GROQ call per concept in 'writer' mode (high token limit, low temperature)
  - Word count enforced: min 200 chars to accept, hard-trim at 700 words
  - Context enriched with titles of CA articles that link to this concept (up to 5)
  - No UPSC language, no exam notes, no tables — pure encyclopaedic prose
  - All exceptions captured to Sentry + structlog; never propagated to caller
  - INTER_CALL_SLEEP already applied inside llm_call() — no extra sleep needed here

Three-entity rule (never confuse these):
  Tag          → article label    → /tags/[slug]     → aggregation page
  ConceptPage  → inline deep-link → /concepts/[slug] → concept detail page
  BookContent  → syllabus topic   → /learn/[slug]    → structured article
"""

import sentry_sdk
import structlog

from engines.book_content.services.llm_service import llm_call
from engines.tags.models import ConceptArticleLink, ConceptPage

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

2. BODY (3–5 sections with ## headings):
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
   Leave a blank line between paragraphs.

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

6. LENGTH: 450 to 600 words. Hard maximum: 650 words.
   Quality over quantity — a tight 450-word entry beats a padded 600-word one.

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


# ── Service ────────────────────────────────────────────────────────────────────


class ConceptContentService:
    """
    Generates full body_md content for ConceptPage stubs.

    Designed to be called from the generate_concept_content management command
    (batch mode) or directly for a single concept (admin/debug mode).
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
                      Use ONLY for admin override — single concept refresh.

        Returns:
            True  — content generated and saved successfully.
            False — skipped (already ready and force=False) or generation failed.
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

        # ── Build and fire prompt ─────────────────────────────────────────────
        prompt = CONCEPT_CONTENT_PROMPT.format(
            concept_name=concept.name,
            linked_article_titles=linked_context,
            brief_description=concept.brief_description or "Not available.",
        )

        try:
            # mode="standard" → max_tokens=2048, sufficient for 450–600 word output.
            # mode="writer" → max_tokens=16384 which exceeds Groq free-tier per-request
            # limit (8192 total tokens) and causes HTTP 413 Payload Too Large.
            raw = llm_call(prompt, mode="standard")
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "concept_content_llm_call_failed",
                slug=concept.slug,
                error=str(exc),
            )
            return False

        if not raw or len(raw.strip()) < 200:
            logger.warning(
                "concept_content_empty_response",
                slug=concept.slug,
                response_length=len(raw.strip()) if raw else 0,
            )
            return False

        # ── Word count guard ──────────────────────────────────────────────────
        words = raw.split()
        word_count = len(words)
        if word_count > 700:
            # Hard-trim to keep concept pages tight
            raw = " ".join(words[:700])
            logger.info(
                "concept_content_trimmed",
                slug=concept.slug,
                original_words=word_count,
                trimmed_to=700,
            )

        # ── Markdown normalisation ────────────────────────────────────────────
        # LLMs occasionally return headings with a single \n before them instead
        # of the blank line (\n\n) that markdown requires for block rendering.
        # Normalise here so the stored body_md always renders correctly.
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        # Blank line before ## / ### headings
        import re as _re

        raw = _re.sub(r"([^\n])\n(#{1,3} )", r"\1\n\n\2", raw)
        # Blank line after ## / ### headings before body text
        raw = _re.sub(r"(#{1,3} [^\n]+)\n([^#\n])", r"\1\n\n\2", raw)
        # Collapse 3+ blank lines to 2
        raw = _re.sub(r"\n{3,}", "\n\n", raw).strip()

        # ── Save and lock ─────────────────────────────────────────────────────
        try:
            concept.body_md = raw
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
            word_count=word_count,
            had_linked_context=bool(linked_titles),
        )
        return True
