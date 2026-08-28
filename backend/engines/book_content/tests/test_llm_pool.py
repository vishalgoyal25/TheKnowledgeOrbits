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

import engines.book_content.services.llm_service as llm


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
        # The circuit breaker is cache-backed; a park from one test must never
        # leak into the next.
        try:
            cache.clear()
        except Exception:
            pass
        llm._local_unhealthy.clear()


# ── Error classification ──────────────────────────────────────────────────────


class TestClassify(_PoolTestCase):
    def test_413_skips_provider_and_is_never_retried(self) -> None:
        """413 is deterministic — retrying it burned 10 minutes per article."""
        assert llm._classify(_HTTPError(413)) == llm._SKIP_PROVIDER
        assert llm._classify(Exception("Request too large for model")) == llm._SKIP_PROVIDER

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
    def test_cerebras_present_but_disabled(self) -> None:
        """Config RETAINED, plug pulled — re-enabling must stay a one-line change."""
        cerebras = [p for p in llm.PROVIDERS if p.name == "cerebras"]
        assert len(cerebras) == 1, "Cerebras config must not be deleted"
        assert cerebras[0].enabled is False

    def test_gemini_present_but_disabled(self) -> None:
        gemini = [p for p in llm.PROVIDERS if p.name == "gemini"]
        assert len(gemini) == 1
        assert gemini[0].enabled is False

    def test_active_providers_are_the_expected_three(self) -> None:
        active = [p.name for p in llm.PROVIDERS if p.enabled]
        assert active == ["groq", "mistral", "openrouter"]

    def test_groq_capacity_is_below_the_article_prompt_size(self) -> None:
        """If this ever rises above ~9k, the 413 outage silently returns."""
        groq = next(p for p in llm.PROVIDERS if p.name == "groq")
        assert groq.max_request_tokens < 9_000


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
        assert len(bad.client.calls) == 1, "413 must not be retried — it is deterministic"

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
        pool = [_entry("groq", exc=_HTTPError(413)), _entry("mistral", exc=_HTTPError(413))]
        with patch.object(llm.sentry_sdk, "capture_message"):
            assert self._dispatch(pool) == ""

    def test_no_capable_provider_returns_empty_string(self) -> None:
        pool = [_entry("groq", content="x", max_tokens=5_500)]
        with patch.object(llm.sentry_sdk, "capture_message"):
            assert self._dispatch(pool, est_tokens=9_000) == ""

    def test_successful_call_returns_stripped_content(self) -> None:
        assert self._dispatch([_entry("groq", content="  spaced  ")]) == "spaced"


if __name__ == "__main__":
    unittest.main()
