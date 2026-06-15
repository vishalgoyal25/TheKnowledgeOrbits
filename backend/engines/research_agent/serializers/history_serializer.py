"""
engines/research_agent/serializers/history_serializer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Compact serializer for the history list (one row per past session).
Reads confidence_score from the related report WITHOUT extra queries
(the view uses select_related('report') — Risk #23, no N+1).
"""

from __future__ import annotations

from rest_framework import serializers

from engines.research_agent.models.research_session import ResearchSession

_QUERY_PREVIEW_CHARS = 80


class HistoryListSerializer(serializers.ModelSerializer):
    """Compact row: truncated query + derived confidence."""

    query = serializers.SerializerMethodField()
    confidence_score = serializers.SerializerMethodField()

    class Meta:
        model = ResearchSession
        fields = [
            "id",
            "query",
            "status",
            "confidence_score",
            "created_at",
            "completed_at",
        ]
        read_only_fields = fields

    def get_query(self, obj) -> str:
        q = obj.query or ""
        return q[:_QUERY_PREVIEW_CHARS] + ("…" if len(q) > _QUERY_PREVIEW_CHARS else "")

    def get_confidence_score(self, obj):
        report = getattr(obj, "report", None)
        return report.confidence_score if report is not None else None
