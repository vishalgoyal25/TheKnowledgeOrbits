"""Would fusing the two locators help? Answered for free, from files we have.

Act 0, phase 0.7b. Spec: 00_MASTER_RECAP.md §16.9.4.

    gate1_results.json  (keyword locator)   13/37 correct
    gate1_results_semantic.json (meaning)   11/42 correct
      -> how many claims did EITHER get right?

🔴 Why this is worth doing before committing 25 phases to Act II.16
-------------------------------------------------------------------
§7.2's shipped retriever is BM25 + semantic + **RRF**, and RRF exists because
fusing two mediocre rankers beats either alone. Act 0 measured each ranker
separately and both were poor -- keyword 35%, semantic 26%.

The question that decides whether 2.16 is worth building as specified:
**do the two fail on the SAME claims, or on DIFFERENT ones?**

  * Same claims  -> fusion cannot help. 2.16 needs rethinking, and learning
                    that now is worth far more than learning it in month three.
  * Different    -> fusion has real headroom, exactly as RRF predicts.

🔴 THIS IS A CEILING, NOT A PREDICTION
---------------------------------------
The union asks "was this claim correct in EITHER run?" -- which assumes a
perfect chooser that always picks the better span. RRF has no such oracle; it
ranks and takes the top result, so it will land BELOW this number.

So read it as: **the most that fusion could possibly recover.** If the ceiling
is barely above the better single locator, fusion is not the answer. If it is
far above, the headroom is real and 2.16 should be built as specified.

⚠️ Costs nothing. No LLM calls, no network, no database -- two JSON files.
"""

import json
from collections import Counter
from pathlib import Path

import structlog
from django.core.management.base import BaseCommand, CommandError

logger = structlog.get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_ACT0 = _REPO_ROOT / "FEATURES" / "DATA_FACTORY" / "act0"


class Command(BaseCommand):
    help = (
        "Compare the keyword and semantic locator runs and report the union "
        "ceiling -- the most that fusing them could recover. Free: no LLM."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--keyword", type=Path, default=_ACT0 / "gate1_results.json"
        )
        parser.add_argument(
            "--semantic", type=Path, default=_ACT0 / "gate1_results_semantic.json"
        )
        parser.add_argument(
            "--out", type=Path, default=_ACT0 / "locator_comparison.json"
        )

    def handle(self, *args, **options):
        keyword = self._load(options["keyword"], "keyword")
        semantic = self._load(options["semantic"], "semantic")

        # Keyed on claim text: the two runs located DIFFERENT spans for the
        # same claims, which is the whole point of the comparison.
        all_claims = sorted(set(keyword) | set(semantic))

        both_right: list[str] = []
        only_keyword: list[str] = []
        only_semantic: list[str] = []
        neither: list[str] = []

        for claim in all_claims:
            k = keyword.get(claim)
            s = semantic.get(claim)
            k_ok = bool(k and k["correct"])
            s_ok = bool(s and s["correct"])

            if k_ok and s_ok:
                both_right.append(claim)
            elif k_ok:
                only_keyword.append(claim)
            elif s_ok:
                only_semantic.append(claim)
            else:
                neither.append(claim)

        union = len(both_right) + len(only_keyword) + len(only_semantic)
        total = len(all_claims)

        k_correct = sum(1 for v in keyword.values() if v["correct"])
        s_correct = sum(1 for v in semantic.values() if v["correct"])
        best_single = max(k_correct, s_correct)

        self.stdout.write("\n" + "=" * 66)
        self.stdout.write(self.style.MIGRATE_HEADING("  LOCATOR COMPARISON"))
        self.stdout.write("=" * 66)
        self.stdout.write(f"  claims seen in either run     {total}")
        self.stdout.write(f"  keyword correct               {k_correct}")
        self.stdout.write(f"  semantic correct              {s_correct}")
        self.stdout.write("-" * 66)
        self.stdout.write(f"  both locators right           {len(both_right)}")
        self.stdout.write(
            self.style.WARNING(f"  ONLY keyword right            {len(only_keyword)}")
        )
        self.stdout.write(
            self.style.WARNING(f"  ONLY semantic right           {len(only_semantic)}")
        )
        self.stdout.write(f"  neither right                 {len(neither)}")
        self.stdout.write("=" * 66)

        gain = union - best_single
        style = self.style.SUCCESS if gain > 0 else self.style.ERROR
        self.stdout.write(
            style(f"  UNION CEILING  {union}/{total}   (best single: {best_single})")
        )
        self.stdout.write(
            self.style.WARNING("  ^ a CEILING, not a prediction - RRF lands below it")
        )

        # 🔴 The interpretation, written out so §16.9.4's question is answered
        # in words and not left to be re-derived from the numbers.
        self.stdout.write("")
        if gain == 0:
            self.stdout.write(
                self.style.ERROR(
                    "  -> FUSION CANNOT HELP. Both locators fail on the SAME claims,\n"
                    "     so RRF has nothing to recover. 2.16 as specified would not\n"
                    "     fix the 35%, and the bottleneck is EXTRACTION, not search."
                )
            )
        elif gain <= 2:
            self.stdout.write(
                self.style.WARNING(
                    f"  -> MARGINAL. Fusion could recover at most {gain} statement(s).\n"
                    "     Real headroom is smaller still. Treat 2.16 as necessary but\n"
                    "     NOT sufficient -- extraction (2.7) is the larger problem."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  -> REAL HEADROOM: {gain} statements are won by exactly ONE\n"
                    "     locator. The two fail on DIFFERENT claims, which is precisely\n"
                    "     the condition RRF exploits. 2.16 should be built as specified."
                )
            )

        if only_keyword:
            self.stdout.write("\n  Won ONLY by keyword (rare exact tokens):")
            for claim in only_keyword:
                self.stdout.write(f"    {claim[:88]}")
        if only_semantic:
            self.stdout.write("\n  Won ONLY by meaning (paraphrase):")
            for claim in only_semantic:
                self.stdout.write(f"    {claim[:88]}")

        # Where the un-winnable ones failed, so extraction vs search is visible.
        reasons = Counter()
        for claim in neither:
            for run in (keyword, semantic):
                entry = run.get(claim)
                if entry:
                    reasons[entry["reason"] or "not_judged"] += 1
        if reasons:
            self.stdout.write("\n  Failure reasons among the un-winnable:")
            for reason, count in reasons.most_common():
                self.stdout.write(f"    {count:>3}  {reason}")

        payload = {
            "claims": total,
            "keyword_correct": k_correct,
            "semantic_correct": s_correct,
            "both_right": len(both_right),
            "only_keyword": only_keyword,
            "only_semantic": only_semantic,
            "neither": len(neither),
            "union_ceiling": union,
            "best_single": best_single,
            "headroom": gain,
            "_caveat": (
                "union_ceiling assumes a perfect chooser. RRF ranks and takes the "
                "top result, so it lands below this. Read as an upper bound on "
                "what fusion could recover."
            ),
        }
        options["out"].write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.stdout.write(f"\n  written -> {options['out']}")

        logger.info(
            "df_locator_comparison",
            union=union,
            best_single=best_single,
            headroom=gain,
            only_keyword=len(only_keyword),
            only_semantic=len(only_semantic),
        )

    def _load(self, path: Path, label: str) -> dict[str, dict]:
        if not path.exists():
            raise CommandError(f"{label} results not found: {path}")

        payload = json.loads(path.read_text(encoding="utf-8"))
        out: dict[str, dict] = {}
        for outcome in payload.get("outcomes", []):
            claim = outcome.get("claim", "")
            if not claim:
                continue
            expected = outcome.get("expected", "")
            verdict = outcome.get("verdict", "")
            out[claim] = {
                "correct": bool(expected) and verdict == expected,
                "verdict": verdict,
                "expected": expected,
                "reason": outcome.get("reason", ""),
            }
        return out
