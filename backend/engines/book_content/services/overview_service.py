"""
engines/book_content/services/overview_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
G3.9 (FEATURES_GROWTH_STACK.md §7.9a) — introductory overview content for
SUBJECT and MODULE nodes, the two hierarchy levels that have no `Topic` row and
therefore can never have a `BookContent`. With them the reader's path is
complete: subject › module › topic › subtopic › sub-subtopic.

Pace (decided 2026-09-16): ONE SUBJECT PER RUN, together with every module
under it — 14 subjects, 14 days. The pieces are short and introductory
(subject ~400–600 words, module ~250–400), not topic-length articles.

Everything here is orchestration over four facts:

  queue     the first subject in `order_index` that has no overview row yet,
            plus each of its modules without one. A module qualifies only when
            ≥ 1 generated topic article exists beneath it (children gate — an
            overview of an empty branch is thin content by construction); a
            module skipped today is picked up on a later run once an article
            exists, because the queue is recomputed from the tables every time
  grounding names + opening lines of the generated topic articles under the
            node, scoped by FK — never a search. What makes the overview a map
            of what is on the site rather than a generic essay
  gate      ≥ 200 words, ≥ 2 `##` headings, ≤ 900 words, real line breaks; one
            corrective retry; a failing draft writes NOTHING
  write     one `OverviewContent` row per node, `is_published=False` unless
            auto-publish is on

The hierarchy is READ-ONLY here: it reads Subject → Module → Topic →
BookContent and writes only `OverviewContent`. No Subject/Module/Topic row is
ever created, moved, renamed or re-statused. The article cron
(`generate_book_content`) never sees this table. Shared with it: only the LLM
pool and its INTER_CALL_SLEEP.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sentry_sdk
import structlog
from django.db.models import Q

from engines.book_content.models import BookContent, OverviewContent
from engines.book_content.services.llm_service import llm_call
from engines.knowledge.models import Module, Subject

logger = structlog.get_logger(__name__)

MIN_WORDS = 200
MIN_HEADINGS = 2
MAX_WORDS = 900
GROUNDING_ARTICLES = 12
OPENING_CHARS = 360

_HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]+")


# ── Targets ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Target:
    target_type: str  # OverviewContent.TARGET_SUBJECT | TARGET_MODULE
    target_id: str
    name: str
    description: str
    subject_name: str  # a module's subject; a subject is its own
    module_names: tuple[str, ...]  # a subject's modules in order; () for a module

    @property
    def key(self) -> str:
        return f"{self.target_type}:{self.target_id}"


def generated_articles_under(target: Target, db: str = "default"):
    """BookContent rows beneath the node, best first — the grounding set."""
    scope = (
        Q(topic__subject_id=target.target_id)
        if target.target_type == OverviewContent.TARGET_SUBJECT
        else Q(topic__module_id=target.target_id)
    )
    return (
        BookContent.objects.using(db)
        .filter(scope, topic__is_active=True)
        .select_related("topic")
        .order_by("-quality_score", "-created_at")
    )


def _subject_target(s: Subject, db: str) -> Target:
    modules = tuple(
        Module.objects.using(db)
        .filter(subject=s, is_active=True)
        .order_by("order_index")
        .values_list("name", flat=True)
    )
    return Target(
        target_type=OverviewContent.TARGET_SUBJECT,
        target_id=str(s.id),
        name=s.name,
        description=s.description or "",
        subject_name=s.name,
        module_names=modules,
    )


def _module_target(m: Module, subject_name: str) -> Target:
    return Target(
        target_type=OverviewContent.TARGET_MODULE,
        target_id=str(m.id),
        name=m.name,
        description=m.description or "",
        subject_name=subject_name,
        module_names=(),
    )


def _existing(db: str) -> set[tuple[str, str]]:
    return {
        (t, str(i))
        for t, i in OverviewContent.objects.using(db).values_list(
            "target_type", "target_id"
        )
    }


def next_subject_batch(db: str = "default") -> list[Target]:
    """
    The work for ONE run: the first active subject (by `order_index`) that has
    no overview row, followed by its modules that have none and pass the
    children gate. Empty when every subject is done.

    A subject with an overview but modules still missing one (skipped on its
    day for lack of articles) is picked up first — so the queue never leaves a
    branch half-finished behind a newer subject.
    """
    existing = _existing(db)
    subjects = list(
        Subject.objects.using(db).filter(is_active=True).order_by("order_index")
    )

    for s in subjects:
        subject_done = (OverviewContent.TARGET_SUBJECT, str(s.id)) in existing
        batch: list[Target] = []
        if not subject_done:
            t = _subject_target(s, db)
            if not generated_articles_under(t, db).exists():
                # No article anywhere under it — nothing to ground on yet.
                continue
            batch.append(t)
        for m in (
            Module.objects.using(db)
            .filter(subject=s, is_active=True)
            .order_by("order_index")
        ):
            if (OverviewContent.TARGET_MODULE, str(m.id)) in existing:
                continue
            mt = _module_target(m, s.name)
            if generated_articles_under(mt, db).exists():
                batch.append(mt)
        if batch:
            return batch
    return []


def pending_summary(db: str = "default") -> dict[str, int]:
    """For the dry run and the log: how much of the queue is left."""
    existing = _existing(db)
    subjects = Subject.objects.using(db).filter(is_active=True)
    modules = Module.objects.using(db).filter(is_active=True)
    return {
        "subjects_total": subjects.count(),
        "subjects_done": sum(
            (OverviewContent.TARGET_SUBJECT, str(i)) in existing
            for i in subjects.values_list("id", flat=True)
        ),
        "modules_total": modules.count(),
        "modules_done": sum(
            (OverviewContent.TARGET_MODULE, str(i)) in existing
            for i in modules.values_list("id", flat=True)
        ),
    }


# ── Prompt ───────────────────────────────────────────────────────────────────

OVERVIEW_PROMPT = """You are writing the short introductory overview for a {kind} of an online UPSC \
study library. Readers arrive from a search engine or from the syllabus map and need to \
understand, in one reading, what this {kind} covers, how its parts fit together, and \
where to begin. This is an introduction, not a full article — the articles beneath it \
carry the depth.

{kind_upper}: {name}
SUBJECT: {subject_name}
SEEDED DESCRIPTION: {description}
{modules_block}
ARTICLES THAT ALREADY EXIST UNDER THIS {kind_upper} (name — opening lines). Ground the \
overview in THESE and refer to them by name — they are what the reader opens next:
{grounding}

────────────────────────────────────────────────────────────────────────────────
WRITE:

1. OPENING (one paragraph): what this {kind} is about and why it matters for the \
UPSC Civil Services syllabus. Open with the subject matter — never with "This {kind}…" \
or "Welcome".

2. BODY — at least 2 sections, each under its own "## " heading on its own line:
   - "What it covers" — the major themes, in the order a learner should meet them
   - "Where to start" — the 3–5 named articles a newcomer should read first, and why
   Add "How the parts connect" ONLY for a subject, and only if you can say something specific.

3. Every ## section: 1–3 paragraphs of 3–5 sentences. A blank line between paragraphs \
and before every heading. Real line breaks — never one long line.

4. Mention article names EXACTLY as given above. Do not invent articles not in the list.

5. LENGTH: {length}. Hard maximum {hard_max} words.

6. DO NOT: use markdown tables, ### sub-headings, callout boxes, the {kind} name as a \
top heading, generic closers ("In conclusion…"), or coaching filler \
("very important for aspirants").

OUTPUT: only the overview markdown — no preamble.
"""

RETRY_SUFFIX = """

────────────────────────────────────────────────────────────────────────────────
YOUR PREVIOUS DRAFT WAS REJECTED: {issues}.
Rewrite it in full: at least {min_words} words and at most {max_words}, at least \
{min_headings} sections each starting with "## " on its own line, a blank line \
between paragraphs.
"""

_LENGTH = {
    OverviewContent.TARGET_SUBJECT: ("400 to 600 words", 700),
    OverviewContent.TARGET_MODULE: ("250 to 400 words", 500),
}


def _opening_paragraph(markdown: str) -> str:
    """First real paragraph of an article (skips headings), clipped."""
    for para in (markdown or "").split("\n\n"):
        text = para.strip()
        if not text or text.startswith("#"):
            continue
        text = re.sub(r"\s+", " ", text)
        return text[:OPENING_CHARS] + ("…" if len(text) > OPENING_CHARS else "")
    return ""


def build_prompt(target: Target, db: str = "default") -> tuple[str, int]:
    rows = list(generated_articles_under(target, db)[:GROUNDING_ARTICLES])
    grounding = (
        "\n".join(
            f"- {bc.topic.name} — {_opening_paragraph(bc.content_markdown)}"
            for bc in rows
        )
        or "- (none)"
    )
    kind = (
        "subject" if target.target_type == OverviewContent.TARGET_SUBJECT else "module"
    )
    modules_block = (
        "MODULES, IN SYLLABUS ORDER: " + "; ".join(target.module_names) + "\n"
        if target.module_names
        else ""
    )
    length, hard_max = _LENGTH[target.target_type]
    return (
        OVERVIEW_PROMPT.format(
            kind=kind,
            kind_upper=kind.upper(),
            name=target.name,
            subject_name=target.subject_name,
            description=target.description or "Not available.",
            modules_block=modules_block,
            grounding=grounding,
            length=length,
            hard_max=hard_max,
        ),
        len(rows),
    )


# ── Gate ─────────────────────────────────────────────────────────────────────


def normalise_markdown(raw: str) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"([^\n])\n(#{1,3} )", r"\1\n\n\2", text)
    text = re.sub(r"(#{1,3} [^\n]+)\n([^#\n])", r"\1\n\n\2", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def quality_issues(body: str) -> list[str]:
    words = len(_WORD_RE.findall(body))
    headings = len(_HEADING_RE.findall(body))
    issues: list[str] = []
    if words < MIN_WORDS:
        issues.append(f"words {words} < {MIN_WORDS}")
    if words > MAX_WORDS:
        issues.append(f"words {words} > {MAX_WORDS}")
    if headings < MIN_HEADINGS:
        issues.append(f"headings {headings} < {MIN_HEADINGS}")
    if len(body) >= 400 and "\n" not in body.strip():
        issues.append("no newline — single-line markdown")
    return issues


def _score(body: str) -> float:
    """Heuristic 0–100: length toward 500 words, plus headings, capped."""
    words = len(_WORD_RE.findall(body))
    headings = len(_HEADING_RE.findall(body))
    return float(min(100, min(words, 500) / 5 + min(headings, 4) * 2))


# ── Generation ───────────────────────────────────────────────────────────────


def generate_overview(
    target: Target, db: str = "default", publish: bool = False
) -> OverviewContent | None:
    """
    One node → one LLM call (plus at most one corrective retry) → one row.
    Returns the row, or None when nothing was written (pool exhausted, gate
    failed twice, save failed). Never raises past this function.
    """
    prompt, grounded_on = build_prompt(target, db)
    body = ""
    issues = ["no draft"]
    passed_on = 0
    for attempt in (1, 2):
        try:
            raw = llm_call(prompt, mode="writer")
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "overview_llm_call_failed",
                target=target.key,
                attempt=attempt,
                error=str(exc),
            )
            return None
        if not raw or len(raw.strip()) < 200:
            logger.warning(
                "overview_empty_response", target=target.key, attempt=attempt
            )
            return None
        body = normalise_markdown(raw)
        issues = quality_issues(body)
        if not issues:
            passed_on = attempt
            break
        logger.warning(
            "overview_gate_failed", target=target.key, attempt=attempt, issues=issues
        )
        prompt = build_prompt(target, db)[0] + RETRY_SUFFIX.format(
            issues="; ".join(issues),
            min_words=MIN_WORDS,
            max_words=MAX_WORDS,
            min_headings=MIN_HEADINGS,
        )

    if issues:
        logger.warning(
            "overview_rejected", target=target.key, name=target.name, issues=issues
        )
        return None

    try:
        row = OverviewContent.objects.using(db).create(
            target_type=target.target_type,
            target_id=target.target_id,
            content_markdown=body,
            quality_score=_score(body),
            generation_pass=passed_on,
            grounded_on=grounded_on,
            is_published=publish,
        )
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.error("overview_save_failed", target=target.key, error=str(exc))
        return None

    logger.info(
        "overview_generated",
        target=target.key,
        name=target.name,
        words=row.word_count,
        grounded_on=grounded_on,
        generation_pass=passed_on,
        published=publish,
    )
    return row
