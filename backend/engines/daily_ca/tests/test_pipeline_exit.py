"""
engines/daily_ca/tests/test_pipeline_exit.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
L12 (FEATURES_LLM_FIX.md Part II) — a zero-article day is a FAILED run.

Between 2026-09-18 and 09-20 the daily pipeline built nothing for three days
while Render showed a green tick: every cycle failure is caught by design and
the process exited 0. These tests pin the new contract — the command raises
CommandError (exit status 1) after every step has run, and only on zero.

Every step is patched out: no LLM, no database.
"""

from unittest.mock import patch

import pytest
from django.core.management.base import CommandError

from engines.daily_ca.management.commands import run_daily_pipeline as mod

_STEPS = "engines.daily_ca.management.commands.run_daily_pipeline"


def _run(published):
    cmd = mod.Command()
    with (
        patch(f"{_STEPS}.call_command") as steps,
        patch.object(mod.Command, "_auto_approve_top_n", return_value=10),
        patch.object(mod.Command, "_prune_old_ca") as prune,
        patch.object(mod.Command, "_verify_output", return_value=published) as guard,
    ):
        cmd.handle(database="default", date="today", top=10, dry_run=False)
        return steps, prune, guard


class TestZeroArticlesExitStatus:
    def test_zero_published_raises_after_every_step_ran(self):
        cmd = mod.Command()
        with (
            patch(f"{_STEPS}.call_command") as steps,
            patch.object(mod.Command, "_auto_approve_top_n", return_value=10),
            patch.object(mod.Command, "_prune_old_ca") as prune,
            patch.object(mod.Command, "_verify_output", return_value=0) as guard,
        ):
            with pytest.raises(CommandError, match="0 published articles"):
                cmd.handle(database="default", date="today", top=10, dry_run=False)

        # Steps 1, 3/4, 5, 6, 7 → five call_command invocations, then the prune
        # and the guard — nothing is skipped by raising last.
        assert steps.call_count == 5
        prune.assert_called_once()
        guard.assert_called_once()

    def test_a_normal_day_exits_clean(self):
        steps, prune, guard = _run(published=10)
        assert steps.call_count == 5
        prune.assert_called_once()
        guard.assert_called_once()

    def test_a_degraded_day_is_a_warning_not_a_failure(self):
        """1–4 articles is Sentry's warning path (L6); the tick stays green."""
        _run(published=3)

    def test_guard_query_failure_does_not_fail_the_run(self):
        """None = the guard's own query failed — already a Sentry error; no double count."""
        _run(published=None)
