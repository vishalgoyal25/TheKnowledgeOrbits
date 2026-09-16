"""
engines/tags/services/concept_seo_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Which concept pages Google is told about — the ONE definition of "indexable",
and (G3.11) the ONE definition of "good enough to save".

WHY (G0.3 verdict, 2026-09-14 — FEATURES_GROWTH_STACK.md §4.3)
  2,438 concept pages exist. 1,065 are stubs (a brief, no body) and 555 of the
  full ones are thin — most are ~600 words with zero headings. Listing all of
  them would present Google with a domain that is ~2/3 thin auto-generated
  pages, and Google scores the domain. The audit's rule: list a concept only
  when it has a body of >= 400 words AND >= 3 headings. 818 qualified on the
  day; the rule is computed live so the ~20 new pages a day classify
  themselves.

WHERE IT IS USED
  - the sitemap feed  (/api/v1/concepts/sitemap/)      → which URLs to list
  - the detail payload (`is_indexable`)                → the page's own
    robots meta: noindex when False, so a stub or thin page reached via an
    internal link tells the crawler not to judge the site on it.
  - the generator (G3.11, `quality_issues`)            → a draft that fails is
    NOT saved as ready; the stub stays a stub and the thin count cannot grow.
  - the regeneration queue (G3.12, `needs_regeneration`) → which ready pages
    to rewrite in place.

`is_content_ready` alone is NOT the gate — a 28-word body carries it.
"""

from engines.tags.models import ConceptPage
from engines.tags.text_rules import (
    MAX_WORDS,
    MIN_HEADINGS,
    MIN_WORDS,
    heading_count,
    passes_index_rule,
    word_count,
)

__all__ = [
    "MAX_WORDS",
    "MIN_HEADINGS",
    "MIN_WORDS",
    "heading_count",
    "word_count",
    "quality_issues",
    "is_indexable",
    "needs_regeneration",
]

# The C7 shape (§4.3 d): a body whose markdown arrived on ONE line — headings
# mid-sentence, no paragraph breaks — renders as a wall of text. Detected by
# the absence of any newline in a body long enough to need several.
_NO_NEWLINE_MIN_CHARS = 400


def quality_issues(body: str) -> list[str]:
    """
    Every reason this body fails the G0.3 rule, empty when it passes.

    Pure function of the text, so the generator can judge a draft BEFORE it is
    saved and the audit script can judge stored rows with the same code.
    """
    body = body or ""
    issues: list[str] = []
    words = word_count(body)
    if words < MIN_WORDS:
        issues.append(f"words {words} < {MIN_WORDS}")
    if words > MAX_WORDS:
        issues.append(f"words {words} > {MAX_WORDS}")
    headings = heading_count(body)
    if headings < MIN_HEADINGS:
        issues.append(f"headings {headings} < {MIN_HEADINGS}")
    if len(body) >= _NO_NEWLINE_MIN_CHARS and "\n" not in body.strip():
        issues.append("no newline — single-line markdown (C7 shape)")
    return issues


def is_indexable(concept: ConceptPage) -> bool:
    """
    True when the page is substantive enough to be listed and indexed.

    Computed from the body, identical to what `ConceptPage.save()` stores in
    `is_indexable` — the feed and the detail payload read the stored column;
    this function is the reference for tests and the audit script.
    """
    return bool(concept.is_content_ready) and passes_index_rule(concept.body_md or "")


def needs_regeneration(concept: ConceptPage) -> bool:
    """
    G3.12 queue membership: a READY page whose stored body fails the rule.
    Stubs (not ready) are the generator's job, not the regenerator's.
    """
    return concept.is_content_ready and bool(quality_issues(concept.body_md or ""))
