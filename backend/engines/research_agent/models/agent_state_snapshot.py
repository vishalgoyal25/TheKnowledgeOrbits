"""
engines/research_agent/models/agent_state_snapshot.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AgentStateSnapshot — full LangGraph ResearchState JSON saved at every node transition.

This is the LLMOps maturity showcase table.
A developer (or recruiter) can query this table and replay the full state
evolution of the research workflow — node by node.

DB table: ra_state_snapshot

One row is written by each LangGraph node AFTER it modifies state:
  supervisor  → row 0
  planner     → row 1
  search      → row 2
  research    → row 3
  verification→ row 4
  ...and so on

state_json stores the FULL ResearchState dict — JSON-serializable only.
state_size_bytes is tracked to catch state bloat (Risk: unbounded search results).

GIN index on state_json enables fast JSONB queries like:
  SELECT * FROM ra_state_snapshot WHERE state_json->>'domain' = 'history'
"""

from __future__ import annotations

import json
import uuid
import structlog
import sentry_sdk
from django.db import models
from django.contrib.postgres.indexes import GinIndex

from engines.research_agent.constants import AgentName

logger = structlog.get_logger(__name__)


class AgentStateSnapshot(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    session = models.ForeignKey(
        "research_agent.ResearchSession",
        on_delete=models.CASCADE,
        related_name="state_snapshots",
        db_index=True,
    )

    # Which LangGraph node produced this snapshot.
    node_name = models.CharField(
        max_length=64,
        choices=[
            (v, v)
            for v in [
                AgentName.SUPERVISOR,
                AgentName.PLANNER,
                AgentName.SEARCH,
                AgentName.RESEARCH,
                AgentName.VERIFICATION,
                AgentName.SUMMARY_GENERATOR,
                AgentName.REPORT_GENERATOR,
                AgentName.REFLECTION,
            ]
        ],
    )

    # Ordering within session: 0 = after supervisor, 1 = after planner, etc.
    # Incremented by the Orchestrator before saving each snapshot.
    sequence_num = models.SmallIntegerField(default=0)

    # Full ResearchState dict — snapshot of shared baton at this exact moment.
    # PostgreSQL stores this as JSONB — binary format, fast querying.
    state_json = models.JSONField(
        default=dict,
        help_text="Full ResearchState dict at this node transition.",
    )

    # Byte size of state_json when serialized.
    # Alert if > 500KB — means raw_search_results is not being truncated.
    state_size_bytes = models.IntegerField(default=0)

    snapshot_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "research_agent"
        db_table = "ra_state_snapshot"
        ordering = ["session", "sequence_num"]
        indexes = [
            # Primary traversal: get all snapshots for a session in order
            models.Index(
                fields=["session", "sequence_num"],
                name="ra_snapshot_session_seq_idx",
            ),
            # GIN index on JSONB state_json — fast key/value queries (Risk #22).
            # Enables: WHERE state_json->>'domain' = 'economy'
            GinIndex(
                fields=["state_json"],
                name="ra_snapshot_state_json_gin",
            ),
        ]
        constraints = [
            # One snapshot per node per session (no duplicate node entries)
            models.UniqueConstraint(
                fields=["session", "node_name"],
                name="ra_snapshot_session_node_unique",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"StateSnapshot({self.node_name} | seq={self.sequence_num} | "
            f"{self.state_size_bytes}B | session={self.session_id})"
        )

    @classmethod
    def capture(
        cls,
        session_id: str,
        node_name: str,
        sequence_num: int,
        state: dict,
    ) -> "AgentStateSnapshot":
        """
        Factory method — called by each LangGraph node after it finishes.
        Serializes current ResearchState, computes byte size, saves row.

        Usage (in each agent's run() method):
            AgentStateSnapshot.capture(
                session_id=state["session_id"],
                node_name=AgentName.PLANNER,
                sequence_num=1,
                state=dict(state),
            )

        Uses update_or_create keyed on (session, node_name): when a node runs
        AGAIN inside a retry/re-plan loop, we UPDATE its snapshot with the latest
        state instead of trying to INSERT a duplicate (which would violate the
        ra_snapshot_session_node_unique constraint).
        """
        try:
            serialized = json.dumps(state, default=str)
            size_bytes = len(serialized.encode("utf-8"))

            snapshot, _ = cls.objects.update_or_create(
                session_id=session_id,
                node_name=node_name,
                defaults={
                    "sequence_num": sequence_num,
                    "state_json": state,
                    "state_size_bytes": size_bytes,
                },
            )

            if size_bytes > 500_000:
                logger.warning(
                    "research_agent.snapshot.state_bloat",
                    node=node_name,
                    session_id=session_id,
                    size_bytes=size_bytes,
                )

            logger.debug(
                "research_agent.snapshot.captured",
                node=node_name,
                session_id=session_id,
                seq=sequence_num,
                size_bytes=size_bytes,
            )
            return snapshot

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise
