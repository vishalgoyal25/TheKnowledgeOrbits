"""
engines/tags/services/concept_seo_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Which concept pages Google is told about — the ONE definition of "indexable".

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

`is_content_ready` alone is NOT the gate — a 28-word body carries it.
"""

import re

from engines.tags.models import ConceptPage

MIN_WORDS = 400
MIN_HEADINGS = 3

_HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]+")


def is_indexable(concept: ConceptPage) -> bool:
    """True when the page is substantive enough to be listed and indexed."""
    if not concept.is_content_ready:
        return False
    body = concept.body_md or ""
    if len(_WORD_RE.findall(body)) < MIN_WORDS:
        return False
    return len(_HEADING_RE.findall(body)) >= MIN_HEADINGS
