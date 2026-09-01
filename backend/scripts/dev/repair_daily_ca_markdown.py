"""
scripts/dev/repair_daily_ca_markdown.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Audit and repair Daily CA article bodies whose markdown structure collapsed.

WHY
  After article generation moved off Cerebras (402) to Mistral, some bodies
  were stored with block markers stranded mid-line — measured 2026-09-01:
  2 of 10 articles had ZERO newlines in ~7,000 chars, so react-markdown
  rendered the whole article as one <p> ("wall of text").

  generator_service now repairs this at write time (STEP 4c). This script
  fixes rows written BEFORE that guard existed, and doubles as the permanent
  audit: run it any time to prove no published article is structurally broken.

USAGE (from backend/, venv active)
  Audit only — never writes:
      python scripts/dev/repair_daily_ca_markdown.py --database=supabase
  Apply the repair:
      python scripts/dev/repair_daily_ca_markdown.py --database=supabase --apply

  --limit N restricts how many recent articles are examined (default 50).

SAFETY
  - Dry-run by DEFAULT. Nothing is written without --apply.
  - Only body_md_processed and body_md are touched, and only for rows the
    normalizer actually changes. Every other column is left alone.
  - The repair only INSERTS newlines; it never rewrites or drops prose. The
    script asserts the word count is unchanged before saving a row, and skips
    the row if that ever fails.
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
    is_structurally_broken,
    normalize_markdown,
)


def _stats(md: str) -> str:
    return (
        f"newlines={md.count(chr(10))} "
        f"blank={md.count(chr(10) + chr(10))} "
        f"h2={md.count('##')} "
        f"chars={len(md)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default="default", help="DB alias")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the repair (default is a dry run)",
    )
    args = parser.parse_args()

    db = args.database
    articles = list(
        DailyCaArticle.objects.using(db).order_by("-published_date", "order_on_date")[
            : args.limit
        ]
    )

    print(
        f"\nScanning {len(articles)} article(s) on '{db}' "
        f"({'APPLY' if args.apply else 'DRY RUN'})\n"
    )

    broken = repaired = skipped = 0

    for a in articles:
        source = a.body_md_processed or ""
        if not is_structurally_broken(source):
            continue

        broken += 1
        fixed = normalize_markdown(source, log_context=a.slug)
        print(f"BROKEN  {a.slug[:60]}")
        print(f"        before: {_stats(source)}")
        print(f"        after : {_stats(fixed)}")

        # Repair inserts newlines only — a changed word count means something
        # went wrong, so refuse to write that row.
        if len(fixed.split()) != len(source.split()):
            print("        SKIPPED — word count changed, refusing to write\n")
            skipped += 1
            continue

        if fixed == source:
            print("        SKIPPED — normalizer made no change\n")
            skipped += 1
            continue

        if args.apply:
            fields = ["body_md_processed"]
            a.body_md_processed = fixed
            # Keep the raw body consistent when it shares the same defect.
            if is_structurally_broken(a.body_md or ""):
                a.body_md = normalize_markdown(a.body_md, log_context=a.slug)
                fields.append("body_md")
            a.save(using=db, update_fields=fields)
            print(f"        REPAIRED ({', '.join(fields)})\n")
        else:
            print("        would repair (re-run with --apply)\n")
        repaired += 1

    print(
        f"\nDone. broken={broken} "
        f"{'repaired' if args.apply else 'repairable'}={repaired} "
        f"skipped={skipped}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
