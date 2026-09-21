"""
engines/daily_ca/tests/test_static_content_exit.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L16 (FEATURES_LLM_FIX.md Part III) — generate_static_content stops the moment
every LLM key is parked for the day.

On 2026-09-21 the run walked its whole topic queue against five empty Groq
daily buckets: every item paid the full retry ladder and the cron ran 4 h+.
The command now reads `pool_exhausted()` before each topic and ends the run
with a summary, a warning log and a Sentry message; the untouched topics stay
in the queue for the next run. No LLM, no network — the pool probe and the
ingestor are patched.
"""

from io import StringIO
from unittest.mock import patch

import pytest

from engines.knowledge.models import Module, Program, Subject, Topic

_CMD = "engines.daily_ca.management.commands.generate_static_content."


def _two_queued_topics() -> None:
    program = Program.objects.create(name="P", description="p")
    subject = Subject.objects.create(name="Polity", program=program, order_index=0)
    module = Module.objects.create(name="Constitution", subject=subject, order_index=0)
    Topic.objects.create(name="Preamble", module=module, subject=subject, order_index=0)
    Topic.objects.create(
        name="Fundamental Rights", module=module, subject=subject, order_index=1
    )


def _run(exhausted_sequence):
    from django.core.management import call_command

    out = StringIO()
    with (
        patch(_CMD + "check_any_llm_available", return_value=True),
        patch(_CMD + "pool_exhausted", side_effect=exhausted_sequence),
        patch(_CMD + "ingest_topic", return_value={"nodes_created": 1}) as ingest,
        patch(_CMD + "sentry_sdk.capture_message") as sentry,
    ):
        call_command(
            "generate_static_content",
            max_articles=3,
            database="default",
            stdout=out,
        )
    return out.getvalue(), ingest, sentry


@pytest.mark.django_db
class TestStaticContentStopsWhenPoolExhausted:
    def test_stops_after_the_current_topic_and_defers_the_rest(self) -> None:
        _two_queued_topics()
        text, ingest, sentry = _run([False, True])

        assert ingest.call_count == 1, "the second topic was never attempted"
        assert "stopped early: LLM daily budget exhausted" in text
        assert "1 topic(s) generated; 1 deferred" in text
        assert sentry.call_count == 1

    def test_exhausted_before_the_first_topic_generates_nothing(self) -> None:
        _two_queued_topics()
        text, ingest, sentry = _run([True])

        assert ingest.call_count == 0
        assert "0 topic(s) generated; 2 deferred" in text
        assert sentry.call_count == 1

    def test_a_healthy_pool_walks_the_queue_as_before(self) -> None:
        _two_queued_topics()
        text, ingest, sentry = _run([False, False, False])

        assert ingest.call_count == 2
        assert "stopped early" not in text
        assert sentry.call_count == 0
