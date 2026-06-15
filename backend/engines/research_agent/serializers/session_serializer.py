"""
engines/research_agent/serializers/session_serializer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Serializers for ResearchSession — query input + session output.
"""

from __future__ import annotations

from rest_framework import serializers

from engines.research_agent.models.research_session import ResearchSession

# Must match the validation bounds in agents/supervisor_agent.py.
MIN_QUERY_LENGTH = 5
MAX_QUERY_LENGTH = 1000


class QuerySubmitSerializer(serializers.Serializer):
    """Validates the inbound research query (POST /query)."""

    query = serializers.CharField(
        min_length=MIN_QUERY_LENGTH,
        max_length=MAX_QUERY_LENGTH,
        trim_whitespace=True,
        error_messages={
            "min_length": "Query is too short to research.",
            "max_length": "Query is too long.",
            "blank": "Query cannot be empty.",
        },
    )


class ResearchSessionSerializer(serializers.ModelSerializer):
    """Output: full session detail."""

    class Meta:
        model = ResearchSession
        fields = [
            "id",
            "query",
            "status",
            "langfuse_trace_id",
            "total_tokens_used",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = fields
