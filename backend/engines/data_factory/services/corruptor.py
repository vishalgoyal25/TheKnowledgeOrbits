"""Deliberately break a true claim, three ways, deterministically.

Act 0, phase 0.5 (Gate 2). Spec: 00_MASTER_RECAP.md 15.4.

    true claim + its correct span  ->  corrupted claim + the SAME span
                                   ->  does the verifier still say TRUE?

🔴 Why Gate 2 is the measurement Gate 1 could not give
-------------------------------------------------------
Gate 1 scored 35%, but every miss was `not_addressed_by_source` -- the LOCATOR
handing over the wrong text. Retrieval and verification were tangled.

Here there is NO retrieval. We take a span already PROVEN to support a claim
(it scored correct in Gate 1), corrupt the claim, and re-judge against that
same span. Whatever happens next is the verifier alone.

The three mechanisms are not invented
--------------------------------------
15.4 derived them from 300 real UPSC questions: across the whole corpus, wrong
statements are built almost exclusively three ways.

  1. OVER-GENERALISATION  "ALL types of UAVs can do vertical landing"
  2. ATTRIBUTE SWAP       IL-76 described as a supersonic combat aircraft
  3. CATEGORY ERROR       mangroves "store freshwater"

Deterministic, not LLM-generated
---------------------------------
🔴 An LLM asked to "corrupt this claim" can produce something still TRUE, and
then a correct TRUE verdict scores as a verifier failure. Every corruption here
is code: the output is guaranteed to differ from the input, and guaranteed to
contradict a source that stated the original.

It is also free, reproducible across runs, and auditable -- the same three
properties that justified moving the verdict out of the model.

What counts as CAUGHT
----------------------
🟢 FALSE **or** UNPROVEN. Both kill the question, which is the correct product
behaviour (8.1: "any UNPROVEN in a counting format kills the question"). Only a
verdict of TRUE is a failure -- that is the verifier waving a planted falsehood
through to a paying student.
"""

import re
from dataclasses import dataclass
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class Mechanism(str, Enum):
    """The three distractor mechanisms of 15.4."""

    OVER_GENERALISATION = "over_generalisation"
    ATTRIBUTE_SWAP = "attribute_swap"
    CATEGORY_ERROR = "category_error"


@dataclass(frozen=True)
class Corruption:
    """One corrupted claim, with what was done to it and why it is false."""

    mechanism: Mechanism
    claim: str
    original: str
    detail: str

    @property
    def is_real(self) -> bool:
        """Whether anything actually changed. A no-op must never be scored."""
        return self.claim.strip() != self.original.strip()


# ── Mechanism 2: attribute swap ────────────────────────────────────────────

# Numbers and years. A claim that survives Gate 1 was matched against a span
# stating the ORIGINAL figure, so any different figure is flatly contradicted
# by that span -- which makes this the cleanest of the three.
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")


def _swap_number(claim: str) -> Corruption | None:
    """Change the first figure. Years shift by 3, other numbers roughly double.

    Years move by 3 rather than 1 because an adjacent year can be accidentally
    true -- a report published in 2024 about 2023 data makes "2023" and "2024"
    both appear in the source. A three-year jump does not.
    """
    year = _YEAR_RE.search(claim)
    if year:
        original = year.group(0)
        replacement = str(int(original) + 3)
        return Corruption(
            mechanism=Mechanism.ATTRIBUTE_SWAP,
            claim=claim[: year.start()] + replacement + claim[year.end() :],
            original=claim,
            detail=f"year {original} -> {replacement}",
        )

    number = _NUMBER_RE.search(claim)
    if number:
        original = number.group(0)
        value = float(original)
        # x2 + 1 so the result is never a rounding of the original and never
        # zero, and keep the integer/decimal shape so it still reads naturally.
        changed = value * 2 + 1
        replacement = str(int(changed)) if value.is_integer() else f"{changed:.1f}"
        return Corruption(
            mechanism=Mechanism.ATTRIBUTE_SWAP,
            claim=claim[: number.start()] + replacement + claim[number.end() :],
            original=claim,
            detail=f"figure {original} -> {replacement}",
        )

    return None


# ── Mechanism 1: over-generalisation ───────────────────────────────────────

# Hedge -> absolute. The source states a qualified fact; the corrupted claim
# states an unqualified one, which that source contradicts.
_HEDGE_SWAPS = (
    (re.compile(r"\baround\b", re.I), "exactly"),
    (re.compile(r"\babout\b", re.I), "exactly"),
    (re.compile(r"\bapproximately\b", re.I), "precisely"),
    (re.compile(r"\bmay\b", re.I), "must always"),
    (re.compile(r"\bcan\b", re.I), "must always"),
    (re.compile(r"\bsome\b", re.I), "all"),
    (re.compile(r"\bseveral\b", re.I), "all"),
    (re.compile(r"\boften\b", re.I), "always"),
    (re.compile(r"\bcertain\b", re.I), "all"),
    (re.compile(r"\bis used to\b", re.I), "is the only instrument used to"),
    (re.compile(r"\baims to\b", re.I), "is legally required to"),
)


def _over_generalise(claim: str) -> Corruption | None:
    """Replace the first hedge with an absolute.

    "around 8%" -> "exactly 8%" is contradicted by a source saying "around".
    "may initiate" -> "must always initiate" is contradicted by a source
    granting discretion -- which is the modal error UPSC uses constantly.
    """
    for pattern, replacement in _HEDGE_SWAPS:
        match = pattern.search(claim)
        if match:
            return Corruption(
                mechanism=Mechanism.OVER_GENERALISATION,
                claim=claim[: match.start()] + replacement + claim[match.end() :],
                original=claim,
                detail=f"{match.group(0)!r} -> {replacement!r}",
            )
    return None


# ── Mechanism 3: category error ────────────────────────────────────────────

# A real institution replaced by another real one of a DIFFERENT kind. Real,
# because an invented name is easy to reject on implausibility alone and would
# flatter the result; different kind, because that is what makes it a category
# error rather than a near miss.
_INSTITUTION_RE = re.compile(
    r"\b(?:the\s+)?(?:Reserve Bank of India|Ministry of [A-Z][\w\s]+?|"
    r"Government of India|Bureau of Indian Standards|United Nations|INTERPOL|"
    r"Supreme Court|Press Information Bureau|World Food Programme|DRDO|ISRO)\b"
)

_WRONG_CATEGORY = "the Botanical Survey of India"


def _category_error(claim: str) -> Corruption | None:
    """Reassign the claim to an organisation of the wrong kind.

    The Botanical Survey of India is a real body that plainly does not issue
    currency, set bomb-disposal standards or run peacekeeping missions. A
    source naming the true body contradicts it.
    """
    match = _INSTITUTION_RE.search(claim)
    if match and _WRONG_CATEGORY.lower() not in claim.lower():
        return Corruption(
            mechanism=Mechanism.CATEGORY_ERROR,
            claim=claim[: match.start()] + _WRONG_CATEGORY + claim[match.end() :],
            original=claim,
            detail=f"{match.group(0)!r} -> {_WRONG_CATEGORY!r}",
        )
    return None


_BUILDERS = (_swap_number, _over_generalise, _category_error)


def corrupt(claim: str) -> list[Corruption]:
    """Every corruption that applies to this claim.

    Returns fewer than three when a mechanism has nothing to grip: a claim with
    no figure cannot have one swapped, and one naming no institution cannot
    suffer a category error.

    ⚠️ That is reported, never padded. Inventing a corruption to reach three
    would mean scoring the verifier on something UPSC does not actually do.
    """
    found = [built for builder in _BUILDERS if (built := builder(claim)) is not None]
    real = [c for c in found if c.is_real]

    if len(real) < len(found):  # pragma: no cover - defensive
        logger.warning("df_corruptor_noop_dropped", claim=claim[:60])

    return real
