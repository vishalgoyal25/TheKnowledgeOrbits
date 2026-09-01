"""
scripts/dev/repair_daily_ca_markdown.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Audit Daily CA article bodies for collapsed markdown, and revert bodies damaged
by the withdrawn heading-reconstruction pass.

WHY
  2026-09-01: after generation moved off Cerebras (402) to Mistral, 2 of 10
  published bodies arrived with ZERO newlines in ~7,000 chars — `##` markers
  stranded mid-line — so the article rendered as one <p> ("wall of text").

  An earlier version of this script "repaired" them by inserting a break before
  each `##`. That made it worse: an ATX heading runs to the END of its line, and
  with no newline after the heading TITLE either, the heading swallowed the
  whole paragraph and rendered it as a giant <h2>.

  Structure cannot be rebuilt: the newlines that marked where each title ended
  are gone, and headings are free-form, so there is nothing to split against.
  generator_service now REJECTS such a body at generation time (STEP 4c) and
  regenerates it, so no new article can be affected.

WHAT THIS DOES NOW
  --audit   (default) report any article whose body is structurally broken.
            This is the permanent regression check — it should print 0.
  --revert  undo the damage from the withdrawn repair, restoring the body to
            the single continuous line it was before. Deterministic, not a
            guess: those bodies had ZERO newlines beforehand, so every newline
            present now was inserted by that pass.

            Reverted articles read as one long paragraph — poor, but honest,
            and far better than paragraphs rendered as giant headings. To make
            them render properly they must be REGENERATED; the text alone
            cannot say where the breaks belonged.

USAGE (from backend/, venv active)
      python scripts/dev/repair_daily_ca_markdown.py --database=supabase
      python scripts/dev/repair_daily_ca_markdown.py --database=supabase --revert

SAFETY
  - Read-only by DEFAULT. Nothing is written without --revert.
  - --revert only touches rows whose heading has swallowed a paragraph, i.e.
    exactly the rows the withdrawn pass damaged.
  - Only body_md_processed and body_md are written.
  - The word count must be unchanged, or the row is skipped: reverting removes
    newlines only and must never alter prose.
"""

import argparse
import os
import sys

import django

# Make `backend/` importable when run directly as a script.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")
django.setup()

from engines.daily_ca.models import DailyCaArticle  # noqa: E402
from engines.daily_ca.services.markdown_normalizer import (  # noqa: E402
    collapse_to_single_line,
    has_overlong_heading,
    is_structurally_broken,
)


def _stats(md: str) -> str:
    return f"newlines={md.count(chr(10))} " f"h2={md.count('##')} " f"chars={len(md)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="default", help="DB alias")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--revert",
        action="store_true",
        help="undo the withdrawn heading repair (default is audit only)",
    )
    args = parser.parse_args()

    db = args.database
    articles = list(
        DailyCaArticle.objects.using(db).order_by("-published_date", "order_on_date")[
            : args.limit
        ]
    )

    mode = "REVERT" if args.revert else "AUDIT (read-only)"
    print(f"\nScanning {len(articles)} article(s) on '{db}' — {mode}\n")

    broken = reverted = skipped = 0

    for a in articles:
        body = a.body_md_processed or ""
        if not is_structurally_broken(body):
            continue

        broken += 1
        swallowed = has_overlong_heading(body)
        kind = "heading swallowed paragraph" if swallowed else "collapsed body"
        print(f"BROKEN  {a.slug[:60]}\n        {kind} — {_stats(body)}")

        if not args.revert:
            print("        (audit only)\n")
            continue

        if not swallowed:
            print("        SKIPPED — not damage from the withdrawn repair\n")
            skipped += 1
            continue

        fixed = collapse_to_single_line(body)
        if len(fixed.split()) != len(body.split()):
            print("        SKIPPED — word count changed, refusing to write\n")
            skipped += 1
            continue

        fields = ["body_md_processed"]
        a.body_md_processed = fixed
        if has_overlong_heading(a.body_md or ""):
            a.body_md = collapse_to_single_line(a.body_md)
            fields.append("body_md")
        a.save(using=db, update_fields=fields)
        print(f"        REVERTED ({', '.join(fields)}) — {_stats(fixed)}\n")
        reverted += 1

    print(f"\nDone. broken={broken} reverted={reverted} skipped={skipped}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
