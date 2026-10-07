"""
engines/data_factory/tests/test_corruptor.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Act 0, phase 0.5 -- the input to Gate 2.
Spec: 00_MASTER_RECAP.md 15.4 (the three distractor mechanisms).

🔴 Why a bad corruption is worse than a bad verifier.

Gate 2 counts how many planted falsehoods slip through. If a corruption is
accidentally STILL TRUE, the verifier answers TRUE correctly and the gate
records it as a failure that did not happen. The number then understates a
working system, and the obvious next move -- "fix the verifier" -- chases a
defect that is in the test harness.

That already happened once. The single Gate 2 miss (Q74, 94.7% instead of
100%) was a range's lower bound shifted into a stage the source also described.
These tests exist so the next one is caught here instead.

What each group pins:
  mechanisms    all three of 15.4 produce output, and the right kind
  🔴 change     a corruption ALWAYS differs from its input
  🔴 falseness  the change contradicts a source stating the original
  honesty       fewer than three variants is reported, never padded
  determinism   the same claim corrupts identically every time
"""

import pytest

from engines.data_factory.services.corruptor import Mechanism, corrupt

GHG = "India's GHG emissions decreased by around 8% in 2020 over 2019."
QUANTUM = (
    "The National Quantum Mission aims to develop intermediate-scale quantum "
    "computers with 50 to 1000 physical qubits."
)
RBI = "The Digital Rupee is issued by the Reserve Bank of India as legal tender."
NO_HOOKS = "The situation improved considerably across the affected districts."


def by_mechanism(claim: str) -> dict[Mechanism, str]:
    return {c.mechanism: c.claim for c in corrupt(claim)}


# ── 🔴 Every corruption must actually change something ─────────────────────


@pytest.mark.parametrize("claim", [GHG, QUANTUM, RBI])
def test_every_corruption_differs_from_the_original(claim):
    """🔴 A no-op corruption is scored as a verifier failure.

    The verifier would answer TRUE -- correctly, because nothing was broken --
    and Gate 2 would count a falsehood waved through. `is_real` exists to make
    that impossible, and this pins it.
    """
    corruptions = corrupt(claim)

    assert corruptions
    for c in corruptions:
        assert c.claim.strip() != c.original.strip()
        assert c.is_real


@pytest.mark.parametrize("claim", [GHG, QUANTUM, RBI])
def test_the_original_is_preserved_for_span_lookup(claim):
    """Gate 2 finds the span by matching on `original`. If the corruptor
    rewrote it, the trial would lose the evidence it is meant to be judged
    against.
    """
    for c in corrupt(claim):
        assert c.original == claim


# ── The three mechanisms of 15.4 ───────────────────────────────────────────


def test_attribute_swap_changes_a_figure():
    """Numbers are the cleanest mechanism: a claim that survived Gate 1 was
    matched against a span stating the ORIGINAL figure, so any other figure is
    flatly contradicted by that same span.
    """
    corrupted = by_mechanism(GHG)[Mechanism.ATTRIBUTE_SWAP]

    assert corrupted != GHG
    assert "2020" not in corrupted or "2023" in corrupted


def test_years_move_by_three_not_one():
    """🔴 An ADJACENT year can be accidentally true.

    A report published in 2024 about 2023 data contains both "2023" and
    "2024", so shifting a year by one can land on a figure the source really
    does state -- and the corruption silently becomes a true claim.
    """
    corrupted = by_mechanism(GHG)[Mechanism.ATTRIBUTE_SWAP]

    assert "2023" in corrupted  # 2020 + 3
    assert "2021" not in corrupted


def test_a_non_year_figure_is_changed_beyond_rounding():
    """x2+1, so the result is never a rounding of the original and never zero.
    "8%" -> "9%" would be within the hedging of "around 8%".
    """
    claim = "The scheme covers 12 states."

    corrupted = by_mechanism(claim)[Mechanism.ATTRIBUTE_SWAP]

    assert "25 states" in corrupted  # 12*2+1
    assert "12 states" not in corrupted


def test_over_generalisation_replaces_a_hedge_with_an_absolute():
    """The source states a QUALIFIED fact; the corrupted claim states an
    unqualified one, which that source contradicts. This is 15.4's most common
    real-world mechanism -- "ALL types of UAVs can do vertical landing".
    """
    corrupted = by_mechanism(GHG)[Mechanism.OVER_GENERALISATION]

    assert "exactly" in corrupted
    assert "around" not in corrupted


def test_over_generalisation_handles_modal_verbs():
    """ "may" -> "must always" is the modal error UPSC uses constantly: a source
    granting discretion contradicts a claim asserting obligation.
    """
    claim = "The officer-in-charge may initiate a preliminary enquiry."

    corrupted = by_mechanism(claim)[Mechanism.OVER_GENERALISATION]

    assert "must always" in corrupted


def test_category_error_reassigns_to_the_wrong_kind_of_body():
    """A REAL institution of a DIFFERENT kind.

    Real, because an invented name is rejectable on implausibility alone and
    would flatter the result. Different kind, because that is what makes it a
    category error rather than a near miss.
    """
    corrupted = by_mechanism(RBI)[Mechanism.CATEGORY_ERROR]

    assert "Botanical Survey of India" in corrupted
    assert "Reserve Bank of India" not in corrupted


# ── 🔴 Honesty about what does not apply ───────────────────────────────────


def test_a_claim_with_no_hooks_yields_no_corruptions():
    """🔴 Fewer than three is reported, never padded.

    Inventing a corruption to reach three would mean scoring the verifier on
    something UPSC does not actually do -- a test measuring a capability the
    product never needs.
    """
    assert corrupt(NO_HOOKS) == []


def test_a_claim_without_a_figure_still_gets_other_mechanisms():
    claim = "The Reserve Bank of India may issue the Digital Rupee."

    mechanisms = {c.mechanism for c in corrupt(claim)}

    assert Mechanism.ATTRIBUTE_SWAP not in mechanisms  # no figure to swap
    assert Mechanism.CATEGORY_ERROR in mechanisms
    assert Mechanism.OVER_GENERALISATION in mechanisms


def test_an_institution_already_wrong_is_not_swapped_onto_itself():
    """Guards the no-op path: if the claim already names the substitute, the
    category error would change nothing and score as a verifier failure.
    """
    claim = "The Botanical Survey of India issued the standard."

    assert Mechanism.CATEGORY_ERROR not in {c.mechanism for c in corrupt(claim)}


# ── Determinism and reporting ──────────────────────────────────────────────


@pytest.mark.parametrize("claim", [GHG, QUANTUM, RBI])
def test_corruption_is_deterministic(claim):
    """Gate 2 must be reproducible across runs: a different corruption set
    would make two runs' catch rates incomparable.
    """
    first = [(c.mechanism, c.claim) for c in corrupt(claim)]
    second = [(c.mechanism, c.claim) for c in corrupt(claim)]

    assert first == second


@pytest.mark.parametrize("claim", [GHG, QUANTUM, RBI])
def test_each_corruption_explains_itself(claim):
    """`detail` is printed in the Gate 2 report and read by a human when a
    corruption slips through. Without it, diagnosing a miss means re-deriving
    what was changed.
    """
    for c in corrupt(claim):
        assert c.detail
        assert "->" in c.detail


def test_one_mechanism_at_most_once_per_claim():
    """Three variants of the same mechanism would weight the catch rate toward
    whichever mechanism happened to apply most often, instead of reporting all
    three evenly as 15.4 intends.
    """
    mechanisms = [c.mechanism for c in corrupt(QUANTUM)]

    assert len(mechanisms) == len(set(mechanisms))
