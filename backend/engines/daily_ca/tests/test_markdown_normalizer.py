"""
engines/daily_ca/tests/test_markdown_normalizer.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Regression tests for Daily CA markdown structure DETECTION.

Background (2026-09-01): after generation moved off Cerebras (402) to Mistral,
2 of 10 published bodies arrived with ZERO newlines in ~7,000 chars — the `##`
markers were present but stranded mid-line, so the article rendered as one <p>.

A first attempt re-inserted breaks before each `##`. That made it WORSE: an ATX
heading runs to the end of its line, and with no newline after the heading TITLE
either, the heading swallowed the whole paragraph and rendered it as a giant
<h2>. The tests below lock in the corrected contract:

    detect and reject — never rewrite structure.

The most important test in this file is
`test_normalize_never_produces_an_overlong_heading`: it is the regression lock
on that shipped bug.

Pure functions: no DB, no network, no LLM.
"""

from engines.daily_ca.services.markdown_normalizer import (
    collapse_to_single_line,
    has_overlong_heading,
    is_structurally_broken,
    normalize_markdown,
)

# ── Fixtures — shaped like the real measured rows ─────────────────────────────

# What Mistral actually stored: one unbroken line, `##` stranded mid-sentence.
COLLAPSED = (
    "On August 31, 2026, a three-judge Bench declined to halt a proposed "
    "protest march ahead of the summit. Within hours the police moved an "
    "urgent application urging the court to quash the FIRs registered against "
    "students who participated in the protests. "
    "## What Happened on August 31 The Supreme Court found no compelling "
    "circumstance to interfere with the planned march. The Bench held that "
    "everybody should follow the law and respect each others rights. "
    "## Why It Matters The dispute over the scope of police discretion has "
    "now entered the highest constitutional forum at a delicate moment."
)

# The shape the withdrawn repair produced: heading at line start, but the whole
# paragraph trapped on the heading's line.
DAMAGED_BY_OLD_REPAIR = (
    "On August 31, 2026, a three-judge Bench declined to halt the march.\n"
    "\n"
    "## What Happened on August 31 The Supreme Court found no compelling "
    "circumstance to interfere with the planned march. The Bench held that "
    "everybody should follow the law and respect each others rights.\n"
)

# Well-formed markdown — the shape the 8 healthy articles had.
HEALTHY = (
    "On August 31, 2026, a three-judge Bench declined to halt the march.\n"
    "\n"
    "## What Happened on August 31\n"
    "\n"
    "The Supreme Court found no compelling circumstance to interfere with the "
    "planned march, and the Bench held that everybody should follow the law.\n"
    "\n"
    "- Article 142 allows the Court to do complete justice\n"
    "- The plea was listed for hearing on September 1\n"
    "\n"
    "## Why It Matters\n"
    "\n"
    "The dispute has entered the highest constitutional forum.\n"
)


# ── Healthy markdown must never be touched or flagged ─────────────────────────


class TestHealthyMarkdown:
    def test_healthy_body_is_returned_unchanged(self) -> None:
        assert normalize_markdown(HEALTHY) == HEALTHY.strip()

    def test_healthy_body_is_not_flagged(self) -> None:
        assert is_structurally_broken(HEALTHY) is False
        assert has_overlong_heading(HEALTHY) is False

    def test_long_paragraphs_are_not_mistaken_for_headings(self) -> None:
        """Only lines STARTING with ## are heading candidates."""
        md = "## Short Title\n\n" + ("A long analytical paragraph line. " * 12)
        assert has_overlong_heading(md) is False

    def test_empty_and_whitespace_bodies_are_safe(self) -> None:
        assert normalize_markdown("") == ""
        assert normalize_markdown("   ") == ""
        assert is_structurally_broken("") is False


# ── The measured failure is detected, NOT rewritten ───────────────────────────


class TestCollapsedBodyIsRejectedNotRepaired:
    def test_collapsed_body_is_detected(self) -> None:
        assert "\n" not in COLLAPSED
        assert is_structurally_broken(COLLAPSED) is True

    def test_normalize_does_not_invent_structure(self) -> None:
        """The core contract: no guessing. A collapsed body stays collapsed."""
        assert normalize_markdown(COLLAPSED) == COLLAPSED.strip()

    def test_collapsed_body_stays_broken_after_normalize(self) -> None:
        """So the caller's gate still fires and the cycle is regenerated."""
        assert is_structurally_broken(normalize_markdown(COLLAPSED)) is True


# ── Regression lock on the bug that shipped ───────────────────────────────────


class TestOverlongHeadingRegression:
    def test_damaged_shape_is_recognised_as_broken(self) -> None:
        """A heading that swallowed its paragraph must never look healthy."""
        assert has_overlong_heading(DAMAGED_BY_OLD_REPAIR) is True
        assert is_structurally_broken(DAMAGED_BY_OLD_REPAIR) is True

    def test_normalize_never_produces_an_overlong_heading(self) -> None:
        """THE lock: normalizing a collapsed body must not create giant <h2>s."""
        for sample in (COLLAPSED, DAMAGED_BY_OLD_REPAIR, HEALTHY):
            assert has_overlong_heading(normalize_markdown(sample)) == (
                has_overlong_heading(sample)
            ), "normalize changed heading-swallowing state"


# ── Lossless repairs that ARE safe ────────────────────────────────────────────


class TestLosslessRepairs:
    def test_literal_backslash_n_becomes_a_real_newline(self) -> None:
        """Safe and exact: the model emitted the structure, merely escaped."""
        md = "Intro line.\\n\\n## Background\\n\\nBody text follows here."
        out = normalize_markdown(md)
        assert "\\n" not in out
        assert "\n## Background\n" in out

    def test_real_newlines_win_over_a_stray_escape(self) -> None:
        md = "Line one.\n\nUse the \\n escape in code.\n\nLine three."
        assert "\\n" in normalize_markdown(md)

    def test_crlf_is_normalised(self) -> None:
        assert "\r" not in normalize_markdown("Line one.\r\n\r\nLine two.")

    def test_excess_blank_lines_are_collapsed(self) -> None:
        assert normalize_markdown("A.\n\n\n\n\nB.") == "A.\n\nB."


# ── Idempotency ───────────────────────────────────────────────────────────────


class TestIdempotent:
    def test_all_samples_are_fixed_points(self) -> None:
        for sample in (HEALTHY, COLLAPSED, DAMAGED_BY_OLD_REPAIR):
            once = normalize_markdown(sample)
            assert normalize_markdown(once) == once


# ── Recovery helper ───────────────────────────────────────────────────────────


class TestCollapseToSingleLine:
    def test_reverts_inserted_breaks_exactly(self) -> None:
        """Bodies damaged by the old repair had 0 newlines beforehand, so
        removing every newline restores the original text."""
        assert "\n" not in collapse_to_single_line(DAMAGED_BY_OLD_REPAIR)

    def test_no_words_are_lost_or_added(self) -> None:
        out = collapse_to_single_line(DAMAGED_BY_OLD_REPAIR)
        assert len(out.split()) == len(DAMAGED_BY_OLD_REPAIR.split())

    def test_does_not_glue_words_together(self) -> None:
        assert collapse_to_single_line("alpha\nbeta") == "alpha beta"
