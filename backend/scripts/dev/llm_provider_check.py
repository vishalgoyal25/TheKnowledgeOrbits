"""
_l0_verify.py — L0 gate for FEATURES_LLM_FIX.md   (v2)

THROWAWAY SCRIPT. DO NOT COMMIT. Delete after L0 passes.

v2 changes after the first run:
  - OpenRouter free models are DISCOVERED LIVE from /models filtered on
    pricing == 0. v1 used hardcoded ":free" IDs which have since moved to paid
    (OpenRouter rotates its free lineup without notice) -> every call 404'd.
  - Mistral models discovered live too.
  - flush=True everywhere so progress is visible while running.
  - Timeout cut 120s -> 60s, and a per-call banner prints BEFORE the call so a
    hang is attributable to a specific model.

Verifies:
  D  discovery   — which models are ACTUALLY free / usable for this key
  T1 small call  — does the key work at all?
  T2 LARGE call  — does it accept a ~9k-token prompt?   <-- THE GATE
  T3 json mode   — does it support response_format={"type":"json_object"}?

Keys are read from backend/.env and MASKED in all output.

Run:  python _l0_verify.py
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

TIMEOUT = 60.0
MAX_MODELS_TO_TRY = 6

PROVIDERS = {
    "openrouter": {
        "env": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
    },
    "mistral": {
        "env": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
    },
}

_FILLER = (
    "Public Interest Litigation in India expanded access to constitutional "
    "remedies under Articles 32 and 226, enabling courts to address systemic "
    "governance failures affecting disadvantaged groups across many states. "
)
LARGE_PROMPT = ("Summarise the following in one short sentence.\n\n" + _FILLER * 460)[:36000]
SMALL_PROMPT = "Reply with exactly: OK"
JSON_PROMPT = 'Return a JSON object with a single key "status" whose value is "ok".'


def p(msg: str = "") -> None:
    print(msg, flush=True)


def mask(key: str) -> str:
    return f"{key[:6]}…{key[-4:]}" if len(key) > 12 else "…"


def short(exc: Exception, n: int = 120) -> str:
    return str(exc).replace("\n", " ")[:n]


def get_keys(env_var: str) -> list[str]:
    return [k.strip() for k in (os.getenv(env_var, "") or "").split(",") if k.strip()]


def openrouter_free_models() -> list[str]:
    """
    Ask OpenRouter which models cost $0 RIGHT NOW, newest-first by context size.
    This endpoint needs no auth. Filtering on pricing is the only reliable way —
    the ':free' suffix convention is not stable.
    """
    try:
        r = requests.get("https://openrouter.ai/api/v1/models", timeout=30)
        r.raise_for_status()
        rows = r.json().get("data", [])
    except Exception as exc:
        p(f"      ! could not fetch OpenRouter model list: {short(exc, 70)}")
        return []

    free = []
    for m in rows:
        pricing = m.get("pricing") or {}
        try:
            if float(pricing.get("prompt", 1)) == 0.0 and float(pricing.get("completion", 1)) == 0.0:
                free.append((int(m.get("context_length") or 0), m.get("id")))
        except (TypeError, ValueError):
            continue

    free.sort(reverse=True)
    ids = [mid for _, mid in free if mid]
    p(f"      live free models on OpenRouter: {len(ids)}")
    for ctx, mid in free[:MAX_MODELS_TO_TRY]:
        p(f"        · {mid}  (ctx {ctx:,})")
    return ids[:MAX_MODELS_TO_TRY]


def sdk_models(client: OpenAI) -> list[str]:
    try:
        ids = [m.id for m in client.models.list().data]
    except Exception as exc:
        p(f"      ! models.list() failed: {short(exc, 70)}")
        return []
    prefer = [m for m in ids if "large" in m or "medium" in m or "small" in m]
    ordered = prefer + [m for m in ids if m not in prefer]
    p(f"      visible models: {len(ids)} → trying {ordered[:MAX_MODELS_TO_TRY]}")
    return ordered[:MAX_MODELS_TO_TRY]


def call(
    client: OpenAI, model: str, prompt: str, json_mode: bool = False, max_tokens: int = 64
) -> tuple[str, float]:
    """Returns (text, elapsed_seconds)."""
    kwargs: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    t0 = time.perf_counter()
    resp = client.chat.completions.create(**kwargs)
    elapsed = time.perf_counter() - t0
    return (resp.choices[0].message.content or "").strip(), elapsed


def main() -> None:
    p("=" * 74)
    p("  L0 — LLM PROVIDER VERIFICATION  (v2, live model discovery)")
    p(f"  Large-prompt gate: {len(LARGE_PROMPT):,} chars (~{len(LARGE_PROMPT)//4:,} tokens)")
    p("=" * 74)

    large_ok: list[str] = []
    json_ok: list[str] = []
    summary: list[tuple] = []

    for name, cfg in PROVIDERS.items():
        keys = get_keys(cfg["env"])
        p(f"\n{'─' * 74}")
        p(f"▶ {name.upper()}  ({cfg['env']}) — {len(keys)} key(s)")
        p("─" * 74)

        if not keys:
            p(f"  ✗ {cfg['env']} not set or empty in .env")
            summary.append((name, "-", "NO KEY", "-", "-", "-", 0.0, 0.0))
            continue

        shared_models = openrouter_free_models() if name == "openrouter" else None

        for i, key in enumerate(keys):
            p(f"\n  Key #{i} [{mask(key)}]")
            try:
                client = OpenAI(api_key=key, base_url=cfg["base_url"], timeout=TIMEOUT)
            except Exception as exc:
                p(f"    ✗ client init failed: {short(exc)}")
                summary.append((name, i, "INIT FAIL", "-", "-", "-", 0.0, 0.0))
                continue

            models = shared_models if shared_models is not None else sdk_models(client)
            if not models:
                p("    ⚠ no candidate models discovered")
                summary.append((name, i, "NO MODELS", "-", "-", "-", 0.0, 0.0))
                continue

            chosen = None
            t1_secs = 0.0
            for model in models:
                p(f"    T1 small  … {model}")
                try:
                    out, t1_secs = call(client, model, SMALL_PROMPT)
                    p(f"    T1 small  ✓ {model} → {out[:40]!r}  [{t1_secs:.1f}s]")
                    chosen = model
                    break
                except Exception as exc:
                    p(f"    T1 small  ✗ {short(exc)}")

            if not chosen:
                p("    ⚠ no working model for this key")
                summary.append((name, i, "FAIL", "-", "-", "-", 0.0, 0.0))
                continue

            t2 = "FAIL"
            t2_secs = 0.0
            p(f"    T2 LARGE  … {chosen} (~{len(LARGE_PROMPT)//4:,} tokens)")
            try:
                _, t2_secs = call(client, chosen, LARGE_PROMPT)
                p(f"    T2 LARGE  ✓ accepted  [{t2_secs:.1f}s]")
                t2 = "PASS"
                large_ok.append(f"{name}#{i}")
            except Exception as exc:
                p(f"    T2 LARGE  ✗ {short(exc)}")

            t3 = "FAIL"
            p(f"    T3 json   … {chosen}")
            try:
                out, t3_secs = call(client, chosen, JSON_PROMPT, json_mode=True)
                p(f"    T3 json   ✓ → {out[:50]!r}  [{t3_secs:.1f}s]")
                t3 = "PASS"
                json_ok.append(f"{name}#{i}")
            except Exception as exc:
                p(f"    T3 json   ✗ {short(exc)}")

            # T4 — AGENT-SIZED GENERATION (the research_agent speed question).
            # 600 output tokens ≈ MAX_TOKENS_SUMMARY. This is the number that
            # decides whether a multi-provider research_agent is usable live.
            p(f"    T4 speed  … {chosen} (600 output tokens)")
            try:
                out, t4_secs = call(
                    client,
                    chosen,
                    "Write a 500-word analytical note on federalism in India.",
                    max_tokens=600,
                )
                tps = len(out) / 4 / t4_secs if t4_secs else 0
                p(f"    T4 speed  ✓ {len(out):,} chars in {t4_secs:.1f}s  (~{tps:.0f} tok/s)")
            except Exception as exc:
                t4_secs = 0.0
                p(f"    T4 speed  ✗ {short(exc)}")

            summary.append((name, i, "PASS", chosen, t2, t3, t2_secs, t4_secs))

    p("\n" + "=" * 74)
    p("  SUMMARY")
    p("=" * 74)
    p(f"  {'provider':<12}{'key':<4}{'small':<10}{'large':<7}{'json':<7}{'9k s':<8}{'gen s':<8}model")
    p("  " + "-" * 78)
    for name, idx, t1, model, t2, t3, t2s, t4s in summary:
        p(
            f"  {name:<12}{str(idx):<4}{t1:<10}{t2:<7}{t3:<7}"
            f"{t2s:<8.1f}{t4s:<8.1f}{model}"
        )

    providers_large = {s.split("#")[0] for s in large_ok}
    p("\n  Keys accepting ~9k tokens : " + (", ".join(large_ok) or "NONE"))
    p("  Keys supporting json mode : " + (", ".join(json_ok) or "NONE"))

    p("\n" + "=" * 74)
    if len(providers_large) >= 2:
        p(f"  ✓ L0 GATE PASSED — {len(providers_large)} providers accept 9k tokens")
    elif len(providers_large) == 1:
        p("  ⚠ L0 GATE PARTIAL — only 1 provider accepts 9k tokens. STOP & review.")
    else:
        p("  ✗ L0 GATE FAILED — no provider accepts 9k tokens. STOP & review.")
    p("=" * 74)


if __name__ == "__main__":
    main()
