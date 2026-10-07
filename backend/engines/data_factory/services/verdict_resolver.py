"""Turn an entailment judgement into a verdict. Pure code, no LLM, no network.

Act 0, phase 0.4. Spec: 09_FUSION_AND_EVIDENCE.md 8-9,
01_AGENT_ARCHITECTURE.md 3.3a.

    claim + span -> [Entailment Judge, LLM] -> SUPPORTS / CONTRADICTS / NEITHER
                 -> [this module, free]     -> TRUE / FALSE / UNPROVEN

Why the verifier splits in two
-------------------------------
One node used to emit TRUE/FALSE/UNPROVEN from a claim and a span. It cannot:

    Claim:    "the scheme covers 15 states"
    Evidence: a release listing 12

That is FALSE if the release is the authoritative complete list, and UNPROVEN
if it is a passing mention. Same claim, same span, opposite verdicts -- and the
deciding fact is a property of the DOCUMENT, which is not visible in the text
the judge reads. So it had been guessing at the one boundary the counting
format depends on.

🔴 Three things that buys:

1. **Free.** Half the verdict stopped costing a token.
2. **Auditable.** Every FALSE the Factory ever publishes is explained by a
   table lookup, testable with no LLM and no network.
3. **Honest.** It removes a judgement the model was never equipped to make,
   instead of hoping a prompt covers it.

Deliberately free of Django
----------------------------
Takes exhaustiveness as a plain string rather than a ``DfArtifact``. Same
discipline as ``span_checker``: the rules are testable in microseconds, and a
resolver that needed a database row could not be run over a hypothetical.

The asymmetry that sets every default
--------------------------------------
A missed FALSE kills one question -- cheap, and invisible to students.
A wrong FALSE publishes a true statement marked false -- an error in a paying
student's hands, and the exact failure that destroys trust in a
verification-first product.

So every ambiguity here resolves toward UNPROVEN.
"""

from dataclasses import dataclass, field
from enum import Enum


class Entailment(str, Enum):
    """What the LLM judge is allowed to say. Deliberately NOT a verdict.

    ⚠️ The words TRUE, FALSE and UNPROVEN must never appear in the judge's
    output schema. Offering them invites the model to make the call it lacks
    the information for -- which is the defect this split exists to fix.
    """

    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEITHER = "NEITHER"


class Verdict(str, Enum):
    """The four states an atom can hold. Mirrors ``DfAtom``'s constants.

    PENDING is not produced here -- it means "never looked at", and this
    module only runs once something has been looked at. Keeping it in the enum
    makes the distinction explicit rather than implied: conflating PENDING with
    UNPROVEN would kill every counting-format question, because "not yet
    checked" would read as "checked and unsupported".
    """

    PENDING = "PENDING"
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNPROVEN = "UNPROVEN"


class Exhaustiveness(str, Enum):
    """Whether a document is COMPLETE for what it covers.

    Mirrors ``DfArtifact.EXHAUSTIVENESS_*``. Only EXHAUSTIVE turns "the span
    does not say this" into proof of falsehood.
    """

    EXHAUSTIVE = "EXHAUSTIVE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Judgement:
    """One (claim, span) pair judged against one source."""

    entailment: Entailment
    exhaustiveness: Exhaustiveness = Exhaustiveness.UNKNOWN
    tier: str = ""
    source_id: str = ""
    span_text: str = ""

    @property
    def can_prove_false(self) -> bool:
        return self.exhaustiveness is Exhaustiveness.EXHAUSTIVE


@dataclass(frozen=True)
class Resolution:
    """The verdict, and enough of the reasoning to audit it later.

    ``reason`` is a short machine-readable key, not prose: it is written to the
    gate's results file and counted, so it must be stable across runs.
    """

    verdict: Verdict
    reason: str
    corroborations: int = 0
    contradicted_by: tuple[str, ...] = field(default_factory=tuple)

    @property
    def needs_adjudication(self) -> bool:
        """Credible sources disagree. Never auto-publish; never auto-discard."""
        return bool(self.contradicted_by) and self.verdict is not Verdict.FALSE


# Tiers whose support is citable evidence. T3 joined on 2026-10-06; T4 is
# generated or derived text, so verifying against it is circular.
CITABLE_TIERS = frozenset({"T1", "T2", "T3"})


def resolve(judgement: Judgement) -> Resolution:
    """Resolve ONE judgement against ONE source.

    The whole decision, and it is four rows:

    ====================  =========================  ==========
    entailment            exhaustiveness             verdict
    ====================  =========================  ==========
    SUPPORTS              any                        TRUE
    CONTRADICTS           any                        FALSE
    NEITHER               EXHAUSTIVE                 FALSE
    NEITHER               PARTIAL / UNKNOWN          UNPROVEN
    ====================  =========================  ==========

    🟢 The newspaper rule falls out of this with no special case anywhere: a
    news article is PARTIAL, so it can prove a claim TRUE but almost never
    FALSE -- which is right, because an article was never trying to be
    exhaustive. Accuracy and completeness are different properties.
    """
    if judgement.entailment is Entailment.SUPPORTS:
        return Resolution(verdict=Verdict.TRUE, reason="span_supports")

    if judgement.entailment is Entailment.CONTRADICTS:
        return Resolution(
            verdict=Verdict.FALSE,
            reason="span_contradicts",
            contradicted_by=(judgement.source_id,) if judgement.source_id else (),
        )

    # NEITHER. Absence is proof only against a document that set out to be
    # complete for this kind of claim.
    if judgement.can_prove_false:
        return Resolution(verdict=Verdict.FALSE, reason="absent_from_exhaustive_source")

    return Resolution(verdict=Verdict.UNPROVEN, reason="not_addressed_by_source")


def resolve_many(judgements: list[Judgement]) -> Resolution:
    """Resolve a claim judged against SEVERAL sources.

    Order of precedence, and the reasoning for each:

    1. 🔴 **Genuine disagreement wins over everything.** One source supports
       and another contradicts -> adjudication, never an automatic verdict.
       Silently picking the winner is what every competitor does, and it is how
       a confident wrong answer reaches a student.
    2. **Contradiction from a source that can prove falsehood** -> FALSE.
    3. **Support from a citable tier** -> TRUE, carrying the corroboration
       count, because three independent witnesses is a different fact from one.
    4. **Absence from an exhaustive source** -> FALSE.
    5. Otherwise -> UNPROVEN.

    An empty list is UNPROVEN, not an error: "nothing was checked" and "checked
    and unsupported" are both un-publishable, and refusing to resolve would
    make the caller invent a verdict.
    """
    if not judgements:
        return Resolution(verdict=Verdict.UNPROVEN, reason="no_evidence")

    supports = [j for j in judgements if j.entailment is Entailment.SUPPORTS]
    contradicts = [j for j in judgements if j.entailment is Entailment.CONTRADICTS]

    citable_support = [j for j in supports if j.tier in CITABLE_TIERS]
    contradicting_ids = tuple(j.source_id for j in contradicts if j.source_id)

    # 1. Credible sources disagree.
    if citable_support and contradicts:
        return Resolution(
            verdict=Verdict.UNPROVEN,
            reason="sources_disagree",
            corroborations=len(citable_support),
            contradicted_by=contradicting_ids,
        )

    # 2. Contradicted, with nothing citable on the other side.
    if contradicts:
        return Resolution(
            verdict=Verdict.FALSE,
            reason="span_contradicts",
            contradicted_by=contradicting_ids,
        )

    # 3. Supported.
    if citable_support:
        return Resolution(
            verdict=Verdict.TRUE,
            reason="span_supports",
            corroborations=len(citable_support),
        )

    # 3b. Supported only by a tier that may not be cited (T4: generated or
    # derived text). Treated as no support at all rather than weak support --
    # verifying against LLM-written text is circular, which is the finding that
    # justifies this entire engine.
    if supports:
        return Resolution(verdict=Verdict.UNPROVEN, reason="support_not_citable")

    # 4. Absent from a source that would have listed it.
    if any(j.can_prove_false for j in judgements):
        return Resolution(verdict=Verdict.FALSE, reason="absent_from_exhaustive_source")

    # 5. Nothing addressed it.
    return Resolution(verdict=Verdict.UNPROVEN, reason="not_addressed_by_source")
