"""
engines/data_factory/tests/test_span_checker.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Act 0, phase 0.1 -- the deterministic gate in front of every LLM call.
Spec: 00_MASTER_RECAP.md 16.6.2 (six checks) and 16.6.5 (this test matrix).

These tests need NO database and NO Django settings: the checker is a pure
function by design, so the whole suite runs in milliseconds and Gate 1 can be
re-measured cheaply.

The property each group pins:
  bounds/blank   -- a structurally impossible citation never reaches a model
  encoding       -- lost bytes are caught, not silently shifted (7.5b)
  hash           -- offsets computed against different text are rejected
  anchors        -- a fabricated figure is caught WITHOUT a model
  validity       -- an expired claim cannot back a current question (14.4)
  🔴 Devanagari  -- offsets are CHARACTER offsets; byte offsets are the bug
"""

from datetime import datetime, timezone

import pytest

from engines.data_factory.services.span_checker import (
    Reason,
    check_span,
    text_hash,
)

# The worked example from 00_MASTER_RECAP.md -- a real UPSC 2026 Q21 statement
# against real MoEFCC phrasing. Used as the happy path so the suite proves the
# actual Act 0 case, not a toy one.
BUR_TEXT = (
    "India submitted its Fourth Biennial Update Report (BUR-4) to the UNFCCC in "
    "December 2024. The report recorded a decrease of around 8% in GHG emissions "
    "in 2020 over 2019, excluding LULUCF. Energy remained the largest contributor."
)
# ⚠️ ONE assertion, matching the ONE sentence cited below.
#
# The first version of this fixture read "India's BUR-4, submitted December
# 2024, recorded around 8% decrease ..." and the checker rejected it with
# missing_anchors=('2024', '4', 'BUR'). The checker was RIGHT twice over:
#
#   1. those tokens live in BUR_TEXT's first sentence, which the cited span
#      does not cover -- textbook mis-spanning, which is check 5's whole job;
#   2. that claim asserted TWO independently checkable facts joined by a
#      comma, which the atom contract forbids ("if it needs 'and', it is two
#      atoms" -- models/atoms.py). It was not a valid atom at all.
#
# Recorded rather than quietly corrected: the first real use of this checker
# caught a bad fixture written by the person who wrote the checker.
BUR_CLAIM = "India's GHG emissions decreased by around 8% in 2020 over 2019."
# Offsets found programmatically -- never hand-counted (16.6.3).
BUR_START = BUR_TEXT.index("The report recorded")
BUR_END = BUR_TEXT.index(", excluding LULUCF")


def test_happy_path_real_bur4_case():
    """The genuine Act 0 example passes every check."""
    result = check_span(
        text=BUR_TEXT,
        char_start=BUR_START,
        char_end=BUR_END,
        claim_text=BUR_CLAIM,
        expected_text_hash=text_hash(BUR_TEXT),
    )
    assert result.ok
    assert result.reason is Reason.OK
    assert not result.missing_anchors
    assert "8%" in result.span_text
    assert bool(result) is True  # __bool__ lets callers write `if check_span(...)`


def test_end_equal_to_length_is_valid():
    """char_end == len(text) is the LAST character, not out of bounds.

    An exclusive upper bound is the single easiest thing to get wrong here, and
    getting it wrong rejects every span that reaches the end of a chunk.
    """
    text = "A short factual sentence about 1947."
    result = check_span(
        text=text,
        char_start=0,
        char_end=len(text),
        claim_text="Something happened in 1947.",
    )
    assert result.ok, result.detail


def test_end_beyond_length_is_out_of_bounds():
    result = check_span(
        text="short", char_start=0, char_end=99, claim_text="irrelevant"
    )
    assert not result.ok
    assert result.reason is Reason.OUT_OF_BOUNDS


def test_negative_start_is_out_of_bounds():
    result = check_span(
        text="short text", char_start=-1, char_end=5, claim_text="irrelevant"
    )
    assert not result.ok
    assert result.reason is Reason.OUT_OF_BOUNDS


@pytest.mark.parametrize(("start", "end"), [(5, 5), (9, 4)])
def test_empty_or_inverted_span_is_rejected(start, end):
    """Equal offsets and swapped offsets are both INVERTED_SPAN.

    Distinguished from OUT_OF_BOUNDS on purpose: inverted means the caller
    swapped two arguments, out-of-bounds means the offsets belong to other text.
    Different bug, different fix.
    """
    result = check_span(
        text="some text here", char_start=start, char_end=end, claim_text="x"
    )
    assert not result.ok
    assert result.reason is Reason.INVERTED_SPAN


def test_whitespace_only_span_is_blank():
    text = "Fact one.      Fact two."
    result = check_span(
        text=text,
        char_start=text.index(".") + 1,
        char_end=text.index("Fact two"),
        claim_text="x",
    )
    assert not result.ok
    assert result.reason is Reason.BLANK_SPAN


def test_replacement_character_anywhere_fails_even_outside_the_span():
    """U+FFFD outside the cited span still fails the whole check.

    This is the 2026-10-02 encoding bug. Lost bytes shift EVERY offset after
    them, so a span that happens to sit before the corruption is still
    untrustworthy -- the chunk as a whole cannot be used.
    """
    text = "Clean leading sentence about 2024. Then � corrupted tail."
    result = check_span(
        text=text,
        char_start=0,
        char_end=text.index("Then"),
        claim_text="Something about 2024.",
    )
    assert not result.ok
    assert result.reason is Reason.ENCODING_CORRUPT
    assert "outside" in result.detail


def test_hash_mismatch_is_rejected():
    """Text re-normalised after offsets were computed must be caught here.

    Nothing else can detect it: the offsets are still in range and the span
    still slices cleanly -- it just points at the wrong words now.
    """
    result = check_span(
        text=BUR_TEXT,
        char_start=BUR_START,
        char_end=BUR_END,
        claim_text=BUR_CLAIM,
        expected_text_hash=text_hash("some other text entirely"),
    )
    assert not result.ok
    assert result.reason is Reason.TEXT_HASH_MISMATCH


def test_fabricated_figure_is_caught_and_named():
    """🔴 The check that earns this module its place.

    The span says 8%; the claim says 18%. No model is consulted -- the missing
    anchor is arithmetic, and the caller is told exactly which token is absent.
    """
    claim = "India recorded around 18% decrease in GHG emissions in 2020 over 2019."
    result = check_span(
        text=BUR_TEXT,
        char_start=BUR_START,
        char_end=BUR_END,
        claim_text=claim,
    )
    assert not result.ok
    assert result.reason is Reason.ANCHOR_MISSING
    assert "18" in result.missing_anchors


def test_mixed_case_acronym_is_a_hard_anchor():
    """MoEFCC must be treated as an anchor.

    An earlier regex anchored the capital run at the word start and silently
    dropped every mixed-case ministry acronym -- MoEFCC, MoSPI, MoHUA -- which
    are exactly the identifying tokens in Indian government sources.
    """
    text = "The statement was issued by MoSPI in 2024."
    claim = "MoEFCC issued the statement in 2024."
    result = check_span(text=text, char_start=0, char_end=len(text), claim_text=claim)
    assert not result.ok
    assert result.reason is Reason.ANCHOR_MISSING
    assert "MoEFCC" in result.missing_anchors


@pytest.mark.parametrize(
    "claim",
    [
        "A decrease of around 8 per cent was recorded in 2020.",
        "A decrease of around 8percent was recorded in 2020.",
    ],
)
def test_percent_spellings_are_equivalent(claim):
    """ "8%" in the source must match "8 per cent" in the claim.

    Indian English uses all three spellings. Strict matching here would reject
    valid atoms, which would corrupt Gate 1's number with false failures.
    """
    result = check_span(
        text=BUR_TEXT, char_start=BUR_START, char_end=BUR_END, claim_text=claim
    )
    assert result.ok, result.detail


def test_indian_digit_grouping_is_equivalent():
    """1,00,000 and 100000 are the same number."""
    text = "The scheme covered 1,00,000 beneficiaries during the year."
    result = check_span(
        text=text,
        char_start=0,
        char_end=len(text),
        claim_text="The scheme covered 100000 beneficiaries.",
    )
    assert result.ok, result.detail


def test_claim_with_no_hard_anchors_passes_with_a_note():
    """A qualitative claim has nothing to assert deterministically.

    It must PASS to the Verifier, not fail. Failing it would kill every
    non-numeric claim before a model ever saw it -- and judging those is
    precisely the Verifier's job.
    """
    text = "The scheme is administered by the ministry through state agencies."
    result = check_span(
        text=text,
        char_start=0,
        char_end=len(text),
        claim_text="The scheme is administered by the ministry.",
    )
    assert result.ok
    assert "no hard anchors" in result.detail


def test_soft_misses_are_reported_but_never_fail():
    """Capitalised words are advisory only.

    Capitalisation is an unreliable proper-noun signal, so a missing
    capitalised token is reported for analysis and does not fail the check.
    """
    text = "Emissions fell by 8% during the year in question."
    result = check_span(
        text=text,
        char_start=0,
        char_end=len(text),
        claim_text="Gujarat reported emissions falling by 8%.",
    )
    assert result.ok, result.detail
    assert "Gujarat" in result.soft_misses


# ── Validity window ──────────────────────────────────────────────────────────

JAN_2024 = datetime(2024, 1, 1, tzinfo=timezone.utc)
JAN_2025 = datetime(2025, 1, 1, tzinfo=timezone.utc)
JAN_2026 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_expired_claim_is_rejected():
    """An atom that stopped being true cannot back a current question (14.4)."""
    result = check_span(
        text=BUR_TEXT,
        char_start=BUR_START,
        char_end=BUR_END,
        claim_text=BUR_CLAIM,
        valid_until=JAN_2025,
        as_of=JAN_2026,
    )
    assert not result.ok
    assert result.reason is Reason.EXPIRED


def test_claim_not_yet_valid_is_rejected():
    """The mirror case: a student is never tested on a future fact."""
    result = check_span(
        text=BUR_TEXT,
        char_start=BUR_START,
        char_end=BUR_END,
        claim_text=BUR_CLAIM,
        valid_from=JAN_2026,
        as_of=JAN_2024,
    )
    assert not result.ok
    assert result.reason is Reason.NOT_YET_VALID


def test_null_valid_until_means_still_true():
    """NULL valid_until is 'still true', not 'expired at epoch'."""
    result = check_span(
        text=BUR_TEXT,
        char_start=BUR_START,
        char_end=BUR_END,
        claim_text=BUR_CLAIM,
        valid_from=JAN_2024,
        valid_until=None,
        as_of=JAN_2026,
    )
    assert result.ok, result.detail


def test_validity_is_skipped_when_no_as_of_given():
    """Without an as-of date there is no temporal question to answer."""
    result = check_span(
        text=BUR_TEXT,
        char_start=BUR_START,
        char_end=BUR_END,
        claim_text=BUR_CLAIM,
        valid_until=JAN_2025,
        as_of=None,
    )
    assert result.ok, result.detail


# ── 🔴 The test most likely to catch a real bug ──────────────────────────────

DEVANAGARI_TEXT = (
    "भारत ने दिसंबर 2024 में BUR-4 प्रस्तुत किया — जिसमें GHG उत्सर्जन में "
    "2019 की तुलना में 2020 में लगभग 8% की कमी दर्ज की गई।"
)


def test_offsets_are_character_offsets_not_byte_offsets():
    """🔴 Python slices CODE POINTS. Byte offsets shift every multibyte span.

    Devanagari is 3 bytes per character in UTF-8, so a byte-derived offset is
    roughly 3x too large here. The suite pins this because it is the defect
    most likely to appear in real ingestion code -- and it is invisible on
    ASCII-only test data.
    """
    # Prove the text really is multibyte, or this test proves nothing.
    assert len(DEVANAGARI_TEXT.encode("utf-8")) > len(DEVANAGARI_TEXT) * 2

    start = DEVANAGARI_TEXT.index("जिसमें")
    end = DEVANAGARI_TEXT.index("।") + 1

    char_based = check_span(
        text=DEVANAGARI_TEXT,
        char_start=start,
        char_end=end,
        claim_text="GHG उत्सर्जन में 2020 में 8% की कमी हुई।",
        expected_text_hash=text_hash(DEVANAGARI_TEXT),
    )
    assert char_based.ok, char_based.detail
    assert "8%" in char_based.span_text

    # The same span expressed as BYTE offsets: what a naive implementation
    # computes. It must not quietly succeed.
    byte_start = len(DEVANAGARI_TEXT[:start].encode("utf-8"))
    byte_end = len(DEVANAGARI_TEXT[:end].encode("utf-8"))
    assert byte_start != start, "test text is not multibyte enough to be meaningful"

    byte_based = check_span(
        text=DEVANAGARI_TEXT,
        char_start=byte_start,
        char_end=byte_end,
        claim_text="GHG उत्सर्जन में 2020 में 8% की कमी हुई।",
    )
    assert not byte_based.ok, (
        "byte offsets must be rejected -- they slice the wrong text, or run off "
        "the end. Silent success here means a corrupted citation chain."
    )


def test_text_hash_is_stable_and_utf8():
    """The helper and the check must agree about encoding, forever."""
    assert text_hash("abc") == text_hash("abc")
    assert text_hash("भारत") != text_hash("abc")
    assert len(text_hash("anything")) == 64
