"""
engines/research_agent/tests/test_api.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Integration tests for the research_agent API endpoints.

  - QuerySubmitSerializer — length validation
  - POST /query/          — cache-hit path + DB confidence back-fill (the fix)
  - GET  /history/        — auth gating + per-user ownership scoping
  - GET  /history/<id>/   — owner 200, other-user 404, guest reads anon session
  - POST /cancel/<id>/    — cancel pending, 404 missing, already-finished no-op

Uses the global `api_client` fixture and force_authenticate (matches auth tests).
"""

from __future__ import annotations

import hashlib

import pytest
from django.contrib.auth import get_user_model

from engines.research_agent.constants import SessionStatus
from engines.research_agent.models.research_report import ResearchReport
from engines.research_agent.models.research_session import ResearchSession
from engines.research_agent.serializers.session_serializer import QuerySubmitSerializer

User = get_user_model()

QUERY_URL = "/api/v1/research/query/"
HISTORY_URL = "/api/v1/research/history/"


def _hash(query: str) -> str:
    return hashlib.sha256(query.lower().encode("utf-8")).hexdigest()


def _user(email="ra-api@example.com"):
    return User.objects.create_user(email=email, password="Pass12345")


# ── QuerySubmitSerializer ────────────────────────────────────────────────────


class TestQuerySerializer:
    def test_valid_query(self):
        assert QuerySubmitSerializer(
            data={"query": "What is the Green Revolution?"}
        ).is_valid()

    def test_too_short_invalid(self):
        assert not QuerySubmitSerializer(data={"query": "hi"}).is_valid()

    def test_blank_invalid(self):
        assert not QuerySubmitSerializer(data={"query": ""}).is_valid()

    def test_too_long_invalid(self):
        assert not QuerySubmitSerializer(data={"query": "x" * 1001}).is_valid()


# ── POST /query/ — cache hit + confidence back-fill ──────────────────────────


@pytest.mark.django_db
class TestQueryCacheHit:
    def test_cache_hit_backfills_confidence_from_db(self, api_client, monkeypatch):
        query = "Green Revolution impact on India"
        qhash = _hash(query)

        # A previously completed session whose report has a real confidence score.
        session = ResearchSession.objects.create(
            query=query,
            query_hash=qhash,
            status=SessionStatus.COMPLETED,
        )
        ResearchReport.objects.create(
            session=session,
            executive_summary="s",
            full_report="r",
            sources=[],
            confidence_score=0.83,
        )

        # Cache returns a blob WITHOUT confidence (old/pre-back-fill entry).
        from engines.research_agent.services.cache_service import cache_service

        monkeypatch.setattr(
            cache_service,
            "get",
            lambda h: {
                "executive_summary": "s",
                "full_report": "r",
                "sources": [],
                "word_count": 10,
                "confidence_score": None,
            },
        )
        # Avoid touching Redis during the back-fill write.
        monkeypatch.setattr(cache_service, "patch_confidence", lambda *a, **k: None)

        resp = api_client.post(QUERY_URL, {"query": query}, format="json")
        assert resp.status_code == 200
        assert resp.data["cached"] is True
        # The null score was resolved from the DB (system of record).
        assert resp.data["report"]["confidence_score"] == pytest.approx(0.83)

    def test_short_query_rejected(self, api_client):
        resp = api_client.post(QUERY_URL, {"query": "hi"}, format="json")
        assert resp.status_code == 400


# ── GET /history/ — auth + ownership ─────────────────────────────────────────


@pytest.mark.django_db
class TestHistoryList:
    def test_requires_auth(self, api_client):
        resp = api_client.get(HISTORY_URL)
        assert resp.status_code in (401, 403)

    def test_lists_only_own_sessions(self, api_client):
        u1, u2 = _user("u1@example.com"), _user("u2@example.com")
        s1 = ResearchSession.objects.create(
            user=u1,
            query="mine",
            query_hash=_hash("mine"),
            status=SessionStatus.COMPLETED,
        )
        s2 = ResearchSession.objects.create(
            user=u2,
            query="theirs",
            query_hash=_hash("theirs"),
            status=SessionStatus.COMPLETED,
        )
        for s in (s1, s2):
            ResearchReport.objects.create(
                session=s,
                executive_summary="s",
                full_report="r",
                confidence_score=0.8,
            )

        api_client.force_authenticate(user=u1)
        resp = api_client.get(HISTORY_URL)
        assert resp.status_code == 200
        queries = [row["query"] for row in resp.data["results"]]
        assert queries == ["mine"]


# ── GET /history/<id>/ — object ownership ────────────────────────────────────


@pytest.mark.django_db
class TestHistoryDetail:
    def test_owner_gets_detail_with_report(self, api_client):
        user = _user()
        session = ResearchSession.objects.create(
            user=user,
            query="q",
            query_hash=_hash("q"),
            status=SessionStatus.COMPLETED,
        )
        ResearchReport.objects.create(
            session=session,
            executive_summary="s",
            full_report="r",
            confidence_score=0.9,
        )
        api_client.force_authenticate(user=user)
        resp = api_client.get(f"{HISTORY_URL}{session.id}/")
        assert resp.status_code == 200
        assert resp.data["report"]["confidence_score"] == pytest.approx(0.9)

    def test_other_user_cannot_read(self, api_client):
        owner, intruder = _user("owner@example.com"), _user("intruder@example.com")
        session = ResearchSession.objects.create(
            user=owner, query="q", query_hash=_hash("q")
        )
        api_client.force_authenticate(user=intruder)
        resp = api_client.get(f"{HISTORY_URL}{session.id}/")
        assert resp.status_code == 404

    def test_guest_reads_anonymous_session(self, api_client):
        session = ResearchSession.objects.create(query="q", query_hash=_hash("q"))
        resp = api_client.get(f"{HISTORY_URL}{session.id}/")
        assert resp.status_code == 200


# ── POST /cancel/<id>/ ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCancel:
    def _url(self, sid):
        return f"/api/v1/research/cancel/{sid}/"

    def test_cancel_pending_session(self, api_client, monkeypatch):
        # Avoid Redis/SSE side effects during the cancel write.
        from engines.research_agent.services.sse_service import sse_service

        monkeypatch.setattr(sse_service, "set_cancelled", lambda *a, **k: None)
        monkeypatch.setattr(sse_service, "emit", lambda *a, **k: None)

        session = ResearchSession.objects.create(
            query="q",
            query_hash=_hash("q"),
            status=SessionStatus.PENDING,
        )
        resp = api_client.post(self._url(session.id))
        assert resp.status_code == 200
        assert resp.data["status"] == SessionStatus.CANCELLED
        session.refresh_from_db()
        assert session.cancelled is True

    def test_cancel_missing_session_404(self, api_client):
        resp = api_client.post(self._url("00000000-0000-0000-0000-000000000000"))
        assert resp.status_code == 404

    def test_cancel_already_finished_is_noop(self, api_client):
        session = ResearchSession.objects.create(
            query="q",
            query_hash=_hash("q"),
            status=SessionStatus.COMPLETED,
        )
        resp = api_client.post(self._url(session.id))
        assert resp.status_code == 200
        assert "already finished" in resp.data["detail"].lower()
