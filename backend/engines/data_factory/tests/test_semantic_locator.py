"""
engines/data_factory/tests/test_semantic_locator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Act 0, phase 0.4c -- finding evidence by MEANING instead of shared keywords.

⚠️ NO MODEL IS LOADED. Every test injects fake vectors by patching
`EmbeddingService`. That is deliberate and not a shortcut:

  * `sentence_transformers` lives in requirements/ml.txt and pulls in torch.
    A unit test that needs a 2 GB install is a test nobody runs.
  * The live service may use the HUGGINGFACE API (it did throughout the Act 0
    run), so an un-patched test would make network calls and could fail on
    someone else's rate limit.
  * What is worth pinning here is the SEARCH LOGIC -- windowing, scoring,
    thresholding, offsets. Whether MiniLM embeds well is the model's business,
    and Gate 1 measured that empirically.

🔴 The honest context for this module: semantic search ALONE scored WORSE than
the crude keyword locator it replaced (26.2% vs 35.1%, 0.6_VERDICT.md §5.1),
because only half the production algorithm was built -- 7.2 specifies
BM25 + semantic + RRF. These tests pin the half that exists so the hybrid can
be built on top of it rather than beside it.

What each group pins:
  🔴 offsets    returned spans are exact slices of the chunk
  windowing     max over a window, not mean -- and why that matters
  threshold     a chunk that does not discuss the claim returns None
  efficiency    the claim is embedded once, not once per sentence
"""

from unittest.mock import patch

import pytest

from engines.data_factory.services.semantic_locator import (
    MIN_SIMILARITY,
    locate_claim_semantically,
)
from engines.data_factory.services.text_normaliser import normalise_document

SERVICE = "engines.content.services.embedding_service.EmbeddingService"

CHUNK = normalise_document(
    "India submitted its Fourth Biennial Update Report to the UNFCCC. "
    "The report recorded a decrease of around 8% in GHG emissions in 2020. "
    "Energy remained the largest contributor to the national inventory. "
    "Agriculture followed, with livestock the dominant sub-sector."
)

# Orthogonal unit vectors, so similarity is exactly controllable: a sentence
# given vector `i` scores 1.0 against a claim given vector `i`, and 0.0 against
# every other. Real embeddings are nothing like this -- which is the point. The
# search logic must be correct independently of how good the model is.
DIM = 8


def unit(index: int) -> list[float]:
    return [1.0 if i == index else 0.0 for i in range(DIM)]


def at_similarity(target: int, other: int, cosine: float) -> list[float]:
    """A UNIT vector whose cosine against ``unit(target)`` is exactly ``cosine``.

    ⚠️ The obvious construction is wrong, and it failed once already: setting
    ``vec[target] = w`` and ``vec[other] = 1 - w`` does NOT give cosine ``w``,
    because that vector is not unit length. At w=0.35 the actual cosine is
    0.474 -- above the threshold the test meant to sit below.

    Putting ``sqrt(1 - c^2)`` in the other component makes the norm exactly 1,
    so the dot product IS the cosine.
    """
    vec = [0.0] * DIM
    vec[target] = cosine
    vec[other] = (1.0 - cosine * cosine) ** 0.5
    return vec


class _FakeEmbeddings:
    """Hands back whatever the test says each sentence means.

    Keyed by text so a test can state its intent declaratively -- "this
    sentence IS the evidence" -- rather than by positional index, which breaks
    silently whenever the fixture is edited.
    """

    def __init__(self, mapping: dict[str, list[float]], default: list[float]):
        self.mapping = mapping
        self.default = default
        self.single_calls = 0
        self.batch_calls = 0

    def generate_embedding(self, text: str) -> list[float]:
        self.single_calls += 1
        return self._lookup(text)

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        self.batch_calls += 1
        return [self._lookup(t) for t in texts]

    def _lookup(self, text: str) -> list[float]:
        for needle, vector in self.mapping.items():
            if needle in text:
                return vector
        return self.default


def with_embeddings(mapping, default=None):
    fake = _FakeEmbeddings(mapping, default or unit(7))
    return fake, patch.multiple(
        SERVICE,
        generate_embedding=lambda text: fake.generate_embedding(text),
        generate_embeddings_batch=lambda texts, **kw: fake.generate_embeddings_batch(
            texts
        ),
    )


# ── 🔴 Offsets are exact slices ────────────────────────────────────────────


def test_the_located_span_is_an_exact_slice_of_the_chunk():
    """🔴 Same discipline as every other locator: compute integers, never build
    text. A span that is not a slice points somewhere else in the source it
    claims to cite, and nothing raises.
    """
    claim = "GHG emissions fell by about 8%."
    fake, patcher = with_embeddings({"decrease of around 8%": unit(0)})

    with patcher:
        located = locate_claim_semantically(CHUNK, claim, claim_vector=unit(0))

    assert located is not None
    assert CHUNK[located.char_start : located.char_end] == located.text


def test_it_returns_the_sentence_the_embeddings_point_at():
    """Proves the search is driven by the vectors rather than by position --
    the evidence here is the SECOND sentence, not the first.
    """
    claim = "GHG emissions fell by about 8%."
    fake, patcher = with_embeddings({"decrease of around 8%": unit(0)})

    with patcher:
        located = locate_claim_semantically(CHUNK, claim, claim_vector=unit(0))

    assert located is not None
    assert "8%" in located.text
    assert "Fourth Biennial" not in located.text


# ── Windowing ──────────────────────────────────────────────────────────────


def test_a_window_scores_by_its_best_sentence_not_its_average():
    """🔴 Why max and not mean.

    A two-sentence span whose FIRST sentence is the evidence should not be
    penalised for the second being unrelated. Averaging does exactly that, and
    systematically favours one-sentence spans even where a claim genuinely
    needs two -- which is the failure the anchor locator already had.

    Here only one sentence matches. Under mean scoring a two-sentence window
    would score 0.5 and fall below the threshold; under max it stays 1.0.
    """
    claim = "Energy was the largest contributor."
    fake, patcher = with_embeddings({"Energy remained": unit(2)})

    with patcher:
        located = locate_claim_semantically(CHUNK, claim, claim_vector=unit(2))

    assert located is not None
    assert located.anchor_coverage == pytest.approx(1.0)


def test_the_narrowest_span_wins_a_tie():
    """Narrower evidence is better evidence -- it is what the explanation
    quotes. Equal scores must not drift wider.
    """
    claim = "Energy was the largest contributor."
    fake, patcher = with_embeddings({"Energy remained": unit(2)})

    with patcher:
        located = locate_claim_semantically(CHUNK, claim, claim_vector=unit(2))

    assert located is not None
    assert located.sentence_count == 1


# ── Threshold: declining is a normal outcome ───────────────────────────────


def test_a_chunk_that_does_not_discuss_the_claim_returns_none():
    """🔴 Returning the least-unrelated sentence would MANUFACTURE EVIDENCE.

    Every sentence here is orthogonal to the claim, so the best similarity is
    0.0 and the honest answer is None.
    """
    claim = "Rajasthan shares the longest international border."
    fake, patcher = with_embeddings({}, default=unit(0))

    with patcher:
        located = locate_claim_semantically(CHUNK, claim, claim_vector=unit(5))

    assert located is None


def test_a_similarity_just_below_the_threshold_is_refused():
    low = MIN_SIMILARITY - 0.1
    fake, patcher = with_embeddings({}, default=at_similarity(0, 5, low))

    with patcher:
        located = locate_claim_semantically(CHUNK, "anything", claim_vector=unit(0))

    assert located is None


def test_a_similarity_just_above_the_threshold_is_accepted():
    high = MIN_SIMILARITY + 0.1
    fake, patcher = with_embeddings({}, default=at_similarity(0, 5, high))

    with patcher:
        located = locate_claim_semantically(CHUNK, "anything", claim_vector=unit(0))

    assert located is not None
    assert located.anchor_coverage == pytest.approx(high, abs=1e-3)


def test_an_empty_chunk_returns_none():
    fake, patcher = with_embeddings({})

    with patcher:
        assert locate_claim_semantically("", "a claim", claim_vector=unit(0)) is None


# ── Efficiency ─────────────────────────────────────────────────────────────


def test_sentences_are_embedded_in_one_batch():
    """Embedding sentence-by-sentence is correct and roughly an order of
    magnitude slower. At 255 chunks that is the difference between seconds and
    minutes, on every re-seed.
    """
    fake, patcher = with_embeddings({"Energy remained": unit(2)})

    with patcher:
        locate_claim_semantically(CHUNK, "Energy claim", claim_vector=unit(2))

    assert fake.batch_calls == 1


def test_a_supplied_claim_vector_is_not_re_embedded():
    """🔴 The caller loops one claim over every chunk in a document. Without
    this, a 41-chunk page re-embeds the same claim 41 times -- and against the
    HuggingFace API that is 41 network calls for one claim.
    """
    fake, patcher = with_embeddings({"Energy remained": unit(2)})

    with patcher:
        locate_claim_semantically(CHUNK, "Energy claim", claim_vector=unit(2))

    assert fake.single_calls == 0


def test_the_claim_is_embedded_when_no_vector_is_supplied():
    fake, patcher = with_embeddings(
        {"Energy claim": unit(2), "Energy remained": unit(2)}
    )

    with patcher:
        located = locate_claim_semantically(CHUNK, "Energy claim")

    assert fake.single_calls == 1
    assert located is not None


# ── Score bookkeeping ──────────────────────────────────────────────────────


def test_the_score_is_recorded_and_anchor_fields_are_left_empty():
    """`anchor_coverage` carries a COSINE here, not a coverage ratio -- two
    different scales on one field. The anchor tuples stay empty so a reader
    cannot mistake this for an anchor match, and the caller stamps
    `score_kind` on the atom so the two are never averaged together.
    """
    fake, patcher = with_embeddings({"Energy remained": unit(2)})

    with patcher:
        located = locate_claim_semantically(CHUNK, "Energy claim", claim_vector=unit(2))

    assert located is not None
    assert 0.0 <= located.anchor_coverage <= 1.0
    assert located.matched_anchors == ()
    assert located.missing_anchors == ()
    assert located.used_soft_anchors is False
