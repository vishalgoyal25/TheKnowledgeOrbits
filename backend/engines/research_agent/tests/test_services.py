"""
engines/research_agent/tests/test_services.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tests for the service + middleware layer. Redis is replaced with an in-memory
FakeRedis (monkeypatched onto each singleton's `_redis`), so tests are
deterministic and independent of a running Redis.

  - CacheService     — set/get roundtrip, miss, confidence back-fill, fail-safe
  - RedisRateLimiter — daily caps (anon/auth), per-provider RPM, fail-open
  - MemoryService    — per-user record/read, isolation, anonymous no-op
  - SSEService       — frame format, decode, terminal stream, cancel flag
  - ResearchOrchestrator — _extract_sources + _save_report (sanitize + persist)
"""

from __future__ import annotations

import pytest

from engines.research_agent.constants import (
    GROQ_REQUESTS_PER_MINUTE,
    PUBLIC_DAILY_LIMIT,
)
from engines.research_agent.middleware.rate_limiter import (
    AUTH_DAILY_LIMIT,
    RateLimitExceeded,
    rate_limiter,
)
from engines.research_agent.evaluation.deepeval_runner import evaluation_runner
from engines.research_agent.models.research_session import ResearchSession
from engines.research_agent.services.cache_service import cache_service
from engines.research_agent.services.memory_service import memory_service
from engines.research_agent.services.orchestrator import ResearchOrchestrator
from engines.research_agent.services.sse_service import sse_service


# ── In-memory fake Redis ─────────────────────────────────────────────────────


class FakeRedis:
    """Minimal Redis stand-in covering only the ops the services use."""

    def __init__(self):
        self.store: dict = {}
        self.hashes: dict = {}
        self.ttls: dict = {}
        self.published: list = []

    def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def expire(self, key, ttl):
        self.ttls[key] = ttl
        return True

    def ttl(self, key):
        return self.ttls.get(key, -1)

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None, **kwargs):
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    def delete(self, key):
        self.store.pop(key, None)
        return 1

    def exists(self, key):
        return 1 if key in self.store else 0

    def hincrby(self, key, field, amount=1):
        h = self.hashes.setdefault(key, {})
        h[field] = int(h.get(field, 0)) + amount
        return h[field]

    def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    def publish(self, channel, payload):
        self.published.append((channel, payload))
        return 1


@pytest.fixture
def fake_redis(monkeypatch):
    """Wire a fresh FakeRedis into every research_agent service singleton."""
    fake = FakeRedis()
    for singleton in (cache_service, rate_limiter, memory_service, sse_service):
        monkeypatch.setattr(singleton, "_redis", lambda fake=fake: fake)
    return fake


# ── CacheService ─────────────────────────────────────────────────────────────


class TestCacheService:
    def test_set_get_roundtrip(self, fake_redis):
        cache_service.set("hash1", {"full_report": "x", "confidence_score": None})
        out = cache_service.get("hash1")
        assert out["full_report"] == "x"

    def test_get_miss_returns_none(self, fake_redis):
        assert cache_service.get("nope") is None

    def test_patch_confidence_backfills(self, fake_redis):
        cache_service.set("hash2", {"full_report": "x", "confidence_score": None})
        cache_service.patch_confidence("hash2", 0.835)
        assert cache_service.get("hash2")["confidence_score"] == pytest.approx(0.835)

    def test_patch_confidence_noop_on_missing_entry(self, fake_redis):
        # Patching a non-existent key must not create one (and must not raise).
        cache_service.patch_confidence("ghost", 0.9)
        assert cache_service.get("ghost") is None

    def test_redis_down_is_safe(self, monkeypatch):
        monkeypatch.setattr(cache_service, "_redis", lambda: None)
        cache_service.set("k", {"a": 1})  # no-op, no raise
        assert cache_service.get("k") is None
        cache_service.patch_confidence("k", 0.5)  # no-op, no raise


# ── RedisRateLimiter ─────────────────────────────────────────────────────────


class TestRateLimiter:
    def test_anonymous_daily_cap(self, fake_redis):
        allowed_flags = [
            rate_limiter.check_query_limit("1.2.3.4", is_authenticated=False)[0]
            for _ in range(PUBLIC_DAILY_LIMIT + 1)
        ]
        # First PUBLIC_DAILY_LIMIT allowed, the next one blocked.
        assert allowed_flags[:PUBLIC_DAILY_LIMIT] == [True] * PUBLIC_DAILY_LIMIT
        assert allowed_flags[PUBLIC_DAILY_LIMIT] is False

    def test_authenticated_higher_cap(self, fake_redis):
        allowed, remaining = rate_limiter.check_query_limit(
            None, is_authenticated=True, user_id="u1"
        )
        assert allowed is True
        assert remaining == AUTH_DAILY_LIMIT - 1

    def test_daily_fail_open_when_redis_down(self, monkeypatch):
        monkeypatch.setattr(rate_limiter, "_redis", lambda: None)
        allowed, remaining = rate_limiter.check_query_limit(
            "1.2.3.4", is_authenticated=False
        )
        assert allowed is True
        assert remaining == PUBLIC_DAILY_LIMIT

    def test_provider_rpm_raises_over_cap(self, fake_redis):
        # Up to the cap is fine; the call that exceeds it fails over via raise.
        for _ in range(GROQ_REQUESTS_PER_MINUTE):
            rate_limiter.check_provider_rpm("groq")
        with pytest.raises(RateLimitExceeded):
            rate_limiter.check_provider_rpm("groq")

    def test_unknown_provider_is_noop(self, fake_redis):
        # No configured cap → returns without raising.
        assert rate_limiter.check_provider_rpm("gemini") is None


# ── MemoryService ────────────────────────────────────────────────────────────


class TestMemoryService:
    def test_record_and_read(self, fake_redis):
        memory_service.record_query("user-1", "polity")
        memory_service.record_query("user-1", "polity")
        memory_service.record_query("user-1", "economy")
        mem = memory_service.get_user_memory("user-1")
        assert mem["domains"]["polity"] == 2
        assert mem["top_domain"] == "polity"
        assert mem["total"] == 3

    def test_user_isolation(self, fake_redis):
        memory_service.record_query("user-1", "polity")
        memory_service.record_query("user-2", "science")
        assert memory_service.get_user_memory("user-2")["domains"] == {"science": 1}

    def test_anonymous_is_noop(self, fake_redis):
        memory_service.record_query(None, "polity")
        assert memory_service.get_user_memory(None) == {
            "domains": {},
            "top_domain": None,
            "total": 0,
        }


# ── SSEService ───────────────────────────────────────────────────────────────


class TestSSEService:
    def test_format_frame(self):
        frame = sse_service._format("node_started", {"agent": "planner"})
        assert frame.startswith("event: node_started\n")
        assert '"agent": "planner"' in frame
        assert frame.endswith("\n\n")

    def test_decode_variants(self):
        assert sse_service._decode(b'{"event": "x"}') == {"event": "x"}
        assert sse_service._decode('{"event": "y"}') == {"event": "y"}
        assert sse_service._decode(None) is None
        assert sse_service._decode("not json") is None

    def test_terminal_stream_emits_final_event(self):
        frames = list(sse_service.terminal_stream("completed"))
        joined = "".join(frames)
        assert "retry:" in joined
        assert "workflow_completed" in joined

    def test_cancel_flag_roundtrip(self, fake_redis):
        assert sse_service.is_cancelled("sid") is False
        sse_service.set_cancelled("sid")
        assert sse_service.is_cancelled("sid") is True

    def test_is_cancelled_false_when_redis_down(self, monkeypatch):
        monkeypatch.setattr(sse_service, "_redis", lambda: None)
        assert sse_service.is_cancelled("sid") is False

    def test_emit_publishes(self, fake_redis):
        sse_service.emit("sid", "node_completed", {"agent": "search"})
        assert len(fake_redis.published) == 1


# ── ResearchOrchestrator helpers ─────────────────────────────────────────────


class TestOrchestratorHelpers:
    def test_extract_sources_filters_and_shapes(self):
        state = {
            "raw_search_results": [
                {
                    "url": "https://a.com",
                    "title": "A",
                    "credibility_score": 0.9,
                    "content": "x",
                },
                {"url": "", "title": "no url"},  # dropped
            ]
        }
        out = ResearchOrchestrator()._extract_sources(state)
        assert out == [{"url": "https://a.com", "title": "A", "credibility_score": 0.9}]

    @pytest.mark.django_db
    def test_save_report_sanitizes_and_persists(self):
        session = ResearchSession.objects.create(query="q", query_hash="c" * 64)
        state = {
            "executive_summary": "Safe summary <script>alert(1)</script>",
            "final_report": "# Report\n<script>bad()</script>ok",
            "raw_search_results": [{"url": "https://a.com", "title": "A"}],
            "report_word_count": 50,
        }
        ResearchOrchestrator()._save_report(session, state)
        session.refresh_from_db()
        report = session.report
        # Dangerous HTML stripped by guardrails before persisting.
        assert "<script>" not in report.full_report
        assert "<script>" not in report.executive_summary
        assert report.word_count == 50


# ── EvaluationRunner (DeepEval-style LLM judge) ──────────────────────────────


_JUDGE_JSON = (
    '{"faithfulness": {"score": 0.8, "reason": "grounded"}, '
    '"relevance": {"score": 0.9, "reason": "on topic"}, '
    '"hallucination": {"score": 0.1, "reason": "none"}, '
    '"completeness": {"score": 0.7, "reason": "covers most"}}'
)


class TestEvaluationRunner:
    def test_parse_clamps_and_shapes(self):
        scores = evaluation_runner._parse(_JUDGE_JSON)
        assert scores["faithfulness"] == pytest.approx(0.8)
        assert scores["hallucination"] == pytest.approx(0.1)
        assert set(scores["detail"].keys()) == {
            "faithfulness",
            "relevance",
            "hallucination",
            "completeness",
        }

    def test_parse_clamps_out_of_range(self):
        scores = evaluation_runner._parse('{"faithfulness": {"score": 5.0}}')
        assert scores["faithfulness"] == 1.0  # clamped to [0,1]

    def test_extract_json_from_noisy_text(self):
        raw = evaluation_runner._extract_json('prelude ```json {"a": 1} ``` tail')
        assert raw == '{"a": 1}'

    def test_neutral_scores(self):
        neutral = evaluation_runner._neutral()
        assert neutral["faithfulness"] == 0.5
        assert neutral["tokens"] == 0

    def test_evaluate_success(self, monkeypatch):
        monkeypatch.setattr(
            "engines.research_agent.llmops.groq_client.llm_client.call",
            lambda **kw: (_JUDGE_JSON, 123),
        )
        scores = evaluation_runner.evaluate(
            "q", "report body", [{"url": "u", "title": "t"}]
        )
        assert scores["relevance"] == pytest.approx(0.9)
        assert scores["tokens"] == 123

    def test_evaluate_failure_returns_neutral(self, monkeypatch):
        def _boom(**kw):
            raise RuntimeError("judge down")

        monkeypatch.setattr(
            "engines.research_agent.llmops.groq_client.llm_client.call", _boom
        )
        scores = evaluation_runner.evaluate("q", "report", [])
        assert scores == evaluation_runner._neutral()
