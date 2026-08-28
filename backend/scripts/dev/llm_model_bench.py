"""
_l0b_model_pick.py — L0b: pick the BEST model per provider

THROWAWAY SCRIPT. DO NOT COMMIT. Delete after L0b.

L0 proved the keys work. L0b answers a different question:
    "Which model on each provider produces the best UPSC content, fast?"

For each candidate model it runs ONE realistic Daily-CA-style generation
(~9k-token grounded prompt, 900 output tokens) and reports:
    - latency
    - throughput
    - word count
    - the first 700 chars of output, so quality is judged by eye

Fixes two discovery bugs found in L0:
    - excludes models that 403 with "only available on agentic harnesses"
    - excludes non-chat models (Google Lyria music models appeared in the
      $0 list because they are genuinely free, but they cannot chat)

Keys are read from backend/.env and MASKED.

Run:  python _l0b_model_pick.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

try:
    import requests
    from dotenv import load_dotenv
    from openai import OpenAI
except ImportError as exc:
    sys.exit(f"Missing dependency: {exc}")

ENV_PATH = Path(__file__).resolve().parent / ".env"
if not ENV_PATH.exists():
    sys.exit(f"No .env at {ENV_PATH}")
load_dotenv(ENV_PATH)

TIMEOUT = 90.0
OUTPUT_TOKENS = 900

# Substrings that mark a model as NOT a general chat model.
_NON_CHAT = (
    "lyria", "whisper", "tts", "embed", "rerank", "image", "vision-only",
    "video", "audio", "sora", "veo", "imagen", "dall-e", "flux", "stable-diffusion",
)
# Models that authenticate but refuse normal API use.
_HARNESS_ONLY = ("inkling",)


def p(msg: str = "") -> None:
    print(msg, flush=True)


def mask(key: str) -> str:
    return f"{key[:6]}…{key[-4:]}" if len(key) > 12 else "…"


def short(exc: Exception, n: int = 110) -> str:
    return str(exc).replace("\n", " ")[:n]


def first_key(env_var: str) -> str | None:
    keys = [k.strip() for k in (os.getenv(env_var, "") or "").split(",") if k.strip()]
    return keys[0] if keys else None


def is_chat_model(model_id: str) -> bool:
    low = model_id.lower()
    if any(bad in low for bad in _NON_CHAT):
        return False
    if any(bad in low for bad in _HARNESS_ONLY):
        return False
    return True


def openrouter_candidates(limit: int = 5) -> list[str]:
    """Live $0 chat models on OpenRouter, largest context first."""
    try:
        r = requests.get("https://openrouter.ai/api/v1/models", timeout=30)
        r.raise_for_status()
        rows = r.json().get("data", [])
    except Exception as exc:
        p(f"  ! model list fetch failed: {short(exc, 70)}")
        return []

    free = []
    for m in rows:
        mid = m.get("id") or ""
        pricing = m.get("pricing") or {}
        if not is_chat_model(mid):
            continue
        try:
            if float(pricing.get("prompt", 1)) == 0.0 and float(pricing.get("completion", 1)) == 0.0:
                free.append((int(m.get("context_length") or 0), mid))
        except (TypeError, ValueError):
            continue

    free.sort(reverse=True)
    p(f"  live free CHAT models: {len(free)}")
    for ctx, mid in free[:limit]:
        p(f"    · {mid}  (ctx {ctx:,})")
    return [mid for _, mid in free[:limit]]


# Explicit Mistral candidates — free tier includes all of these.
MISTRAL_CANDIDATES = [
    "mistral-large-latest",
    "mistral-medium-2508",
    "mistral-medium-2505",
    "magistral-medium-latest",
    "mistral-small-latest",
]

_FILLER = (
    "The Supreme Court has repeatedly held that Article 21 encompasses the right "
    "to livelihood, shelter and dignity, and that executive action curtailing these "
    "must satisfy the tests of legality, necessity and proportionality. "
)

PROMPT = (
    "SYSTEM:\nYou are a senior editorial writer for a premier UPSC knowledge "
    "platform. Write in analytical, exam-oriented prose.\n\n"
    "TASK: Using ONLY the grounding material below, write a ~600 word analytical "
    "article on the constitutional dimensions of student fee-reimbursement "
    "litigation. Include: context, constitutional provisions, judicial reasoning, "
    "and UPSC relevance. Use markdown headings.\n\n"
    "GROUNDING MATERIAL:\n" + _FILLER * 170
)[:36000]


def bench(label: str, client: OpenAI, model: str) -> tuple | None:
    p(f"\n  ── {model}")
    try:
        t0 = time.perf_counter()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": PROMPT}],
            max_tokens=OUTPUT_TOKENS,
            temperature=0.25,
        )
        elapsed = time.perf_counter() - t0
    except Exception as exc:
        p(f"     ✗ {short(exc)}")
        return None

    text = (resp.choices[0].message.content or "").strip()
    words = len(text.split())
    tps = (len(text) / 4) / elapsed if elapsed else 0
    p(f"     ✓ {words} words · {elapsed:.1f}s · ~{tps:.0f} tok/s")
    p("     ┌─ sample ─────────────────────────────────────────────")
    for line in text[:700].splitlines():
        p(f"     │ {line}")
    p("     └──────────────────────────────────────────────────────")
    return (label, model, words, elapsed, tps)


def main() -> None:
    p("=" * 76)
    p("  L0b — BEST-MODEL SELECTION")
    p(f"  Prompt {len(PROMPT):,} chars (~{len(PROMPT)//4:,} tok) → {OUTPUT_TOKENS} output tokens")
    p("=" * 76)

    results: list[tuple] = []

    # ── Mistral ───────────────────────────────────────────────────────────────
    key = first_key("MISTRAL_API_KEY")
    p(f"\n{'─' * 76}\n▶ MISTRAL  [{mask(key) if key else 'NO KEY'}]\n{'─' * 76}")
    if key:
        client = OpenAI(api_key=key, base_url="https://api.mistral.ai/v1", timeout=TIMEOUT)
        for model in MISTRAL_CANDIDATES:
            r = bench("mistral", client, model)
            if r:
                results.append(r)

    # ── OpenRouter ────────────────────────────────────────────────────────────
    key = first_key("OPENROUTER_API_KEY")
    p(f"\n{'─' * 76}\n▶ OPENROUTER  [{mask(key) if key else 'NO KEY'}]\n{'─' * 76}")
    if key:
        cands = openrouter_candidates()
        client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1", timeout=TIMEOUT)
        for model in cands:
            r = bench("openrouter", client, model)
            if r:
                results.append(r)

    # ── Summary ───────────────────────────────────────────────────────────────
    p("\n" + "=" * 76)
    p("  RESULTS  (pick by quality of sample above, then by speed)")
    p("=" * 76)
    p(f"  {'provider':<12}{'words':<8}{'secs':<8}{'tok/s':<8}model")
    p("  " + "-" * 72)
    for label, model, words, elapsed, tps in sorted(results, key=lambda r: (r[0], r[3])):
        p(f"  {label:<12}{words:<8}{elapsed:<8.1f}{tps:<8.0f}{model}")
    p("=" * 76)
    p("  Target: ~600 words, coherent markdown, UPSC-analytical tone.")
    p("=" * 76)


if __name__ == "__main__":
    main()
