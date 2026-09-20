"""
engines/book_content/tests/test_llm_pool.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Regression tests for the multi-provider LLM pool (FEATURES_LLM_FIX.md).

These lock in the behaviour that fixes the 2026-08-19 outage, where Daily CA
generation produced 0 articles for three days:

  • Groq returns 413 for the ~9k-token article prompt (free tier ≈ 6k TPM).
    That is DETERMINISTIC — retrying or adding keys can never satisfy it,
    because one request cannot be split across keys.
  • Cerebras returned 402 on every key, and the old pool retried those five
    dead keys on every call in every job.

Every test here is offline: fake clients, no network, no real settings.
If one of these fails, the outage conditions have been reintroduced.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings

import engines.book_content.services.llm_service as llm

# Hermetic, per-process cache for the TTL circuit breaker. The project's real
# cache is Redis-backed and SHARED across pytest-xdist workers, so a provider
# parked by one test (or a parallel worker) leaked into another → flaky
# "no capable provider" failures locally. LocMemCache is per-process, so each
# worker is isolated and setUp's clear() fully resets it. (CI's pytest-split
# sharding dodged the race, which is why it was green there.)
_ISOLATED_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "llm-pool-tests",
    }
}


# ── Helpers ───────────────────────────────────────────────────────────────────


class _HTTPError(Exception):
    """Provider error carrying an HTTP status, like the real SDK exceptions."""

    def __init__(self, status_code: int, message: str = "") -> None:
        super().__init__(message or f"Error code: {status_code}")
        self.status_code = status_code


def _spec(name="groq", max_tokens=1_000_000, json_ok=True):
    """Real-shaped ProviderSpec stand-in. Never named 'openrouter' — that would
    trigger live model resolution over the network."""
    return SimpleNamespace(
        name=name,
        model_setting=f"{name.upper()}_MODEL",
        default_model=f"{name}-model",
        max_request_tokens=max_tokens,
        supports_json_mode=json_ok,
    )


def _client(content: str | None = None, exc: Exception | None = None):
    """Fake OpenAI-compatible client recording every call it receives."""
    calls: list = []

    def create(**kwargs):
        calls.append(kwargs)
        if exc is not None:
            raise exc
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    client.calls = calls  # type: ignore[attr-defined]
    return client


def _entry(provider="groq", content=None, exc=None, max_tokens=1_000_000, json_ok=True):
    return llm._LLMEntry(
        client=_client(content, exc),
        provider=provider,
        spec=_spec(provider, max_tokens, json_ok),
    )


class _PoolTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # Swap the (shared, Redis-backed) cache for a per-process in-memory one
        # so the circuit breaker can never leak a park across tests OR across
        # parallel xdist workers.
        override = override_settings(CACHES=_ISOLATED_CACHE)
        override.enable()
        self.addCleanup(override.disable)
        # A park from one test must never leak into the next.
        try:
            cache.clear()
        except Exception:
            pass
        llm._local_unhealthy.clear()
        llm._local_rate_limited.clear()
        llm._local_demoted.clear()

        # _current_key_idx is a module-level round-robin counter that advances on
        # EVERY successful dispatch, including those in other tests. Left alone,
        # the pool starts at a different entry depending on how many tests ran
        # first, so a test asserting "the first provider was tried" passes or
        # fails purely on collection order. Reset it so entry 0 is always first.
        llm._current_key_idx = 0

        # Never let a pool test phone home to real Sentry. Local dev has
        # SENTRY_DSN set, so the failure-path tests (and any accidental failure)
        # would otherwise emit a live "LLM permanently failed" event.
        for _fn in ("capture_message", "capture_exception"):
            _p = patch.object(llm.sentry_sdk, _fn)
            _p.start()
            self.addCleanup(_p.stop)


# ── Error classification ──────────────────────────────────────────────────────


class TestClassify(_PoolTestCase):
    def test_413_skips_provider_and_is_never_retried(self) -> None:
        """413 is deterministic — retrying it burned 10 minutes per article."""
        assert llm._classify(_HTTPError(413)) == llm._SKIP_PROVIDER
        assert (
            llm._classify(Exception("Request too large for model"))
            == llm._SKIP_PROVIDER
        )

    def test_402_disables_provider(self) -> None:
        """The exact Cerebras failure: park it, don't retry 5 dead keys forever."""
        assert llm._classify(_HTTPError(402)) == llm._DISABLE_PROVIDER
        assert llm._classify(Exception("Payment required")) == llm._DISABLE_PROVIDER

    def test_401_and_403_disable_provider(self) -> None:
        assert llm._classify(_HTTPError(401)) == llm._DISABLE_PROVIDER
        assert llm._classify(_HTTPError(403)) == llm._DISABLE_PROVIDER

    def test_404_skips_provider(self) -> None:
        """Retired model — the Cerebras-Llama failure mode."""
        assert llm._classify(_HTTPError(404)) == llm._SKIP_PROVIDER
        assert llm._classify(Exception("unavailable for free")) == llm._SKIP_PROVIDER

    def test_429_and_unknown_errors_retry(self) -> None:
        assert llm._classify(_HTTPError(429)) == llm._RETRY
        assert llm._classify(Exception("connection reset")) == llm._RETRY


# ── Capability routing ────────────────────────────────────────────────────────


class TestCapabilityRouting(_PoolTestCase):
    def test_small_capacity_provider_excluded_from_large_prompt(self) -> None:
        """THE FIX: a 9k prompt is never offered to a ~6k-capacity provider."""
        pool = [
            _entry("groq", content="x", max_tokens=5_500),
            _entry("mistral", content="x", max_tokens=120_000),
        ]
        with patch.object(llm, "_pool", pool):
            small = {e.provider for e in llm._usable_entries(500, False)}
            large = {e.provider for e in llm._usable_entries(9_000, False)}

        assert small == {"groq", "mistral"}
        assert large == {"mistral"}, "groq must be filtered out before the call"

    def test_provider_without_json_mode_excluded_when_json_required(self) -> None:
        pool = [
            _entry("groq", content="x", json_ok=False),
            _entry("mistral", content="x", json_ok=True),
        ]
        with patch.object(llm, "_pool", pool):
            assert {e.provider for e in llm._usable_entries(100, True)} == {"mistral"}
            assert {e.provider for e in llm._usable_entries(100, False)} == {
                "groq",
                "mistral",
            }

    def test_no_capable_provider_returns_empty_list(self) -> None:
        pool = [_entry("groq", content="x", max_tokens=5_500)]
        with patch.object(llm, "_pool", pool):
            assert llm._usable_entries(9_000, False) == []


# ── Registry ──────────────────────────────────────────────────────────────────


class TestRegistry(_PoolTestCase):
    def test_cerebras_removed(self) -> None:
        """
        Removed 2026-09-16 (was: disabled, config retained). Its module-level SDK
        import crashed every lean install without the package — the CA scraper
        died twice on it. Every remaining provider must build on an SDK that
        `requirements/base.txt` AND the pool's own imports actually carry.
        """
        assert all(p.name != "cerebras" for p in llm.PROVIDERS)
        assert {p.sdk for p in llm.PROVIDERS} <= {"groq", "openai"}

    def test_gemini_present_but_disabled(self) -> None:
        gemini = [p for p in llm.PROVIDERS if p.name == "gemini"]
        assert len(gemini) == 1
        assert gemini[0].enabled is False

    def test_active_providers_are_the_expected_three(self) -> None:
        active = [p.name for p in llm.PROVIDERS if p.enabled]
        assert active == ["groq", "mistral", "openrouter"]

    def test_groq_gate_stays_inside_the_proven_request_envelope(self) -> None:
        """
        L11a (2026-09-20): the gate is 7,500 *estimated* tokens because a live call
        proved Groq accepts 10,889 tokens per request (prompt + max_tokens) and real
        tokens run 0.873 × estimate. Raising it past that arithmetic brings the 413
        outage back; lowering it below the article prompt (≤ 6,000 est.) sends the
        article back to the free-tier lottery that died on 2026-09-18.
        """
        groq = next(p for p in llm.PROVIDERS if p.name == "groq")
        largest_completion = max(cfg["max_tokens"] for cfg in llm._MODE_CONFIG.values())
        assert groq.max_request_tokens * 0.873 + largest_completion <= 10_889
        assert groq.max_request_tokens >= 6_000

    def test_ca_article_mode_has_the_measured_completion_budget(self) -> None:
        """
        4,000 because 2,048 truncated the article; "medium" because the A/B on the
        rewritten prompt (2026-09-20) gave 8/6/6 links and 0–3 untraceable numbers,
        while "low" gave 0/3/8 links and 5–9 numbers that traced to nothing.
        """
        cfg = llm._MODE_CONFIG["ca_article"]
        assert cfg["max_tokens"] == 4000
        assert cfg["reasoning_effort"] == "medium"
        assert cfg["temperature"] == llm._MODE_CONFIG["writer"]["temperature"]


# ── Reasoning effort (ca_article) ─────────────────────────────────────────────


class TestReasoningEffort(_PoolTestCase):
    def test_sent_to_groq_reasoning_models_only(self) -> None:
        cfg = {"temperature": 0.25, "max_tokens": 4000, "reasoning_effort": "low"}
        assert llm._reasoning_kwargs("groq", "openai/gpt-oss-120b", cfg) == {
            "extra_body": {"reasoning_effort": "low"}
        }
        assert llm._reasoning_kwargs("groq", "qwen/qwen3-32b", cfg) == {
            "extra_body": {"reasoning_effort": "low"}
        }
        # A Groq model without reasoning support would answer 400.
        assert llm._reasoning_kwargs("groq", "llama-3.3-70b-versatile", cfg) == {}
        # Never to the OpenAI-compatible providers.
        assert llm._reasoning_kwargs("mistral", "mistral-medium-2508", cfg) == {}
        assert (
            llm._reasoning_kwargs("openrouter", "openai/gpt-oss-120b:free", cfg) == {}
        )

    def test_modes_without_an_effort_send_nothing(self) -> None:
        for mode, cfg in llm._MODE_CONFIG.items():
            if mode == "ca_article":
                continue
            assert llm._reasoning_kwargs("groq", "openai/gpt-oss-120b", cfg) == {}, mode

    def test_dispatch_passes_extra_body_only_where_it_applies(self) -> None:
        groq = _entry("groq", content="article")
        mistral = _entry("mistral", content="article")
        cfg = dict(llm._MODE_CONFIG["ca_article"])
        with (
            patch.object(llm, "_pool", [groq, mistral]),
            patch.object(llm, "_pool_size", 2),
            patch.object(llm.time, "sleep", return_value=None),
            patch.object(llm, "_model_for", return_value="openai/gpt-oss-120b"),
        ):
            llm._dispatch(
                messages=[{"role": "user", "content": "hi"}],
                cfg=cfg,
                log_name="test",
                json_mode=False,
                est_tokens=100,
            )
        assert groq.client.calls[0]["extra_body"] == {"reasoning_effort": "medium"}
        assert groq.client.calls[0]["max_tokens"] == 4000
        assert mistral.client.calls == []  # groq answered first

        groq_fail = _entry("groq", exc=_HTTPError(413))
        mistral_ok = _entry("mistral", content="article")
        with (
            patch.object(llm, "_pool", [groq_fail, mistral_ok]),
            patch.object(llm, "_pool_size", 2),
            patch.object(llm.time, "sleep", return_value=None),
            patch.object(llm, "_model_for", return_value="mistral-medium-2508"),
        ):
            llm._dispatch(
                messages=[{"role": "user", "content": "hi"}],
                cfg=cfg,
                log_name="test",
                json_mode=False,
                est_tokens=100,
            )
        assert "extra_body" not in mistral_ok.client.calls[0]


# ── Dispatch behaviour ────────────────────────────────────────────────────────


class TestDispatch(_PoolTestCase):
    def _dispatch(self, pool, est_tokens=100, json_mode=False):
        cfg = {"temperature": 0.1, "max_tokens": 512}
        with (
            patch.object(llm, "_pool", pool),
            patch.object(llm, "_pool_size", len(pool)),
            patch.object(llm.time, "sleep", return_value=None),
        ):
            return llm._dispatch(
                messages=[{"role": "user", "content": "hi"}],
                cfg=cfg,
                log_name="test",
                json_mode=json_mode,
                est_tokens=est_tokens,
            )

    def test_413_fails_over_without_retrying_the_same_provider(self) -> None:
        bad = _entry("groq", exc=_HTTPError(413))
        good = _entry("mistral", content="recovered")

        assert self._dispatch([bad, good]) == "recovered"
        assert (
            len(bad.client.calls) == 1
        ), "413 must not be retried — it is deterministic"

    def test_402_parks_provider_for_later_calls(self) -> None:
        dead = _entry("groq", exc=_HTTPError(402))
        good = _entry("mistral", content="ok")

        assert self._dispatch([dead, good]) == "ok"
        assert llm._is_unhealthy("groq") is True
        assert llm._is_unhealthy("mistral") is False

    def test_empty_response_is_a_failure_not_a_success(self) -> None:
        """A free model was seen returning HTTP 200 with an empty body."""
        empty = _entry("groq", content="   ")
        good = _entry("mistral", content="real content")

        assert self._dispatch([empty, good]) == "real content"

    def test_all_providers_failing_returns_empty_string(self) -> None:
        """Callers rely on '' meaning failure (generator_service raises on it)."""
        pool = [
            _entry("groq", exc=_HTTPError(413)),
            _entry("mistral", exc=_HTTPError(413)),
        ]
        with patch.object(llm.sentry_sdk, "capture_message"):
            assert self._dispatch(pool) == ""

    def test_no_capable_provider_returns_empty_string(self) -> None:
        pool = [_entry("groq", content="x", max_tokens=5_500)]
        with patch.object(llm.sentry_sdk, "capture_message"):
            assert self._dispatch(pool, est_tokens=9_000) == ""

    def test_successful_call_returns_stripped_content(self) -> None:
        assert self._dispatch([_entry("groq", content="  spaced  ")]) == "spaced"


# ── L11b — OpenRouter models earn adoption ────────────────────────────────────


def _smoke_client(answers: dict[str, str | Exception]):
    """Fake client whose reply depends on the model id it is asked for."""
    calls: list = []

    def create(**kwargs):
        calls.append(kwargs)
        reply = answers.get(kwargs["model"], "")
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))]
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    client.calls = calls  # type: ignore[attr-defined]
    return client


class TestOpenRouterAdoption(_PoolTestCase):
    """
    2026-09-18: the blind daily pick landed on a model returning HTTP 200 with an
    empty body and the cache served it all day; on 09-20 the id went paid-only
    (404) and the cache still held it. Adoption now needs a smoke call, and a
    model that fails in service is demoted for a day.
    """

    def setUp(self) -> None:
        super().setUp()
        # The env pin bypasses resolution entirely; make sure local .env cannot
        # short-circuit these tests. (override_settings cannot decorate a plain
        # unittest.TestCase class, hence enable/cleanup here, as _PoolTestCase does.)
        override = override_settings(OPENROUTER_MODEL="")
        override.enable()
        self.addCleanup(override.disable)

    def test_resolver_smoke_tests_candidates_and_skips_demoted_ones(self) -> None:
        llm.demote_openrouter_model("a/dead:free", "seen empty on 09-18")
        client = _smoke_client({"b/silent:free": "", "c/alive:free": "OK"})
        with patch.object(
            llm,
            "_free_openrouter_candidates",
            return_value=["a/dead:free", "b/silent:free", "c/alive:free"],
        ):
            chosen = llm._resolve_openrouter_model("seed", client)

        assert chosen == "c/alive:free"
        assert [c["model"] for c in client.calls] == ["b/silent:free", "c/alive:free"]
        assert llm._is_demoted("b/silent:free"), "a failed smoke call demotes"
        assert cache.get(llm.OPENROUTER_MODEL_CACHE_KEY) == "c/alive:free"

    def test_resolver_returns_seed_without_caching_when_the_list_is_unreachable(
        self,
    ) -> None:
        with patch.object(llm, "_free_openrouter_candidates", return_value=[]):
            assert llm._resolve_openrouter_model("seed", _smoke_client({})) == "seed"
        assert cache.get(llm.OPENROUTER_MODEL_CACHE_KEY) is None

    def test_a_demoted_seed_is_never_returned(self) -> None:
        """The seed went paid-only on 2026-09-20 — a fallback that 404s is no fallback."""
        llm.demote_openrouter_model("seed", "404 unavailable for free")
        with patch.object(llm, "_free_openrouter_candidates", return_value=[]):
            assert llm._resolve_openrouter_model("seed", _smoke_client({})) == ""

    def test_nothing_passing_the_smoke_call_returns_empty_and_caches_nothing(
        self,
    ) -> None:
        """First live run: five failed smoke calls, then the seed got cached and 404'd."""
        client = _smoke_client({"a:free": "", "b:free": ""})
        with patch.object(
            llm, "_free_openrouter_candidates", return_value=["a:free", "b:free"]
        ):
            assert llm._resolve_openrouter_model("seed", client) == ""
        assert cache.get(llm.OPENROUTER_MODEL_CACHE_KEY) is None
        assert llm._is_demoted("a:free") and llm._is_demoted("b:free")

    def test_daily_quota_429_parks_the_provider_and_demotes_no_model(self) -> None:
        """'free-models-per-day' is the ACCOUNT's quota, not a model fault."""
        quota = _HTTPError(
            429, "Error code: 429 - Rate limit exceeded: free-models-per-day"
        )
        client = _smoke_client({"a:free": quota, "b:free": quota})
        with patch.object(
            llm, "_free_openrouter_candidates", return_value=["a:free", "b:free"]
        ):
            assert llm._resolve_openrouter_model("seed", client) == ""
        assert len(client.calls) == 1, "stop at the first quota answer"
        assert llm._is_rate_limited("openrouter") is True
        assert not llm._is_demoted("a:free") and not llm._is_demoted("b:free")
        assert cache.get(llm.OPENROUTER_MODEL_CACHE_KEY) is None

    def test_dispatch_skips_a_provider_with_no_usable_model_without_calling_it(
        self,
    ) -> None:
        router = _entry("openrouter", content="never")
        groq = _entry("groq", content="article")
        with (
            patch.object(llm, "_pool", [router, groq]),
            patch.object(llm, "_pool_size", 2),
            patch.object(llm.time, "sleep", return_value=None),
            patch.object(llm, "_model_for", side_effect=["", "openai/gpt-oss-120b"]),
        ):
            result = llm._dispatch(
                messages=[{"role": "user", "content": "hi"}],
                cfg={"temperature": 0.1, "max_tokens": 512},
                log_name="test",
                json_mode=False,
                est_tokens=100,
            )
        assert result == "article"
        assert router.client.calls == []

    def test_demotion_clears_the_cached_pick(self) -> None:
        cache.set(llm.OPENROUTER_MODEL_CACHE_KEY, "x/model:free", 3600)
        llm.demote_openrouter_model("x/model:free", "404 unavailable for free")
        assert cache.get(llm.OPENROUTER_MODEL_CACHE_KEY) is None
        assert llm._is_demoted("x/model:free")

    def test_empty_body_demotes_the_model_and_the_next_entry_re_resolves(self) -> None:
        silent = _entry("openrouter", content="")
        alive = _entry("openrouter", content="article")
        with (
            patch.object(llm, "_pool", [silent, alive]),
            patch.object(llm, "_pool_size", 2),
            patch.object(llm.time, "sleep", return_value=None),
            patch.object(
                llm, "_model_for", side_effect=["x/dead:free", "y/alive:free"]
            ),
            patch.object(llm, "demote_openrouter_model") as demote,
        ):
            result = llm._dispatch(
                messages=[{"role": "user", "content": "hi"}],
                cfg={"temperature": 0.1, "max_tokens": 512},
                log_name="test",
                json_mode=False,
                est_tokens=100,
            )
        assert result == "article"
        demote.assert_called_once_with("x/dead:free", "empty response")

    def test_paid_only_404_demotes_the_model_instead_of_skipping_the_provider(
        self,
    ) -> None:
        gone = _entry(
            "openrouter",
            exc=_HTTPError(404, "Error code: 404 - This model is unavailable for free"),
        )
        alive = _entry("openrouter", content="article")
        with (
            patch.object(llm, "_pool", [gone, alive]),
            patch.object(llm, "_pool_size", 2),
            patch.object(llm.time, "sleep", return_value=None),
            patch.object(
                llm, "_model_for", side_effect=["x/paid:free", "y/alive:free"]
            ),
            patch.object(llm, "demote_openrouter_model") as demote,
        ):
            result = llm._dispatch(
                messages=[{"role": "user", "content": "hi"}],
                cfg={"temperature": 0.1, "max_tokens": 512},
                log_name="test",
                json_mode=False,
                est_tokens=100,
            )
        assert result == "article"
        assert demote.call_args[0][0] == "x/paid:free"

    def test_demotions_are_capped_per_call_then_the_provider_is_skipped(self) -> None:
        pool = [_entry("openrouter", content="") for _ in range(3)]
        with (
            patch.object(llm, "_pool", pool),
            patch.object(llm, "_pool_size", 3),
            patch.object(llm.time, "sleep", return_value=None),
            patch.object(llm, "_model_for", return_value="x/dead:free"),
            patch.object(llm, "demote_openrouter_model") as demote,
        ):
            result = llm._dispatch(
                messages=[{"role": "user", "content": "hi"}],
                cfg={"temperature": 0.1, "max_tokens": 512},
                log_name="test",
                json_mode=False,
                est_tokens=100,
            )
        assert result == ""
        assert demote.call_count == llm.OPENROUTER_MAX_DEMOTIONS_PER_CALL
        total_calls = sum(len(e.client.calls) for e in pool)
        assert total_calls == 3, "after the cap the provider is skipped, not retried"


# ── L11d — the rotation stays on the primary provider ────────────────────────


class TestPrimaryProviderRotation(_PoolTestCase):
    """
    First live run on 2026-09-20: the flat key rotation started roughly a third
    of all calls on Mistral or OpenRouter, so a free model wrote some proposals
    and could have written articles. Registry order is the routing order; the
    rotation only spreads load across the FIRST provider's keys.
    """

    def _dispatch(self, pool):
        with (
            patch.object(llm, "_pool", pool),
            patch.object(llm, "_pool_size", len(pool)),
            patch.object(llm.time, "sleep", return_value=None),
            patch.object(llm.sentry_sdk, "capture_message"),
        ):
            return llm._dispatch(
                messages=[{"role": "user", "content": "hi"}],
                cfg={"temperature": 0.1, "max_tokens": 512},
                log_name="test",
                json_mode=False,
                est_tokens=100,
            )

    def test_consecutive_calls_rotate_groq_keys_and_never_start_on_a_fallback(
        self,
    ) -> None:
        k1 = _entry("groq", content="k1")
        k2 = _entry("groq", content="k2")
        k3 = _entry("groq", content="k3")
        mistral = _entry("mistral", content="mistral")
        router = _entry("openrouter", content="router")
        pool = [k1, k2, k3, mistral, router]

        answers = [self._dispatch(pool) for _ in range(6)]

        assert answers == ["k1", "k2", "k3", "k1", "k2", "k3"]
        assert mistral.client.calls == [] and router.client.calls == []

    def test_fallbacks_are_reached_only_after_every_primary_key_failed(self) -> None:
        k1 = _entry("groq", exc=_HTTPError(429, "Error code: 429 - Rate limit"))
        k2 = _entry("groq", exc=_HTTPError(429, "Error code: 429 - Rate limit"))
        mistral = _entry("mistral", content="mistral")
        llm._current_key_idx = 1  # rotation parked on k2 from an earlier call

        assert self._dispatch([k1, k2, mistral]) == "mistral"
        assert len(k1.client.calls) == 1 and len(k2.client.calls) == 1
        assert llm._current_key_idx == 1, "a fallback answer does not move the rotation"

    def test_a_skipped_primary_makes_the_next_provider_primary(self) -> None:
        groq = _entry("groq", exc=_HTTPError(413))
        m1 = _entry("mistral", content="m1")
        m2 = _entry("mistral", content="m2")
        # 413 skips groq for this call; mistral becomes the primary for the rest of it
        assert self._dispatch([groq, m1, m2]) == "m1"


# ── L11c — rate-limit park ────────────────────────────────────────────────────


_GROQ_TPM = (
    "Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` in "
    "organization `org_x` service tier `on_demand` on tokens per minute (TPM): "
    "Limit 8000, Used 7900, Requested 3100. Please try again in 2.5s."
)
_GROQ_TPD = (
    "Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` in "
    "organization `org_x` on tokens per day (TPD): Limit 200000, Used 200000."
)
_OPENROUTER_DAILY = (
    "Error code: 429 - Rate limit exceeded: free-models-per-day. Add 10 credits"
)


class TestRateLimitPark(_PoolTestCase):
    """
    A spent free tier used to cost the whole 15/30/60/120 s ladder on every call.
    But only a QUOTA-class 429 may park: on 2026-09-20 the first version parked
    Groq — the only working provider — after three short rounds of per-minute
    429s under sustained load, and four of five Step-7 rewrites were lost.
    """

    def _dispatch(self, pool):
        with (
            patch.object(llm, "_pool", pool),
            patch.object(llm, "_pool_size", len(pool)),
            patch.object(llm.time, "sleep", return_value=None),
            patch.object(llm.sentry_sdk, "capture_message"),
        ):
            return llm._dispatch(
                messages=[{"role": "user", "content": "hi"}],
                cfg={"temperature": 0.1, "max_tokens": 512},
                log_name="test",
                json_mode=False,
                est_tokens=100,
            )

    def test_quota_classification(self) -> None:
        assert llm._is_quota_429(_HTTPError(429, _GROQ_TPD)) is True
        assert llm._is_quota_429(_HTTPError(429, _OPENROUTER_DAILY)) is True
        assert llm._is_quota_429(_HTTPError(429, _GROQ_TPM)) is False
        assert llm._is_quota_429(_HTTPError(429, "Rate limit exceeded")) is False
        assert llm._is_quota_429(_HTTPError(503, "per day")) is False

    def test_three_all_quota_429_rounds_park_the_provider(self) -> None:
        pool = [
            _entry("openrouter", exc=_HTTPError(429, _OPENROUTER_DAILY)),
            _entry("openrouter", exc=_HTTPError(429, _OPENROUTER_DAILY)),
        ]
        with patch.object(llm, "_model_for", return_value="x/model:free"):
            assert self._dispatch(pool) == ""
        assert llm._is_rate_limited("openrouter") is True
        total_calls = sum(len(e.client.calls) for e in pool)
        assert (
            total_calls == 2 * llm.RATE_LIMIT_ROUNDS_TO_PARK
        ), "parked after three all-quota-429 rounds, not after the full ladder"

    def test_per_minute_429s_never_park_even_across_the_whole_ladder(self) -> None:
        """Groq under sustained load: every round 429s, the ladder keeps trying."""
        pool = [
            _entry("groq", exc=_HTTPError(429, _GROQ_TPM)),
            _entry("groq", exc=_HTTPError(429, _GROQ_TPM)),
        ]
        assert self._dispatch(pool) == ""
        assert llm._is_rate_limited("groq") is False
        total_calls = sum(len(e.client.calls) for e in pool)
        assert total_calls == 2 * (
            1 + len(llm.RETRY_WAIT_TIMES)
        ), "every round of the ladder was attempted — nothing parked Groq"

    def test_a_generic_429_without_a_quota_marker_never_parks(self) -> None:
        """Mistral's bare 'Rate limit exceeded' is not proof of a spent tier."""
        pool = [
            _entry(
                "mistral", exc=_HTTPError(429, "Error code: 429 - Rate limit exceeded")
            ),
            _entry(
                "mistral", exc=_HTTPError(429, "Error code: 429 - Rate limit exceeded")
            ),
        ]
        assert self._dispatch(pool) == ""
        assert llm._is_rate_limited("mistral") is False

    def test_a_burst_429_followed_by_success_never_parks(self) -> None:
        pool = [
            _entry("groq", exc=_HTTPError(429, _GROQ_TPM)),
            _entry("groq", content="ok"),
        ]
        assert self._dispatch(pool) == "ok"
        assert llm._is_rate_limited("groq") is False

    def test_parked_provider_is_excluded_from_routing(self) -> None:
        pool = [_entry("mistral", content="x"), _entry("groq", content="x")]
        llm._mark_rate_limited("mistral")
        with patch.object(llm, "_pool", pool):
            assert {e.provider for e in llm._usable_entries(100, False)} == {"groq"}


if __name__ == "__main__":
    unittest.main()
