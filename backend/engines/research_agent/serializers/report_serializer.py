"""
engines/research_agent/serializers/report_serializer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Serializer for ResearchReport — the final output payload.
"""

from __future__ import annotations

from rest_framework import serializers

from engines.research_agent.models.research_report import ResearchReport


class ResearchReportSerializer(serializers.ModelSerializer):
    """Output: the completed report for a session."""

    session_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = ResearchReport
        fields = [
            "session_id",
            "executive_summary",
            "full_report",
            "sources",
            "confidence_score",
            "word_count",
            "created_at",
        ]
        read_only_fields = fields
