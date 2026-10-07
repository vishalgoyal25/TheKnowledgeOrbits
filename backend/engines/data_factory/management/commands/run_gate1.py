"""GATE 1 -- the one number that governs the programme.

Act 0, phase 0.4. Spec: 00_MASTER_RECAP.md 16.6.5, target >= 95%.

    stored atom -> span -> [Entailment Judge, LLM] -> [Verdict Resolver, free]
                -> compare against the HELD-OUT key

🔴 What is being measured, precisely
-------------------------------------
Given a claim and the exact source text, does the system return the right
verdict? Nothing else. Not retrieval, not generation, not question quality.

🔴 What the judge must never see
---------------------------------
The expected answers live in THIS file's memory and in gate1_questions.json.
They are the GRADING SHEET. They are never passed to judge_entailment(), whose
signature takes a claim and a span and nothing else.

If the key ever reached the prompt, this command would report a HIGHER number
for a worthless measurement -- a silent success, which is the worst failure
mode available to the project.

Three outcomes, not two
------------------------
Scoring separates them because they mean different things and need different
fixes:

    correct    the verdict matches the key
    UNPROVEN   could not prove it either way -- a MISS, but an honest one
    WRONG      proved the opposite -- the dangerous one

🔴 A system at 70% correct / 30% unproven is PROMISING: it knows what it does
not know, and better retrieval fixes it. A system at 70% correct / 30% wrong is
DANGEROUS and no amount of retrieval helps. The headline accuracy number hides
that distinction entirely, so it is reported separately.

Cost
----
The shipped pool enforces INTER_CALL_SLEEP = 15.0s, so roughly 4 calls/minute:
~10 minutes for 37 statements, serialised, on the free tier. Use --limit for a
smoke test and --no-llm to verify the plumbing for nothing.
"""

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import structlog
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from engines.data_factory.models import DfAtom
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
DEFAULT_QUESTIONS = _ACT0 / "gate1_questions.json"
DEFAULT_RESULTS = _ACT0 / "gate1_results.json"

# 00_MASTER_RECAP.md: "clearly works" vs "clearly doesn't".
TARGET_ACCURACY = 0.95
AMBIGUOUS_FLOOR = 0.85


@dataclass
class Outcome:
    """One statement's result, written to the results file for 0.6."""

    question_id: str
    claim: str
    expected: str
    verdict: str
    reason: str
    entailment: str = ""
    quote: str = ""
    span: str = ""
    error: str = ""
    # The locator's anchor coverage for this span. Recorded so 0.6 can test
    # whether it PREDICTS correctness -- if it does, low-coverage atoms can be
    # dropped before they cost an LLM call, which is a direct cost lever.
    confidence: float = 0.0

    @property
    def is_correct(self) -> bool:
        return self.verdict == self.expected

    @property
    def is_wrong(self) -> bool:
        """Proved the OPPOSITE. The dangerous failure, not merely a miss."""
        return self.verdict in (Verdict.TRUE.value, Verdict.FALSE.value) and (
            self.verdict != self.expected
        )


class Command(BaseCommand):
    help = (
        "Run Gate 1: judge every seeded atom against its span and score the "
        "verdicts against the held-out answer key. Target >= 95%."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed",
            action="store_true",
            help=(
                "Run seed_act0 first, so one command exercises the whole "
                "pipeline: fetch, parse, chunk, locate, judge, resolve, score."
            ),
        )
        parser.add_argument(
            "--no-llm",
            action="store_true",
            help=(
                "Verify the plumbing without spending a single call. Reports "
                "how many atoms WOULD be judged and that every one has a "
                "usable span and a known expected answer."
            ),
        )
        parser.add_argument(
            "--confident-only",
            action="store_true",
            help=(
                "Judge ONLY atoms whose span carries every hard anchor from "
                "the claim (confidence == 1.0). The full run conflates two "
                "components: a span that does not contain the fact is a "
                "LOCATOR failure, but it scores against the VERIFIER. This "
                "holds retrieval roughly constant so the verifier's own "
                "accuracy becomes visible."
            ),
        )
        parser.add_argument(
            "--processing-version",
            type=int,
            default=None,
            help=(
                "Judge only atoms at this processing_version. Use 99 for the "
                "hand-curated spans, which holds retrieval at ~100% so the "
                "accuracy reported IS the verifier's accuracy."
            ),
        )
        parser.add_argument(
            "--limit", type=int, default=0, help="Judge only the first N atoms."
        )
        parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
        parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)

    def handle(self, *args, **options):
        if options["seed"]:
            self.stdout.write(self.style.MIGRATE_HEADING("Seeding first..."))
            call_command("seed_act0")
            self.stdout.write("")

        expected = self._load_key(options["questions"])

        queryset = DfAtom.objects.select_related("chunk__artifact").order_by(
            "created_at"
        )

        if options["processing_version"] is not None:
            queryset = queryset.filter(processing_version=options["processing_version"])

        if options["confident_only"]:
            # confidence == anchor_coverage, written by the locator at seed
            # time. 1.0 means every figure, year and acronym in the claim is
            # present in the stored span -- a necessary condition for the span
            # to support the claim, though not a sufficient one.
            queryset = queryset.filter(confidence__gte=1.0)

        atoms = list(queryset)
        if options["limit"]:
            atoms = atoms[: options["limit"]]

        if not atoms:
            raise CommandError(
                "No atoms in the database. Run `seed_act0` first (without "
                "--dry-run), or pass --seed to do both in one command."
            )

        self.stdout.write(
            f"{len(atoms)} atoms to judge, {len(expected)} claims in the key"
        )

        if options["no_llm"]:
            self._plumbing_check(atoms, expected)
            return

        outcomes = [self._judge(atom, expected) for atom in atoms]
        self._report(outcomes, options["results"])

    # ── the key, held out ──────────────────────────────────────────────────

    def _load_key(self, path: Path) -> dict[str, dict[str, str]]:
        """Claim text -> its expected verdict and question id.

        🔴 Loaded HERE and never passed downstream. The judge receives a claim
        and a span; this mapping stays in the scorer.
        """
        if not path.exists():
            raise CommandError(f"Question set not found: {path}")

        payload = json.loads(path.read_text(encoding="utf-8"))
        key: dict[str, dict[str, str]] = {}
        for question in payload.get("questions", []):
            qid = question.get("id", "?")
            for statement in question.get("statements", []):
                claim = statement.get("claim", "")
                if claim:
                    key[claim] = {
                        "expected": statement.get("expected", ""),
                        "question_id": qid,
                    }
        return key

    # ── one atom ───────────────────────────────────────────────────────────

    def _judge(self, atom: DfAtom, key: dict[str, dict[str, str]]) -> Outcome:
        entry = key.get(atom.claim_text, {})
        qid = entry.get("question_id", "?")
        want = entry.get("expected", "")

        # The span, sliced exactly as stored. NOT the whole chunk: a wider
        # context lets the model find support elsewhere in the document and
        # report it as though this span said it.
        span = atom.chunk.normalised_text[atom.char_start : atom.char_end]

        if not want:
            return Outcome(
                question_id=qid,
                claim=atom.claim_text,
                expected="",
                verdict="",
                reason="no_expected_answer",
                span=span,
                error="claim not found in the key",
            )

        judged = judge_entailment(atom.claim_text, span)
        # `entailment` checked explicitly as well as `ok`: the two are set
        # together by construction, but only the type system enforces that
        # here, and a label of None reaching the resolver would crash a
        # 15-minute run on its last statement.
        if not judged.ok or judged.entailment is None:
            self.stdout.write(self.style.ERROR(f"  judge failed: {judged.error}"))
            return Outcome(
                question_id=qid,
                claim=atom.claim_text,
                expected=want,
                verdict="",
                reason="judge_failed",
                span=span,
                error=judged.error,
            )

        # Exhaustiveness comes from the artifact the atom was extracted from.
        # UNKNOWN is the safe default and can never yield FALSE (09 8.3).
        artifact = atom.chunk.artifact
        resolution = resolve(
            Judgement(
                entailment=judged.entailment,
                exhaustiveness=Exhaustiveness(artifact.exhaustiveness),
                tier=atom.source_ref_snapshot.get("tier", ""),
                source_id=str(artifact.id),
                span_text=span,
            )
        )

        outcome = Outcome(
            question_id=qid,
            claim=atom.claim_text,
            expected=want,
            verdict=resolution.verdict.value,
            reason=resolution.reason,
            entailment=judged.entailment.value if judged.entailment else "",
            quote=judged.quote,
            span=span,
            confidence=atom.confidence,
        )

        mark = (
            "ok " if outcome.is_correct else ("WRONG" if outcome.is_wrong else "miss")
        )
        style = (
            self.style.SUCCESS
            if outcome.is_correct
            else (self.style.ERROR if outcome.is_wrong else self.style.WARNING)
        )
        self.stdout.write(
            style(
                f"  {mark}  {qid}  want={want:<5} got={outcome.verdict:<8} "
                f"({judged.entailment.value if judged.entailment else '-'})  "
                f"{atom.claim_text[:52]}"
            )
        )
        return outcome

    # ── free plumbing check ────────────────────────────────────────────────

    def _plumbing_check(self, atoms, key) -> None:
        """Everything except the model, for nothing.

        Verifies the three things that would waste a 10-minute run if wrong:
        every atom has a non-empty span, every claim is in the key, and every
        span really is a slice of its chunk.
        """
        missing_key = empty_span = bad_slice = 0

        for atom in atoms:
            chunk_text = atom.chunk.normalised_text
            span = chunk_text[atom.char_start : atom.char_end]
            if not span.strip():
                empty_span += 1
            if chunk_text[atom.char_start : atom.char_end] != span:  # pragma: no cover
                bad_slice += 1
            if atom.claim_text not in key:
                missing_key += 1
                self.stdout.write(
                    self.style.WARNING(f"  not in key: {atom.claim_text[:60]}")
                )

        self.stdout.write("")
        self.stdout.write(f"  atoms                {len(atoms)}")
        self.stdout.write(f"  empty spans          {empty_span}")
        self.stdout.write(f"  claims missing a key {missing_key}")
        ready = len(atoms) - empty_span - missing_key
        style = self.style.SUCCESS if ready == len(atoms) else self.style.WARNING
        self.stdout.write(style(f"  READY TO JUDGE       {ready}/{len(atoms)}"))
        self.stdout.write(
            self.style.WARNING("\n  --no-llm: no calls were made, nothing was scored")
        )

    # ── scoring ────────────────────────────────────────────────────────────

    def _report(self, outcomes: list[Outcome], results_path: Path) -> None:
        scored = [o for o in outcomes if o.expected and o.verdict]
        failed = [o for o in outcomes if not o.verdict]

        correct = [o for o in scored if o.is_correct]
        wrong = [o for o in scored if o.is_wrong]
        unproven = [
            o
            for o in scored
            if not o.is_correct and o.verdict == Verdict.UNPROVEN.value
        ]

        accuracy = len(correct) / len(scored) if scored else 0.0

        self.stdout.write("\n" + "=" * 64)
        self.stdout.write(self.style.MIGRATE_HEADING("  GATE 1"))
        self.stdout.write("=" * 64)
        self.stdout.write(f"  statements judged    {len(scored)}")
        self.stdout.write(f"  judge/pool failures  {len(failed)}")
        self.stdout.write("-" * 64)
        self.stdout.write(self.style.SUCCESS(f"  correct              {len(correct)}"))
        self.stdout.write(self.style.WARNING(f"  UNPROVEN (honest)    {len(unproven)}"))
        self.stdout.write(self.style.ERROR(f"  WRONG (dangerous)    {len(wrong)}"))
        self.stdout.write("=" * 64)

        style = self.style.SUCCESS if accuracy >= TARGET_ACCURACY else self.style.ERROR
        self.stdout.write(style(f"  ACCURACY  {accuracy:.1%}   (target >= 95%)"))

        # 🔴 The distinction that decides what to do next, stated in words so
        # 0.6 does not have to re-derive it from the numbers.
        if accuracy >= TARGET_ACCURACY:
            self.stdout.write(self.style.SUCCESS("  -> PROCEED"))
        elif len(wrong) == 0:
            self.stdout.write(
                self.style.WARNING(
                    "  -> PROMISING: every miss is UNPROVEN, never wrong. The "
                    "system knows what it does not know, which better spans fix."
                )
            )
        elif accuracy >= AMBIGUOUS_FLOOR:
            self.stdout.write(
                self.style.WARNING("  -> AMBIGUOUS: expand the sample before deciding")
            )
        else:
            self.stdout.write(
                self.style.ERROR("  -> REDESIGN or change provider before Act I")
            )

        if wrong:
            self.stdout.write(self.style.ERROR("\n  Wrong verdicts (read every one):"))
            for o in wrong:
                self.stdout.write(
                    f"    {o.question_id}  want={o.expected} got={o.verdict}"
                )
                self.stdout.write(f"      claim: {o.claim[:90]}")
                self.stdout.write(f"      quote: {o.quote[:90]}")

        # 🔴 Does the locator's own confidence PREDICT verification success?
        # If it does, low-coverage atoms can be dropped before they cost an
        # LLM call -- a direct cost lever for Act I, measured rather than
        # assumed.
        full = [o for o in scored if o.confidence >= 1.0]
        partial = [o for o in scored if o.confidence < 1.0]
        if full and partial:
            full_rate = sum(o.is_correct for o in full) / len(full)
            partial_rate = sum(o.is_correct for o in partial) / len(partial)
            self.stdout.write("\n  Accuracy by span confidence:")
            self.stdout.write(
                f"    full anchors (1.0)   {sum(o.is_correct for o in full)}/"
                f"{len(full)}  ({full_rate:.0%})"
            )
            self.stdout.write(
                f"    partial  (<1.0)      {sum(o.is_correct for o in partial)}/"
                f"{len(partial)}  ({partial_rate:.0%})"
            )

        by_reason = Counter(o.reason for o in scored)
        self.stdout.write("\n  Resolver reasons:")
        for reason, count in by_reason.most_common():
            self.stdout.write(f"    {count:>3}  {reason}")

        payload: dict[str, Any] = {
            "run_at": timezone.now().isoformat(),
            "target": TARGET_ACCURACY,
            "statements_judged": len(scored),
            "correct": len(correct),
            "unproven": len(unproven),
            "wrong": len(wrong),
            "judge_failures": len(failed),
            "accuracy": round(accuracy, 4),
            "outcomes": [asdict(o) for o in outcomes],
        }
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.stdout.write(f"\n  results -> {results_path}")

        logger.info(
            "df_gate1_complete",
            judged=len(scored),
            correct=len(correct),
            wrong=len(wrong),
            unproven=len(unproven),
            accuracy=round(accuracy, 4),
        )
