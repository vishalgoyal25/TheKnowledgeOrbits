"""
engines/data_factory/tests/test_verdict_resolver.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Act 0, phase 0.4 -- the half of verification that costs nothing.
Spec: 09_FUSION_AND_EVIDENCE.md 8-9, 01_AGENT_ARCHITECTURE.md 3.3a.

🔴 Why this file matters more than its size suggests: after the split, EVERY
`FALSE` the Factory ever publishes is produced here, by a table lookup. So
every FALSE is explainable, and every rule is testable with no LLM, no network
and no database. That is the whole point of moving the decision out of the
model.

The asymmetry that sets every default, restated because it decides the tests:
  a missed FALSE  kills one question -- cheap, invisible to students
  a wrong FALSE   publishes a true statement marked false, in a paying
                  student's hands

So the tests assert that ambiguity resolves toward UNPROVEN, not toward FALSE.

What each group pins:
  truth table   the four rows, exhaustively
  🔴 defaults   UNKNOWN can never produce FALSE
  newspapers    the T3 rule falls out with no special case
  🔴 disagree   credible sources in conflict are never auto-resolved
  circularity   T4 support is no support
  vocabulary    the judge's words and the verdict's words stay separate
"""

import pytest

from engines.data_factory.services.verdict_resolver import (
    CITABLE_TIERS,
    Entailment,
    Exhaustiveness,
    Judgement,
    Verdict,
    resolve,
    resolve_many,
)


def judged(
    entailment: Entailment,
    *,
    exhaustiveness: Exhaustiveness = Exhaustiveness.UNKNOWN,
    tier: str = "T1",
    source_id: str = "src-1",
) -> Judgement:
    return Judgement(
        entailment=entailment,
        exhaustiveness=exhaustiveness,
        tier=tier,
        source_id=source_id,
    )


# ── The truth table, exhaustively ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("entailment", "exhaustiveness", "expected"),
    [
        # Support and contradiction do not depend on completeness.
        (Entailment.SUPPORTS, Exhaustiveness.EXHAUSTIVE, Verdict.TRUE),
        (Entailment.SUPPORTS, Exhaustiveness.PARTIAL, Verdict.TRUE),
        (Entailment.SUPPORTS, Exhaustiveness.UNKNOWN, Verdict.TRUE),
        (Entailment.CONTRADICTS, Exhaustiveness.EXHAUSTIVE, Verdict.FALSE),
        (Entailment.CONTRADICTS, Exhaustiveness.PARTIAL, Verdict.FALSE),
        (Entailment.CONTRADICTS, Exhaustiveness.UNKNOWN, Verdict.FALSE),
        # 🔴 Silence means different things depending on the document.
        (Entailment.NEITHER, Exhaustiveness.EXHAUSTIVE, Verdict.FALSE),
        (Entailment.NEITHER, Exhaustiveness.PARTIAL, Verdict.UNPROVEN),
        (Entailment.NEITHER, Exhaustiveness.UNKNOWN, Verdict.UNPROVEN),
    ],
)
def test_the_whole_truth_table(entailment, exhaustiveness, expected):
    """All nine combinations. The three NEITHER rows are the reason the
    verifier was split at all -- they are the only ones where the verdict
    depends on something the LLM cannot see.
    """
    assert (
        resolve(judged(entailment, exhaustiveness=exhaustiveness)).verdict is expected
    )


def test_absence_from_an_exhaustive_source_is_proof_of_falsehood():
    """The MEA "List of Outcomes" case, which is why Q43 is the strongest entry
    in the Gate 1 set: an official document that enumerates EVERY outcome makes
    "not in the list" a positive finding rather than a shrug.
    """
    result = resolve(
        judged(Entailment.NEITHER, exhaustiveness=Exhaustiveness.EXHAUSTIVE)
    )

    assert result.verdict is Verdict.FALSE
    assert result.reason == "absent_from_exhaustive_source"


# ── 🔴 The default direction ───────────────────────────────────────────────


def test_an_unclassified_source_can_never_produce_false():
    """🔴 The single most important default in this module.

    Most artifacts will sit at UNKNOWN for a long time -- classification is
    hand-config (09 13 F2). If UNKNOWN behaved as EXHAUSTIVE, every
    unclassified source would start manufacturing FALSE verdicts on claims it
    simply never mentioned.
    """
    for entailment in Entailment:
        result = resolve(judged(entailment, exhaustiveness=Exhaustiveness.UNKNOWN))
        if entailment is Entailment.CONTRADICTS:
            assert result.verdict is Verdict.FALSE  # the span said so, explicitly
        else:
            assert result.verdict is not Verdict.FALSE


def test_can_prove_false_is_exhaustive_only():
    assert judged(
        Entailment.NEITHER, exhaustiveness=Exhaustiveness.EXHAUSTIVE
    ).can_prove_false
    assert not judged(
        Entailment.NEITHER, exhaustiveness=Exhaustiveness.PARTIAL
    ).can_prove_false
    assert not judged(
        Entailment.NEITHER, exhaustiveness=Exhaustiveness.UNKNOWN
    ).can_prove_false


# ── Newspapers, with no special case anywhere ──────────────────────────────


def test_a_newspaper_can_prove_true():
    """T3 became citable on 2026-10-06. The Hindu is primary journalism."""
    result = resolve(
        judged(Entailment.SUPPORTS, tier="T3", exhaustiveness=Exhaustiveness.PARTIAL)
    )

    assert result.verdict is Verdict.TRUE


def test_a_newspaper_almost_never_proves_false():
    """🔴 Accuracy and COMPLETENESS are different properties.

    "The scheme covers 12 states" in The Hindu is good evidence that it covers
    12. It is NOT evidence that it does not cover 15 -- the article never set
    out to be exhaustive.

    🟢 Note there is no newspaper branch in the resolver. A news artifact is
    PARTIAL, and PARTIAL + NEITHER is UNPROVEN. The rule falls out of the
    table.
    """
    result = resolve(
        judged(Entailment.NEITHER, tier="T3", exhaustiveness=Exhaustiveness.PARTIAL)
    )

    assert result.verdict is Verdict.UNPROVEN


def test_t4_is_not_citable_because_verifying_against_generated_text_is_circular():
    assert "T4" not in CITABLE_TIERS
    assert {"T1", "T2", "T3"} <= CITABLE_TIERS


# ── Several sources ────────────────────────────────────────────────────────


def test_no_evidence_is_unproven_not_an_error():
    """ "Nothing was checked" and "checked and unsupported" are both
    un-publishable. Raising here would make the caller invent a verdict.
    """
    result = resolve_many([])

    assert result.verdict is Verdict.UNPROVEN
    assert result.reason == "no_evidence"


def test_corroboration_is_counted():
    """Three independent witnesses is a different fact from one, and the count
    is what makes that visible to a student rather than implied.
    """
    result = resolve_many(
        [
            judged(Entailment.SUPPORTS, tier="T1", source_id="pib"),
            judged(Entailment.SUPPORTS, tier="T2", source_id="un"),
            judged(Entailment.SUPPORTS, tier="T3", source_id="hindu"),
        ]
    )

    assert result.verdict is Verdict.TRUE
    assert result.corroborations == 3


def test_disagreement_outranks_everything_and_is_never_auto_resolved():
    """🔴 THE rule that separates this product from its competitors.

    One credible source supports, another contradicts. Silently picking the
    winner is what every other generator does, and it is exactly how a
    confident wrong answer reaches a paying student.

    The claim becomes unusable for a question -- and remains valuable as
    "sources differ" content.
    """
    result = resolve_many(
        [
            judged(Entailment.SUPPORTS, tier="T1", source_id="pib"),
            judged(Entailment.CONTRADICTS, tier="T1", source_id="rbi"),
        ]
    )

    assert result.verdict is Verdict.UNPROVEN
    assert result.reason == "sources_disagree"
    assert result.needs_adjudication
    assert "rbi" in result.contradicted_by


def test_a_lone_contradiction_is_false_not_a_disagreement():
    """Nothing citable on the other side, so there is no conflict to adjudicate
    -- just a refuted claim.
    """
    result = resolve_many([judged(Entailment.CONTRADICTS, source_id="pib")])

    assert result.verdict is Verdict.FALSE
    assert not result.needs_adjudication


def test_support_only_from_an_uncitable_tier_is_not_support():
    """🔴 Circularity, which is the finding that justifies this whole engine.

    book_chunk is LLM-generated and Wikipedia is derived. A claim "confirmed"
    by either has been confirmed by a machine repeating itself.
    """
    result = resolve_many([judged(Entailment.SUPPORTS, tier="T4", source_id="wiki")])

    assert result.verdict is Verdict.UNPROVEN
    assert result.reason == "support_not_citable"


def test_absence_from_an_exhaustive_source_beats_silence_from_a_partial_one():
    """A passing mention that omits the fact proves nothing; an official
    complete list that omits it proves the fact is false. The exhaustive
    source decides.
    """
    result = resolve_many(
        [
            judged(
                Entailment.NEITHER,
                exhaustiveness=Exhaustiveness.PARTIAL,
                source_id="news",
            ),
            judged(
                Entailment.NEITHER,
                exhaustiveness=Exhaustiveness.EXHAUSTIVE,
                source_id="mea",
            ),
        ]
    )

    assert result.verdict is Verdict.FALSE
    assert result.reason == "absent_from_exhaustive_source"


def test_everything_silent_is_unproven():
    result = resolve_many(
        [
            judged(Entailment.NEITHER, exhaustiveness=Exhaustiveness.PARTIAL),
            judged(Entailment.NEITHER, exhaustiveness=Exhaustiveness.UNKNOWN),
        ]
    )

    assert result.verdict is Verdict.UNPROVEN
    assert result.reason == "not_addressed_by_source"


# ── Vocabulary separation ──────────────────────────────────────────────────


def test_the_judges_vocabulary_contains_no_verdicts():
    """⚠️ The words TRUE, FALSE and UNPROVEN must never be offerable to the
    LLM. Putting them in its output schema invites it to make the call it
    lacks the information for -- the defect the split exists to fix.
    """
    judge_words = {e.value for e in Entailment}
    verdict_words = {v.value for v in Verdict}

    assert judge_words.isdisjoint(verdict_words)
    assert judge_words == {"SUPPORTS", "CONTRADICTS", "NEITHER"}


def test_pending_is_a_verdict_state_but_never_resolved_to():
    """PENDING means "never looked at". This module only runs after something
    HAS been looked at, so it must never emit it -- conflating PENDING with
    UNPROVEN would kill every counting-format question.
    """
    assert Verdict.PENDING.value == "PENDING"

    outcomes = {
        resolve(judged(e, exhaustiveness=x)).verdict
        for e in Entailment
        for x in Exhaustiveness
    }
    assert Verdict.PENDING not in outcomes


def test_reasons_are_stable_machine_readable_keys():
    """Written to the gate's results file and counted, so they must not drift
    into prose between runs.
    """
    reasons = {
        resolve(judged(e, exhaustiveness=x)).reason
        for e in Entailment
        for x in Exhaustiveness
    }

    assert reasons == {
        "span_supports",
        "span_contradicts",
        "absent_from_exhaustive_source",
        "not_addressed_by_source",
    }
    for reason in reasons:
        assert reason.islower()
        assert " " not in reason
