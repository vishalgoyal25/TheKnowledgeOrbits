"""Sample random chunks so A8 can be counted by hand.

Act 0. Spec: 00_MASTER_RECAP.md §16.6.4 · §19 item 18 · `06_DESIGN.md` §2.1 A8.

    A8 = how many INDEPENDENTLY CHECKABLE FACTS live in one ~1,200-char chunk

🔴 Why one guessed number matters this much
--------------------------------------------
A8 is the multiplier between "pages we read" and "facts we own":

    1,000 articles/day  x  ~6 chunks each  x  A8  =  facts stored per day

    A8 = 1  ->  ~2.2 M facts/year
    A8 = 3  ->  ~6.6 M   (the current GUESS, marked low-confidence)
    A8 = 6  ->  ~13 M

Every row count, index-memory figure and storage cost in `06_DESIGN.md` §2
inherits from it. **Wrong by 2x means all of them are wrong by 2x** -- including
§19 item 7's HNSW memory question, which depends directly on the atom count.

Four dividends beyond storage:
  * how much raw material is needed to reliably yield 25-30 questions/day
  * cost per ACCEPTED question, which §8.2 requires and cannot be computed
    without A8
  * 🟢 a silent validation of the 1,200-char chunk size: A8 near 0.5 means
    chunks are splitting facts in half; A8 near 20 means the verifier is being
    handed haystacks
  * a sanity check on the 137->100 generate-to-ship ratio (§19 item 15)

🔴 WHY RANDOM SAMPLING, AND WHY NOT THE ACT 0 ATOMS
----------------------------------------------------
The 60 Act 0 statements were SELECTED because they were verifiable against a
T1/T2 source. Counting them would measure our own selection bias and report it
as a property of the corpus -- the same class of error that made Gate 1
unreadable.

So: sample chunks at random from everything ingested, and count every claim a
human could check, including the ones no question would ever use.

⚠️ This command does NOT compute A8. It cannot -- "is this an independently
checkable fact?" is a judgement. It lays the sample out for counting and does
the arithmetic afterwards.
"""

import json
import random
from pathlib import Path

import structlog
from django.core.management.base import BaseCommand, CommandError

from engines.data_factory.models import DfChunk

logger = structlog.get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_ACT0 = _REPO_ROOT / "FEATURES" / "DATA_FACTORY" / "act0"

# Fixed so the sample is reproducible: a second run must show the SAME chunks,
# or the count cannot be checked or revised.
SEED = 20261007


class Command(BaseCommand):
    help = (
        "Write a random sample of chunks to a worksheet for hand-counting A8 "
        "(independently checkable facts per chunk)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--sample", type=int, default=10, help="How many chunks to sample."
        )
        parser.add_argument("--out", type=Path, default=_ACT0 / "a8_worksheet.md")
        parser.add_argument(
            "--counts",
            type=Path,
            default=None,
            help=(
                "A JSON file of {chunk_id: fact_count} to score instead of "
                "sampling. Run the sample first, count by hand, then pass this."
            ),
        )

    def handle(self, *args, **options):
        if options["counts"]:
            self._score(options["counts"])
            return

        total = DfChunk.objects.count()
        if not total:
            raise CommandError("No chunks in the database. Run `seed_act0` first.")

        # Sample over IDs rather than ORDER BY RANDOM(), so the selection is
        # reproducible from SEED and does not depend on database ordering.
        ids = list(DfChunk.objects.values_list("id", flat=True))
        rng = random.Random(SEED)
        picked = rng.sample(ids, min(options["sample"], len(ids)))

        chunks = list(
            DfChunk.objects.filter(id__in=picked).select_related("artifact__source")
        )

        lines = [
            "# A8 WORKSHEET — facts per chunk",
            "",
            f"> Sampled {len(chunks)} of {total} chunks, seed `{SEED}` (reproducible).",
            "> **Count every claim a human could check against this text** — including",
            "> ones no exam question would ever use. Do NOT count opinions, predictions,",
            "> navigation text, or the same fact stated twice.",
            "",
            "## How to count — the rule that keeps this consistent",
            "",
            "A fact counts when it is **one claim, checkable against this chunk alone**:",
            "",
            "| Counts | Does NOT count |",
            "|---|---|",
            "| *India submitted BUR-4 in December 2024* | *The report is encouraging* (opinion) |",
            "| *Emissions fell about 8% in 2020* | *Emissions will keep falling* (prediction) |",
            "| *Energy was the largest contributor* | *Skip to main content* (navigation) |",
            "| Two different figures in one sentence = **2** | the same fact repeated = **1** |",
            "",
            "⚠️ A compound sentence asserting three things is **three** facts. That is",
            "the atom rule (`06_DESIGN.md` 5.2: one atom = one claim) applied to counting.",
            "",
            "---",
            "",
            "## Record counts here, then feed them back",
            "",
            "```json",
            "{",
        ]
        lines += [f'  "{c.id}": 0,' for c in chunks]
        lines += [
            "}",
            "```",
            "",
            "Save that as `a8_counts.json` (remove the trailing comma) and run:",
            "",
            "🟢 **Add your reasoning freely.** Any key starting with `_` is treated as",
            "documentation and ignored by the scorer, so record WHAT you counted and",
            "WHY per chunk. A bare number nobody can audit is worth very little —",
            "and the per-chunk notes are what let someone else check or revise this.",
            "",
            "```",
            "python manage.py measure_a8 --counts ../FEATURES/DATA_FACTORY/act0/a8_counts.json",
            "```",
            "",
            "---",
            "",
        ]

        for i, chunk in enumerate(chunks, 1):
            lines += [
                f"## {i}. chunk `{chunk.id}`",
                "",
                f"- **source:** {chunk.artifact.source.name}",
                f"- **url:** {chunk.artifact.source_url}",
                f"- **chunk {chunk.chunk_index}**, {chunk.char_count} chars",
                "",
                "```",
                chunk.normalised_text,
                "```",
                "",
                "**Facts counted: ____**",
                "",
                "---",
                "",
            ]

        options["out"].parent.mkdir(parents=True, exist_ok=True)
        options["out"].write_text("\n".join(lines), encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(f"  {len(chunks)} chunks of {total} -> {options['out']}")
        )
        self.stdout.write("  Count by hand, then re-run with --counts")

    # ── scoring ────────────────────────────────────────────────────────────

    def _score(self, path: Path) -> None:
        """Turn hand counts into A8, and say what it changes."""
        if not path.exists():
            raise CommandError(f"Counts file not found: {path}")

        raw: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))

        # 🔴 Skip documentation keys. The counts file is hand-written and
        # SHOULD carry its reasoning -- per-chunk notes on what was counted and
        # why, plus the findings -- because a bare number nobody can audit is
        # worth very little. Those keys are `_`-prefixed by convention and
        # their values are strings, lists and dicts.
        #
        # Filtering on BOTH the prefix and the value type, because a hand-edited
        # file will eventually contain `"<chunk-id>": "7"` as a string, and
        # crashing on that would be unhelpful when the intent is obvious.
        values: list[int] = []
        skipped: list[str] = []
        for key, value in raw.items():
            if key.startswith("_"):
                continue
            # Narrow before converting, rather than suppressing the type error.
            # ⚠️ `bool` is excluded explicitly because it is a subclass of int in
            # Python, so `"<chunk-id>": true` would silently count as 1 fact.
            if isinstance(value, bool) or not isinstance(value, int | float | str):
                skipped.append(key)
                continue
            try:
                values.append(int(value))
            except ValueError:
                # A string that is not a number, e.g. "seven" or "TODO".
                skipped.append(key)

        if skipped:
            self.stdout.write(
                self.style.WARNING(
                    f"  ⚠️ skipped {len(skipped)} non-numeric entr(ies): "
                    f"{', '.join(k[:12] for k in skipped)}"
                )
            )

        if not values:
            raise CommandError(
                'No numeric counts found. Expected {"<chunk-id>": <int>} pairs; '
                "keys beginning with '_' are treated as documentation."
            )

        a8 = sum(values) / len(values)
        guess = 3.0
        ratio = a8 / guess

        ordered = sorted(values)
        median = ordered[len(ordered) // 2]

        self.stdout.write("\n" + "=" * 62)
        self.stdout.write(self.style.MIGRATE_HEADING("  A8 — FACTS PER CHUNK"))
        self.stdout.write("=" * 62)
        self.stdout.write(f"  chunks counted       {len(values)}")
        self.stdout.write(f"  total facts          {sum(values)}")
        self.stdout.write(
            f"  min / median / max   {ordered[0]} / {median} / {ordered[-1]}"
        )
        self.stdout.write("-" * 62)
        self.stdout.write(
            self.style.SUCCESS(f"  🔴 A8 = {a8:.2f}   (plan assumed 3.0)")
        )
        self.stdout.write("=" * 62)

        # What it changes, computed rather than described.
        self.stdout.write(f"\n  Every §2 volume figure scales by {ratio:.2f}x:")
        for label, planned in (
            ("df_atom at month 12", 382_000),
            ("df_atom at month 24", 1_260_000),
        ):
            self.stdout.write(
                f"    {label:<22} {planned:>10,} -> {int(planned * ratio):>10,}"
            )

        # The HNSW memory question (§19 item 7) depends on this directly.
        chunks_m24 = 1_260_000 / 3.0  # chunks implied by the planned atom count
        vec_gb = chunks_m24 * 3.4 / 1_000_000  # A10: 3.4 KB per vector + index
        self.stdout.write(
            f"\n  Chunk vectors at month 24 stay ~{vec_gb:.1f} GB of index "
            "(A8 does not change the CHUNK count -- only atoms per chunk)."
        )

        # 🟢 The chunk-size validation nobody had checked.
        self.stdout.write("")
        if a8 < 1.0:
            self.stdout.write(
                self.style.ERROR(
                    "  🔴 CHUNKS ARE TOO BIG OR TOO SPARSE. Under one fact per 1,200\n"
                    "     chars means most of what we store is not evidence -- revisit\n"
                    "     the three-filter gate before revisiting chunk size."
                )
            )
        elif a8 > 10.0:
            self.stdout.write(
                self.style.WARNING(
                    "  ⚠️ CHUNKS ARE DENSE. Over ten facts per chunk means the verifier\n"
                    "     is handed a haystack for every single claim. Consider a smaller\n"
                    "     chunk size in a new processing_version."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "  🟢 The 1,200-char chunk size is sound: a handful of facts per\n"
                    "     chunk is the right granularity for span-level verification."
                )
            )

        if abs(ratio - 1.0) > 0.5:
            self.stdout.write(
                self.style.WARNING(
                    f"\n  ⚠️ The guess was off by {ratio:.1f}x. Update 06_DESIGN.md §2.1 A8\n"
                    "     and re-derive §2.2 and §2.3 in the same turn."
                )
            )

        logger.info(
            "df_a8_measured", a8=round(a8, 2), chunks=len(values), facts=sum(values)
        )
