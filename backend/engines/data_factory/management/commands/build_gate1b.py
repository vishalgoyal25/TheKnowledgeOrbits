"""Resolve hand-chosen evidence sentences into verbatim spans for Gate 1b.

Act 0, phase 0.4b. Spec: act0/0.4_GATE1_FINDINGS.md §6.

    gate1b_selectors.json  (a human's judgements: WHICH sentence, and a label)
        + act0/extracted/<qid>.txt   (the parser's own output)
        -> gate1b_spans.json         (the verbatim text, copied BY CODE)

🔴 Why this command exists at all
----------------------------------
The first curation attempt (`curate_act0`, 2026-10-07) located **2 of 9**
spans. The cause was not the idea; it was the input format. It asked a human
for anchor PHRASES, I supplied them from approximation, and government pages
carry curly apostrophes (U+2019), backticks used as apostrophes and
non-breaking spaces. An approximated anchor fails on a character nobody can
see.

So nothing is retyped here. The selector file addresses a sentence by LINE
RANGE in the dump, and this command copies the characters out of the dump. The
human contributes a judgement; every byte comes from the parser.

Two further things are never retyped:

    claim text   read from gate1_questions.json by (question_id, index), so it
                 cannot drift from the answer key, which is keyed on it
    offsets      not computed here at all -- `curate_act0` computes them
                 against the STORED chunk, which is what an atom indexes into

🔴 The rule this command enforces mechanically
-----------------------------------------------
Every one of the 60 statements must carry exactly one label, and the file is
rejected if any is missing or duplicated. The denominator is therefore fixed by
what the DOCUMENTS contain, before a single verdict is seen -- which is the one
discipline the retracted "97.7% combined verifier accuracy" broke.

What the labels cost
--------------------
    SPAN_SUPPLIED     enters the denominator -- a real verifier test
    EVIDENCE_ABSENT   leaves it. Measures extraction (2.7), not verification
    SOURCE_FAILED     leaves it. Measures fetching (2.5)

⚠️ A high score on a small denominator is NOT a pipeline result. This command
prints both numbers side by side so the two can never be quoted as one.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
from django.core.management.base import BaseCommand, CommandError

logger = structlog.get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_ACT0 = _REPO_ROOT / "FEATURES" / "DATA_FACTORY" / "act0"
DEFAULT_SELECTORS = _ACT0 / "gate1b_selectors.json"
DEFAULT_QUESTIONS = _ACT0 / "gate1_questions.json"
DEFAULT_EXTRACTED = _ACT0 / "extracted"
DEFAULT_OUT = _ACT0 / "gate1b_spans.json"

# seed_act0 --dump writes: header lines, "", "="*70, "", parsed.text
_SEPARATOR = "\n" + ("=" * 70) + "\n\n"

LABEL_SUPPLIED = "SPAN_SUPPLIED"
LABEL_ABSENT = "EVIDENCE_ABSENT"
LABEL_FAILED = "SOURCE_FAILED"
_LABELS = (LABEL_SUPPLIED, LABEL_ABSENT, LABEL_FAILED)


@dataclass
class Resolved:
    """One statement, labelled, with its verbatim span if it has one."""

    question_id: str
    statement_index: int
    claim: str
    expected: str
    label: str
    source_url: str = ""
    source_tier: str = ""
    exact_text: str = ""
    lines: list[int] = field(default_factory=list)
    occurrences: int = 0
    absent_kind: str = ""
    falsification_mode: str = ""
    reason: str = ""


class Command(BaseCommand):
    help = (
        "Resolve gate1b_selectors.json against the dumps in act0/extracted/ "
        "and write gate1b_spans.json with every span copied verbatim. "
        "Validates that all 60 statements carry exactly one label."
    )

    def add_arguments(self, parser):
        parser.add_argument("--selectors", type=Path, default=DEFAULT_SELECTORS)
        parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
        parser.add_argument("--extracted", type=Path, default=DEFAULT_EXTRACTED)
        parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
        parser.add_argument(
            "--check",
            action="store_true",
            help="Validate and report without writing the output file.",
        )
        parser.add_argument(
            "--show",
            type=str,
            default="",
            help=(
                "Print the full resolved span for one question id, so a "
                "curation can be read before it is trusted."
            ),
        )

    def handle(self, *args, **options):
        selectors = self._load_json(options["selectors"])
        questions = self._load_json(options["questions"])
        extracted: Path = options["extracted"]
        if not extracted.is_dir():
            raise CommandError(f"Extracted dumps not found: {extracted}")

        statements = _index_statements(questions)
        entries = _index_entries(selectors)
        self._verify_coverage(statements, entries)

        bodies: dict[str, str] = {}
        file_lines: dict[str, list[str]] = {}
        resolved: list[Resolved] = []
        failures: list[str] = []

        for key in sorted(statements):
            meta = statements[key]
            entry = entries[key]
            label = entry.get("label", "")
            if label not in _LABELS:
                failures.append(f"{key[0]}#{key[1]}: unknown label {label!r}")
                continue

            item = Resolved(
                question_id=key[0],
                statement_index=key[1],
                claim=meta["claim"],
                expected=meta["expected"],
                label=label,
                source_url=meta["source_url"],
                source_tier=meta["source_tier"],
                absent_kind=entry.get("absent_kind", ""),
                falsification_mode=entry.get("falsification_mode", ""),
                reason=entry.get("reason", ""),
            )

            if label == LABEL_SUPPLIED:
                error = self._resolve_span(item, entry, extracted, bodies, file_lines)
                if error:
                    failures.append(f"{key[0]}#{key[1]}: {error}")
                    continue

            resolved.append(item)

        if failures:
            for line in failures:
                self.stdout.write(self.style.ERROR(f"  {line}"))
            raise CommandError(
                f"{len(failures)} selector(s) could not be resolved. Nothing "
                "was written -- fix the selector file and re-run."
            )

        if options["show"]:
            self._show(resolved, options["show"])

        self._report(resolved, selectors)

        if options["check"]:
            self.stdout.write(self.style.WARNING("\n  --check: nothing was written"))
            return

        self._write(resolved, selectors, questions, options["out"])

    # ── loading ────────────────────────────────────────────────────────────

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise CommandError(f"Not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    # ── the one check that keeps the denominator honest ────────────────────

    def _verify_coverage(self, statements: dict, entries: dict) -> None:
        """Every statement labelled exactly once, no strays.

        🔴 This is the mechanical form of "label every statement BEFORE seeing
        any verdict". If a statement could be omitted, the denominator would
        become a choice, and a chosen denominator is how the retracted 97.7%
        happened.
        """
        missing = sorted(set(statements) - set(entries))
        strays = sorted(set(entries) - set(statements))
        problems: list[str] = []
        for qid, index in missing:
            problems.append(f"no label for {qid} statement {index}")
        for qid, index in strays:
            problems.append(f"label for a statement that does not exist: {qid} {index}")
        if problems:
            for line in problems:
                self.stdout.write(self.style.ERROR(f"  {line}"))
            raise CommandError(
                f"{len(problems)} coverage problem(s). Every statement in the "
                "question set needs exactly one label."
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"  coverage OK: {len(statements)} statements, each labelled once"
            )
        )

    # ── one span, copied rather than typed ─────────────────────────────────

    def _resolve_span(
        self,
        item: Resolved,
        entry: dict[str, Any],
        extracted: Path,
        bodies: dict[str, str],
        file_lines: dict[str, list[str]],
    ) -> str:
        selector = entry.get("selector") or {}
        lines = selector.get("lines") or []
        if len(lines) != 2:
            return "selector needs a two-element 'lines' range"

        qid = item.question_id
        if qid not in bodies:
            path = extracted / f"{qid}.txt"
            if not path.exists():
                return f"dump not found: {path.name}"
            content = path.read_text(encoding="utf-8")
            if _SEPARATOR not in content:
                return f"{path.name} has no header separator"
            bodies[qid] = content.split(_SEPARATOR, 1)[1]
            file_lines[qid] = content.split("\n")

        start, end = int(lines[0]), int(lines[1])
        all_lines = file_lines[qid]
        if not 1 <= start <= end <= len(all_lines):
            return f"line range {start}-{end} outside the file (1-{len(all_lines)})"

        # Stripping is safe: removing leading/trailing WHITESPACE leaves a
        # substring that still occurs verbatim in the body, which the check
        # below proves rather than assumes.
        text = "\n".join(all_lines[start - 1 : end]).strip()
        if not text:
            return f"line range {start}-{end} is blank"

        expect = selector.get("expect_contains", "")
        if expect and expect not in text:
            return (
                f"expect_contains {expect[:40]!r} is not in the text at lines "
                f"{start}-{end} -- the range is probably wrong"
            )

        body = bodies[qid]
        occurrences = body.count(text)
        if occurrences == 0:
            # Would mean the slice crossed the header boundary, or the dump
            # was rewritten since the line numbers were read.
            return (
                f"lines {start}-{end} do not occur in the document body -- the "
                "range may include header lines"
            )

        item.exact_text = text
        item.lines = [start, end]
        item.occurrences = occurrences
        return ""

    # ── reading a curation before trusting it ──────────────────────────────

    def _show(self, resolved: list[Resolved], question_id: str) -> None:
        wanted = [r for r in resolved if r.question_id == question_id]
        if not wanted:
            self.stdout.write(self.style.WARNING(f"  no entries for {question_id}"))
            return
        for item in wanted:
            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"  {item.question_id} #{item.statement_index}  "
                    f"[{item.expected}]  {item.label}"
                )
            )
            self.stdout.write(f"    claim : {item.claim}")
            self.stdout.write(f"    why   : {item.reason}")
            if item.exact_text:
                self.stdout.write(
                    f"    lines : {item.lines[0]}-{item.lines[1]} "
                    f"({len(item.exact_text)} chars, {item.occurrences}x in body)"
                )
                for line in item.exact_text.split("\n"):
                    self.stdout.write(f"    | {line}")

    # ── the two numbers, kept apart ────────────────────────────────────────

    def _report(self, resolved: list[Resolved], selectors: dict[str, Any]) -> None:
        supplied = [r for r in resolved if r.label == LABEL_SUPPLIED]
        absent = [r for r in resolved if r.label == LABEL_ABSENT]
        failed = [r for r in resolved if r.label == LABEL_FAILED]

        self.stdout.write("")
        self.stdout.write("=" * 64)
        self.stdout.write(self.style.MIGRATE_HEADING("  GATE 1b -- THE DENOMINATOR"))
        self.stdout.write("=" * 64)
        self.stdout.write(f"  statements in the question set   {len(resolved)}")
        self.stdout.write("-" * 64)
        self.stdout.write(
            self.style.SUCCESS(f"  SPAN_SUPPLIED  (the denominator)  {len(supplied)}")
        )
        self.stdout.write(
            self.style.WARNING(f"  EVIDENCE_ABSENT (extraction loss) {len(absent)}")
        )
        self.stdout.write(
            self.style.WARNING(f"  SOURCE_FAILED   (fetch loss)      {len(failed)}")
        )
        self.stdout.write("=" * 64)

        want_true = sum(1 for r in supplied if r.expected == "TRUE")
        want_false = len(supplied) - want_true
        self.stdout.write(
            f"  denominator split: {want_true} expected TRUE, "
            f"{want_false} expected FALSE"
        )

        kinds: dict[str, int] = {}
        for item in absent:
            kinds[item.absent_kind or "unspecified"] = (
                kinds.get(item.absent_kind or "unspecified", 0) + 1
            )
        if kinds:
            self.stdout.write("\n  why evidence was absent:")
            for kind, count in sorted(kinds.items()):
                self.stdout.write(f"    {count:>3}  {kind}")

        modes: dict[str, int] = {}
        for item in supplied:
            if item.expected == "FALSE":
                modes[item.falsification_mode or "unspecified"] = (
                    modes.get(item.falsification_mode or "unspecified", 0) + 1
                )
        if modes:
            self.stdout.write("\n  how the FALSE statements are falsified:")
            for mode, count in sorted(modes.items()):
                self.stdout.write(f"    {count:>3}  {mode}")

        # 🔴 Which verdicts will depend on a DECLARED property rather than on
        # the span. Named here so the number can be audited, because a FALSE
        # that rests on exhaustiveness rests on a human's classification of
        # the source (09 §8.2), not on anything the judge saw.
        exhaustive_qids = {
            a["question_id"]
            for a in selectors.get("artifacts", [])
            if a.get("exhaustiveness") == "EXHAUSTIVE"
        }
        dependent = [
            r
            for r in supplied
            if r.expected == "FALSE"
            and r.question_id in exhaustive_qids
            and r.falsification_mode in ("definitional_scope", "absence_from_list")
        ]
        if dependent:
            self.stdout.write(
                self.style.WARNING(
                    "\n  🔴 verdicts that will depend on the EXHAUSTIVENESS "
                    "declaration, not on the span alone:"
                )
            )
            for item in dependent:
                self.stdout.write(
                    f"    {item.question_id} #{item.statement_index} "
                    f"({item.falsification_mode})"
                )

        self.stdout.write(
            self.style.WARNING(
                f"\n  ⚠️  {len(supplied)}/{len(resolved)} statements reach the "
                "verifier. A score on the first number is the VERIFIER's; only "
                "a score on the second would be the PIPELINE's. Never merge them."
            )
        )

    # ── output ─────────────────────────────────────────────────────────────

    def _write(
        self,
        resolved: list[Resolved],
        selectors: dict[str, Any],
        questions: dict[str, Any],
        out: Path,
    ) -> None:
        supplied = [r for r in resolved if r.label == LABEL_SUPPLIED]
        excluded = [r for r in resolved if r.label != LABEL_SUPPLIED]
        urls = {
            q.get("id", ""): q.get("source_url", "")
            for q in questions.get("questions", [])
        }

        payload: dict[str, Any] = {
            "_meta": {
                "generated_by": "manage.py build_gate1b",
                "from_selectors": str(
                    selectors.get("_meta", {}).get("declared_at", "")
                ),
                "spec": "act0/0.4_GATE1_FINDINGS.md §6",
                "warning": (
                    "Every 'exact_text' below was COPIED from act0/extracted/ by "
                    "code, never retyped. Do not hand-edit this file -- edit "
                    "gate1b_selectors.json and regenerate."
                ),
                "statements_total": len(resolved),
                "denominator": len(supplied),
                "excluded": len(excluded),
            },
            "artifacts": [
                {**a, "source_url": urls.get(a.get("question_id", ""), "")}
                for a in selectors.get("artifacts", [])
            ],
            "spans": [
                {
                    "question_id": r.question_id,
                    "statement_index": r.statement_index,
                    "claim": r.claim,
                    "expected": r.expected,
                    "source_url": r.source_url,
                    "source_tier": r.source_tier,
                    "lines": r.lines,
                    "occurrences_in_body": r.occurrences,
                    "falsification_mode": r.falsification_mode,
                    "reason": r.reason,
                    "exact_text": r.exact_text,
                }
                for r in supplied
            ],
            "excluded": [
                {
                    "question_id": r.question_id,
                    "statement_index": r.statement_index,
                    "claim": r.claim,
                    "expected": r.expected,
                    "label": r.label,
                    "absent_kind": r.absent_kind,
                    "reason": r.reason,
                }
                for r in excluded
            ],
        }

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.stdout.write(f"\n  spans -> {out}")
        self.stdout.write(
            "\n  Now run:  python manage.py curate_act0 --spans " f"{out.name} --reset"
        )

        logger.info(
            "df_gate1b_built",
            statements=len(resolved),
            denominator=len(supplied),
            excluded=len(excluded),
        )


def _index_statements(
    questions: dict[str, Any],
) -> dict[tuple[str, int], dict[str, str]]:
    """(question_id, index) -> claim, expected answer and provenance.

    Claims are read here and never written into the selector file, so a
    curation cannot drift from the answer key.
    """
    out: dict[tuple[str, int], dict[str, str]] = {}
    for question in questions.get("questions", []):
        qid = question.get("id", "")
        for index, statement in enumerate(question.get("statements", [])):
            out[(qid, index)] = {
                "claim": statement.get("claim", ""),
                "expected": statement.get("expected", ""),
                "source_url": question.get("source_url", ""),
                "source_tier": question.get("source_tier", ""),
            }
    return out


def _index_entries(selectors: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    """(question_id, index) -> the human's label and selector."""
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for entry in selectors.get("entries", []):
        key = (entry.get("question_id", ""), int(entry.get("statement_index", -1)))
        out[key] = entry
    return out
