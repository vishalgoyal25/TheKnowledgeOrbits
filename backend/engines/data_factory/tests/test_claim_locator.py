"""
engines/data_factory/tests/test_claim_locator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Act 0, phase 0.3 -- offsets COMPUTED, never hand-read.
Spec: 00_MASTER_RECAP.md 16.6.3.

🔴 The property that makes the locator trustworthy is not "it finds the right
sentence". It is that WHATEVER it returns, the span checker then accepts --
because both use the same anchors. A locator with its own notion of relevance
would propose spans the checker rejects, and every disagreement would look
like a verifier failure when it was really a seeding bug.

That handoff is the last group here, and it is the one that matters.

What each group pins:
  offsets       returned positions are exact slices of the chunk
  anchors       scoring uses the checker's figures, years and acronyms
  narrowness    the smallest sufficient span wins -- it is what gets quoted
  🔴 refusal    a claim the chunk does not support returns None, cheaply
  🔴 handoff    located spans pass check_span
"""

import pytest

from engines.data_factory.services.claim_locator import (
    locate_claim,
    split_sentences,
)
from engines.data_factory.services.span_checker import check_span
from engines.data_factory.services.text_normaliser import normalise_document

CHUNK = normalise_document(
    "India submitted its Fourth Biennial Update Report (BUR-4) to the UNFCCC "
    "in December 2024. The report recorded a decrease of around 8% in GHG "
    "emissions in 2020 over 2019, excluding LULUCF. Energy remained the "
    "largest contributor to the national inventory. Agriculture followed, "
    "with livestock the dominant sub-sector."
)

CLAIM_8_PERCENT = "India's GHG emissions decreased by around 8% in 2020 over 2019."
CLAIM_BUR4 = "India submitted BUR-4 to the UNFCCC in December 2024."


# ── Sentence splitting: offsets are the whole point ────────────────────────


def test_sentences_are_exact_slices_of_the_chunk():
    """A splitter returning strings without positions would force the caller to
    search for them again, and that search is where an off-by-one creeps in.
    """
    for sentence in split_sentences(CHUNK):
        assert CHUNK[sentence.start : sentence.end] == sentence.text


def test_sentences_are_in_order_and_do_not_overlap():
    sentences = split_sentences(CHUNK)

    assert len(sentences) == 4
    for earlier, later in zip(sentences, sentences[1:], strict=False):
        assert earlier.end <= later.start


def test_devanagari_danda_ends_a_sentence():
    """Kept in step with the chunker deliberately. A locator that split Hindi
    differently would propose spans straddling a boundary the chunker had
    already decided was real.
    """
    hindi = normalise_document("भारत ने रिपोर्ट प्रस्तुत की। उत्सर्जन में 8% की कमी आई।")

    sentences = split_sentences(hindi)

    assert len(sentences) == 2
    assert sentences[0].text.endswith("।")


# ── Locating ───────────────────────────────────────────────────────────────


def test_the_located_span_is_an_exact_slice_of_the_chunk():
    """🔴 Same discipline as the chunker: compute integers, never build text."""
    located = locate_claim(CHUNK, CLAIM_8_PERCENT)

    assert located is not None
    assert CHUNK[located.char_start : located.char_end] == located.text


def test_it_finds_the_sentence_carrying_the_figures():
    located = locate_claim(CHUNK, CLAIM_8_PERCENT)

    assert located is not None
    assert "8%" in located.text
    assert "2020 over 2019" in located.text
    # ... and did not drag in the neighbouring sentences.
    assert "Energy remained" not in located.text


def test_a_different_claim_finds_a_different_sentence():
    """Proves scoring actually discriminates, rather than always returning the
    first sentence or the whole chunk.
    """
    located = locate_claim(CHUNK, CLAIM_BUR4)

    assert located is not None
    assert "Fourth Biennial Update Report" in located.text
    assert "8%" not in located.text


def test_full_anchor_coverage_is_reported_as_confident():
    located = locate_claim(CHUNK, CLAIM_8_PERCENT)

    assert located is not None
    assert located.anchor_coverage == 1.0
    assert located.is_confident
    assert located.missing_anchors == ()


def test_the_narrowest_sufficient_span_wins():
    """Narrower evidence is better evidence -- it is what the explanation will
    quote. A span covering five sentences is a paragraph that happens to
    contain the words, not support for one claim.
    """
    located = locate_claim(CHUNK, CLAIM_8_PERCENT)

    assert located is not None
    assert located.sentence_count == 1


def test_a_claim_spanning_two_sentences_is_allowed_to_widen():
    """Some claims genuinely need two sentences. The window may grow to
    MAX_SENTENCE_WINDOW, but only when one sentence is insufficient.
    """
    chunk = normalise_document(
        "The National Quantum Mission was launched in 2023. "
        "It targets intermediate-scale computers with 50 to 1000 physical qubits."
    )
    claim = "The National Quantum Mission, launched in 2023, targets 50 to 1000 qubits."

    located = locate_claim(chunk, claim)

    assert located is not None
    assert located.sentence_count == 2
    assert "2023" in located.text
    assert "1000" in located.text


# ── 🔴 Refusal: declining is a normal outcome ──────────────────────────────


def test_a_claim_the_chunk_does_not_support_returns_none():
    """🔴 Forcing a span would MANUFACTURE EVIDENCE -- the precise failure the
    whole engine exists to prevent. None must stay cheap and uncontroversial.
    """
    assert (
        locate_claim(CHUNK, "Rajasthan shares the longest international border.")
        is None
    )


def test_a_claim_sharing_only_a_year_is_rejected():
    """One matching anchor out of four means the sentence shares a year with
    the claim and nothing else. That is coincidence, not evidence.
    """
    located = locate_claim(
        CHUNK, "In 2020 the Supreme Court delivered 1,234 judgments on Article 370."
    )

    assert located is None


def test_a_claim_with_no_hard_anchors_returns_none():
    """Nothing numeric or named to anchor on. The checker passes such claims
    "with a note", but there is nothing to LOCATE by, and guessing is worse
    than declining.
    """
    assert locate_claim(CHUNK, "The situation improved considerably.") is None


def test_an_empty_chunk_returns_none():
    assert locate_claim("", CLAIM_8_PERCENT) is None


# ── 🔴 The handoff: located spans pass the checker ─────────────────────────


@pytest.mark.parametrize("claim", [CLAIM_8_PERCENT, CLAIM_BUR4])
def test_a_located_span_passes_the_span_checker(claim):
    """🔴 THE test. The locator and the checker must agree BY CONSTRUCTION.

    Both read anchors from span_checker, so a span the locator proposes cannot
    be missing an anchor the checker demands. If this ever fails, the two have
    drifted apart and every resulting gate failure would be misattributed to
    the verifier.
    """
    located = locate_claim(CHUNK, claim)
    assert located is not None

    result = check_span(
        text=CHUNK,
        char_start=located.char_start,
        char_end=located.char_end,
        claim_text=claim,
    )

    assert result.ok, result.detail
    assert not result.missing_anchors


def test_the_handoff_survives_hostile_typography():
    """Non-breaking spaces, CRLF and a Devanagari place name in one chunk.

    Normalisation runs first, exactly as it will in the pipeline, so this
    exercises the real chain: normalise -> locate -> check.
    """
    chunk = normalise_document(
        "The Mahé district recorded a decrease of around 8% in 2020.\r\n"
        "Neighbouring districts reported no change."
    )
    claim = "Mahé district recorded a decrease of around 8% in 2020."

    located = locate_claim(chunk, claim)
    assert located is not None

    result = check_span(
        text=chunk,
        char_start=located.char_start,
        char_end=located.char_end,
        claim_text=claim,
    )

    assert result.ok, result.detail
