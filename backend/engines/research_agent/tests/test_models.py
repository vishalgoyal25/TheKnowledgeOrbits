"""
engines/research_agent/tests/test_models.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tests for all 5 research_agent models (ra_* tables):

  - ResearchSession      (ra_session)         — lifecycle state machine
  - ResearchReport       (ra_report)          — final output + confidence back-fill
  - AgentExecutionLog    (ra_agent_log)       — per-agent telemetry, complete()/fail()
  - AgentStateSnapshot   (ra_state_snapshot)  — capture() upsert (one row per node)
  - EvaluationResult     (ra_evaluation)      — weighted composite score math

Pure-DB tests — no external services. The global conftest mocks ML/LLM libs and
provides the `db` fixture via pytest-django.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from engines.research_agent.constants import AgentName, SessionStatus
from engines.research_agent.models.agent_execution_log import AgentExecutionLog
from engines.research_agent.models.agent_state_snapshot import AgentStateSnapshot
from engines.research_agent.models.evaluation_result import EvaluationResult
from engines.research_agent.models.research_report import ResearchReport
from engines.research_agent.models.research_session import ResearchSession

User = get_user_model()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_session(**overrides) -> ResearchSession:
    """Create a minimal anonymous ResearchSession for tests."""
    defaults = dict(
        query="What is the Panchayati Raj system?",
        query_hash="a" * 64,
    )
    defaults.update(overrides)
    return ResearchSession.objects.create(**defaults)


def _make_report(session: ResearchSession, **overrides) -> ResearchReport:
    defaults = dict(
        executive_summary="A short executive summary.",
        full_report="# Full Report\n\nBody text.",
        sources=[
            {"url": "https://example.com", "title": "Example", "credibility_score": 0.9}
        ],
        word_count=120,
    )
    defaults.update(overrides)
    return ResearchReport.objects.create(session=session, **defaults)


# ── ResearchSession ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestResearchSession:
    def test_create_defaults(self):
        session = _make_session()
        assert session.id is not None  # UUID pk auto-generated
        assert session.status == SessionStatus.PENDING
        assert session.cancelled is False
        assert session.total_tokens_used == 0
        assert session.user_id is None  # anonymous allowed
        assert session.created_at is not None

    def test_str_anonymous(self):
        session = _make_session()
        assert "anonymous" in str(session)
        assert session.status in str(session)

    def test_str_with_user(self):
        user = User.objects.create_user(email="ra@example.com", password="Pass1234")
        session = _make_session(user=user)
        assert "anonymous" not in str(session)
        assert str(user.id) in str(session)

    def test_mark_running(self):
        session = _make_session()
        session.mark_running()
        session.refresh_from_db()
        assert session.status == SessionStatus.RUNNING

    def test_mark_completed_sets_tokens_and_timestamp(self):
        session = _make_session()
        session.mark_completed(total_tokens=4321)
        session.refresh_from_db()
        assert session.status == SessionStatus.COMPLETED
        assert session.total_tokens_used == 4321
        assert session.completed_at is not None

    def test_mark_failed_stores_error(self):
        session = _make_session()
        session.mark_failed("boom — provider exhausted")
        session.refresh_from_db()
        assert session.status == SessionStatus.FAILED
        assert "boom" in session.error_message

    def test_mark_cancelled_sets_flag(self):
        session = _make_session()
        session.mark_cancelled()
        session.refresh_from_db()
        assert session.status == SessionStatus.CANCELLED
        assert session.cancelled is True


# ── ResearchReport ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestResearchReport:
    def test_create_defaults(self):
        session = _make_session()
        report = ResearchReport.objects.create(
            session=session,
            executive_summary="summary",
            full_report="report",
        )
        # confidence is None until DeepEval runs; sources default to [].
        assert report.confidence_score is None
        assert report.sources == []
        assert report.word_count == 0

    def test_one_to_one_reverse_accessor(self):
        session = _make_session()
        report = _make_report(session)
        assert session.report == report

    def test_update_confidence(self):
        session = _make_session()
        report = _make_report(session)
        report.update_confidence(0.835)
        report.refresh_from_db()
        assert report.confidence_score == pytest.approx(0.835)

    def test_str_includes_confidence(self):
        session = _make_session()
        report = _make_report(session, word_count=200)
        assert "words=200" in str(report)


# ── AgentExecutionLog ────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAgentExecutionLog:
    def _make_log(self, session, **overrides) -> AgentExecutionLog:
        defaults = dict(
            session=session,
            agent_name=AgentName.PLANNER,
            started_at=timezone.now(),
            model_provider="groq",
            model_name="openai/gpt-oss-120b",
        )
        defaults.update(overrides)
        return AgentExecutionLog.objects.create(**defaults)

    def test_create_defaults(self):
        session = _make_session()
        log = self._make_log(session)
        assert log.status == AgentExecutionLog.STATUS_STARTED
        assert log.tokens_used == 0
        assert log.retry_count == 0
        assert log.duration_ms is None

    def test_complete_sets_fields(self):
        session = _make_session()
        log = self._make_log(session)
        log.complete(duration_ms=2500, tokens=299, output_summary="ok")
        log.refresh_from_db()
        assert log.status == AgentExecutionLog.STATUS_COMPLETED
        assert log.duration_ms == 2500
        assert log.tokens_used == 299
        assert log.completed_at is not None
        assert log.output_summary == "ok"

    def test_complete_truncates_output_to_400(self):
        session = _make_session()
        log = self._make_log(session)
        log.complete(duration_ms=1, tokens=0, output_summary="x" * 1000)
        log.refresh_from_db()
        assert len(log.output_summary) == 400

    def test_fail_truncates_error_to_1000(self):
        session = _make_session()
        log = self._make_log(session)
        log.fail("e" * 5000)
        log.refresh_from_db()
        assert log.status == AgentExecutionLog.STATUS_FAILED
        assert len(log.error) == 1000

    def test_unique_per_session_agent(self):
        session = _make_session()
        self._make_log(session, agent_name=AgentName.SEARCH)
        with pytest.raises(IntegrityError):
            self._make_log(session, agent_name=AgentName.SEARCH)


# ── AgentStateSnapshot ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAgentStateSnapshot:
    def _state(self, session) -> dict:
        return {"session_id": str(session.id), "domain": "polity", "query": "x"}

    def test_capture_creates_row_with_size(self):
        session = _make_session()
        snap = AgentStateSnapshot.capture(
            session_id=session.id,
            node_name=AgentName.SUPERVISOR,
            sequence_num=0,
            state=self._state(session),
        )
        assert snap.sequence_num == 0
        assert snap.node_name == AgentName.SUPERVISOR
        assert snap.state_size_bytes > 0
        assert snap.state_json["domain"] == "polity"

    def test_capture_upserts_same_node(self):
        """Re-running a node UPDATES its single row (no duplicate, seq advances)."""
        session = _make_session()
        AgentStateSnapshot.capture(
            session_id=session.id,
            node_name=AgentName.PLANNER,
            sequence_num=1,
            state=self._state(session),
        )
        AgentStateSnapshot.capture(
            session_id=session.id,
            node_name=AgentName.PLANNER,
            sequence_num=9,
            state=self._state(session),
        )
        rows = AgentStateSnapshot.objects.filter(
            session=session, node_name=AgentName.PLANNER
        )
        assert rows.count() == 1
        assert rows.first().sequence_num == 9

    def test_capture_distinct_nodes_create_distinct_rows(self):
        session = _make_session()
        AgentStateSnapshot.capture(
            session_id=session.id,
            node_name=AgentName.SUPERVISOR,
            sequence_num=0,
            state=self._state(session),
        )
        AgentStateSnapshot.capture(
            session_id=session.id,
            node_name=AgentName.PLANNER,
            sequence_num=1,
            state=self._state(session),
        )
        assert AgentStateSnapshot.objects.filter(session=session).count() == 2


# ── EvaluationResult ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEvaluationResult:
    def test_composite_weighted_math(self):
        """faith*0.35 + rel*0.30 + (1-hall)*0.20 + comp*0.15."""
        session = _make_session()
        _make_report(session)
        ev = EvaluationResult.objects.create(
            session=session,
            faithfulness_score=0.8,
            relevance_score=0.9,
            hallucination_score=0.1,
            completeness_score=0.7,
        )
        composite = ev.compute_and_save_composite()
        # 0.28 + 0.27 + 0.18 + 0.105 = 0.835
        assert composite == pytest.approx(0.835)

    def test_composite_written_to_report(self):
        session = _make_session()
        report = _make_report(session)
        ev = EvaluationResult.objects.create(
            session=session,
            faithfulness_score=1.0,
            relevance_score=1.0,
            hallucination_score=0.0,
            completeness_score=1.0,
        )
        ev.compute_and_save_composite()
        report.refresh_from_db()
        assert report.confidence_score == pytest.approx(1.0)

    def test_composite_none_safe(self):
        """All-None metrics must not raise — None treated as 0.0."""
        session = _make_session()
        _make_report(session)
        ev = EvaluationResult.objects.create(session=session)
        composite = ev.compute_and_save_composite()
        # faith/rel/comp = 0; hallucination 0 → (1-0)*0.20 = 0.20
        assert composite == pytest.approx(0.20)

    def test_composite_clamped_and_persisted(self):
        session = _make_session()
        _make_report(session)
        ev = EvaluationResult.objects.create(
            session=session,
            faithfulness_score=0.5,
            relevance_score=0.5,
            hallucination_score=0.5,
            completeness_score=0.5,
        )
        composite = ev.compute_and_save_composite()
        assert 0.0 <= composite <= 1.0
        ev.refresh_from_db()
        assert ev.composite_score == pytest.approx(composite)
