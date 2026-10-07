"""Find, by code, the span in a chunk that supports a claim.

Act 0, phase 0.3. Spec: 00_MASTER_RECAP.md 16.6.3.

    chunk text + claim -> char_start, char_end  (COMPUTED, never hand-read)

Why a human must not do this
-----------------------------
Reading a character position off a PDF viewer or a browser is wrong before it
is written down. Whitespace collapsing, non-breaking spaces, soft hyphens and
Unicode form all shift positions between what is displayed and what is stored.
The offsets have to come from the same text the checker will later verify
against, which means they have to be computed from that string.

How it decides, and why this particular method
-----------------------------------------------
The claim is OUR wording; the source is the publisher's. So an exact substring
search finds nothing, and the locator needs a notion of "which sentence is
about this claim".

It reuses the span checker's own anchors -- figures, years and acronyms -- and
scores each candidate sentence by how many of them it contains.

🟢 That reuse is the point, not a convenience. The locator and the verifier
agree, BY CONSTRUCTION, on what makes a span relevant: if the checker would
fail a span for missing "8%", the locator never proposes that span in the first
place. Two independent notions of relevance would guarantee disagreements that
look like verifier errors.

⚠️ SCOPE: this is a seeding aid for Act 0, not the production retriever.
Act II.16's Retriever does this over the whole corpus with BM25 + embeddings +
RRF. Here the chunk is already known -- we are placing a claim inside a
document we chose -- which is a far smaller problem.

Honest about failure
---------------------
Returning None is a normal outcome and MUST stay cheap. A claim whose anchors
are absent is a claim this chunk does not support, and forcing a span would
manufacture evidence -- the precise failure the whole engine exists to prevent.
"""

import re
from dataclasses import dataclass

import structlog

from engines.data_factory.services.span_checker import (
    extract_anchors,
    fold_for_comparison,
)

logger = structlog.get_logger(__name__)

# Sentence terminators, including the Devanagari danda for Hindi sources.
# Kept in step with chunker._SENTENCE_END deliberately: a locator that split
# sentences differently from the chunker would propose spans straddling a
# boundary the chunker had already decided was real.
_SENTENCE_SPLIT = re.compile(r"(?<=[.?!।])\s+")

# How many consecutive sentences a span may cover. A claim often needs two --
# "The report recorded X. This was the largest decrease since Y." -- but a span
# covering five sentences is no longer evidence for one claim, it is a
# paragraph that happens to contain the words.
MAX_SENTENCE_WINDOW = 3

# Below this, the best candidate is not evidence. One matching anchor out of
# four means the sentence shares a year with the claim and nothing else.
MIN_ANCHOR_COVERAGE = 0.5

# Soft anchors -- capitalised proper nouns -- are used ONLY when a claim has no
# hard ones, and then at a far stricter bar.
#
# Found 2026-10-06 by the first real run: claims like "The Sugamya Bharat
# Abhiyan targets universal accessibility" carry no figure, no year and no
# acronym, so the locator declined them outright and several Act 0 statements
# could never reach Gate 1.
#
# 🔴 This is NOT a relaxation of the checker's rules, and the distinction
# matters. The checker treats soft anchors as ADVISORY when VERIFYING -- a true
# claim may legitimately phrase a name differently from its source. Here the
# job is different: LOCATING a sentence, where a proper noun is often the only
# signal that exists. Same data, different question.
#
# The bar is 0.75 rather than 0.5 because capitalised words are weak evidence
# individually: "India" and "Report" appearing together means little, while
# "Sugamya Bharat Abhiyan" appearing whole is close to conclusive.
MIN_SOFT_COVERAGE = 0.75


@dataclass(frozen=True)
class LocatedSpan:
    """Where a claim is supported, and how confident the locator is.

    ``anchor_coverage`` is kept because it is the honest signal of how much
    work the locator did. A span found at 1.0 is a near-certain match; one at
    0.5 needs a human eye before it seeds a gate.
    """

    char_start: int
    char_end: int
    text: str
    anchor_coverage: float
    matched_anchors: tuple[str, ...]
    missing_anchors: tuple[str, ...]
    sentence_count: int
    used_soft_anchors: bool = False

    @property
    def is_confident(self) -> bool:
        """Full coverage on HARD anchors only.

        A soft-anchor match is never "confident" however complete it is: proper
        nouns can repeat across a document in ways figures do not, so these
        spans are flagged for a human glance before they seed a gate.
        """
        return self.anchor_coverage >= 1.0 and not self.used_soft_anchors


@dataclass(frozen=True)
class _Sentence:
    start: int
    end: int
    text: str


def split_sentences(text: str) -> list[_Sentence]:
    """Sentences with their offsets. Offsets are the whole point.

    Slices only -- the same discipline as the chunker. A sentence splitter that
    returned strings without positions would force the caller to search for
    them again, and that search is exactly where an off-by-one creeps in.
    """
    sentences: list[_Sentence] = []
    cursor = 0

    for piece in _SENTENCE_SPLIT.split(text):
        if not piece:
            continue
        start = text.find(piece, cursor)
        if start < 0:  # pragma: no cover - split pieces always come from text
            continue
        end = start + len(piece)
        stripped = piece.rstrip()
        sentences.append(
            _Sentence(start=start, end=start + len(stripped), text=stripped)
        )
        cursor = end

    return sentences


def locate_claim(chunk_text: str, claim: str) -> LocatedSpan | None:
    """Find the smallest span of whole sentences supporting ``claim``.

    Args:
        chunk_text: the chunk's ``normalised_text``, exactly as stored. Offsets
            returned index into THIS string, which is what ``df_atom`` expects.
        claim: our wording of the assertion.

    Returns:
        The best span, or None when the chunk does not support the claim. None
        is a normal, cheap outcome -- see the module docstring.
    """
    hard, soft = extract_anchors(claim)

    # Hard anchors when they exist; proper nouns only as a fallback, at a
    # stricter bar. See MIN_SOFT_COVERAGE for why this is not a relaxation.
    using_soft = not hard
    anchors = hard or soft
    threshold = MIN_SOFT_COVERAGE if using_soft else MIN_ANCHOR_COVERAGE

    if not anchors:
        # Nothing numeric, named OR capitalised. "The situation improved
        # considerably" has nothing to locate by, and guessing would be worse
        # than declining.
        return None

    sentences = split_sentences(chunk_text)
    if not sentences:
        return None

    best: LocatedSpan | None = None

    # Smallest window first, so a one-sentence span always beats a
    # three-sentence span with the same coverage. Narrower evidence is better
    # evidence: it is what the explanation will quote.
    for window in range(1, MAX_SENTENCE_WINDOW + 1):
        for start_index in range(len(sentences) - window + 1):
            group = sentences[start_index : start_index + window]
            span_start = group[0].start
            span_end = group[-1].end
            span_text = chunk_text[span_start:span_end]

            matched, missing = _match_anchors(anchors, span_text)
            coverage = len(matched) / len(anchors)

            if coverage < threshold:
                continue

            candidate = LocatedSpan(
                char_start=span_start,
                char_end=span_end,
                text=span_text,
                anchor_coverage=coverage,
                matched_anchors=matched,
                missing_anchors=missing,
                sentence_count=window,
                used_soft_anchors=using_soft,
            )

            if best is None or coverage > best.anchor_coverage:
                best = candidate

            if candidate.is_confident:
                # Every anchor present in the narrowest window tried so far.
                # Nothing wider can beat it, and nothing narrower was accepted.
                return candidate

    # ⚠️ Deliberately silent on a miss.
    #
    # This function answers "is the claim in THIS chunk?", and the caller asks
    # it once per chunk. For a six-chunk document, five Nones are the CORRECT
    # answer even when the claim is found in the sixth -- so logging here
    # produced five "df_locate_failed" lines per successfully located claim and
    # made a healthy run look broken. (Observed on the first real run,
    # 2026-10-06.)
    #
    # A pure function returning None is a RESULT, not an event. Whether a claim
    # was located anywhere is a question only the caller can answer, so the
    # caller logs it, once.
    return best


def _match_anchors(
    anchors: tuple[str, ...], span_text: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Which anchors appear in the span, using the CHECKER's comparison rules.

    ``fold_for_comparison`` comes from span_checker rather than being
    re-implemented, so "8 per cent" in the source matches "8%" in the claim
    here exactly as it will when the verifier re-checks the stored span.
    """
    folded_span = fold_for_comparison(span_text)

    matched = tuple(a for a in anchors if fold_for_comparison(a) in folded_span)
    missing = tuple(a for a in anchors if fold_for_comparison(a) not in folded_span)
    return matched, missing
