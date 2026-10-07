"""Ask a model one question: does THIS text support THIS claim?

Act 0, phase 0.4. Spec: 01_AGENT_ARCHITECTURE.md 3.2-3.3a,
09_FUSION_AND_EVIDENCE.md 9.

    claim + span  ->  SUPPORTS / CONTRADICTS / NEITHER  ->  verdict_resolver

🔴 This is the only LLM call in Act 0, and Gate 1 measures exactly it.

What it may NOT see (01_AGENT_ARCHITECTURE 3.2, 09 9.5)
--------------------------------------------------------
the answer key - any explanation prose - the question stem or its options -
which statements the Constructor meant to be true - sibling statements from the
same question - the topic - the blueprint - run history - any earlier verdict on
the same claim.

⚠️ In Act 0 the VisionIAS key is the GRADING SHEET. If it ever reaches this
prompt, Gate 1 measures reading comprehension of an answer key and the number
is worthless. The function signature takes a claim and a span and nothing else,
which is the cheapest possible enforcement.

🔴 The instruction the whole gate rests on
-------------------------------------------
The model must judge ONLY against the supplied text, never from what it already
knows. A model answering "SUPPORTS" because it remembers the fact is not
verifying -- it is recalling, and the pipeline it is standing in contributes
nothing. That would make Gate 1 a measure of the model's training data rather
than of this system, and the number would not survive contact with a document
published after the cutoff.

Hence the prompt forbids outside knowledge twice, and NEITHER is presented as a
normal, expected, unpenalised answer. A judge that feels pushed toward a verdict
will manufacture one.

Restricted vocabulary, deliberately
------------------------------------
The model may emit only SUPPORTS, CONTRADICTS or NEITHER. The words TRUE, FALSE
and UNPROVEN appear nowhere, because offering them invites it to decide
something it cannot see: whether the SOURCE was complete. That is
``verdict_resolver``'s job, in free code.

Fail-safe (8.4)
----------------
Never raises. An exhausted pool, a timeout or unparseable output all return
``ok=False``, so one bad statement never ends a 60-statement gate run.
"""

import json
from dataclasses import dataclass
from datetime import datetime

import structlog

from engines.data_factory.services.verdict_resolver import Entailment

logger = structlog.get_logger(__name__)

# 🔴 The output vocabulary. Kept as a frozenset so an unexpected word is a
# parse failure rather than something coerced into a verdict.
_ALLOWED = frozenset(e.value for e in Entailment)

# Act 0 runs on the free pool ("Groq first, free"). `standard` is the cheapest
# mode in the shipped pool's config.
DEFAULT_MODE = "standard"

SYSTEM_PROMPT = (
    "You are a strict evidence checker. You are given one SOURCE TEXT and one "
    "CLAIM.\n"
    "\n"
    "Decide ONLY whether the SOURCE TEXT itself supports or contradicts the "
    "CLAIM.\n"
    "\n"
    "RULES:\n"
    "1. Use ONLY the SOURCE TEXT. Ignore everything you know from training. If "
    "the claim is famously true but the SOURCE TEXT does not say it, the answer "
    "is NEITHER.\n"
    "2. NEITHER is a normal and correct answer. It is not a failure. Most "
    "passages do not address most claims.\n"
    "3. CONTRADICTS means the SOURCE TEXT states something incompatible with "
    "the CLAIM -- a different number, a different name, a different direction. "
    "Silence is NOT contradiction; silence is NEITHER.\n"
    "4. Pay exact attention to numbers, dates, names and direction. "
    "'increased' and 'decreased' are a contradiction. 500 and 5,000 are a "
    "contradiction. A different institution's name is a contradiction.\n"
    "5. Do not decide whether the claim is true in the world. That is not your "
    "job and you do not have enough information to do it.\n"
    "\n"
    'Answer with JSON only: {"entailment": "SUPPORTS" | "CONTRADICTS" | '
    '"NEITHER", "quote": "<the exact sentence from the SOURCE TEXT that '
    'decided it, or empty>"}'
)


@dataclass(frozen=True)
class JudgeResult:
    """One entailment judgement, plus what it cost and how it was reached.

    ``quote`` is requested because it is nearly free and it is the fastest way
    to see WHY a judgement went wrong: a quote from the wrong sentence is a
    retrieval problem, while a correct quote with the wrong label is a
    reasoning problem. Those need different fixes.
    """

    ok: bool
    entailment: Entailment | None = None
    quote: str = ""
    raw: str = ""
    error: str = ""

    def __bool__(self) -> bool:
        return self.ok


def build_prompt(
    claim: str,
    span: str,
    *,
    as_of: datetime | None = None,
    valid_until: datetime | None = None,
) -> str:
    """The user half of the prompt. Pure, so the exact text is testable.

    Order matters: SOURCE TEXT comes first and the CLAIM last, so the model
    reads the evidence before it knows what it is being asked to find. Leading
    with the claim invites it to go looking for confirmation.
    """
    parts = [f"SOURCE TEXT:\n{span.strip()}", ""]

    if as_of is not None and valid_until is not None:
        # Only stated when it could matter. A validity window is evidence
        # about the claim, not about the world, so it is given plainly and
        # without instruction -- the deterministic checker already enforces it.
        parts.append(
            f"(The source states this was accurate until "
            f"{valid_until:%d %B %Y}; the claim is being read as of "
            f"{as_of:%d %B %Y}.)"
        )
        parts.append("")

    parts.append(f"CLAIM:\n{claim.strip()}")
    return "\n".join(parts)


def judge_entailment(
    claim: str,
    span: str,
    *,
    mode: str = DEFAULT_MODE,
    as_of: datetime | None = None,
    valid_until: datetime | None = None,
) -> JudgeResult:
    """Judge one claim against one span.

    Args:
        claim: the assertion, in our wording.
        span: the exact source text, sliced by ``char_start``/``char_end``.
            🔴 Pass the SPAN, never the whole chunk -- a wider context lets the
            model find support somewhere else in the document and report it as
            if this span said it.
        mode: pool mode. Act 0 uses the free tier.
        as_of / valid_until: stated only when a validity window exists.

    Returns:
        A ``JudgeResult``. Check ``ok`` first; this never raises.
    """
    if not claim.strip() or not span.strip():
        return JudgeResult(ok=False, error="empty claim or span")

    # ⚠️ Imported INSIDE the function, following every shipped caller
    # (assessment, article_generation, book_content). llm_service pulls in LLM
    # SDKs, and CLAUDE.md 4.1 forbids those being reachable at URL-conf load --
    # every manage.py command runs the URL system check first, and the GitHub
    # Actions scraper installs requirements/scraper.txt, which has none of them.
    from engines.book_content.services.llm_service import llm_call_json

    prompt = build_prompt(claim, span, as_of=as_of, valid_until=valid_until)

    try:
        raw = llm_call_json(prompt, system_prompt=SYSTEM_PROMPT, mode=mode)
    except Exception as exc:  # noqa: BLE001 - provider SDKs raise varied types
        # 8.4: one statement's failure must never end a 60-statement run.
        logger.warning("df_judge_call_failed", error=str(exc))
        return JudgeResult(ok=False, error=f"call failed: {exc}")

    if not raw:
        # The pool returns "" when every capable provider is exhausted. That is
        # a supply failure, not a judgement, and must never be read as NEITHER.
        logger.warning("df_judge_pool_exhausted")
        return JudgeResult(ok=False, error="pool exhausted")

    return _parse(raw)


def _parse(raw: str) -> JudgeResult:
    """Read the model's JSON, strictly.

    An unexpected label is a FAILURE, never coerced to the nearest verdict.
    Coercion would silently convert a confused model into a confident one, and
    Gate 1 would score the coercion rather than the model.
    """
    text = raw.strip()

    # Models wrap JSON in fences despite json_mode often enough to be worth
    # handling here rather than losing the call.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("df_judge_unparseable", raw=raw[:200])
        return JudgeResult(ok=False, raw=raw, error=f"not JSON: {exc}")

    if not isinstance(payload, dict):
        return JudgeResult(ok=False, raw=raw, error="JSON is not an object")

    label = str(payload.get("entailment", "")).strip().upper()
    if label not in _ALLOWED:
        logger.warning("df_judge_bad_label", label=label[:40])
        return JudgeResult(
            ok=False, raw=raw, error=f"unexpected label: {label[:40] or '<missing>'}"
        )

    return JudgeResult(
        ok=True,
        entailment=Entailment(label),
        quote=str(payload.get("quote", "") or "").strip(),
        raw=raw,
    )
