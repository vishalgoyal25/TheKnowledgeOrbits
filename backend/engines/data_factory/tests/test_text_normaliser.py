"""
engines/data_factory/tests/test_text_normaliser.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Act 0, phase 0.3 -- the text every offset indexes into.
Spec: 00_MASTER_RECAP.md 16.6.3.

🔴 Why these tests exist at all: EVERY failure mode here is SILENT.

Nothing crashes, nothing logs, and the text looks correct in any editor. The
citation simply points a character or two off, and a student clicking "show me
the proof" sees a mangled fragment. There is no way to notice by looking, so a
test is the only instrument that can see it.

What each group pins:
  🔴 idempotence  running twice == running once. If this breaks, re-processing
                  from the S3 archive silently invalidates every stored offset
  line endings    CRLF is TWO characters where LF is one -- the Windows-dev /
                  Linux-Fargate split makes this a certainty, not a risk
  invisibles      zero-width and soft hyphens occupy an index while being
                  unprintable, so an exact anchor match fails for no visible
                  reason
  unicode form    the same visible character as 1 or 2 code points has two
                  different lengths
  🔴 characters   offsets are CHARACTER offsets, never byte offsets
  restraint       what the normaliser deliberately does NOT touch
  composition     normaliser output feeds the span checker unchanged
"""

import pytest

from engines.data_factory.services.span_checker import check_span
from engines.data_factory.services.text_normaliser import (
    NORMALISER_VERSION,
    has_replacement_char,
    is_normalised,
    normalise_document,
)

# The worked example from the spec discussion. Chosen because the offset it
# produces differs by exactly one between a Windows and a Linux fetch, which
# is the cheapest possible demonstration of why this module exists.
CRLF_DOC = "India submitted BUR-4.\r\nEmissions fell 8%."

# Devanagari: 4 code points, 12 bytes. Any confusion between the two shows up
# immediately as an offset 8 characters out.
DEVANAGARI_DOC = "भारत GHG 8%"


# ── 🔴 Idempotence: the property this module lives or dies by ───────────────


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("plain text, nothing to do", id="already-clean"),
        pytest.param(CRLF_DOC, id="crlf"),
        pytest.param("line one\r\rline two", id="lone-cr"),
        pytest.param("a b c", id="space-likes"),
        pytest.param("G​H‌G", id="zero-width"),
        pytest.param("emis­sions", id="soft-hyphen"),
        pytest.param("Mahé district", id="decomposed-accent"),
        pytest.param("too     many      spaces", id="horizontal-runs"),
        pytest.param("para one\n\n\n\n\npara two", id="blank-runs"),
        pytest.param("   leading and trailing   ", id="document-edges"),
        pytest.param("  indented\n   lines  \n", id="line-edges"),
        pytest.param("\x00\x07control\x1fchars", id="control-chars"),
        pytest.param(DEVANAGARI_DOC, id="devanagari"),
        pytest.param("", id="empty"),
        pytest.param("   \n\n   \t  ", id="whitespace-only"),
        pytest.param("mixed\r\n ​चीज़\x07   end", id="everything-at-once"),
    ],
)
def test_normalising_twice_changes_nothing(raw):
    """🔴 THE test. If this fails, the S3 archive becomes a liability.

    A re-parse must reproduce byte-identical text, or every offset already
    stored against the first parse silently points somewhere else. Nothing
    raises; the citation is just wrong from then on.
    """
    once = normalise_document(raw)
    twice = normalise_document(once)

    assert once == twice


@pytest.mark.parametrize(
    "raw",
    ["plain", CRLF_DOC, DEVANAGARI_DOC, "a b", "  x  ", ""],
)
def test_is_normalised_agrees_with_normalise_document(raw):
    """The cheap assertion any offset-computing code path can make.

    `is_normalised` is how a caller checks it was handed canonical text rather
    than raw text, so it must never disagree with the function it guards.
    """
    assert is_normalised(normalise_document(raw))


# ── Line endings: the Windows-dev / Linux-Fargate split ─────────────────────


def test_crlf_becomes_lf_and_the_offset_is_the_linux_one():
    """The concrete breakage, pinned with real numbers.

    In the raw CRLF text "Emissions" starts at character 24, because \\r\\n is
    two characters. After normalisation it starts at 23 -- the same index a
    Linux fetch of the identical document would produce.

    Without this, an offset recorded on the developer's Windows machine and
    re-checked on Fargate slices "missions " instead of "Emissions", and
    nothing anywhere reports a problem.
    """
    assert CRLF_DOC.index("Emissions") == 24  # the trap, before normalising

    text = normalise_document(CRLF_DOC)

    assert "\r" not in text
    assert text.index("Emissions") == 23
    assert text[23:32] == "Emissions"


def test_lone_carriage_return_also_becomes_a_newline():
    """Classic-Mac line endings still appear in older government exports."""
    assert normalise_document("one\rtwo") == "one\ntwo"


# ── Invisible characters: present in the index, absent from the screen ──────


def test_zero_width_space_inside_a_word_is_removed():
    """An anchor match failing for no visible reason is the worst bug class.

    "G\\u200bHG" renders as "GHG" in every editor and browser, so the text
    looks perfect while an exact match against the acronym fails. The evidence
    of the problem is literally unprintable.
    """
    text = normalise_document("G​HG emissions")

    assert text.startswith("GHG")
    assert len(text) == len("GHG emissions")


def test_soft_hyphen_from_pdf_extraction_is_removed():
    """PDF extractors scatter soft hyphens at original line-break positions."""
    assert normalise_document("emis­sions") == "emissions"


def test_non_breaking_space_becomes_a_plain_space_without_changing_length():
    """Rife in government HTML as `&nbsp;`. The substitution is 1:1, so it is
    safe at any point -- unlike the removals, which shorten the string.
    """
    raw = "BUR-4 report"
    text = normalise_document(raw)

    assert text == "BUR-4 report"
    assert len(text) == len(raw)


def test_control_characters_are_removed_but_newlines_survive():
    """Tabs and newlines carry structure; the rest of C0/C1 is extractor noise."""
    text = normalise_document("line one\x07\n\nline two\x1f")

    assert "\x07" not in text
    assert "\x1f" not in text
    assert text == "line one\n\nline two"


# ── Unicode form: one visible character, two possible lengths ───────────────


def test_decomposed_accent_is_composed_to_a_single_code_point():
    """ "Mahé" can be 4 code points or 5. Government transliterations of Indian
    place names produce both, and the two forms index differently.
    """
    decomposed = "Mahé"  # e + COMBINING ACUTE
    assert len(decomposed) == 5

    text = normalise_document(decomposed)

    assert len(text) == 4
    assert text == "Mahé"


# ── 🔴 Character offsets, never byte offsets ────────────────────────────────


def test_offsets_are_character_offsets_not_byte_offsets():
    """🔴 The single most likely real defect in this whole design.

    In "भारत GHG 8%" the acronym starts at CHARACTER 5 and BYTE 13, because
    each Devanagari code point is 3 bytes in UTF-8. Any code that reaches for
    `len(text.encode())` or slices bytes lands 8 characters away from the
    evidence it claims to cite.
    """
    text = normalise_document(DEVANAGARI_DOC)

    assert len(text) == 11  # characters
    assert len(text.encode("utf-8")) == 19  # bytes -- deliberately different

    assert text.index("GHG") == 5  # the character offset we store
    assert text.encode("utf-8").index(b"GHG") == 13  # what a byte offset gives

    assert text[5:8] == "GHG"


# ── Whitespace shape ────────────────────────────────────────────────────────


def test_horizontal_runs_collapse_but_line_structure_survives():
    """HTML extraction produces long runs; paragraph structure is worth keeping
    because a stored citation gets read by a human when it is disputed.
    """
    text = normalise_document("word     word\n\npara     two")

    assert text == "word word\n\npara two"


def test_blank_line_runs_collapse_to_exactly_two_newlines():
    assert normalise_document("a\n\n\n\n\n\nb") == "a\n\nb"


def test_line_edges_and_document_edges_are_stripped():
    text = normalise_document("   leading\n   indented   \ntrailing   ")

    assert text == "leading\nindented\ntrailing"


# ── Restraint: what it deliberately does NOT touch ──────────────────────────


@pytest.mark.parametrize(
    ("raw", "preserved"),
    [
        ("India’s emissions", "’"),  # RIGHT SINGLE QUOTATION MARK
        ("“quoted”", "“"),  # curly double quotes
        ("2019–2020", "–"),  # EN DASH
        ("a—b", "—"),  # EM DASH
    ],
)
def test_typography_is_left_exactly_as_published(raw, preserved):
    """Deliberate non-transformation, not an oversight.

    Each of these is a SINGLE character, so none can shift an offset. Leaving
    them keeps the stored text faithful to what a human auditing the citation
    sees on the page, and anchor matching is unaffected -- the checker extracts
    numbers, years, acronyms and capitalised words, none of which care about
    the shape of a quotation mark.

    The governing rule: transform only where NOT transforming causes an offset
    bug. Every transformation is a chance to be wrong.
    """
    assert preserved in normalise_document(raw)


# ── Decoding failures caught at ingestion, not downstream ───────────────────


def test_replacement_character_is_detected():
    """U+FFFD means the bytes were decoded with the wrong codec and the real
    characters are GONE -- not recoverable by re-normalising. Catching it here
    means re-fetching one artifact instead of poisoning every chunk from it.
    """
    assert has_replacement_char("emissions fell 8�")
    assert not has_replacement_char("emissions fell 8%")


def test_normaliser_version_is_set():
    """Chunks carry this as `processing_version`, so a rules change produces
    NEW rows beside the old ones rather than rewriting them (8.3).
    """
    assert isinstance(NORMALISER_VERSION, int)
    assert NORMALISER_VERSION >= 1


# ── Composition: the handoff this phase exists to make safe ────────────────


def test_offsets_computed_on_normalised_text_pass_the_span_checker():
    """🔴 The actual contract of 16.6.3, end to end.

    Text that arrives with every hazard at once -- CRLF, a non-breaking space,
    a zero-width space inside the acronym -- is normalised ONCE, the claim
    sentence is located BY CODE, and the resulting offsets are handed to the
    checker that will re-verify them in production.

    This is the handoff the whole phase exists to make safe: normalisation and
    verification must agree on what the text is, or Contract 1 is violated on
    its first real use.
    """
    raw = (
        "India submitted its Fourth Biennial Update Report (BUR-4) to the "
        "UNFCCC in December 2024.\r\n"
        "The report recorded a decrease of around 8% in G​HG emissions in "
        "2020 over 2019, excluding LULUCF."
    )
    text = normalise_document(raw)

    # Located by code, never by a human reading a position off a screen.
    sentence = (
        "The report recorded a decrease of around 8% in GHG emissions in 2020 over 2019"
    )
    start = text.index(sentence)
    end = start + len(sentence)

    result = check_span(
        text=text,
        char_start=start,
        char_end=end,
        claim_text="India's GHG emissions decreased by around 8% in 2020 over 2019.",
    )

    assert result.ok, result.detail
    assert not result.missing_anchors
    assert "8%" in result.span_text
