"""Deterministic span verification -- the gate in front of every LLM call.

Six checks, no model, no network, no database. Spec: 00_MASTER_RECAP.md 16.6.2.

    1. Bounds          0 <= start < end <= len(text)
    2. Extraction      the slice is not blank
    3. Encoding        no U+FFFD anywhere in span or chunk
    4. Hash stability  the text hash matches what the offsets were computed against
    5. Anchors         the claim's numbers, years and acronyms appear in the span
    6. Validity        the claim's window is open at the as-of date

What this module does NOT do
----------------------------
It does not decide whether a claim is TRUE. It decides whether a claim is
CHECKABLE. "Does this span support this claim?" is a judgment and belongs to
the Verifier; "is this citation structurally sound?" is arithmetic and belongs
here. A failed check means the Verifier is NEVER CALLED -- that is the entire
cost lever, and the reason this runs first.

Why it is pure
--------------
No Django imports, no ORM, no logging. Three consequences, all deliberate:

* a Fargate worker can call it without loading the ORM into its hot path;
* it is testable without a database;
* at ~600 calls per paper and ~1,590 atoms/day, logging inside would be pure
  noise -- the CALLER logs the result (CLAUDE.md 4.5: never let a reporting
  path raise into a serving path).

Offsets are PYTHON CHARACTER offsets
------------------------------------
``text[start:end]`` slices code points, not bytes. Computing offsets against
UTF-8 bytes shifts every span after the first non-ASCII character. That is the
most likely real defect in this area, which is why the suite tests Devanagari.
"""

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Compiled once at import: this module runs ~600 times per paper and ~1,590
# times a day in steady state, so per-call compilation would be waste.

# Numbers, including decimals and Indian digit grouping (1,00,000).
_NUMBER_RE = re.compile(r"\d+(?:[, \s]\d+)*(?:\.\d+)?")
# Four-digit years in a plausible range. Matched separately from numbers so a
# missing year reads as a missing year in the report.
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
# Acronyms: the reliably-detectable subset of proper nouns. BUR, GHG, MoEFCC,
# ISRO, SEBI, NITI. Any word containing two CONSECUTIVE capitals anywhere --
# which excludes "India" and "Ministry" while catching mixed-case government
# acronyms.
#
# ⚠️ An earlier version anchored the capitals at the start (`\b[A-Z]{2,}...`)
# and silently missed `MoEFCC` -- M, then lowercase o, then EFCC -- because
# there is no word boundary before the capital run. Mixed-case acronyms are the
# norm in Indian ministry sources (MoEFCC, MoSPI, MoHUA), so that form dropped
# the most load-bearing anchors in the corpus.
_ACRONYM_RE = re.compile(r"\b[A-Za-z]*[A-Z]{2,}[A-Za-z]*\b")
# Capitalised tokens. SOFT only -- see `_SOFT_ANCHORS_ARE_ADVISORY` below for
# why these never fail a check.
#
# ⚠️ An earlier version excluded sentence-initial position to avoid matching
# "The". That threw away real proper nouns, because a proper noun is very often
# the first word of its sentence ("Gujarat reported..."). Since soft anchors are
# advisory, a false POSITIVE costs a noisy line in a report while a false
# NEGATIVE loses the signal entirely -- so match everything and subtract the
# grammatical words instead.
_CAPITALISED_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")

# Capitalised words that are grammar, not names. Casefolded for comparison.
_FUNCTION_WORDS = frozenset(
    {
        "the",
        "this",
        "that",
        "these",
        "those",
        "there",
        "their",
        "they",
        "its",
        "and",
        "but",
        "for",
        "from",
        "with",
        "without",
        "after",
        "before",
        "during",
        "under",
        "over",
        "between",
        "among",
        "also",
        "thus",
        "hence",
        "however",
        "although",
        "while",
        "when",
        "where",
        "which",
        "what",
        "who",
        "whom",
        "whose",
        "such",
        "both",
        "each",
        "every",
        "many",
        "some",
        "most",
        "more",
        "less",
        "other",
        "another",
        "about",
        "around",
        "approximately",
        "according",
        "based",
        "since",
        "until",
        "unless",
        "because",
        "though",
        "despite",
        "including",
    }
)

# Percent spellings that mean the same thing. Indian English uses all three.
_PERCENT_RE = re.compile(r"\s*(?:%|per\s*cent|percent)", re.IGNORECASE)

REPLACEMENT_CHAR = "�"

# 🔴 Divergence from 00_MASTER_RECAP.md 16.6.2, recorded deliberately.
#
# The spec lists "numbers, years and proper nouns" as hard anchors. Proper nouns
# detected by capitalisation are NOT reliable: sentence-initial words, "India's"
# possessives and title-case headings all produce false anchors, and a false
# anchor fails a perfectly good atom. So proper nouns split in two:
#
#   ACRONYMS         -> hard. Unambiguous, and they carry the identifying load
#                       in UPSC source text (BUR-4, MoEFCC, GHG, NITI).
#   Capitalised words -> SOFT. Reported for analysis, never cause a failure.
#
# Act 0 is a MEASUREMENT. A checker that is too strict manufactures failures and
# corrupts Gate 1's number; one that is too lenient hides real fabrication.
# Reporting soft misses separately keeps both visible.
_SOFT_ANCHORS_ARE_ADVISORY = True


class Reason(str, Enum):
    """Why a span passed or failed. A code, not a sentence.

    Values are stable strings so they can be counted in metrics and stored
    without a mapping table. Never renumber or reword an existing member.
    """

    OK = "ok"
    OUT_OF_BOUNDS = "out_of_bounds"
    INVERTED_SPAN = "inverted_span"
    BLANK_SPAN = "blank_span"
    ENCODING_CORRUPT = "encoding_corrupt"
    TEXT_HASH_MISMATCH = "text_hash_mismatch"
    ANCHOR_MISSING = "anchor_missing"
    NOT_YET_VALID = "not_yet_valid"
    EXPIRED = "expired"


@dataclass(frozen=True)
class SpanCheck:
    """The verdict, plus everything needed to act on it or analyse it.

    ``span_text`` is deliberately included: it is exactly what the Verifier
    receives (01_AGENT_ARCHITECTURE.md 3.2 -- ONE claim + ONE span + validity
    window, and nothing else). Building it here means the caller never has to
    re-slice and cannot accidentally widen the projection.
    """

    ok: bool
    reason: Reason
    detail: str = ""
    span_text: str = ""
    missing_anchors: tuple[str, ...] = field(default_factory=tuple)
    soft_misses: tuple[str, ...] = field(default_factory=tuple)

    def __bool__(self) -> bool:
        return self.ok


def _normalise_for_comparison(value: str) -> str:
    """Fold away differences that do not change meaning.

    🔴 FOR COMPARISON ONLY. This value is never written back and never used for
    slicing. Re-normalising stored text would shift every offset already
    computed against it, which is the exact failure Contract 1 exists to
    prevent.

    NFC first, because the same character can be one code point or a base plus
    a combining mark, and those compare unequal while looking identical.
    """
    folded = unicodedata.normalize("NFC", value)
    folded = _PERCENT_RE.sub("%", folded)
    # Collapse digit grouping so "1,00,000" and "100000" compare equal.
    folded = re.sub(r"(?<=\d)[, \s](?=\d)", "", folded)
    return " ".join(folded.split()).casefold()


def _extract_anchors(claim: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split a claim's load-bearing tokens into hard and soft anchors.

    Hard anchors MUST appear in the span. These are the tokens a fabricated or
    mis-spanned claim gets wrong: figures, years and acronyms.
    """
    years = set(_YEAR_RE.findall(claim))
    # A year is also a number; count it once, as a year.
    numbers = {n for n in _NUMBER_RE.findall(claim) if n not in years}
    acronyms = set(_ACRONYM_RE.findall(claim))
    capitalised = {
        word
        for word in _CAPITALISED_RE.findall(claim)
        if word.casefold() not in _FUNCTION_WORDS
    } - acronyms

    hard = tuple(sorted(years | numbers | acronyms))
    soft = tuple(sorted(capitalised))
    return hard, soft


# ── Public surface for other Factory services ──────────────────────────────
#
# Added 2026-10-06 for claim_locator, which must agree with this module about
# what makes a span relevant. Exposed as supported names rather than letting a
# second module reach into privates, and far better than the alternative: a
# locator with its OWN notion of anchors would propose spans the checker then
# rejects, and every such disagreement would look like a verifier error.


def extract_anchors(claim: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The claim's ``(hard, soft)`` anchors, as the checker sees them."""
    return _extract_anchors(claim)


def fold_for_comparison(value: str) -> str:
    """Fold text the way anchor matching does.

    🔴 FOR COMPARISON ONLY -- never store this and never slice with it. It
    casefolds, collapses digit grouping and rewrites percent spellings, so an
    offset taken against the result points nowhere in the stored text.
    """
    return _normalise_for_comparison(value)


def check_span(
    *,
    text: str,
    char_start: int,
    char_end: int,
    claim_text: str,
    expected_text_hash: str | None = None,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    as_of: datetime | None = None,
) -> SpanCheck:
    """Run the six deterministic checks. Keyword-only, because a positional
    call site that swapped ``char_start`` and ``char_end`` would be silently
    wrong in exactly the way this module exists to prevent.

    Args:
        text: the chunk's normalised text. Offsets index into THIS string.
        char_start: inclusive start offset, in characters.
        char_end: exclusive end offset, in characters.
        claim_text: the single assertion the span is supposed to support.
        expected_text_hash: SHA-256 hex of ``text``. When given, check 4 runs.
            Omit ONLY when text and offsets were loaded in the same transaction.
        valid_from: when the claim became true. None means timeless.
        valid_until: when it stopped being true. None means still true.
        as_of: the date to judge validity against. None skips check 6.

    Returns:
        A ``SpanCheck``. Checks run in order and the first hard failure returns,
        because later checks are meaningless once an earlier one fails -- there
        is no point hunting anchors in a span whose bounds are wrong.
    """
    length = len(text)

    # 1. Bounds. Inverted and out-of-range are distinguished because they have
    #    different causes: inverted means swapped arguments, out-of-range means
    #    the offsets belong to different text.
    if char_start >= char_end:
        return SpanCheck(
            ok=False,
            reason=Reason.INVERTED_SPAN,
            detail=f"char_start ({char_start}) must be < char_end ({char_end})",
        )
    if char_start < 0 or char_end > length:
        return SpanCheck(
            ok=False,
            reason=Reason.OUT_OF_BOUNDS,
            detail=(
                f"span [{char_start}:{char_end}] falls outside text of "
                f"{length} characters -- the offsets were probably computed "
                f"against different text, or against bytes rather than "
                f"characters"
            ),
        )

    span_text = text[char_start:char_end]

    # 2. Extraction. A span of only whitespace is a citation that shows the
    #    student nothing.
    if not span_text.strip():
        return SpanCheck(
            ok=False,
            reason=Reason.BLANK_SPAN,
            detail=f"span [{char_start}:{char_end}] contains only whitespace",
        )

    # 3. Encoding. U+FFFD means bytes were lost during decoding, so every offset
    #    after the first one is suspect -- not just this span. Checking the whole
    #    text, not only the slice, is deliberate (00_MASTER_RECAP.md 7.5b).
    if REPLACEMENT_CHAR in text:
        in_span = REPLACEMENT_CHAR in span_text
        return SpanCheck(
            ok=False,
            reason=Reason.ENCODING_CORRUPT,
            detail=(
                f"text contains U+FFFD ({text.count(REPLACEMENT_CHAR)} "
                f"occurrence(s), {'inside' if in_span else 'outside'} this "
                f"span). Bytes were lost at decode time, so offsets after the "
                f"first corrupted character cannot be trusted. Re-fetch and "
                f"re-decode with an explicit encoding."
            ),
            span_text=span_text,
        )

    # 4. Hash stability. If the text was re-normalised after these offsets were
    #    computed, they are silently wrong and this is the ONLY way to know.
    if expected_text_hash is not None:
        actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if actual != expected_text_hash:
            return SpanCheck(
                ok=False,
                reason=Reason.TEXT_HASH_MISMATCH,
                detail=(
                    f"text hash {actual[:12]}... does not match the stored "
                    f"{expected_text_hash[:12]}.... The text changed after "
                    f"these offsets were computed, so every offset into it is "
                    f"invalid. Re-extract; do not adjust the offsets."
                ),
                span_text=span_text,
            )

    # 6. Validity window, evaluated before anchors because it is cheaper and
    #    an expired atom should not be reported as an anchor problem.
    if as_of is not None:
        if valid_from is not None and as_of < valid_from:
            return SpanCheck(
                ok=False,
                reason=Reason.NOT_YET_VALID,
                detail=f"claim becomes valid at {valid_from.isoformat()}, as-of is {as_of.isoformat()}",
                span_text=span_text,
            )
        if valid_until is not None and as_of >= valid_until:
            return SpanCheck(
                ok=False,
                reason=Reason.EXPIRED,
                detail=f"claim expired at {valid_until.isoformat()}, as-of is {as_of.isoformat()}",
                span_text=span_text,
            )

    # 5. Anchors. The check that makes this more than a bounds test.
    hard, soft = _extract_anchors(claim_text)
    folded_span = _normalise_for_comparison(span_text)

    missing_hard = tuple(
        a for a in hard if _normalise_for_comparison(a) not in folded_span
    )
    missing_soft = tuple(
        a for a in soft if _normalise_for_comparison(a) not in folded_span
    )

    if missing_hard:
        return SpanCheck(
            ok=False,
            reason=Reason.ANCHOR_MISSING,
            detail=(
                f"the claim's load-bearing tokens {list(missing_hard)} do not "
                f"appear in the cited span. The claim is fabricated, or the "
                f"span points at the wrong sentence."
            ),
            span_text=span_text,
            missing_anchors=missing_hard,
            soft_misses=missing_soft,
        )

    # Passing with no hard anchors at all is a real and legitimate outcome: a
    # qualitative claim ("the scheme is administered by the ministry") has no
    # figures to check. It is reported, not failed -- judging it is the
    # Verifier's job, which is precisely the division of labour this module
    # exists to enforce.
    detail = "" if hard else "no hard anchors in claim; nothing deterministic to assert"

    return SpanCheck(
        ok=True,
        reason=Reason.OK,
        detail=detail,
        span_text=span_text,
        soft_misses=missing_soft,
    )


def text_hash(text: str) -> str:
    """SHA-256 hex of text, for storing on ``DfChunk.text_hash``.

    Lives here, beside the check that compares against it, so the two can never
    disagree about encoding -- UTF-8, always.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
