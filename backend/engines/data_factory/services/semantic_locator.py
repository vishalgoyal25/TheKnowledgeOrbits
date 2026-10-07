"""Find the evidence span by MEANING instead of by shared keywords.

Act 0, phase 0.4c. Replaces the anchor heuristic that confounded Gate 1.

    claim -> vector          }
    every sentence -> vector } -> closest sentences = the evidence
                             }

🔴 Why this exists: a real failure from the Gate 1 run
-------------------------------------------------------
Claim:  "An INTERPOL Silver Notice is used to identify and trace criminal assets."
Source: "Silver Notice (pilot phase):\\nTo identify and trace criminal assets"

The fact was on the page, verbatim. The anchor locator still missed it, because
the only HARD anchor it could extract from that claim was "INTERPOL" -- a token
that appears ~20 times on an INTERPOL page, in the header, the menu and every
paragraph. It matched the first occurrence, declared full confidence, and handed
the verifier an unrelated block.

That happened 24 times in 37. Every one of those scored against the VERIFIER,
which had correctly answered "this text does not discuss your claim".

Keyword matching cannot work here, and not because of tuning:

  * A claim's only distinctive token is often the publisher's own name.
  * Sources paraphrase. Our claim says "universal accessibility"; the ministry
    page says "barrier-free environment". Same fact, ZERO shared words, so no
    keyword method can ever connect them.

Meaning comparison fixes both. "barrier-free environment" and "universal
accessibility" land near each other in vector space; a single common word like
INTERPOL barely moves a sentence's position.

🔴 This costs NO LLM tokens, ever
----------------------------------
An embedding model is not an LLM. all-MiniLM-L6-v2 is ~90 MB and runs on CPU;
the verifier is a 120-billion-parameter model rented per call. Embedding 1,250
sentences is seconds of local compute and zero tokens.

🟢 And it REDUCES the LLM bill: today we pay for ~24 verification calls that
return "can't tell" purely because the span was wrong. Those are pure waste.

Reuses the shipped service, as 4.6a requires
---------------------------------------------
``content.services.EmbeddingService`` already wraps all-MiniLM-L6-v2 at 384
dimensions -- the same model behind `content_embedding` and the production RAG
that scores 10/10 grounding. Using anything else here would measure a different
retriever from the one Act II will ship.

⚠️ Act 0 scope: this ranks sentences WITHIN a known document. Act II.16's
Retriever does the harder job -- finding the document, across the whole corpus,
with BM25 + semantic + RRF. This is the half that was blocking the gate.
"""

from dataclasses import dataclass

import structlog

from engines.data_factory.services.claim_locator import LocatedSpan, split_sentences

logger = structlog.get_logger(__name__)

# How many consecutive sentences a span may cover. Matches claim_locator so the
# two are comparable: a difference in the number must come from the SEARCH, not
# from one of them being allowed wider evidence.
MAX_SENTENCE_WINDOW = 3

# Below this cosine similarity, the best sentence is not evidence -- it is just
# the least unrelated thing in the document.
#
# 0.45 is deliberately permissive for a FIRST measurement. Being too strict
# would reproduce the failure we are fixing: declining to return a span that a
# verifier could have used. A low-similarity span costs one LLM call and an
# honest UNPROVEN; a missing span costs the statement entirely.
MIN_SIMILARITY = 0.45


@dataclass(frozen=True)
class _Candidate:
    start: int
    end: int
    text: str
    score: float
    sentence_count: int


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity, without numpy.

    MiniLM output is already L2-normalised in sentence-transformers, so a dot
    product would usually suffice -- but the HuggingFace API path may not
    normalise, and silently comparing normalised to unnormalised vectors would
    produce scores that look plausible and rank wrongly. Dividing by the norms
    costs nothing at this volume and removes the assumption.
    """
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def locate_claim_semantically(
    chunk_text: str,
    claim: str,
    *,
    claim_vector: list[float] | None = None,
) -> LocatedSpan | None:
    """Find the span whose MEANING is closest to the claim.

    Returns the same ``LocatedSpan`` type as the anchor locator, so it is a
    drop-in replacement and the two can be compared on identical scoring.

    Args:
        chunk_text: the chunk's stored ``normalised_text``. Offsets index into
            THIS string.
        claim: the assertion, in our wording.
        claim_vector: a precomputed embedding of the claim. Pass it when
            looping over many chunks for one claim -- re-embedding the same
            claim per chunk is the obvious waste here.

    Returns:
        The best span, or None when nothing in the chunk is close enough.
        None stays a normal outcome: a chunk that does not discuss the claim
        must not be made to produce evidence.
    """
    sentences = split_sentences(chunk_text)
    if not sentences:
        return None

    # Imported inside the function: EmbeddingService lazily imports
    # sentence_transformers, and 4.1 forbids heavy ML imports being reachable
    # at URL-conf load.
    from engines.content.services.embedding_service import EmbeddingService

    if claim_vector is None:
        claim_vector = EmbeddingService.generate_embedding(claim)

    # One batch for the whole chunk. Embedding sentence-by-sentence would be
    # correct and roughly an order of magnitude slower.
    sentence_vectors = EmbeddingService.generate_embeddings_batch(
        [s.text for s in sentences]
    )

    best: _Candidate | None = None

    for window in range(1, MAX_SENTENCE_WINDOW + 1):
        for i in range(len(sentences) - window + 1):
            group = sentences[i : i + window]
            vectors = sentence_vectors[i : i + window]

            # Max over the window, not mean. A two-sentence span where the
            # first sentence IS the evidence should not be penalised for the
            # second sentence being unrelated -- and averaging does exactly
            # that, which systematically favours one-sentence spans even when
            # the claim genuinely needs two.
            score = max((_cosine(claim_vector, v) for v in vectors), default=0.0)

            if score < MIN_SIMILARITY:
                continue

            # Tie-break toward the NARROWER span: narrower evidence is better
            # evidence, because it is what the explanation will quote.
            if best is None or score > best.score + 1e-9:
                best = _Candidate(
                    start=group[0].start,
                    end=group[-1].end,
                    text=chunk_text[group[0].start : group[-1].end],
                    score=score,
                    sentence_count=window,
                )

    if best is None:
        return None

    return LocatedSpan(
        char_start=best.start,
        char_end=best.end,
        text=best.text,
        # Reuses the field the anchor locator writes, so both are stored and
        # compared the same way. Here it is a similarity, not a coverage ratio
        # -- recorded in the atom's snapshot by the caller so the two are never
        # silently averaged together.
        anchor_coverage=round(best.score, 4),
        matched_anchors=(),
        missing_anchors=(),
        sentence_count=best.sentence_count,
        used_soft_anchors=False,
    )


def embed_claim(claim: str) -> list[float]:
    """Embed one claim, for callers looping it over many chunks."""
    from engines.content.services.embedding_service import EmbeddingService

    return EmbeddingService.generate_embedding(claim)
