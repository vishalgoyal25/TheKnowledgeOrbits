"""
scripts/dev/ca_prompt_budget.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURES_LLM_FIX.md Part II, L9 — does the Daily-CA article prompt fit Groq?

WHY
  The article prompt (~35k chars, ~8.8k estimated tokens) sits above Groq's
  capability gate (5,500 tokens), so the pool never offers it to Groq and the
  article body depends on Mistral (quota-dead) and OpenRouter's daily free-model
  pick (broke on 2026-09-18, paid-only on 09-20) — three days of zero articles
  behind a green cron tick. Before the template is rewritten (L10) the budget
  has to be a MEASURED number, not len/4: this script builds the exact prompt
  the pipeline sends and, on request, asks Groq itself how many tokens it is.

WHAT IT DOES
  measure (default)
      For the last N proposals, rebuilds the SAME prompt the pipeline sends —
      same CA chunks + parent article, same RAG grounding, same wiki rule, same
      template — and prints its size by component against the Groq gate.
  --live
      ONE real Groq call on the first prompt, with the production `ca_article`
      config. On success prints `usage` (real prompt / completion tokens,
      finish_reason) and the real-to-estimated ratio. On a 413 prints Groq's
      own message — it states the TPM limit AND the token count Groq measured,
      which is the cheapest possible tokenizer read.
  --trial
      For each proposal, generates an article through the normal pool
      (`llm_call(mode="ca_article")`), then parses, validates, normalises and
      scores it EXACTLY as the pipeline does (D6 metrics), and saves the
      markdown under --out for reading by eye. NOTHING is written to the DB.

USAGE (from backend/, venv active)
      python scripts/dev/ca_prompt_budget.py --database=supabase
      python scripts/dev/ca_prompt_budget.py --database=supabase --proposals 5 --live
      python scripts/dev/ca_prompt_budget.py --database=supabase --proposals 3 --trial

SAFETY
  Read-only against the database — no model is saved, no status is changed.
  Grounding makes one embedding call per proposal (as the pipeline does).
  --live costs one LLM call; --trial costs one LLM call per proposal plus the
  pool's INTER_CALL_SLEEP. Provider error text is printed verbatim so the
  limit numbers can be read — redact any organisation id before pasting it
  into a tracked file.
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

import django

# Make `backend/` importable when run directly as a script.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")
django.setup()

from engines.book_content.services import llm_service  # noqa: E402
from engines.book_content.services.retrieval_service import (  # noqa: E402
    as_static_facts,
    retrieve_grounding,
)
from engines.daily_ca.models import CaDailyProposal  # noqa: E402
from engines.daily_ca.services import generator_service as gen  # noqa: E402
from engines.daily_ca.services.markdown_normalizer import (  # noqa: E402
    is_structurally_broken,
    normalize_markdown,
)
from engines.daily_ca.services.prompt_builder import (  # noqa: E402
    _format_static_facts,
    _format_wiki_enrichment,
    build_ca_prompt,
)
from engines.daily_ca.services.static_background_service import (  # noqa: E402
    StaticBackgroundService,
)
from engines.daily_ca.services.wiki_enrichment_service import (  # noqa: E402
    WikiEnrichmentService,
)

# Prompt-template rules the trial checks for (mirrors what the pipeline asks for).
LINK_RE = re.compile(r"\[\[[^\]]+\]\]")
HEADING_RE = re.compile(r"^##\s+\S", re.MULTILINE)
SUBHEADING_RE = re.compile(r"^###\s+\S", re.MULTILINE)
FORBIDDEN_HEADINGS = (
    "upsc angle",
    "exam relevance",
    "prelims focus",
    "mains value",
    "practice questions",
    "important for upsc",
    "why in news",
)
# Groq's 413 body: "... on tokens per minute (TPM): Limit 8000, Requested 10362 ..."
LIMIT_RE = re.compile(r"Limit\s+(\d+),\s*Requested\s+(\d+)", re.IGNORECASE)

# The prompt asks for 550–750; 800 is the acceptance tolerance (the pipeline's own
# hard cap is 1,000 and its quality band 450–1,000). A 751 is not a failure.
TARGET_WORDS = (550, 800)
TARGET_LINKS = (5, 8)


def groq_gate() -> int:
    for spec in llm_service.PROVIDERS:
        if spec.name == "groq":
            return spec.max_request_tokens
    return 0


def load_proposals(db: str, n: int, status: str | None) -> list[CaDailyProposal]:
    qs = CaDailyProposal.objects.using(db).select_related("topic")
    if status:
        qs = qs.filter(status=status)
    return list(qs.order_by("-date", "-created_at")[:n])


def build_inputs(p: CaDailyProposal, db: str) -> dict:
    """Reproduce generator_service._run_single_cycle steps 1–3, read-only."""
    try:
        static_facts = StaticBackgroundService.get_background_facts(p.topic_id)
    except Exception as exc:  # the static path is effectively dead; never block on it
        print(
            f"    static background unavailable ({exc.__class__.__name__}) — using None"
        )
        static_facts = None

    ca_text, chunk_wc = gen._fetch_enriched_ca_context(p.ca_chunk_ids, db_alias=db)
    name = p.topic.name if p.topic else p.title

    grounding = retrieve_grounding(
        seed_topic_id=p.topic_id, query=name, k_ca=0, db_alias=db
    )
    grounding_facts = (
        as_static_facts(grounding, title=name) if grounding.get("book_chunks") else None
    )
    static_key_facts = grounding_facts or static_facts

    wiki: dict = {}
    if not grounding_facts and chunk_wc < 300:
        wiki = WikiEnrichmentService.get_enrichment(name)

    subject = p.subject_name or ""
    prompt = build_ca_prompt(
        ca_chunks_text=ca_text,
        static_key_facts=static_key_facts,
        wiki_enrichment=wiki or None,
        subject_name=subject,
        topic_name=name,
    )
    return {
        "proposal": p,
        "name": name,
        "subject": subject,
        "prompt": prompt,
        "news_chars": len(ca_text[:6000]) if ca_text else 0,
        "facts_chars": len(_format_static_facts(static_key_facts)),
        "wiki_chars": len(_format_wiki_enrichment(wiki or None)),
        # Template + tone + the "Not available." fillers = the prompt with no data in it.
        "template_chars": len(build_ca_prompt("", None, None, subject, name)),
    }


def report_measure(rows: list[dict], gate: int) -> None:
    print(
        f"\n{'=' * 78}\nDaily-CA article prompt budget — Groq gate {gate:,} est. tokens\n{'=' * 78}"
    )
    print(
        f"{'#':>2}  {'total':>7} {'est.tok':>7}  {'template':>8} {'news':>6} "
        f"{'facts':>6} {'wiki':>5}  fits  proposal"
    )
    for i, r in enumerate(rows, 1):
        est = llm_service._estimate_tokens(r["prompt"])
        fits = "yes" if est <= gate else "NO "
        print(
            f"{i:>2}  {len(r['prompt']):>7,} {est:>7,}  {r['template_chars']:>8,} "
            f"{r['news_chars']:>6,} {r['facts_chars']:>6,} {r['wiki_chars']:>5,}  "
            f"{fits}   {r['proposal'].title[:44]}"
        )
    worst = max(rows, key=lambda r: len(r["prompt"]))
    est_worst = llm_service._estimate_tokens(worst["prompt"])
    print(
        f"\nWorst case: {len(worst['prompt']):,} chars = {est_worst:,} est. tokens "
        f"→ {'fits' if est_worst <= gate else 'over the gate by'} "
        f"{'' if est_worst <= gate else f'{est_worst - gate:,} tokens'}"
    )
    print(
        f"Template share: {worst['template_chars']:,} of {len(worst['prompt']):,} chars "
        f"({100 * worst['template_chars'] // max(len(worst['prompt']), 1)} %) — "
        "the part L10 rewrites. Data (news + facts + wiki) is untouched (D1)."
    )


def live_call(prompt: str, max_tokens: int | None, reasoning: str | None) -> None:
    """
    One real Groq call — the tokenizer read.

    Defaults to the production `ca_article` config. `max_tokens` / `reasoning`
    override it for probing: a 413 answer prints Groq's own limit, a 200 prints
    `usage` and whether the completion was cut (`finish_reason=length`).
    `reasoning_effort` goes through `extra_body` so an SDK that does not know the
    field still sends it (Groq honours it for the gpt-oss models).
    """
    entries = [e for e in llm_service._pool if e.provider == "groq"]
    if not entries:
        print("\n--live: no Groq key in the pool (GROQ_API_KEY unset?)")
        return
    entry = entries[0]
    # The production mode for the article (L11: 4,000 tokens, low reasoning effort);
    # --max-tokens / --reasoning override it for probing.
    cfg = dict(llm_service._MODE_CONFIG["ca_article"])
    if max_tokens:
        cfg["max_tokens"] = max_tokens
    if reasoning:
        cfg["reasoning_effort"] = reasoning
    model = llm_service._model_for(entry.spec)
    est = llm_service._estimate_tokens(prompt)
    print(
        f"\n{'=' * 78}\n--live: one Groq call  model={model}  est.tokens={est:,}  "
        f"max_tokens={cfg['max_tokens']}  reasoning_effort={cfg.get('reasoning_effort')}"
        f"\n{'=' * 78}"
    )
    kwargs: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
    }
    kwargs.update(llm_service._reasoning_kwargs(entry.provider, model, cfg))
    started = time.time()
    try:
        resp = entry.client.chat.completions.create(**kwargs)
    except Exception as exc:
        text = str(exc)
        print(f"Groq answered an error after {time.time() - started:.1f}s:\n  {text}")
        m = LIMIT_RE.search(text)
        if m:
            limit, requested = int(m.group(1)), int(m.group(2))
            real_prompt = requested - cfg["max_tokens"]
            print(
                f"\n  Groq's own numbers: limit {limit:,} TPM · requested {requested:,} "
                f"(= real prompt tokens + max_tokens {cfg['max_tokens']:,})"
                f"\n  → real prompt tokens ≈ {real_prompt:,}  ·  real/est ratio "
                f"{real_prompt / max(est, 1):.3f}"
                f"\n  → prompt budget at this max_tokens ≈ {limit - cfg['max_tokens']:,} real tokens"
            )
        return

    usage = getattr(resp, "usage", None)
    content = (resp.choices[0].message.content or "").strip()
    finish = getattr(resp.choices[0], "finish_reason", "?")
    print(
        f"OK in {time.time() - started:.1f}s · finish_reason={finish} · "
        f"{len(content.split()):,} words returned · "
        f"links={len(LINK_RE.findall(content))} · callouts={content.count(':::callout')} · "
        f"closing lines={'yes' if 'SOURCE:' in content and 'TAGS:' in content else 'NO'}"
    )
    print(f"  head: {content[:160]!r}\n  tail: {content[-200:]!r}")
    if usage is not None:
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        details = getattr(usage, "completion_tokens_details", None)
        reasoning = getattr(details, "reasoning_tokens", None) if details else None
        print(
            f"usage: prompt_tokens={prompt_tokens} completion_tokens={completion_tokens} "
            f"reasoning_tokens={reasoning} total={getattr(usage, 'total_tokens', None)}"
        )
        if prompt_tokens:
            print(f"real/est ratio {prompt_tokens / max(est, 1):.3f}")


NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def untraceable_numbers(body: str, prompt: str) -> list[str]:
    """
    Numbers in the article that appear nowhere in the prompt's source blocks —
    the cheapest fabrication signal there is. Years inside [[links]] and the
    Article numbers the prompt itself cites are excluded; everything else must
    trace. Advisory: the eye review decides, this only points at where to look.
    """
    haystack = prompt.replace(",", "")
    seen: list[str] = []
    for raw in NUMBER_RE.findall(body):
        num = raw.replace(",", "")
        if len(num) < 2 or num in seen:
            continue
        if num not in haystack:
            seen.append(num)
    return seen


def trial(rows: list[dict], out_dir: Path, reasoning: str | None) -> None:
    """Generate through the normal pool and judge exactly as the pipeline does."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = llm_service._MODE_CONFIG["ca_article"]
    if reasoning:
        cfg["reasoning_effort"] = (
            reasoning  # A/B the effort level without a code change
        )
    print(
        f"\n{'=' * 78}\n--trial: {len(rows)} article(s) through the pool "
        f"(mode ca_article, max_tokens {cfg['max_tokens']}, reasoning "
        f"{cfg.get('reasoning_effort')}), nothing saved to the DB\n{'=' * 78}"
    )
    for i, r in enumerate(rows, 1):
        p = r["proposal"]
        print(f"\n[{i}/{len(rows)}] {p.title[:70]}")
        raw = llm_service.llm_call(r["prompt"], mode="ca_article")
        provider, model = (
            llm_service.last_call_provider(),
            llm_service.last_call_model(),
        )
        if not raw:
            print(
                "  FAILED — empty response after all retries (see llm_* log lines above)"
            )
            continue

        title, body, tags, source, category = gen._parse_response(raw)
        if not title or title == "Untitled":
            title = p.title
        title = gen._validate_title(title, fallback_title=p.title)
        body = normalize_markdown(body, log_context=p.title[:60])
        broken = is_structurally_broken(body)
        body = gen._simplify_text(body)
        words = len(body.split())
        if words > gen.DailyCaGeneratorService.MAX_WORDS:
            body = gen._truncate_body(body, gen.DailyCaGeneratorService.MAX_WORDS)
            words = len(body.split())

        links = len(LINK_RE.findall(body))
        headings = len(HEADING_RE.findall(body))
        subheadings = len(SUBHEADING_RE.findall(body))
        callouts = body.count(":::callout")
        low = body.lower()
        bad_headings = [h for h in FORBIDDEN_HEADINGS if h in low]
        score = gen._score_quality(body)
        untraced = untraceable_numbers(body, r["prompt"])

        checks = {
            "quality >= 8.0": score >= 8.0,
            f"words {TARGET_WORDS[0]}-{TARGET_WORDS[1]}": TARGET_WORDS[0]
            <= words
            <= TARGET_WORDS[1],
            f"links {TARGET_LINKS[0]}-{TARGET_LINKS[1]}": TARGET_LINKS[0]
            <= links
            <= TARGET_LINKS[1],
            "one callout": callouts == 1,
            "3+ ## headings, no ###": headings >= 3 and subheadings == 0,
            "closing lines (category/tags/source)": bool(tags) and bool(source),
            "markdown not broken": not broken,
            "no forbidden heading": not bad_headings,
        }
        verdict = "PASS" if all(checks.values()) else "FAIL"
        print(
            f"  provider={provider} model={model} · quality={score} · words={words} · "
            f"links={links} · callouts={callouts} · headings={headings} · category={category}"
        )
        for name, ok in checks.items():
            print(f"    {'ok ' if ok else 'NO '} {name}")
        print(
            f"    {'ok ' if len(untraced) <= 3 else '?? '} numbers not in the sources: "
            f"{len(untraced)} {untraced[:8]}  (advisory — read the article)"
        )
        print(f"  → {verdict}")

        safe = re.sub(r"[^a-z0-9]+", "-", p.title.lower())[:60].strip("-") or "article"
        path = out_dir / f"{i:02d}_{verdict}_{safe}.md"
        path.write_text(
            f"# {title}\n\n"
            f"<!-- provider={provider} model={model} quality={score} words={words} "
            f"links={links} category={category} tags={tags} source={source} -->\n\n"
            f"{body}\n",
            encoding="utf-8",
        )
        print(f"  saved → {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("WHY")[0].strip())
    ap.add_argument("--database", default="default")
    ap.add_argument("--proposals", type=int, default=5)
    ap.add_argument("--status", default=None, help="e.g. failed, approved, generated")
    ap.add_argument(
        "--live", action="store_true", help="one real Groq call on the first prompt"
    )
    ap.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="--live only: override the ca_article max_tokens (probe the TPM ceiling)",
    )
    ap.add_argument(
        "--reasoning",
        choices=("low", "medium", "high"),
        default=None,
        help="--live / --trial: Groq reasoning_effort for the gpt-oss models",
    )
    ap.add_argument(
        "--trial",
        action="store_true",
        help="generate + judge, save markdown, no DB write",
    )
    ap.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parents[3] / "trash" / "ca_prompt_trials"),
        help="folder for --trial markdown (default: <repo>/trash/ca_prompt_trials, gitignored)",
    )
    args = ap.parse_args()

    proposals = load_proposals(args.database, args.proposals, args.status)
    if not proposals:
        print("No proposals found.")
        return
    print(f"Building {len(proposals)} prompt(s) from '{args.database}' (read-only)…")
    rows = [build_inputs(p, args.database) for p in proposals]

    report_measure(rows, groq_gate())
    if args.live:
        live_call(rows[0]["prompt"], args.max_tokens, args.reasoning)
    if args.trial:
        out = Path(args.out)
        if args.reasoning:
            out = out / args.reasoning  # keep A/B runs apart for the eye review
        trial(rows, out, args.reasoning)


if __name__ == "__main__":
    main()
