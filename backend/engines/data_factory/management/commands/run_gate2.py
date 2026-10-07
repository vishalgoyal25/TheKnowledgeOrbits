"""GATE 2 -- can the verifier catch a falsehood that was planted on purpose?

Act 0, phase 0.5. Spec: 00_MASTER_RECAP.md 15.4, target >= 90%.

    a span PROVEN to support a claim (it scored correct in Gate 1)
      -> corrupt the claim three ways, deterministically
      -> judge each against the SAME span
      -> does anything still come back TRUE?

🔴 Why this is a cleaner measurement than Gate 1
-------------------------------------------------
Gate 1 reported 35%, but every miss was `not_addressed_by_source`: the locator
handing over the wrong text. Retrieval and verification were tangled, and the
number belonged to neither.

**Gate 2 contains no retrieval at all.** The span is fixed and already known to
support the original claim. Only the claim changes, and only by code. Whatever
happens is the verifier alone -- which is what Act 0 was commissioned to
measure.

What counts as CAUGHT
----------------------
🟢 **FALSE or UNPROVEN.** Both kill the question, which is correct product
behaviour (8.1: "any UNPROVEN in a counting format kills the question").

🔴 Only TRUE is a failure. That is the verifier waving a planted falsehood
through to a paying student, and it is the single outcome this gate exists to
count.

Input comes from Gate 1's own successes
----------------------------------------
Only statements that (a) expected TRUE and (b) Gate 1 got right are corrupted.
That pairing is the guarantee the whole gate rests on: the span demonstrably
states the original fact, so a corruption of that fact is demonstrably
contradicted BY THAT SPAN. Corrupting a claim whose span never supported it
would measure nothing.
"""

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import structlog
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from engines.data_factory.services.corruptor import Mechanism, corrupt
from engines.data_factory.services.entailment_judge import judge_entailment
from engines.data_factory.services.verdict_resolver import (
    Exhaustiveness,
    Judgement,
    Verdict,
    resolve,
)

logger = structlog.get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_ACT0 = _REPO_ROOT / "FEATURES" / "DATA_FACTORY" / "act0"
DEFAULT_GATE1 = _ACT0 / "gate1_results.json"
DEFAULT_RESULTS = _ACT0 / "gate2_results.json"

TARGET_CATCH_RATE = 0.90


@dataclass
class Trial:
    question_id: str
    mechanism: str
    original: str
    corrupted: str
    detail: str
    verdict: str
    entailment: str = ""
    quote: str = ""
    error: str = ""

    @property
    def caught(self) -> bool:
        """Anything other than TRUE kills the question, which is correct."""
        return self.verdict in (Verdict.FALSE.value, Verdict.UNPROVEN.value)

    @property
    def waved_through(self) -> bool:
        """🔴 The only real failure: a planted falsehood accepted as TRUE."""
        return self.verdict == Verdict.TRUE.value


class Command(BaseCommand):
    help = (
        "Run Gate 2: corrupt every claim Gate 1 verified correctly, re-judge "
        "against the same span, and count how many corruptions slip through."
    )

    def add_arguments(self, parser):
        parser.add_argument("--gate1", type=Path, default=DEFAULT_GATE1)
        parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Show every corruption that WOULD be judged, and spend nothing. "
                "Worth doing first: a corruption that is accidentally still "
                "true would score a correct TRUE as a verifier failure."
            ),
        )
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **options):
        path: Path = options["gate1"]
        if not path.exists():
            raise CommandError(
                f"Gate 1 results not found: {path}\nRun `run_gate1` first."
            )

        payload = json.loads(path.read_text(encoding="utf-8"))

        # The guarantee: expected TRUE, verdict TRUE, and a span recorded. Only
        # then is the span known to state the fact being corrupted.
        sources = [
            o
            for o in payload.get("outcomes", [])
            if o.get("expected") == Verdict.TRUE.value
            and o.get("verdict") == Verdict.TRUE.value
            and o.get("span")
        ]

        if not sources:
            raise CommandError(
                "No verified-TRUE statements in the Gate 1 results. Gate 2 "
                "needs spans already proven to support their claim."
            )

        self.stdout.write(f"{len(sources)} verified span/claim pairs from Gate 1\n")

        trials: list[Trial] = []
        for outcome in sources:
            for corruption in corrupt(outcome["claim"]):
                trials.append(
                    Trial(
                        question_id=outcome.get("question_id", "?"),
                        mechanism=corruption.mechanism.value,
                        original=corruption.original,
                        corrupted=corruption.claim,
                        detail=corruption.detail,
                        verdict="",
                    )
                )

        if options["limit"]:
            trials = trials[: options["limit"]]

        if options["dry_run"]:
            self._preview(trials)
            return

        for trial in trials:
            self._judge(trial, sources)

        self._report(trials, options["results"])

    # ── free preview ───────────────────────────────────────────────────────

    def _preview(self, trials: list[Trial]) -> None:
        """Read every corruption before paying to judge it.

        🔴 The one way this gate can lie: a corruption that is accidentally
        still TRUE. Then a correct TRUE verdict is counted as the verifier
        waving a falsehood through, and the gate reports a failure that did not
        happen. Deterministic mechanisms make that unlikely; reading them makes
        it checkable.
        """
        by_mechanism = Counter(t.mechanism for t in trials)
        for trial in trials:
            self.stdout.write(f"\n  {trial.question_id}  [{trial.mechanism}]")
            self.stdout.write(f"    {trial.detail}")
            self.stdout.write(f"    was: {trial.original[:100]}")
            self.stdout.write(self.style.WARNING(f"    now: {trial.corrupted[:100]}"))

        self.stdout.write("\n" + "=" * 62)
        self.stdout.write(f"  {len(trials)} corruptions would be judged")
        for mechanism in Mechanism:
            self.stdout.write(
                f"    {by_mechanism.get(mechanism.value, 0):>3}  {mechanism.value}"
            )
        self.stdout.write(self.style.WARNING("\n  DRY RUN - nothing was judged"))

    # ── one trial ──────────────────────────────────────────────────────────

    def _judge(self, trial: Trial, sources: list[dict]) -> None:
        span = next(
            (o["span"] for o in sources if o["claim"] == trial.original),
            "",
        )
        if not span:  # pragma: no cover - defensive
            trial.error = "span not found for original claim"
            return

        judged = judge_entailment(trial.corrupted, span)
        # `entailment` checked alongside `ok` -- see the same note in
        # run_gate1. A None label reaching the resolver would crash the run.
        if not judged.ok or judged.entailment is None:
            trial.error = judged.error
            self.stdout.write(self.style.ERROR(f"  judge failed: {judged.error}"))
            return

        # Exhaustiveness is UNKNOWN here by design: Gate 2 asks whether the
        # verifier catches the corruption, and leaning on an EXHAUSTIVE source
        # to turn silence into FALSE would hand it the answer for free.
        resolution = resolve(
            Judgement(
                entailment=judged.entailment,
                exhaustiveness=Exhaustiveness.UNKNOWN,
                tier="T1",
            )
        )
        trial.verdict = resolution.verdict.value
        trial.entailment = judged.entailment.value
        trial.quote = judged.quote

        if trial.waved_through:
            style, mark = self.style.ERROR, "WAVED THROUGH"
        else:
            style, mark = self.style.SUCCESS, "caught       "
        self.stdout.write(
            style(
                f"  {mark}  {trial.question_id}  {trial.mechanism:<20} "
                f"-> {trial.verdict:<8} ({trial.entailment})"
            )
        )

    # ── scoring ────────────────────────────────────────────────────────────

    def _report(self, trials: list[Trial], results_path: Path) -> None:
        judged = [t for t in trials if t.verdict]
        caught = [t for t in judged if t.caught]
        through = [t for t in judged if t.waved_through]
        rate = len(caught) / len(judged) if judged else 0.0

        self.stdout.write("\n" + "=" * 62)
        self.stdout.write(self.style.MIGRATE_HEADING("  GATE 2"))
        self.stdout.write("=" * 62)
        self.stdout.write(f"  corruptions judged   {len(judged)}")
        self.stdout.write(f"  judge failures       {len(trials) - len(judged)}")
        self.stdout.write("-" * 62)
        self.stdout.write(self.style.SUCCESS(f"  caught               {len(caught)}"))
        self.stdout.write(self.style.ERROR(f"  WAVED THROUGH        {len(through)}"))
        self.stdout.write("=" * 62)

        style = self.style.SUCCESS if rate >= TARGET_CATCH_RATE else self.style.ERROR
        self.stdout.write(style(f"  CATCH RATE  {rate:.1%}   (target >= 90%)"))

        # Per mechanism, because they are not equally hard and a single number
        # hides which kind of falsehood gets through.
        self.stdout.write("\n  By mechanism:")
        for mechanism in Mechanism:
            rows = [t for t in judged if t.mechanism == mechanism.value]
            if not rows:
                continue
            hits = sum(t.caught for t in rows)
            self.stdout.write(
                f"    {mechanism.value:<22} {hits}/{len(rows)}  "
                f"({hits / len(rows):.0%})"
            )

        if through:
            self.stdout.write(self.style.ERROR("\n  Waved through (read every one):"))
            for t in through:
                self.stdout.write(f"    {t.question_id}  {t.mechanism}  {t.detail}")
                self.stdout.write(f"      {t.corrupted[:100]}")
                self.stdout.write(f"      quote: {t.quote[:100]}")

        payload = {
            "run_at": timezone.now().isoformat(),
            "target": TARGET_CATCH_RATE,
            "judged": len(judged),
            "caught": len(caught),
            "waved_through": len(through),
            "catch_rate": round(rate, 4),
            "trials": [asdict(t) for t in trials],
        }
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.stdout.write(f"\n  results -> {results_path}")

        logger.info(
            "df_gate2_complete",
            judged=len(judged),
            caught=len(caught),
            waved_through=len(through),
            catch_rate=round(rate, 4),
        )
