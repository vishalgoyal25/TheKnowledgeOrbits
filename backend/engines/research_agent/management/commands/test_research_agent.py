"""
engines/research_agent/management/commands/test_research_agent.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Management command: run the FULL research pipeline end-to-end from the terminal,
with NO API / SSE / Celery layer in the way.

This is the first time the whole 8-agent graph runs against a real query. It
creates a ResearchSession (so the agents' DB writes have a valid FK), builds the
initial state, invokes the compiled LangGraph, and prints every stage's output.

Usage:
  python manage.py test_research_agent --query "What is Article 370?"
  python manage.py test_research_agent --query "..." --dry-run   # compile only
  python manage.py test_research_agent --query "..." --full      # print full report

--dry-run  : build/compile the graph and print the initial state, but DON'T
             invoke it (no LLM calls, no DB session). Verifies wiring cheaply.
"""

from __future__ import annotations

import hashlib
import json

import structlog
from django.core.management.base import BaseCommand

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Run the Research Agent pipeline end-to-end via the terminal."

    def add_arguments(self, parser):
        parser.add_argument(
            "--query",
            type=str,
            default="What is the Preamble of the Indian Constitution?",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compile the graph and print initial state only — no LLM/DB.",
        )
        parser.add_argument(
            "--full",
            action="store_true",
            help="Print the full report instead of a truncated preview.",
        )

    # ──────────────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        # Lazy imports — keep `manage.py` startup from building the graph/agents
        # unless this command actually runs.
        from engines.research_agent.graph.graph import get_compiled_graph
        from engines.research_agent.graph.state import make_initial_state

        query = options["query"].strip()
        dry_run = options["dry_run"]
        full = options["full"]

        self._header(f"Research Agent — end-to-end test\nQuery: {query!r}")

        # ── Compile the graph (validates all wiring) ──────────────────────────
        try:
            graph = get_compiled_graph()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Graph compile failed: {exc}"))
            raise

        self.stdout.write(self.style.SUCCESS("✓ Graph compiled (all 8 nodes wired)."))

        if dry_run:
            initial = make_initial_state(session_id="dry-run", query=query)
            self._section("Initial state (dry-run, not invoked)")
            self.stdout.write(json.dumps(initial, indent=2, default=str))
            self.stdout.write(
                self.style.WARNING("\nDry run complete — graph NOT invoked.")
            )
            return

        # ── Create a real session so agent DB writes have a valid FK ──────────
        from engines.research_agent.models.research_session import ResearchSession

        query_hash = hashlib.sha256(query.lower().encode("utf-8")).hexdigest()
        session = ResearchSession.objects.create(
            user=None,
            query=query,
            query_hash=query_hash,
        )
        session.mark_running()
        session_id = str(session.id)
        self.stdout.write(self.style.SUCCESS(f"✓ Session created: {session_id}"))

        # ── Invoke the full pipeline ──────────────────────────────────────────
        initial_state = make_initial_state(session_id=session_id, query=query)
        config = {"configurable": {"thread_id": session_id}}

        self._section("Running pipeline (this calls real LLMs — ~30-90s)...")
        try:
            final_state = graph.invoke(initial_state, config=config)
        except Exception as exc:
            session.mark_failed(str(exc))
            self.stderr.write(self.style.ERROR(f"Pipeline failed: {exc}"))
            raise

        total_tokens = final_state.get("total_tokens_used", 0)
        session.mark_completed(total_tokens=total_tokens)

        # ── Print every stage ─────────────────────────────────────────────────
        self._print_results(final_state, full=full)
        self.stdout.write(
            self.style.SUCCESS(f"\n✓ Done. Session {session_id} marked completed.")
        )

    # ──────────────────────────────────────────────────────────────────────────
    # OUTPUT HELPERS
    # ──────────────────────────────────────────────────────────────────────────
    def _print_results(self, state: dict, full: bool) -> None:
        self._section("1. PLANNER")
        self.stdout.write(f"Domain:       {state.get('domain')}")
        self.stdout.write(f"Sub-queries:  {state.get('sub_queries')}")
        self.stdout.write(
            f"Plan:         {self._truncate(state.get('research_plan'), 300)}"
        )

        self._section("2. SEARCH")
        sources = state.get("raw_search_results") or []
        self.stdout.write(f"Sources kept: {len(sources)}")
        for i, src in enumerate(sources[:5], start=1):
            self.stdout.write(
                f"  [{i}] ({src.get('credibility_score')}) "
                f"{src.get('title', '')[:60]} — {src.get('source')}"
            )

        self._section("3. RESEARCH")
        self.stdout.write(self._truncate(state.get("synthesized_content"), 500))
        self.stdout.write(f"\nKey findings: {len(state.get('key_findings') or [])}")
        for f in (state.get("key_findings") or [])[:6]:
            self.stdout.write(f"  • {f}")

        self._section("4. VERIFICATION")
        self.stdout.write(f"Passed: {state.get('verification_passed')}")
        self.stdout.write(f"Notes:  {state.get('verification_notes')}")
        self.stdout.write(f"Retry count (shared budget): {state.get('retry_count')}")

        self._section("5. EXECUTIVE SUMMARY")
        self.stdout.write(self._truncate(state.get("executive_summary"), 600))

        self._section("6. FULL REPORT")
        report = state.get("final_report") or ""
        self.stdout.write(f"Word count: {state.get('report_word_count')}")
        self.stdout.write(report if full else self._truncate(report, 800))

        self._section("7. REFLECTION")
        self.stdout.write(f"Score: {state.get('reflection_score')}")
        self.stdout.write(f"Notes: {state.get('reflection_notes')}")

        self._section("TELEMETRY")
        self.stdout.write(f"Agent timings (ms): {state.get('agent_timings')}")
        self.stdout.write(f"Tokens per agent:   {state.get('tokens_per_agent')}")
        self.stdout.write(f"Total tokens:       {state.get('total_tokens_used')}")
        errors = state.get("errors") or []
        if errors:
            self.stdout.write(self.style.WARNING(f"Non-fatal errors: {errors}"))

    def _header(self, text: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("\n" + "=" * 70))
        self.stdout.write(self.style.MIGRATE_HEADING(text))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 70))

    def _section(self, title: str) -> None:
        self.stdout.write(
            self.style.HTTP_INFO(f"\n── {title} " + "─" * (60 - len(title)))
        )

    @staticmethod
    def _truncate(text, limit: int) -> str:
        if not text:
            return "(empty)"
        text = str(text)
        return text if len(text) <= limit else text[:limit] + " …[truncated]"
