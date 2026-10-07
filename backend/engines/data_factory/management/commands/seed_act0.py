"""Seed the Act 0 evidence set: 19 sources, ~60 atoms, offsets computed by code.

Act 0, phase 0.3. Spec: 00_MASTER_RECAP.md 16.6.3.

    gate1_questions.json -> fetch -> parse -> chunk -> locate -> df_atom

🔴 Writes to the DEFAULT (local) database, deliberately.
---------------------------------------------------------
There is no ``--database`` flag, and that is the point. Act 0's atoms are
EXPERIMENTAL -- regenerated every time the extractor changes -- and Supabase
holds real content behind a connection ceiling that a background job can
exhaust, taking the WEBSITE down rather than the Factory (CLAUDE.md 9.2).

Schema goes to both databases; this data stays local. Adding a flag here would
make the wrong thing one typo away.

What this command is NOT
-------------------------
It does not verify anything. Every atom lands as ``PENDING``, which is a
distinct state from ``UNPROVEN`` precisely so that "not yet looked at" can
never be mistaken for "looked at and found unsupported" -- conflating them
would kill every counting-format question in Gate 1.

Honest failure is the output
-----------------------------
A source that 403s and a claim that cannot be located are both RESULTS, not
errors. The summary reports how many of the ~60 statements were actually
anchored to a span, because that number -- not a green tick -- is what decides
whether Gate 1 can run at all.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from urllib.parse import urlsplit

import structlog
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from engines.data_factory.models import DfArtifact, DfAtom, DfChunk, DfSource
from engines.data_factory.services.chunker import chunk_document
from engines.data_factory.services.claim_locator import locate_claim
from engines.data_factory.services.fetcher import fetch_document
from engines.data_factory.services.parser import parse_document
from engines.data_factory.services.semantic_locator import (
    embed_claim,
    locate_claim_semantically,
)
from engines.data_factory.services.span_checker import (
    extract_anchors,
    fold_for_comparison,
    text_hash,
)
from engines.data_factory.services.text_normaliser import NORMALISER_VERSION

logger = structlog.get_logger(__name__)

# backend/engines/data_factory/management/commands/seed_act0.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_QUESTIONS = (
    _REPO_ROOT / "FEATURES" / "DATA_FACTORY" / "act0" / "gate1_questions.json"
)

# Atoms located by MEANING rather than by shared keywords. A separate version,
# not an overwrite, so both locators' output coexists and can be scored against
# the same key (8.3). Chunks stay at NORMALISER_VERSION -- the TEXT did not
# change, only the search over it.
SEMANTIC_VERSION = 2


@dataclass
class Tally:
    """What actually happened. Printed at the end, and the point of the run."""

    questions: int = 0
    sources_created: int = 0
    artifacts_fetched: int = 0
    artifacts_reused: int = 0
    chunks_written: int = 0
    statements: int = 0
    atoms_written: int = 0
    confident: int = 0
    partial: int = 0
    media_found: int = 0
    links_found: int = 0
    structured_found: int = 0
    published_dates: int = 0
    unlocated: list[str] = field(default_factory=list)
    failed_sources: list[str] = field(default_factory=list)


class Command(BaseCommand):
    help = (
        "Fetch the Act 0 sources, chunk them, and write atoms whose char spans "
        "are COMPUTED, never hand-read. Writes to the local database only."
    )

    # Class-level default so `_process` can read it even if something ever
    # calls this command's internals without going through `handle`.
    _dump_dir: Path | None = None
    _semantic: bool = False

    def add_arguments(self, parser):
        parser.add_argument(
            "--questions",
            type=Path,
            default=DEFAULT_QUESTIONS,
            help="Path to gate1_questions.json (gitignored, under FEATURES/).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Fetch, parse, chunk and locate, but write nothing. Gives the "
                "full diagnostic -- including how many claims could be anchored "
                "-- with zero database impact."
            ),
        )
        parser.add_argument(
            "--semantic",
            action="store_true",
            help=(
                "Locate spans by MEANING instead of shared keywords, and write "
                "them at processing_version=2 so the keyword result survives "
                "for comparison. Costs NO LLM tokens -- embeddings run on CPU. "
                "Requires requirements/ml.txt."
            ),
        )
        parser.add_argument(
            "--dump",
            type=Path,
            default=None,
            help=(
                "Write each question's extracted text to <dir>/<question-id>.txt. "
                "Used to HAND-CURATE spans: a human reads what the page really "
                "says and supplies the deciding sentence, while code still "
                "computes the offsets (16.6.3 is about never reading a POSITION "
                "off a screen, not about never choosing a sentence)."
            ),
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "Delete this command's own Act 0 rows before seeding, for a "
                "clean re-run after the locator changes. Scoped strictly to "
                "sources with category='act0_seed' on the LOCAL database; it "
                "cannot touch a shipped engine's tables."
            ),
        )
        parser.add_argument(
            "--inspect",
            type=str,
            default="",
            help=(
                "Dump what was actually extracted for ONE question id "
                "(e.g. 2026-Q38) and stop: the text, its chunks, each claim's "
                "anchors, and why each one did or did not match. Use this "
                "instead of guessing at a locator change from log lines."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Process only the first N questions. 0 means all.",
        )

    def handle(self, *args, **options):
        path: Path = options["questions"]
        dry_run: bool = options["dry_run"]
        limit: int = options["limit"]

        if not path.exists():
            raise CommandError(
                f"Question set not found: {path}\n"
                "It lives under FEATURES/ which is gitignored, so a fresh "
                "clone will not have it."
            )

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            # Worth a clear message: this file is hand-maintained, and a
            # missing comma between question objects has already happened once.
            raise CommandError(f"{path} is not valid JSON: {exc}") from exc

        questions: list[dict[str, Any]] = payload.get("questions", [])
        if limit:
            questions = questions[:limit]

        self._semantic = options["semantic"]
        self._dump_dir: Path | None = options["dump"]
        if self._dump_dir is not None:
            self._dump_dir.mkdir(parents=True, exist_ok=True)
            self.stdout.write(self.style.WARNING(f"dumping text to {self._dump_dir}\n"))

        if options["reset"] and not dry_run:
            self._reset()

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - nothing will be written\n"))

        inspect: str = options["inspect"]
        if inspect:
            target = next((q for q in questions if q.get("id") == inspect), None)
            if target is None:
                raise CommandError(
                    f"No question with id {inspect!r}. "
                    f"Available: {', '.join(q.get('id', '?') for q in questions)}"
                )
            self._inspect(target)
            return

        tally = Tally()
        for question in questions:
            self._process(question, tally=tally, dry_run=dry_run)

        self._report(tally, dry_run=dry_run)

    # ── reset ──────────────────────────────────────────────────────────────

    def _reset(self) -> None:
        """Clear this command's own seed rows, bottom-up.

        🔴 Deletion order is NOT arbitrary. Every FK in the evidence chain is
        PROTECT, not CASCADE, because "artifacts are evidence. Deleting a
        registry row must never silently destroy the documents that back
        published citations" (models/sources.py). So a top-down delete raises
        ProtectedError -- the schema refusing to let evidence vanish, working
        exactly as designed.

        Scope is narrow by construction: only sources this command created
        (`category='act0_seed'`), only the local database. It cannot reach a
        shipped engine's tables, and the rows are experiment data the command
        wrote itself -- never the production content CLAUDE.md 3.2 protects.
        """
        sources = DfSource.objects.filter(category="act0_seed")
        artifacts = DfArtifact.objects.filter(source__in=sources)
        chunks = DfChunk.objects.filter(artifact__in=artifacts)

        atoms_removed, _ = DfAtom.objects.filter(chunk__in=chunks).delete()
        chunks_removed, _ = chunks.delete()
        artifacts_removed, _ = artifacts.delete()
        sources_removed, _ = sources.delete()

        self.stdout.write(
            self.style.WARNING(
                f"--reset: {atoms_removed} atoms, {chunks_removed} chunks, "
                f"{artifacts_removed} artifacts, {sources_removed} sources removed"
            )
        )
        self.stdout.write("")

    # ── one question ───────────────────────────────────────────────────────

    def _process(
        self, question: dict[str, Any], *, tally: Tally, dry_run: bool
    ) -> None:
        qid = question.get("id", "<no id>")
        url = question.get("source_url", "")
        statements = question.get("statements", [])

        tally.questions += 1
        tally.statements += len(statements)

        if not url:
            tally.failed_sources.append(f"{qid}: no source_url")
            return

        self.stdout.write(f"  {qid}  {url[:72]}")

        result = fetch_document(url)
        if not result.ok:
            # 8.4: one source's failure is recorded against that source and the
            # run continues. A blocked publisher must never cost the other 18.
            self.stdout.write(
                self.style.ERROR(
                    f"    fetch failed: {result.failure} {result.detail[:80]}"
                )
            )
            tally.failed_sources.append(f"{qid}: fetch {result.failure}")
            return

        parsed = parse_document(
            result.raw_bytes,
            content_type=result.declared_content_type,
            encoding=result.encoding_used,
            selectors=tuple(question.get("selectors", ())),
            # Resolves relative <img src> against the page, so a captured
            # media reference is fetchable later without the page beside it.
            base_url=result.url,
        )
        if not parsed.ok:
            self.stdout.write(
                self.style.ERROR(
                    f"    parse failed: {parsed.failure} {parsed.detail[:80]}"
                )
            )
            tally.failed_sources.append(f"{qid}: parse {parsed.failure}")
            return

        chunks = chunk_document(parsed.text)

        if self._dump_dir is not None:
            # The full extracted text, plus the claims, so curation happens
            # against what the parser REALLY produced rather than against the
            # live page -- which may differ, and it is the parser's output that
            # offsets index into.
            target = self._dump_dir / f"{qid}.txt"
            lines = [f"# {qid}  {url}", f"# extracted_via={parsed.extracted_via}", ""]
            for statement in statements:
                lines.append(
                    f"# CLAIM [{statement.get('expected', '?')}]: {statement.get('claim', '')}"
                )
            lines += ["", "=" * 70, "", parsed.text]
            target.write_text("\n".join(lines), encoding="utf-8")

        tally.media_found += len(parsed.media)
        tally.links_found += len(parsed.links)
        if parsed.structured:
            tally.structured_found += 1
            if parsed.structured.published_at:
                tally.published_dates += 1
        media_note = f", {len(parsed.media)} images" if parsed.media else ""
        docs = sum(1 for link in parsed.links if link.is_document)
        link_note = f", {docs} linked docs" if docs else ""
        meta_note = " +json-ld" if parsed.structured else ""
        self.stdout.write(
            f"    {len(parsed.text):,} chars via {parsed.extracted_via} "
            f"-> {len(chunks)} chunks{media_note}{link_note}{meta_note}"
        )

        # Locate every statement BEFORE writing anything. A question whose
        # claims cannot be anchored should not leave an artifact behind
        # pretending it contributed evidence.
        placements = []
        for statement in statements:
            claim = statement.get("claim", "")
            best = None
            best_chunk = None

            # Embed the claim ONCE, not once per chunk. A 10-chunk document
            # would otherwise re-embed the same sentence ten times.
            claim_vector = embed_claim(claim) if self._semantic else None

            for chunk in chunks:
                if self._semantic:
                    located = locate_claim_semantically(
                        chunk.text, claim, claim_vector=claim_vector
                    )
                else:
                    located = locate_claim(chunk.text, claim)

                if located and (
                    best is None or located.anchor_coverage > best.anchor_coverage
                ):
                    best, best_chunk = located, chunk
                    # Only the keyword locator has a meaningful "confident"
                    # shortcut; a similarity score always benefits from seeing
                    # every chunk before choosing.
                    if not self._semantic and located.is_confident:
                        break

            if best is None:
                # Logged HERE, once per claim, not inside locate_claim -- which
                # is asked about every chunk and correctly says None for most
                # of them. See the note at the end of locate_claim.
                logger.info(
                    "df_claim_unlocated",
                    question=qid,
                    claim=claim[:80],
                    chunks_searched=len(chunks),
                )
                tally.unlocated.append(f"{qid}: {claim[:60]}")
                self.stdout.write(self.style.WARNING(f"    unlocated: {claim[:60]}"))
                continue

            if best.is_confident:
                tally.confident += 1
            else:
                tally.partial += 1
                self.stdout.write(
                    f"    partial ({best.anchor_coverage:.0%}, missing "
                    f"{', '.join(best.missing_anchors)}): {claim[:50]}"
                )
            placements.append((best_chunk, best, statement))

        if dry_run or not placements:
            return

        try:
            with transaction.atomic():
                self._persist(question, result, parsed, chunks, placements, tally=tally)
        except DatabaseError as exc:
            # 🔴 8.4: fail-safe, never fail-stop. An IntegrityError on one
            # question killed the whole 19-source run on 2026-10-06 and left
            # 11 atoms behind -- a partial database that LOOKED like a result.
            # The atomic block rolls this question back; the loop continues.
            logger.warning("df_seed_persist_failed", question=qid, error=str(exc))
            self.stdout.write(self.style.ERROR(f"    write failed: {str(exc)[:110]}"))
            tally.failed_sources.append(f"{qid}: write {type(exc).__name__}")

    # ── diagnosis ──────────────────────────────────────────────────────────

    def _inspect(self, question: dict[str, Any]) -> None:
        """Show what was EXTRACTED, not what was logged.

        Added 2026-10-06 after two fixes in a row were diagnosed from log
        lines. The log says a claim was not located; it cannot say whether the
        text was wrong, the chunking was wrong, or the anchors were wrong --
        and those need different fixes. This prints all three.
        """
        qid = question.get("id", "?")
        url = question.get("source_url", "")
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"{qid}  {url}"))
        self.stdout.write("")

        result = fetch_document(url)
        if not result.ok:
            self.stdout.write(
                self.style.ERROR(f"fetch failed: {result.failure} {result.detail}")
            )
            return

        parsed = parse_document(
            result.raw_bytes,
            content_type=result.declared_content_type,
            encoding=result.encoding_used,
            selectors=tuple(question.get("selectors", ())),
            base_url=result.url,
        )
        if not parsed.ok:
            self.stdout.write(
                self.style.ERROR(f"parse failed: {parsed.failure} {parsed.detail}")
            )
            return

        chunks = chunk_document(parsed.text)
        self.stdout.write(
            f"extracted_via={parsed.extracted_via}  chars={len(parsed.text):,}  "
            f"chunks={len(chunks)}  images={len(parsed.media)}  links={len(parsed.links)}"
        )
        if parsed.structured:
            self.stdout.write(
                f"json-ld: types={list(parsed.structured.raw_types)[:4]} "
                f"published={parsed.structured.published_at or '-'}"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING("--- first 1200 chars of extracted text ---")
        )
        self.stdout.write(parsed.text[:1200])

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("--- claims ---"))
        for statement in question.get("statements", []):
            claim = statement.get("claim", "")
            hard, soft = extract_anchors(claim)
            mode = "HARD" if hard else "soft"
            anchors = hard or soft
            self.stdout.write("")
            self.stdout.write(f"  {claim}")
            self.stdout.write(f"    mode={mode}  anchors={list(anchors)}")

            if not anchors:
                self.stdout.write(
                    self.style.ERROR("    NO ANCHORS - nothing to locate by")
                )
                continue

            # Which anchors exist ANYWHERE in the document? This separates
            # "the text does not contain the fact" from "the chunking or the
            # window split it up" -- two different bugs with one symptom.
            folded_doc = fold_for_comparison(parsed.text)
            present = [a for a in anchors if fold_for_comparison(a) in folded_doc]
            absent = [a for a in anchors if fold_for_comparison(a) not in folded_doc]
            self.stdout.write(f"    in document: {present}")
            if absent:
                self.stdout.write(
                    self.style.WARNING(f"    MISSING from document: {absent}")
                )

            best, best_i = None, -1
            for chunk in chunks:
                located = locate_claim(chunk.text, claim)
                if located and (
                    best is None or located.anchor_coverage > best.anchor_coverage
                ):
                    best, best_i = located, chunk.index

            if best is None:
                self.stdout.write(self.style.ERROR("    NOT LOCATED in any chunk"))
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"    located in chunk {best_i} at {best.anchor_coverage:.0%} "
                        f"({best.sentence_count} sentences): {best.text[:140]}"
                    )
                )

    # ── persistence ────────────────────────────────────────────────────────

    def _persist(
        self, question, result, parsed, chunks, placements, *, tally: Tally
    ) -> None:
        source, created = _ensure_source(question, result)
        if created:
            tally.sources_created += 1

        artifact = DfArtifact.objects.filter(content_hash=result.content_hash).first()
        if artifact:
            # Dedup level 1. Re-running the command is a no-op for unchanged
            # documents, which is what makes it safe to run repeatedly while
            # the locator is being tuned.
            tally.artifacts_reused += 1
        else:
            artifact = DfArtifact.objects.create(
                source=source,
                content_hash=result.content_hash,
                source_url=result.url,
                http_status=result.http_status,
                declared_content_type=result.declared_content_type,
                encoding_used=result.encoding_used,
                byte_size=result.byte_size,
                retrieved_at=timezone.now(),
                # From the page's own JSON-LD where it published one. This
                # column drives ingestion-freshness SLOs and atom validity
                # windows, and reading it from structured data is fact where
                # parsing it out of prose would be guesswork.
                published_at=_published_at(parsed),
                # Hand-classified in the question set; UNKNOWN is the safe
                # default and can never yield a FALSE verdict (09 8.3).
                exhaustiveness=question.get(
                    "exhaustiveness", DfArtifact.EXHAUSTIVENESS_UNKNOWN
                ),
                exhaustive_scope=question.get("exhaustive_scope", ""),
                section_type=question.get("section_type", DfArtifact.SECTION_NEWS),
            )
            tally.artifacts_fetched += 1

        chunk_rows: dict[int, DfChunk] = {}
        for chunk in chunks:
            row, made = DfChunk.objects.get_or_create(
                artifact=artifact,
                chunk_index=chunk.index,
                processing_version=NORMALISER_VERSION,
                defaults={
                    "normalised_text": chunk.text,
                    "text_hash": text_hash(chunk.text),
                    "char_count": chunk.char_count,
                },
            )
            chunk_rows[chunk.index] = row
            if made:
                tally.chunks_written += 1

        snapshot = {
            "url": result.url,
            "publisher": question.get("source_publisher", ""),
            "tier": question.get("source_tier", ""),
            "encoding": result.encoding_used,
            "content_hash": result.content_hash,
            "retrieved_at": artifact.retrieved_at.isoformat(),
            "extracted_via": parsed.extracted_via,
        }

        for chunk, located, statement in placements:
            # get_or_create, not create: the first run crashed partway and left
            # 11 atoms behind, and a re-run must not double them. Keyed on
            # (chunk, claim, version) because that triple is what an atom IS --
            # one claim, located in one chunk, by one version of the rules.
            #
            # ⚠️ An improved locator finding a BETTER span for an existing atom
            # will NOT update it. That is deliberate: rewriting a stored span
            # in place is the one thing 8.3 forbids. Use --reset to re-seed.
            _, made = DfAtom.objects.get_or_create(
                chunk=chunk_rows[chunk.index],
                claim_text=statement["claim"],
                # 🔴 Semantic spans are a DIFFERENT INTERPRETATION of the same
                # artifact, so they get their own version rather than
                # overwriting the keyword result (8.3: "v2 runs alongside v1").
                # That is what makes the two locators directly comparable on
                # identical scoring instead of one erasing the other.
                processing_version=SEMANTIC_VERSION
                if self._semantic
                else NORMALISER_VERSION,
                defaults={
                    "char_start": located.char_start,
                    "char_end": located.char_end,
                    # Frozen at extraction: a citation sold to a student must
                    # never change under them (06_DESIGN 5.5).
                    "source_ref_snapshot": {
                        **snapshot,
                        "locator": "semantic" if self._semantic else "anchor",
                        # Named explicitly: for the keyword locator this is an
                        # anchor-coverage RATIO, for the semantic one a cosine
                        # SIMILARITY. Two different scales that must never be
                        # averaged together by a later reader.
                        "score_kind": "cosine" if self._semantic else "anchor_coverage",
                    },
                    "confidence": located.anchor_coverage,
                },
            )
            if made:
                tally.atoms_written += 1

    # ── reporting ──────────────────────────────────────────────────────────

    def _report(self, tally: Tally, *, dry_run: bool) -> None:
        located = tally.confident + tally.partial
        rate = located / tally.statements if tally.statements else 0.0

        self.stdout.write("\n" + "=" * 62)
        self.stdout.write(f"  questions processed      {tally.questions}")
        self.stdout.write(f"  sources created          {tally.sources_created}")
        self.stdout.write(
            f"  artifacts fetched/reused {tally.artifacts_fetched}/{tally.artifacts_reused}"
        )
        self.stdout.write(f"  chunks written           {tally.chunks_written}")
        self.stdout.write(
            f"  images seen              {tally.media_found}  "
            f"(references only - storage is Act II 2.5a)"
        )
        self.stdout.write(f"  links captured           {tally.links_found}")
        self.stdout.write(
            f"  pages with JSON-LD       {tally.structured_found}  "
            f"({tally.published_dates} gave a publication date)"
        )
        self.stdout.write(f"  atoms written            {tally.atoms_written}")
        self.stdout.write("-" * 62)
        self.stdout.write(f"  statements               {tally.statements}")
        self.stdout.write(f"  located (full anchors)   {tally.confident}")
        self.stdout.write(f"  located (partial)        {tally.partial}")
        self.stdout.write(f"  UNLOCATED                {len(tally.unlocated)}")
        self.stdout.write("=" * 62)

        # 🔴 The number 0.3 exists to produce. Gate 1 can only be run on
        # statements that have a span, so this is the real exit criterion --
        # not "the command finished".
        style = self.style.SUCCESS if rate >= 0.9 else self.style.WARNING
        self.stdout.write(
            style(f"  ANCHOR RATE  {located}/{tally.statements} ({rate:.0%})")
        )

        if tally.failed_sources:
            self.stdout.write(self.style.ERROR("\n  Sources that failed:"))
            for item in tally.failed_sources:
                self.stdout.write(f"    {item}")

        if tally.unlocated:
            self.stdout.write(self.style.WARNING("\n  Claims with no span:"))
            for item in tally.unlocated:
                self.stdout.write(f"    {item}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n  DRY RUN - nothing was written"))

        logger.info(
            "df_act0_seed_complete",
            questions=tally.questions,
            atoms=tally.atoms_written,
            anchor_rate=round(rate, 3),
            failed_sources=len(tally.failed_sources),
        )


def _ensure_source(question: dict[str, Any], result) -> tuple[DfSource, bool]:
    """One registry row per PUBLISHER, not per document.

    🔴 Fixed 2026-10-06. The first version keyed on the document URL, which
    made four PIB releases into four sources -- and `DfSource.name` is unique,
    so the second PIB question raised IntegrityError and ended the run.

    The model's own docstring already said it: "A registry row describing one
    place material comes from. Adding PIB is one row." PIB is ONE source with
    many artifacts. The per-document URL belongs on `DfArtifact.source_url`,
    which is exactly where it already goes.

    `endpoint` is the publisher's ORIGIN rather than any one page, because a
    registry row answers "where do we fetch from", not "what did we fetch".

    Both `name` and `endpoint` are unique, so an existing row is matched on
    either before anything is created -- two spellings of one publisher must
    not collide on the host, and two hosts must not collide on a name.
    """
    split = urlsplit(result.url)
    origin = f"{split.scheme}://{split.netloc}"
    name = (question.get("source_publisher") or split.netloc or result.url)[:200]

    existing = DfSource.objects.filter(Q(name=name) | Q(endpoint=origin)).first()
    if existing is not None:
        return existing, False

    return (
        DfSource.objects.create(
            name=name,
            endpoint=origin,
            tier=question.get("source_tier", DfSource.TIER_T1),
            adapter="pdf" if result.is_binary else "html",
            category="act0_seed",
        ),
        True,
    )


def _published_at(parsed):
    """The publisher's own timestamp, from JSON-LD, or None.

    Never raises and never guesses. A malformed date is simply absent -- a
    wrong publication date would corrupt freshness SLOs and atom validity
    windows more quietly than a missing one.
    """
    if not parsed.structured or not parsed.structured.published_at:
        return None
    parsed_dt = parse_datetime(parsed.structured.published_at)
    if parsed_dt is None:
        return None
    if timezone.is_naive(parsed_dt):
        return timezone.make_aware(parsed_dt)
    return parsed_dt
