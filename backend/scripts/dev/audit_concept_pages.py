"""
scripts/dev/audit_concept_pages.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
G0.3 — are the auto-generated concept pages an SEO asset or a liability?

WHY
  /concepts/[slug] pages are minted organically whenever CA generation wraps a
  term in [[double brackets]] (~20 a day). Google's helpful-content system
  scores a DOMAIN, not a page: a large volume of thin machine-written pages
  drags the good pages down with it. G3's sitemap therefore needs a verdict
  before it lists ~1,500 of them: all, none, or a curated subset — and if a
  subset, by what rule.

WHAT IT MEASURES (read-only, no LLM)
  Population   total · full (is_content_ready) vs stub · usage distribution ·
               stubs the site links to heavily (priority for generation)
  Per full page
    words      body_md word count
    headings   ATX headings (structure)
    tables     markdown tables
    lists      bullet / numbered lines
    overlap    share of brief_description's tokens that reappear in the body —
               a high overlap on a short body is a restated definition, not an
               article
    opening    normalised first ~40 words with the concept's own name removed,
               hashed — identical openings across pages = a template, which is
               exactly what "thin auto-generated" looks like to a crawler
    links      how many articles link to it (grounding / discoverability)
  Verdict      counts against a thin-page rule, and a proposed sitemap rule

USAGE (from backend/, venv active)
      python scripts/dev/audit_concept_pages.py --database=supabase
      python scripts/dev/audit_concept_pages.py --database=supabase --show 12
      python scripts/dev/audit_concept_pages.py --database=supabase --min-words 500

SAFETY
  Read-only. Nothing is written. Safe against production.
"""

import argparse
import hashlib
import os
import re
import statistics
import sys
from collections import defaultdict

import django

# Make `backend/` importable when run directly as a script.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")
django.setup()

from django.db.models import Count  # noqa: E402

from engines.tags.models import ConceptPage  # noqa: E402

HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
TABLE_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
LIST_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S", re.MULTILINE)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]+")
STOP = frozenset(
    "the a an and or of to in on for with by is are was were be been it its this "
    "that as at from which who whom whose into than then also not no but such "
    "these those their there here has have had can may will would should".split()
)


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def content_tokens(text: str) -> set[str]:
    return {w.lower() for w in words(text) if w.lower() not in STOP and len(w) > 2}


def opening_hash(body: str, name: str) -> str:
    """First ~40 words, lower-cased, with the concept's own name blanked out."""
    head = " ".join(words(body)[:40]).lower()
    for token in words(name):
        head = head.replace(token.lower(), "")
    head = re.sub(r"\s+", " ", head).strip()
    return hashlib.sha1(head.encode()).hexdigest()[:10]


def pct(n: int, d: int) -> str:
    return f"{(100 * n / d):5.1f}%" if d else "   n/a"


def quantiles(values: list[int]) -> str:
    if not values:
        return "n/a"
    if len(values) < 4:
        return f"min={min(values)} max={max(values)}"
    q = statistics.quantiles(values, n=10)
    return f"p10={int(q[0])} p50={int(q[4])} p90={int(q[8])} max={max(values)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("WHY")[0].strip())
    parser.add_argument("--database", default="default", help="DB alias")
    parser.add_argument(
        "--min-words", type=int, default=400, help="thin-page word threshold"
    )
    parser.add_argument(
        "--min-headings", type=int, default=3, help="thin-page heading threshold"
    )
    parser.add_argument(
        "--show", type=int, default=8, help="how many best/worst pages to list"
    )
    args = parser.parse_args()
    db = args.database

    qs = ConceptPage.objects.using(db).annotate(n_links=Count("article_links"))
    total = qs.count()
    full = list(qs.filter(is_content_ready=True))
    stubs = list(qs.filter(is_content_ready=False))

    print(f"\n{'=' * 72}\nG0.3 concept-page audit — database '{db}'\n{'=' * 72}")

    # ── Population ──────────────────────────────────────────────────────────
    print("\nPOPULATION")
    print(f"  total pages          {total}")
    print(f"  full (content ready) {len(full):>5}  {pct(len(full), total)}")
    print(f"  stubs (brief only)   {len(stubs):>5}  {pct(len(stubs), total)}")

    usage_all = [c.usage_count for c in full + stubs]
    print(f"  usage_count          {quantiles(usage_all)}")
    hot_stubs = sorted(
        (c for c in stubs if c.usage_count >= 3),
        key=lambda c: -c.usage_count,
    )
    print(
        f"  stubs linked >=3x    {len(hot_stubs):>5}  "
        "(the site keeps pointing readers at pages with no body)"
    )
    for c in hot_stubs[: args.show]:
        print(f"      {c.usage_count:>3}x  /concepts/{c.slug}")

    if not full:
        print("\nVERDICT: no full pages exist — every /concepts/ URL is a stub.")
        print("  Sitemap rule: list NONE until a generation phase has run.\n")
        return 0

    # ── Per-page metrics on full pages ──────────────────────────────────────
    rows = []
    openings: dict[str, list[str]] = defaultdict(list)
    for c in full:
        body = c.body_md or ""
        n_words = len(words(body))
        n_head = len(HEADING_RE.findall(body))
        n_table = len(TABLE_RE.findall(body))
        n_list = len(LIST_RE.findall(body))
        brief = content_tokens(c.brief_description or "")
        body_tok = content_tokens(body)
        overlap = (len(brief & body_tok) / len(brief)) if brief else 0.0
        oh = opening_hash(body, c.name)
        openings[oh].append(c.slug)
        thin = n_words < args.min_words or n_head < args.min_headings
        rows.append(
            {
                "slug": c.slug,
                "words": n_words,
                "headings": n_head,
                "tables": n_table,
                "lists": n_list,
                "overlap": overlap,
                "links": c.n_links,
                "usage": c.usage_count,
                "opening": oh,
                "thin": thin,
            }
        )

    n = len(rows)
    thin_rows = [r for r in rows if r["thin"]]
    no_head = sum(1 for r in rows if r["headings"] == 0)
    no_struct = sum(
        1 for r in rows if r["headings"] == 0 and r["tables"] == 0 and r["lists"] == 0
    )
    restated = sum(
        1 for r in rows if r["overlap"] >= 0.8 and r["words"] < args.min_words
    )
    templated = {k: v for k, v in openings.items() if len(v) >= 3}
    templated_pages = sum(len(v) for v in templated.values())
    orphans = sum(1 for r in rows if r["links"] == 0)

    print("\nFULL PAGES — structure")
    print(f"  words                {quantiles([r['words'] for r in rows])}")
    print(f"  headings             {quantiles([r['headings'] for r in rows])}")
    print(f"  tables               {quantiles([r['tables'] for r in rows])}")
    print(f"  list lines           {quantiles([r['lists'] for r in rows])}")
    print(
        f"  thin  (<{args.min_words}w or <{args.min_headings}h) "
        f"{len(thin_rows):>5}  {pct(len(thin_rows), n)}"
    )
    print(f"  zero headings        {no_head:>5}  {pct(no_head, n)}")
    print(f"  no structure at all  {no_struct:>5}  {pct(no_struct, n)}")
    print(
        f"  restated brief       {restated:>5}  {pct(restated, n)}  "
        "(>=80% of the brief's words, under the word floor)"
    )
    print(
        f"  templated openings   {templated_pages:>5}  {pct(templated_pages, n)}  "
        f"in {len(templated)} cluster(s) of >=3 identical openings"
    )
    for oh, slugs in sorted(templated.items(), key=lambda kv: -len(kv[1]))[:3]:
        print(f"      x{len(slugs):<3} e.g. {', '.join(s[:40] for s in slugs[:3])}")
    print(f"  orphans (0 links)    {orphans:>5}  {pct(orphans, n)}")

    # ── Worst / best for a human read ───────────────────────────────────────
    ranked = sorted(rows, key=lambda r: (r["words"], r["headings"]))
    print(f"\nREAD THESE — {args.show} thinnest full pages")
    for r in ranked[: args.show]:
        print(
            f"  {r['words']:>5}w {r['headings']:>2}h {r['tables']:>2}t "
            f"ov={r['overlap']:.2f} links={r['links']:<3} /concepts/{r['slug']}"
        )
    print(f"\nREAD THESE — {args.show} richest full pages")
    for r in ranked[-args.show :][::-1]:
        print(
            f"  {r['words']:>5}w {r['headings']:>2}h {r['tables']:>2}t "
            f"ov={r['overlap']:.2f} links={r['links']:<3} /concepts/{r['slug']}"
        )

    # ── Verdict ─────────────────────────────────────────────────────────────
    good = n - len(thin_rows)
    share = good / n if n else 0.0
    print(f"\n{'-' * 72}\nVERDICT")
    if share >= 0.8 and templated_pages / n < 0.1:
        label = "ASSET"
        rule = "list every full page; keep stubs out"
    elif share <= 0.4 or templated_pages / n >= 0.3:
        label = "LIABILITY"
        rule = (
            "list NONE until regenerated; noindex /concepts/ meanwhile "
            "(keep internal links — readers still use them)"
        )
    else:
        label = "CURATE"
        rule = (
            f"list only is_content_ready AND words>={args.min_words} "
            f"AND headings>={args.min_headings} AND not in a templated cluster"
        )
    passing = sum(1 for r in rows if not r["thin"] and len(openings[r["opening"]]) < 3)
    print(f"  {label}")
    print(f"  full pages passing the thin rule   {good}/{n}  {pct(good, n)}")
    print(f"  passing rule + not templated       {passing}/{n}  {pct(passing, n)}")
    print(f"  stubs (never listed)               {len(stubs)}")
    print(f"  proposed sitemap rule: {rule}")
    print(
        "\n  Numbers are structural proxies. Read the thinnest and richest pages "
        "above before\n  writing the verdict into FEATURES_GROWTH_STACK.md §4.3.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
