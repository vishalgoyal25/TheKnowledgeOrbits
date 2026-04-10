"""
engines/daily_ca/services/wiki_enrichment_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase H — WikiEnrichmentService

Thin wrapper around the existing `engines/book_content/services/wiki_service.py`.
NO changes to wiki_service.py itself — it remains untouched.

Purpose:
  When a CA article's source chunks are thin (< 300 words total), the LLM
  doesn't have enough factual material to write a quality 450-700 word article.
  This service fetches Wikipedia context to fill that gap — zero GROQ calls,
  uses the Wikipedia API only.

  Called by DailyCaGeneratorService._run_single_cycle() as STEP 2:
    if len(ca_text.split()) < 300:
        wiki_data = WikiEnrichmentService.get_enrichment(topic_name)

  The returned dict is passed to build_ca_prompt() as `wiki_enrichment`.
  The LLM uses it as supplementary reference — NOT copied verbatim.

Output shape:
  {
    'intro':         str,       # Wikipedia intro paragraph (first ~500 chars of summary)
    'key_facts':     list[str], # Bullet facts extracted from the most relevant section
    'related_terms': list[str], # Titles of related Wikipedia articles (See Also style)
    'wiki_url':      str,       # Wikipedia URL for citation
  }
  OR empty dict {} if Wikipedia page not found (caller handles gracefully).
"""

import re

import sentry_sdk
import structlog

from engines.book_content.services.wiki_service import (
    extract_relevant_section,
    fetch_full_page,
)

logger = structlog.get_logger(__name__)

# Max chars of Wikipedia content to analyse for fact extraction
_MAX_SECTION_CHARS = 2000

# Max bullet facts to return (keep the prompt concise)
_MAX_KEY_FACTS = 6

# Max related terms to return
_MAX_RELATED_TERMS = 5

# Pattern for extracting See Also / related page links from Wikipedia content
_SEE_ALSO_PATTERN = re.compile(
    r"(?:==\s*See also\s*==)(.*?)(?:==|\Z)", re.IGNORECASE | re.DOTALL
)

# Bullet-like lines in Wikipedia plain text (after section extraction)
_BULLET_LINE = re.compile(r"^\s*[-*•]\s+(.+)$", re.MULTILINE)

# Sentence splitter — used to turn a paragraph into extractable facts
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _extract_key_facts(section_text: str) -> list[str]:
    """
    Extracts short factual statements from a Wikipedia section.

    Strategy:
      1. Try to find bullet-like lines (some Wikipedia sections use them)
      2. Fall back to first N sentences of the section if no bullets found

    Returns list of strings, each ≤ 200 chars.
    """
    # Strategy 1: bullet lines
    bullets = [
        m.group(1).strip()
        for m in _BULLET_LINE.finditer(section_text)
        if len(m.group(1).strip()) > 20
    ]
    if bullets:
        return [b[:200] for b in bullets[:_MAX_KEY_FACTS]]

    # Strategy 2: first N sentences
    sentences = _SENTENCE_SPLIT.split(section_text.strip())
    facts = []
    for s in sentences:
        clean = s.strip()
        if len(clean) > 30:
            facts.append(clean[:200])
        if len(facts) >= _MAX_KEY_FACTS:
            break
    return facts


def _extract_related_terms(wiki_content: str) -> list[str]:
    """
    Extracts related topic names from the 'See Also' section of a Wikipedia article.
    Falls back to empty list if no See Also section exists.
    """
    match = _SEE_ALSO_PATTERN.search(wiki_content)
    if not match:
        return []

    see_also_text = match.group(1)
    # Wikipedia See Also lines are typically bare topic names on each line
    lines = [
        line.strip()
        for line in see_also_text.splitlines()
        if line.strip() and not line.strip().startswith("=")
    ]
    return [l[:100] for l in lines[:_MAX_RELATED_TERMS]]


class WikiEnrichmentService:
    """
    Fetches supplementary Wikipedia context for thin CA source articles.

    Usage:
        wiki_data = WikiEnrichmentService.get_enrichment("Fast Breeder Reactor")
        # Returns dict with intro, key_facts, related_terms, wiki_url
        # Returns {} if Wikipedia page not found
    """

    @staticmethod
    def get_enrichment(topic_name: str) -> dict:
        """
        Fetches and structures Wikipedia data for a topic.

        Uses fetch_full_page() → tries topic_name, then "{topic_name} India" fallback.
        Extracts the most relevant section using extract_relevant_section().
        Returns structured dict for injection into CA_DAILY_PROMPT as SUPPLEMENTARY REFERENCE.

        Returns empty dict {} on any failure — caller handles gracefully with "Not available."
        """
        if not topic_name or not topic_name.strip():
            return {}

        try:
            # Fetch full Wikipedia page (handles disambiguation + India fallback internally)
            wiki_result = fetch_full_page(topic_name.strip())

            if not wiki_result.get("found"):
                logger.info(
                    "wiki_enrichment_not_found",
                    topic_name=topic_name,
                )
                return {}

            full_content = wiki_result["content"]
            summary = wiki_result["summary"]
            url = wiki_result["url"]

            # Intro: first ~500 chars of Wikipedia's own summary paragraph
            intro = summary[:500].strip() if summary else ""

            # Most relevant section for fact extraction
            relevant_section = extract_relevant_section(
                wiki_content=full_content,
                subtopic=topic_name,
                max_chars=_MAX_SECTION_CHARS,
            )

            key_facts = _extract_key_facts(relevant_section)
            related_terms = _extract_related_terms(full_content)

            result = {
                "intro": intro,
                "key_facts": key_facts,
                "related_terms": related_terms,
                "wiki_url": url,
            }

            logger.info(
                "wiki_enrichment_success",
                topic_name=topic_name,
                wiki_title=wiki_result["title"],
                intro_chars=len(intro),
                key_facts_count=len(key_facts),
                related_terms_count=len(related_terms),
            )
            return result

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "wiki_enrichment_failed",
                topic_name=topic_name,
                error=str(exc)[:200],
            )
            return {}
