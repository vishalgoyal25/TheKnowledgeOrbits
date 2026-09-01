"""
engines/daily_ca/services/markdown_normalizer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Detect Daily CA article bodies whose markdown structure collapsed, and apply
only LOSSLESS repairs.

WHY THIS EXISTS
  After article generation moved off Cerebras (402) to Mistral, some bodies
  arrived with ZERO newline characters in ~7,000 chars — the `##` markers were
  present but stranded mid-line. CommonMark then renders the whole article as a
  single <p>: the "wall of text" bug (measured 2026-09-01, 2 of 10 articles).

WHY THIS DOES NOT TRY TO REBUILD THE STRUCTURE
  A first version of this module re-inserted line breaks BEFORE each `##`. That
  made things worse, and the reason is worth recording:

      ...diplomatic moment. ## What Happened on August 31 The Supreme Court
      found no "compelling circumstance" to interfere...

  Breaking before the `##` puts the heading at the start of a line, but an ATX
  heading runs to the END of its line — and in a collapsed body there is no
  newline after the heading TITLE either. So the heading swallowed the entire
  paragraph and rendered it as a giant <h2>. One wall of plain text became
  several walls of huge bold text.

  Splitting the title from the body is genuinely ambiguous: in
  "## Key Provisions Section 482 of the CrPC allows..." nothing marks whether
  the title is "Key Provisions" or "Key Provisions Section 482". The newlines
  that carried that information are GONE — no heuristic can recover them
  reliably, and a wrong guess corrupts the article.

  So: this module never invents structure. It detects the damage and lets the
  caller reject the generation, which is regenerated from a provider that
  returns well-formed markdown.

WHAT IT STILL REPAIRS (lossless only)
  - CRLF/CR line endings → LF.
  - Literal "\\n" escapes → real newlines. This is safe and exact: the model
    DID emit the structure, it merely escaped it, so unescaping restores the
    author's intended layout including the break after each heading title.
  - Runs of 3+ blank lines collapsed to one blank line.

Idempotent: normalize(normalize(x)) == normalize(x).
"""

import re

import structlog

logger = structlog.get_logger(__name__)

# Below this length a body is a stub or an error string; emptiness is the
# caller's concern, not ours.
_MIN_BODY_CHARS = 400

# A heading line longer than this has clearly swallowed body prose — a real
# section title is a short phrase.
_MAX_HEADING_LINE_CHARS = 120

# ── Detection patterns (never used to rewrite, only to judge) ────────────────

# An ATX heading with non-whitespace before it on the same line. Requiring 2-4
# hashes AND a following space keeps "C# ", "#1" and hashtags out of scope.
_INLINE_HEADING = re.compile(r"\S[ \t]*#{2,4}[ \t]+\S")

# A callout fence that does not start its line.
_INLINE_CALLOUT = re.compile(r"\S[ \t]*:::")

# A heading line that also carries a paragraph.
_OVERLONG_HEADING = re.compile(
    rf"^#{{2,4}}[ \t]+.{{{_MAX_HEADING_LINE_CHARS},}}$", re.MULTILINE
)

# Literal backslash-n emitted instead of a real newline. The (?:\\r)? group is
# required: `\\r?\\n` would scope the `?` to the "r" character and demand TWO
# backslashes, never matching a plain \n escape.
_LITERAL_NEWLINE = re.compile(r"(?:\\r)?\\n")

_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


def _unescape_literal_newlines(text: str) -> str:
    """
    Turn literal ``\\n`` sequences into real newlines.

    Applied only when the literal sequences OUTNUMBER real newlines, so a
    legitimate ``\\n`` mentioned inside otherwise well-formed prose or a code
    sample is never touched.
    """
    literal_count = len(_LITERAL_NEWLINE.findall(text))
    if literal_count == 0 or literal_count <= text.count("\n"):
        return text
    return _LITERAL_NEWLINE.sub("\n", text)


def has_inline_block_markers(text: str) -> bool:
    """True when a heading or callout fence is stranded mid-line."""
    if not text:
        return False
    return bool(_INLINE_HEADING.search(text) or _INLINE_CALLOUT.search(text))


def has_overlong_heading(text: str) -> bool:
    """
    True when a heading line is long enough to have swallowed a paragraph.

    This is the signature of a "repaired" collapsed body — the failure mode the
    first version of this module created. Detecting it keeps such a body from
    ever being treated as healthy.
    """
    if not text:
        return False
    return bool(_OVERLONG_HEADING.search(text))


def is_structurally_broken(text: str) -> bool:
    """
    True when a body will not render as readable markdown.

    Three independent signatures:
      1. A heading or callout fence stranded mid-line.
      2. A heading line that has swallowed a paragraph.
      3. A substantial body containing NO newline at all.

    Signatures 1 and 2 are misplaced markers — unambiguous damage at ANY
    length. Only signature 3 needs the length gate, because a genuinely short
    body (a stub, a two-sentence note) has no newline quite legitimately.
    """
    if not text:
        return False
    if has_inline_block_markers(text) or has_overlong_heading(text):
        return True
    return len(text) >= _MIN_BODY_CHARS and "\n" not in text


def normalize_markdown(text: str, *, log_context: str = "") -> str:
    """
    Apply lossless markdown clean-up. Never invents structure.

    Safe to call on every body: well-formed markdown is returned unchanged
    apart from line-ending normalisation. A collapsed body is returned still
    collapsed — use :func:`is_structurally_broken` to reject it.
    """
    if not text:
        return text

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    unescaped = _unescape_literal_newlines(text)
    if unescaped != text:
        logger.info(
            "daily_ca_markdown_unescaped",
            context=log_context,
            newlines_after=unescaped.count("\n"),
        )
        text = unescaped

    text = _EXCESS_BLANK_LINES.sub("\n\n", text)
    return text.strip()


def collapse_to_single_line(text: str) -> str:
    """
    Undo inserted line breaks, returning the body to one continuous line.

    Recovery helper for bodies damaged by the withdrawn heading-reconstruction
    pass. Those bodies had ZERO newlines before that pass ran, so every newline
    now present was inserted by it — removing them all restores the original
    text exactly. Reads as an unbroken paragraph, which is poor but honest,
    and far better than paragraphs rendered as giant headings.

    Only meaningful for such bodies. Never call it on healthy markdown.
    """
    if not text:
        return text
    return re.sub(r"[ \t]*\n+[ \t]*", " ", text).strip()
