"""
engines/daily_ca/services/markdown_normalizer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Provider-agnostic markdown structure repair for Daily CA article bodies.

WHY THIS EXISTS
  Article generation moved off Cerebras when every key started returning 402
  (FEATURES_LLM_FIX.md); Mistral now serves the ~9k-token article prompt.
  prompt_builder asks for "## headings only" and "a blank line between
  paragraphs", but that is a SOFT instruction to a model — nothing enforced it.

  Measured on 2026-09-01: 2 of 10 published articles were stored with **zero
  newline characters** in ~7,000 chars of body. The `##` markers were present
  (h2=5) but sat mid-line, so the whole article rendered as one <p> — the
  "wall of text" bug. The other 8 articles were fine, which is why it looked
  intermittent: it tracks which provider/attempt served each call.

  The CommonMark rules that make this fatal:
    - A single "\\n" is NOT a paragraph break. It is a soft break, rendered as
      a space. Only a BLANK line starts a new paragraph.
    - An ATX heading is only a heading when it STARTS a line. Mid-line, `##`
      is literal text.

WHAT THIS DOES
  Detects block markers that appear MID-LINE — the precise failure signature —
  and re-inserts the breaks they need. Deliberately conservative: well-formed
  markdown is returned untouched, so healthy articles cannot regress.

  Idempotent by construction: normalize(normalize(x)) == normalize(x), because
  every repair moves a marker to the start of a line, where its pattern
  (which requires a preceding non-newline character) can no longer match.
"""

import re

import structlog

logger = structlog.get_logger(__name__)

# A body shorter than this is not worth judging — stubs and empties are handled
# by the caller's own emptiness checks.
_MIN_BODY_CHARS = 400

# ── Block-marker patterns ────────────────────────────────────────────────────
# Every pattern requires a preceding NON-newline char, i.e. the marker is
# mid-line — exactly the broken state. Once repaired the marker starts a line
# and stops matching, which is what makes the pass idempotent.

# ATX heading. Requiring 2-4 hashes AND a following space keeps "C# ", "#1"
# and hashtags safe.
_INLINE_HEADING = re.compile(r"([^\n])[ \t]*(#{2,4}[ \t]+\S)")

# Callout fences (:::callout … :::) used by splitCallouts() on the frontend.
_INLINE_CALLOUT_OPEN = re.compile(r"([^\n])[ \t]*(:::callout)")
_INLINE_CALLOUT_CLOSE = re.compile(r"([^\n])[ \t]*:::(?!callout)")
_TEXT_AFTER_CALLOUT_CLOSE = re.compile(r"^:::[ \t]+(?=\S)", re.MULTILINE)

# Bullets and numbered items are anchored to sentence-ending punctuation and a
# capitalised/markup start. Prose hyphens ("India - Pakistan talks") are not
# preceded by ".:!?" so they are left alone.
_INLINE_BULLET = re.compile(r"(?<=[.:!?])[ \t]+([-*•])[ \t]+(?=[A-Z(\[*_`\"'])")
_INLINE_NUMBERED = re.compile(r"(?<=[.:!?])[ \t]+(\d{1,2}\.)[ \t]+(?=[A-Z(\[*_`\"'])")

# Literal backslash-n that a model emitted instead of a real newline.
# The (?:\\r)? group is required: `\\r?\\n` would scope the `?` to the "r"
# character and demand TWO backslashes, never matching a plain \n escape.
_LITERAL_NEWLINE = re.compile(r"(?:\\r)?\\n")

_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


def _unescape_literal_newlines(text: str) -> str:
    """
    Turn literal ``\\n`` sequences into real newlines.

    Some models emit escaped newlines when they drift toward JSON-style output.
    Only applied when the text has more literal sequences than real newlines,
    so a legitimate ``\\n`` inside a code sample is never mangled.
    """
    literal_count = len(_LITERAL_NEWLINE.findall(text))
    if literal_count == 0:
        return text
    if literal_count <= text.count("\n"):
        return text
    return _LITERAL_NEWLINE.sub("\n", text)


def _restore_block_structure(text: str) -> str:
    """Re-insert the line breaks that mid-line block markers require."""
    text = _INLINE_HEADING.sub(r"\1\n\n\2", text)
    text = _INLINE_CALLOUT_OPEN.sub(r"\1\n\n\2", text)
    text = _INLINE_CALLOUT_CLOSE.sub(r"\1\n:::", text)
    text = _TEXT_AFTER_CALLOUT_CLOSE.sub(":::\n\n", text)
    text = _INLINE_BULLET.sub(r"\n\n\1 ", text)
    text = _INLINE_NUMBERED.sub(r"\n\n\1 ", text)
    return text


def has_inline_block_markers(text: str) -> bool:
    """
    True when a block marker sits mid-line — the signature of a collapsed body.

    This is a structural test, not a heuristic ratio: either a heading/callout
    is on its own line (renders correctly) or it is not (renders as literal
    text). Used both to decide whether to repair and to gate publishing.
    """
    if not text:
        return False
    return bool(
        _INLINE_HEADING.search(text)
        or _INLINE_CALLOUT_OPEN.search(text)
        or _INLINE_CALLOUT_CLOSE.search(text)
    )


def is_structurally_broken(text: str) -> bool:
    """
    True when a body would render as an unreadable wall of text.

    Two independent signatures:
      1. A substantial body with NO newline at all (the measured failure).
      2. Block markers stranded mid-line.
    """
    if not text or len(text) < _MIN_BODY_CHARS:
        return False
    if "\n" not in text:
        return True
    return has_inline_block_markers(text)


def normalize_markdown(text: str, *, log_context: str = "") -> str:
    """
    Repair markdown block structure. Safe to call on every article body.

    Well-formed markdown is returned unchanged apart from line-ending
    normalisation, so healthy articles cannot regress.

    Args:
        text:         raw article body markdown.
        log_context:  slug/title used only for log correlation.

    Returns:
        Markdown whose headings, callouts and list items each start a line.
    """
    if not text:
        return text

    original = text
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _unescape_literal_newlines(text)

    if has_inline_block_markers(text):
        text = _restore_block_structure(text)
        logger.warning(
            "daily_ca_markdown_repaired",
            context=log_context,
            newlines_before=original.count("\n"),
            newlines_after=text.count("\n"),
            chars=len(text),
        )

    text = _EXCESS_BLANK_LINES.sub("\n\n", text)
    return text.strip()
