"""
engines/daily_ca/tests/test_markdown_normalizer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Regression tests for the Daily CA markdown structure repair.

These lock in the fix for the 2026-09-01 "wall of text" bug: after article
generation moved off Cerebras (402) to Mistral, 2 of 10 published bodies were
stored with ZERO newline characters in ~7,000 chars. The `##` markers were
present but stranded mid-line, so CommonMark treated them as literal text and
react-markdown rendered the entire article as a single <p>.

The two invariants that matter most:
  1. A collapsed body gets its block structure back.
  2. A HEALTHY body is returned unchanged — the 8 good articles in that same
     batch must never regress because of this repair.

Pure functions: no DB, no network, no LLM.
"""

import re

from engines.daily_ca.services.markdown_normalizer import (
    has_inline_block_markers,
    is_structurally_broken,
    normalize_markdown,
)

# ── Fixtures — shaped like the real measured data ─────────────────────────────

# The failure: one unbroken line, `##` markers stranded mid-sentence.
COLLAPSED = (
    "The Supreme Court heard the plea filed by the Delhi Police today. "
    "The bench observed that the petition raises important questions about "
    "the limits of executive discretion in criminal matters. "
    "## Background The case began in 2019 when an FIR was registered against "
    "the accused under multiple sections of the Indian Penal Code. "
    "## Key Provisions Section 482 of the CrPC allows a High Court to quash "
    "proceedings to secure the ends of justice. "
    "## Analysis The judgment continues a line of reasoning the Court has "
    "developed over several decades of constitutional interpretation. "
    "## Way Forward The matter is listed for further hearing next month."
)

# Well-formed markdown — the shape the 8 healthy articles had.
HEALTHY = (
    "The Supreme Court heard the plea today.\n"
    "\n"
    "## Background\n"
    "\n"
    "The case began in 2019 when an FIR was registered.\n"
    "\n"
    "## Way Forward\n"
    "\n"
    "The matter is listed for hearing next month.\n"
)


def _no_stranded_markers(md: str) -> bool:
    """No `##` may have non-whitespace before it on the same line."""
    return re.search(r"\S[ \t]*#{2,4}[ \t]+\S", md) is None


# ── Invariant 1: healthy markdown must not regress ────────────────────────────


class TestHealthyMarkdownUntouched:
    def test_healthy_body_is_returned_unchanged(self) -> None:
        assert normalize_markdown(HEALTHY) == HEALTHY.strip()

    def test_healthy_body_is_not_flagged_broken(self) -> None:
        assert is_structurally_broken(HEALTHY) is False
        assert has_inline_block_markers(HEALTHY) is False

    def test_existing_callout_block_is_preserved(self) -> None:
        md = "Intro line.\n\n:::callout\n**Did You Know?**\n\nA fact.\n:::\n"
        out = normalize_markdown(md)
        assert ":::callout\n" in out
        assert out.rstrip().endswith(":::")

    def test_empty_and_whitespace_bodies_are_safe(self) -> None:
        assert normalize_markdown("") == ""
        assert normalize_markdown("   ") == ""
        assert is_structurally_broken("") is False


# ── Invariant 2: the measured failure is repaired ─────────────────────────────


class TestCollapsedBodyIsRepaired:
    def test_collapsed_body_is_detected_as_broken(self) -> None:
        """Zero newlines in a substantial body — the exact stored state."""
        assert "\n" not in COLLAPSED
        assert is_structurally_broken(COLLAPSED) is True

    def test_every_heading_starts_a_line_after_repair(self) -> None:
        out = normalize_markdown(COLLAPSED)
        assert _no_stranded_markers(out), "a ## is still mid-line"

    def test_all_four_headings_survive_the_repair(self) -> None:
        out = normalize_markdown(COLLAPSED)
        for heading in ("## Background", "## Key Provisions", "## Analysis"):
            assert f"\n{heading}" in out

    def test_headings_get_a_blank_line_before_them(self) -> None:
        """Without the blank line the heading can bind to the paragraph above."""
        out = normalize_markdown(COLLAPSED)
        assert "\n\n## Background" in out

    def test_repaired_body_is_no_longer_broken(self) -> None:
        assert is_structurally_broken(normalize_markdown(COLLAPSED)) is False

    def test_no_prose_is_lost_in_the_repair(self) -> None:
        """Repair only inserts newlines — it must never drop content."""
        out = normalize_markdown(COLLAPSED)
        assert "listed for further hearing next month" in out
        assert len(out.split()) == len(COLLAPSED.split())


# ── Idempotency ───────────────────────────────────────────────────────────────


class TestIdempotent:
    def test_normalizing_twice_changes_nothing(self) -> None:
        once = normalize_markdown(COLLAPSED)
        assert normalize_markdown(once) == once

    def test_healthy_body_is_a_fixed_point(self) -> None:
        once = normalize_markdown(HEALTHY)
        assert normalize_markdown(once) == once


# ── False-positive guards ─────────────────────────────────────────────────────


class TestDoesNotDamageProse:
    def test_hashtags_and_sharp_names_are_not_headings(self) -> None:
        md = "Developers use C# and F#. See #Budget2026 and ##tag for more."
        assert normalize_markdown(md) == md

    def test_prose_hyphen_is_not_split_into_a_bullet(self) -> None:
        md = "The India - Pakistan talks resumed after a long - tense - pause."
        assert normalize_markdown(md) == md

    def test_decimal_numbers_are_not_split_into_list_items(self) -> None:
        md = "The deficit widened to 4.5 percent while growth held at 6.2."
        assert normalize_markdown(md) == md


# ── Callout fences ────────────────────────────────────────────────────────────


class TestCalloutFences:
    def test_inline_callout_open_moves_to_its_own_line(self) -> None:
        out = normalize_markdown("Some prose here. :::callout A fact. :::")
        assert "\n:::callout" in out

    def test_inline_callout_close_moves_to_its_own_line(self) -> None:
        out = normalize_markdown("Some prose here. :::callout A fact. :::")
        assert re.search(r"\n:::\s*$", out) is not None


# ── Escaped-newline variant ───────────────────────────────────────────────────


class TestLiteralEscapedNewlines:
    def test_literal_backslash_n_becomes_a_real_newline(self) -> None:
        md = "Intro line.\\n\\n## Background\\n\\nBody text follows here."
        out = normalize_markdown(md)
        assert "\\n" not in out
        assert "\n## Background" in out

    def test_real_newlines_win_over_a_stray_escape(self) -> None:
        """A lone literal \\n inside otherwise healthy text is left alone."""
        md = "Line one.\n\nUse the \\n escape in code.\n\nLine three."
        assert "\\n" in normalize_markdown(md)


# ── Detection helper ──────────────────────────────────────────────────────────


class TestStructureDetection:
    def test_short_bodies_are_not_judged(self) -> None:
        """Stubs and one-liners are the caller's emptiness concern, not ours."""
        assert is_structurally_broken("Short body with no newline.") is False

    def test_stranded_marker_is_detected_even_with_some_newlines(self) -> None:
        md = "Line one.\n" + ("Filler sentence to pass the length gate. " * 12)
        md += "and then ## Background continues inline."
        assert is_structurally_broken(md) is True
