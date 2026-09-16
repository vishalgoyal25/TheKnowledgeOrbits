"""
engines/tags/text_rules.py
━━━━━━━━━━━━━━━━━━━━━━━━━━
The G0.3 indexability rule as pure functions of TEXT — no models, no Django.

Lives outside `services/` so the model can call it from `save()` without a
circular import (the services import the models). Everything that judges a
concept body — the sitemap flag, the generator gate (G3.11), the regeneration
queue (G3.12), the audit script — must come here for its numbers.
"""

import re

MIN_WORDS = 400
MIN_HEADINGS = 3
# Above this the generator is rambling, not thorough; the prompt asks for
# 500–700 (G3.12 lifted the old 600 ceiling that produced 681–694-word pages).
MAX_WORDS = 900

_HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]+")


def word_count(body: str) -> int:
    return len(_WORD_RE.findall(body or ""))


def heading_count(body: str) -> int:
    return len(_HEADING_RE.findall(body or ""))


def passes_index_rule(body: str) -> bool:
    """>= 400 words AND >= 3 headings — what the sitemap lists and Google indexes."""
    return word_count(body) >= MIN_WORDS and heading_count(body) >= MIN_HEADINGS
