"""
engines/data_factory/tests/test_chunker.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Act 0, phase 0.3 -- the coordinate system every span lives in.

🔴 The invariant everything else rests on:

    document[c.doc_offset : c.doc_offset + len(c.text)] == c.text

An atom's char_start indexes into df_chunk.normalised_text. If a chunk is not
an exact SLICE of the document, an offset that is correct inside the chunk
points somewhere else in the source it claims to cite -- and nothing raises.

So the first group proves slicing by RECONSTRUCTION rather than by assertion:
re-read every chunk out of the original text and compare.

What each group pins:
  🔴 slicing     chunks are slices, never edited copies
  coverage       no content is lost, and none is duplicated
  determinism    same input, same chunks -- processing_version depends on it
  boundaries     paragraph > sentence > line > space > hard cut
  devanagari     "।" is a sentence end, or Hindi splits mid-sentence forever
  termination    pathological input still finishes
"""

import pytest

from engines.data_factory.services.chunker import (
    DEFAULT_MAX_CHARS,
    chunk_document,
)
from engines.data_factory.services.text_normaliser import normalise_document

SENTENCE = (
    "India submitted its Fourth Biennial Update Report to the UNFCCC in "
    "December 2024 recording a decrease of around 8% in emissions. "
)


def build_document(sentences: int) -> str:
    return normalise_document(SENTENCE * sentences)


# ── 🔴 Slicing: proved by reconstruction ───────────────────────────────────


@pytest.mark.parametrize("sentence_count", [1, 5, 20, 100])
def test_every_chunk_is_an_exact_slice_of_the_document(sentence_count):
    """🔴 THE test. Everything downstream assumes it.

    Re-reading each chunk out of the original text must return the chunk
    verbatim. If the chunker ever edits instead of slicing, this is the only
    thing that notices -- the resulting offsets are silently wrong, not broken.
    """
    document = build_document(sentence_count)

    for chunk in chunk_document(document):
        assert document[chunk.doc_offset : chunk.doc_end] == chunk.text


def test_chunks_do_not_overlap():
    """Overlap would create the same atom twice with two different spans, and
    inflate A8 -- the capacity input 0.3 exists to measure -- with duplicates.
    """
    chunks = chunk_document(build_document(60))

    for earlier, later in zip(chunks, chunks[1:], strict=False):
        assert earlier.doc_end <= later.doc_offset


def test_chunks_are_in_document_order_with_sequential_indices():
    chunks = chunk_document(build_document(60))

    assert [c.index for c in chunks] == list(range(len(chunks)))
    offsets = [c.doc_offset for c in chunks]
    assert offsets == sorted(offsets)


def test_no_chunk_begins_or_ends_with_whitespace():
    """A chunk starting on a newline makes every span inside it off by one
    relative to the sentence a human reading the source sees.
    """
    for chunk in chunk_document(build_document(40)):
        assert chunk.text == chunk.text.strip()


# ── Coverage: nothing silently dropped ─────────────────────────────────────


def test_all_non_whitespace_content_survives_chunking():
    """Only inter-chunk whitespace may be discarded. Losing a sentence would
    mean a claim that exists in the source can never be located -- it would
    look like a verifier failure rather than an ingestion one.
    """
    document = build_document(50)
    chunks = chunk_document(document)

    rejoined = "".join(c.text for c in chunks)

    assert "".join(rejoined.split()) == "".join(document.split())


def test_short_text_is_one_chunk():
    document = normalise_document("One short release. Nothing more.")

    chunks = chunk_document(document)

    assert len(chunks) == 1
    assert chunks[0].text == document
    assert chunks[0].doc_offset == 0


def test_empty_text_yields_no_chunks_not_one_empty_chunk():
    assert chunk_document("") == []
    assert chunk_document("   \n\n  ") == []


# ── Determinism ────────────────────────────────────────────────────────────


def test_chunking_is_deterministic():
    """processing_version only means something if v1 can be reproduced."""
    document = build_document(80)

    first = chunk_document(document)
    second = chunk_document(document)

    assert [(c.index, c.doc_offset, c.text) for c in first] == [
        (c.index, c.doc_offset, c.text) for c in second
    ]


# ── Boundary preference ────────────────────────────────────────────────────


def test_a_paragraph_break_is_preferred_over_a_sentence_end():
    """A paragraph boundary in a release is usually also a topic boundary, so
    atoms do not straddle subjects.
    """
    first = "A. " * 250  # ~750 chars, well past the 50% floor
    document = normalise_document(first + "\n\n" + "B. " * 400)

    chunks = chunk_document(document)

    assert len(chunks) > 1
    # The first chunk ends at the paragraph break, carrying no "B".
    assert "B" not in chunks[0].text


def test_a_split_never_lands_inside_a_word():
    """Splitting a word destroys an anchor: "UNFCCC" cut in half matches
    nothing, and the span checker treats acronyms as HARD anchors.
    """
    document = build_document(90)

    for chunk in chunk_document(document):
        assert not chunk.text.startswith("%")
        # A chunk that began mid-word would start with a lowercase fragment of
        # one; every sentence here starts with a capital or a digit.
        assert chunk.text[0].isupper() or chunk.text[0].isdigit()


def test_devanagari_danda_is_a_sentence_boundary():
    """🔴 Hindi PIB releases are in the source set. Without "।" in the sentence
    pattern, every Hindi document splits on whitespace, mid-sentence, forever.
    """
    hindi = "भारत ने रिपोर्ट प्रस्तुत की। " * 120
    document = normalise_document(hindi)

    chunks = chunk_document(document)

    assert len(chunks) > 1
    # Each chunk ends at a danda, not mid-clause.
    for chunk in chunks[:-1]:
        assert chunk.text.endswith("।")


def test_chunks_stay_near_the_target_size():
    document = build_document(100)

    chunks = chunk_document(document)

    for chunk in chunks[:-1]:
        # Never over the window, never absurdly under it (the 50% floor).
        assert chunk.char_count <= DEFAULT_MAX_CHARS
        assert chunk.char_count >= DEFAULT_MAX_CHARS * 0.4


# ── Termination on pathological input ──────────────────────────────────────


def test_text_with_no_boundaries_at_all_still_terminates():
    """A minified blob or one very long table row. Progress matters more than
    elegance -- a hard cut is correct here, an infinite loop is not.
    """
    document = "x" * 5000

    chunks = chunk_document(document)

    assert len(chunks) == 5000 // DEFAULT_MAX_CHARS + 1
    assert "".join(c.text for c in chunks) == document


def test_a_custom_max_chars_is_honoured():
    document = build_document(20)

    chunks = chunk_document(document, max_chars=300)

    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        assert chunk.char_count <= 300


def test_a_non_positive_max_chars_is_rejected_loudly():
    """A zero window would loop forever. Better to fail at the call site."""
    with pytest.raises(ValueError):
        chunk_document("some text", max_chars=0)
