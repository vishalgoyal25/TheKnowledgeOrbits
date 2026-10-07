"""
engines/data_factory/tests/test_entailment_judge.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Act 0, phase 0.4 -- the only LLM call in the programme.
Spec: 01_AGENT_ARCHITECTURE.md 3.2-3.3a, 09_FUSION_AND_EVIDENCE.md 9.

⚠️ NO NETWORK and NO LLM. Every test patches `llm_call_json`. These pin the
CONTRACT around the model -- what it is shown, what its answers are allowed to
be, and what happens when it or the pool misbehaves. They cannot and do not
measure whether the model reasons well; that is Gate 1's job, and Gate 1 is a
measurement, not a test.

🔴 The most important test here is `test_the_prompt_cannot_leak_the_answer`.
In Act 0 the VisionIAS key is the GRADING SHEET. If it reaches the prompt,
Gate 1 measures reading comprehension of an answer key and the number is
worthless -- a failure that would look like success.

What each group pins:
  🔴 isolation   the prompt carries the span and the claim, nothing else
  ordering      evidence before question, so the model is not hunting
  vocabulary    only three words are offerable, and none is a verdict
  🔴 no coercion an unexpected label FAILS rather than being rounded off
  supply        an exhausted pool is never read as a judgement
  fail-safe     nothing raises; one statement cannot end a 60-statement run
"""

from unittest.mock import patch

import pytest

from engines.data_factory.services.entailment_judge import (
    SYSTEM_PROMPT,
    JudgeResult,
    build_prompt,
    judge_entailment,
)
from engines.data_factory.services.verdict_resolver import Entailment, Verdict

CALL = "engines.book_content.services.llm_service.llm_call_json"

SPAN = (
    "The report recorded a decrease of around 8% in GHG emissions in 2020 "
    "over 2019, excluding LULUCF."
)
CLAIM = "India's GHG emissions decreased by around 8% in 2020 over 2019."


def reply(entailment: str, quote: str = "") -> str:
    return '{"entailment": "%s", "quote": "%s"}' % (entailment, quote)


# ── 🔴 Isolation: what the model is allowed to see ─────────────────────────


def test_the_prompt_contains_the_span_and_the_claim():
    prompt = build_prompt(CLAIM, SPAN)

    assert SPAN in prompt
    assert CLAIM in prompt


def test_the_prompt_cannot_leak_the_answer():
    """🔴 THE test of this file.

    The function signature takes a claim and a span and nothing else, which is
    the cheapest possible enforcement of 01_AGENT_ARCHITECTURE 3.2. This pins
    that the built prompt really does carry nothing else -- no answer letter,
    no explanation prose, no question stem, no sibling statements, no topic.

    If this ever fails, Gate 1 is measuring the wrong thing and would report a
    HIGHER number for it. A silent success is the worst failure mode available
    to this project.
    """
    prompt = build_prompt(CLAIM, SPAN)
    forbidden = [
        "answer",
        "correct option",
        "option (a)",
        "option (b)",
        "VisionIAS",
        "UPSC",
        "statement 1",
        "expected",
        "TRUE",
        "FALSE",
        "UNPROVEN",
    ]

    lowered = prompt.lower()
    for token in forbidden:
        assert token.lower() not in lowered, f"prompt leaked {token!r}"


def test_evidence_comes_before_the_question():
    """Leading with the claim invites the model to go hunting for confirmation.
    Showing the evidence first makes it read before it knows what to look for.
    """
    prompt = build_prompt(CLAIM, SPAN)

    assert prompt.index(SPAN) < prompt.index(CLAIM)
    assert prompt.startswith("SOURCE TEXT:")


def test_a_validity_window_is_stated_only_when_it_exists():
    from datetime import datetime

    plain = build_prompt(CLAIM, SPAN)
    assert "accurate until" not in plain

    dated = build_prompt(
        CLAIM,
        SPAN,
        as_of=datetime(2026, 1, 1),
        valid_until=datetime(2025, 3, 31),
    )
    assert "31 March 2025" in dated


# ── Vocabulary ─────────────────────────────────────────────────────────────


def test_the_system_prompt_offers_no_verdict_words_as_LABELS():
    """⚠️ Offering TRUE/FALSE/UNPROVEN invites the model to decide something it
    cannot see: whether the SOURCE was complete. That is verdict_resolver's
    job, in free code.

    ⚠️ The check is on QUOTED LABELS, not on the bare words. An earlier version
    asserted `"TRUE" not in prompt.upper()` and failed on the sentence "if the
    claim is famously TRUE but the SOURCE TEXT does not say it" -- which is
    ordinary English and in fact one of the most important instructions in the
    prompt. What must not appear is a verdict offered as an ANSWER.
    """
    for verdict in (Verdict.TRUE, Verdict.FALSE, Verdict.UNPROVEN, Verdict.PENDING):
        assert f'"{verdict.value}"' not in SYSTEM_PROMPT.upper()

    # ... while all three entailment labels ARE offered, quoted, as the schema.
    for allowed in Entailment:
        assert f'"{allowed.value}"' in SYSTEM_PROMPT


def test_the_system_prompt_forbids_outside_knowledge():
    """🔴 The instruction the whole gate rests on.

    A model answering SUPPORTS because it REMEMBERS the fact is recalling, not
    verifying, and the pipeline around it contributes nothing. Gate 1 would
    then measure the model's training data instead of this system.
    """
    lowered = SYSTEM_PROMPT.lower()

    assert "only the source text" in lowered
    assert "training" in lowered
    # NEITHER must be presented as acceptable, or the model manufactures a
    # verdict rather than admitting the passage is silent.
    assert "neither is a normal" in lowered


# ── Parsing ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("label", ["SUPPORTS", "CONTRADICTS", "NEITHER"])
def test_each_allowed_label_parses(label):
    with patch(CALL, return_value=reply(label, "quoted sentence")):
        result = judge_entailment(CLAIM, SPAN)

    assert result.ok
    assert result.entailment is Entailment(label)
    assert result.quote == "quoted sentence"


def test_a_lowercase_label_is_accepted():
    """Models ignore casing instructions routinely. Normalising case is not
    coercion -- the word is unambiguous.
    """
    with patch(CALL, return_value=reply("supports")):
        result = judge_entailment(CLAIM, SPAN)

    assert result.ok
    assert result.entailment is Entailment.SUPPORTS


def test_fenced_json_is_recovered():
    """Models wrap JSON in code fences despite json_mode often enough that
    losing the call over it would waste real quota.
    """
    fenced = "```json\n" + reply("NEITHER") + "\n```"

    with patch(CALL, return_value=fenced):
        result = judge_entailment(CLAIM, SPAN)

    assert result.ok
    assert result.entailment is Entailment.NEITHER


# ── 🔴 No coercion ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "label", ["TRUE", "YES", "SUPPORTED", "PARTIALLY_SUPPORTS", "", "MAYBE"]
)
def test_an_unexpected_label_fails_instead_of_being_rounded_off(label):
    """🔴 Coercion would silently convert a confused model into a confident
    one, and Gate 1 would score the coercion rather than the model.

    "PARTIALLY_SUPPORTS" is the dangerous one: it is tempting to map to
    SUPPORTS, and doing so would hide exactly the hedging that distinguishes a
    weak judge from a strong one.
    """
    with patch(CALL, return_value=reply(label)):
        result = judge_entailment(CLAIM, SPAN)

    assert not result.ok
    assert result.entailment is None
    assert "unexpected label" in result.error


def test_unparseable_output_fails_and_keeps_the_raw_text():
    with patch(CALL, return_value="I think the answer is probably supports."):
        result = judge_entailment(CLAIM, SPAN)

    assert not result.ok
    assert "not JSON" in result.error
    assert result.raw  # kept for diagnosis


def test_json_that_is_not_an_object_fails():
    with patch(CALL, return_value='["SUPPORTS"]'):
        result = judge_entailment(CLAIM, SPAN)

    assert not result.ok


# ── Supply failures are not judgements ─────────────────────────────────────


def test_an_exhausted_pool_is_never_read_as_neither():
    """🔴 The pool returns "" when every capable provider is exhausted.

    Treating that as NEITHER would silently convert a SUPPLY failure into an
    UNPROVEN verdict, and Gate 1's accuracy would quietly degrade as quota ran
    out -- a result that looks like a weak model and is actually an empty tank.
    """
    with patch(CALL, return_value=""):
        result = judge_entailment(CLAIM, SPAN)

    assert not result.ok
    assert result.entailment is None
    assert "exhausted" in result.error


def test_a_provider_exception_does_not_propagate():
    """8.4: fail-safe, never fail-stop. One statement must not end a
    60-statement gate run.
    """
    with patch(CALL, side_effect=RuntimeError("provider blew up")):
        result = judge_entailment(CLAIM, SPAN)

    assert not result.ok
    assert "provider blew up" in result.error


@pytest.mark.parametrize(("claim", "span"), [("", SPAN), (CLAIM, ""), ("  ", "  ")])
def test_empty_input_is_refused_without_calling_the_pool(claim, span):
    """Checked before the call, so an empty statement never costs quota."""
    with patch(CALL) as mocked:
        result = judge_entailment(claim, span)

    assert not result.ok
    mocked.assert_not_called()


def test_result_is_falsy_when_not_ok():
    assert not JudgeResult(ok=False, error="x")
    assert JudgeResult(ok=True, entailment=Entailment.NEITHER)
