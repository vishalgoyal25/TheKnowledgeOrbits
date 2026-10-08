"""Write hand-curated evidence spans as a separate processing version.

Act 0, phase 0.4b. Spec: 00_MASTER_RECAP.md 16.6.3, act0/0.4_GATE1_FINDINGS.md.

    curated anchors -> locate IN CODE -> df_atom at CURATED_VERSION

🔴 Why this exists
-------------------
Gate 1 scored 35.1%, but every miss carried `not_addressed_by_source` -- a
LOCATOR reason. The gate measured retrieval x verification and reported the
product as if it were verification.

Here a human supplies WHICH SENTENCE is the evidence; code still computes
WHERE it is. With retrieval held at ~100%, the resulting accuracy IS the
verifier's accuracy -- the number Act 0 was commissioned to produce.

🔴 16.6.3 is not violated
--------------------------
Its rule is "never read a character POSITION off a screen", because
whitespace, encoding and Unicode form shift positions invisibly between what
is displayed and what is stored. Choosing which sentence is evidence is a
JUDGEMENT. Computing where it starts is a MEASUREMENT, and the measurement
still belongs to code -- `str.find` on the stored chunk, never a human's eye.

Why a separate processing_version
----------------------------------
Curated spans are a DIFFERENT INTERPRETATION of the same artifact, so they
become new rows rather than edits to existing ones. That is exactly what
`processing_version` is for (8.3: "v2 can run alongside v1"), and it means the
locator's own result survives intact for comparison instead of being
overwritten by the answer.

🔴 Anchors FAILED. Verbatim text, copied by code, replaced them
----------------------------------------------------------------
The original design asked a human for two short anchor phrases at the edges of
the evidence, reasoning that a literal span would fail on a character nobody
can see -- curly apostrophes (U+2019), backticks used as apostrophes,
non-breaking spaces.

**It failed worse: 2 of 9 located.** The anchors were themselves typed by a
human, so they carried exactly the invisible-character problem they were meant
to dodge.

🟢 **Gate 1b fixes it by never typing the text at all.** `build_gate1b` copies
each chosen sentence out of `act0/extracted/` -- the parser's own output, the
string the chunks are slices of -- and writes it into `gate1b_spans.json` as
`exact_text`. This command then does a plain `str.find` for it, which cannot
fail on a character nobody can see because nobody typed one.

Both formats are accepted: an entry with `exact_text` takes the Gate 1b path,
an entry with `start_anchor`/`end_anchor` the legacy one. The legacy path is
kept only so the 2026-10-07 attempt stays reproducible.

Exhaustiveness
--------------
A Gate 1b file may also declare `artifacts[].exhaustiveness` and
`exhaustive_scope`, which this command writes onto `df_artifact`. Those columns
shipped in PR #37 and were never populated, so every artifact sat at `UNKNOWN`
-- and `UNKNOWN` can never yield `FALSE` (09_FUSION_AND_EVIDENCE.md §8.3). The
declaration is per DOCUMENT KIND from 09 §8.2's table, made before any verdict
is seen, with its justification carried in the file.
"""

import json
from pathlib import Path

import structlog
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from engines.data_factory.models import DfArtifact, DfAtom, DfChunk
from engines.data_factory.services.span_checker import Reason, check_span

logger = structlog.get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_ACT0 = _REPO_ROOT / "FEATURES" / "DATA_FACTORY" / "act0"
DEFAULT_SPANS = _ACT0 / "gate1b_spans.json"

# A deliberately distant version number: these rows are not "the next version"
# of the locator's output, they are a parallel, human-anchored interpretation
# kept for one measurement. Nothing should ever auto-promote them.
CURATED_VERSION = 99


class Command(BaseCommand):
    help = (
        "Locate hand-curated evidence spans in already-seeded chunks and write "
        "them as atoms at processing_version=99, leaving the locator's own "
        "atoms untouched for comparison."
    )

    # source_url -> that document's chunks, loaded once. See _locate_exact.
    _chunk_cache: dict[str, list[DfChunk]]

    def add_arguments(self, parser):
        parser.add_argument(
            "--spans",
            type=Path,
            default=DEFAULT_SPANS,
            help=(
                "A spans file. A bare filename is resolved inside "
                "FEATURES/DATA_FACTORY/act0/."
            ),
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Remove existing curated atoms (version 99) before writing.",
        )

    def handle(self, *args, **options):
        path: Path = options["spans"]
        if not path.exists() and not path.is_absolute():
            path = _ACT0 / path
        if not path.exists():
            raise CommandError(
                f"Curated spans not found: {path}. Run `build_gate1b` first."
            )

        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = payload.get("spans", [])
        self._chunk_cache = {}

        if options["reset"]:
            removed, _ = DfAtom.objects.filter(
                processing_version=CURATED_VERSION
            ).delete()
            self.stdout.write(self.style.WARNING(f"removed {removed} curated atoms"))

        self._declare_exhaustiveness(payload.get("artifacts", []))

        written = skipped = failed = 0

        for entry in entries:
            qid = entry.get("question_id", "?")
            claim = entry.get("claim", "")
            exact_text = entry.get("exact_text", "")
            start_anchor = entry.get("start_anchor", "")
            end_anchor = entry.get("end_anchor", "")

            if not claim or not (exact_text or (start_anchor and end_anchor)):
                self.stdout.write(self.style.ERROR(f"  {qid}: incomplete entry"))
                failed += 1
                continue

            if exact_text:
                located = self._locate_exact(exact_text, entry.get("source_url", ""))
            else:
                located = self._locate(claim, start_anchor, end_anchor)
            if located is None:
                failed += 1
                continue

            chunk, start, end = located
            span_text = chunk.normalised_text[start:end]

            # The same deterministic check production will run. A curated span
            # that cannot pass it is a BAD CURATION, not a verifier problem,
            # and must be fixed here rather than carried into the measurement.
            check = check_span(
                text=chunk.normalised_text,
                char_start=start,
                char_end=end,
                claim_text=claim,
                expected_text_hash=chunk.text_hash,
            )
            # 🔴 ANCHOR_MISSING is ADVISORY on the curated path, fatal nowhere
            # else changed. 0.4_GATE1_FINDINGS.md §4 already rejected anchor
            # coverage as a pre-filter because it is systematically biased
            # against FALSE claims -- a claim is false BECAUSE its anchor is
            # absent from the source. It rejected 8 of 31 correct curations on
            # the first Gate 1b run, including all four INTERPOL notices, whose
            # spans omit the word "INTERPOL" for the simple reason that the
            # whole page is about INTERPOL.
            #
            # Every OTHER reason stays fatal: a hash mismatch, an out-of-bounds
            # offset or a corrupted decode means the offsets are wrong, and a
            # wrong offset is the one thing this command must never write.
            if not check.ok and check.reason is not Reason.ANCHOR_MISSING:
                self.stdout.write(
                    self.style.ERROR(f"  {qid}: span check failed - {check.detail}")
                )
                failed += 1
                continue

            snapshot = _snapshot_from_sibling(chunk, claim)
            # The resolver reads `tier` off the snapshot, and a sibling may not
            # exist for a document whose every v1 atom failed to locate -- so
            # it comes from the question set rather than being hoped for.
            snapshot["tier"] = entry.get("source_tier", "") or snapshot.get("tier", "")
            snapshot["curated"] = True

            with transaction.atomic():
                _, made = DfAtom.objects.get_or_create(
                    chunk=chunk,
                    claim_text=claim,
                    processing_version=CURATED_VERSION,
                    defaults={
                        "char_start": start,
                        "char_end": end,
                        "source_ref_snapshot": snapshot,
                        "confidence": 1.0,
                    },
                )

            if made:
                written += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {qid}  [{end - start:>4} chars]  {span_text[:80]}"
                    )
                )
                if check.missing_anchors:
                    # Not fatal: a FALSE claim is false BECAUSE an anchor is
                    # absent from the source, so missing anchors are expected
                    # and even desirable on the contradiction cases.
                    self.stdout.write(
                        f"         missing anchors (expected on FALSE claims): "
                        f"{', '.join(check.missing_anchors)}"
                    )
            else:
                skipped += 1

        self.stdout.write("")
        self.stdout.write(f"  curated atoms written {written}")
        self.stdout.write(f"  already present       {skipped}")
        style = self.style.ERROR if failed else self.style.SUCCESS
        self.stdout.write(style(f"  FAILED                {failed}"))
        self.stdout.write(
            "\n  Now run:  python manage.py run_gate1 --processing-version 99"
        )

        logger.info(
            "df_curate_complete", written=written, skipped=skipped, failed=failed
        )

    def _declare_exhaustiveness(self, artifacts: list[dict]) -> None:
        """Write the declared exhaustiveness onto the matching df_artifact rows.

        🔴 Why this is not result-steering, and how to tell
        ---------------------------------------------------
        `UNKNOWN` can never yield `FALSE` (09 §8.3), so leaving every artifact
        unclassified would make a whole class of FALSE statements unreachable
        no matter how good the verifier is -- and would quietly report that as
        a verifier failure.

        The three guards: the value is declared per DOCUMENT KIND from 09
        §8.2's table and not per claim; it is written in the selector file
        BEFORE any verdict is seen; and `build_gate1b` prints exactly which
        statements' verdicts depend on it, so the number can be audited.
        """
        declared = updated = 0
        for row in artifacts:
            value = row.get("exhaustiveness", "")
            url = row.get("source_url", "")
            if not value or not url or value == DfArtifact.EXHAUSTIVENESS_UNKNOWN:
                continue
            declared += 1
            updated += DfArtifact.objects.filter(source_url=url).update(
                exhaustiveness=value,
                exhaustive_scope=row.get("exhaustive_scope", ""),
            )
        if declared:
            self.stdout.write(
                f"  exhaustiveness declared on {updated} artifact(s) "
                f"from {declared} declaration(s)"
            )

    def _locate_exact(self, exact_text: str, source_url: str):
        """Find a verbatim sentence in the stored chunks and compute offsets.

        🟢 The Gate 1b path. `exact_text` was copied out of the parser's own
        output by `build_gate1b`, so a plain `str.find` is sufficient and
        cannot be defeated by an invisible character -- nobody typed one.

        Chunks of the matching artifact are searched first. Restricting by URL
        matters: a sentence as short as a table row could plausibly occur in a
        second document, and an atom must cite the document it was chosen from.

        ⚠️ The per-document chunk list is CACHED. Without it this method loads
        every chunk row -- `normalised_text` included -- once per statement:
        31 statements x 478 chunks of full document text, for a job that needs
        each document once (§4.6b: know the cost of a loop that touches the DB).
        """
        if source_url not in self._chunk_cache:
            queryset = DfChunk.objects.exclude(
                processing_version=CURATED_VERSION
            ).select_related("artifact")
            if source_url:
                self._chunk_cache[source_url] = list(
                    queryset.filter(artifact__source_url=source_url)
                )
            else:
                self._chunk_cache[source_url] = list(queryset)

        for chunk in self._chunk_cache[source_url]:
            start = chunk.normalised_text.find(exact_text)
            if start >= 0:
                return chunk, start, start + len(exact_text)

        # The one residual failure mode §6.1 predicted: the chunker split the
        # sentence across a boundary. That is a finding about chunk size, not a
        # typo, so it is reported as such.
        self.stdout.write(
            self.style.ERROR(
                "  verbatim text not found in this document's chunks -- the "
                "chunker may have split it across a boundary, or the document "
                f"was never seeded: {exact_text[:60]!r}"
            )
        )
        self.stdout.write(f"         document: {source_url[:90]}")
        self._diagnose_cut(exact_text, source_url)
        return None

    def _diagnose_cut(self, exact_text: str, source_url: str) -> None:
        """Say WHERE the text stops being findable, not merely that it is not.

        🔴 §4.6b-i: build the inspector before the second fix. "Not found"
        cannot distinguish three different problems -- the document was never
        seeded, the chunker split the passage, or the line range was wrong --
        and each needs a different fix. One more run per guess is the cost of
        not knowing.

        Presence of a prefix is monotone (if a prefix of length n is in the
        text, every shorter one is too), so the longest findable prefix is a
        binary search, not a scan.
        """
        chunks = self._chunk_cache.get(source_url, [])
        if not chunks:
            self.stdout.write(
                self.style.ERROR(
                    "         no chunks at all for this document -- it was "
                    "never seeded, so trimming the span will not help"
                )
            )
            return

        best_length = 0
        best_chunk = chunks[0]
        for chunk in chunks:
            low, high = 0, len(exact_text)
            while low < high:
                middle = (low + high + 1) // 2
                if exact_text[:middle] in chunk.normalised_text:
                    low = middle
                else:
                    high = middle - 1
            if low > best_length:
                best_length, best_chunk = low, chunk

        if best_length == 0:
            self.stdout.write(
                self.style.ERROR(
                    "         not even the first character matches -- the line "
                    "range is wrong, not the chunking"
                )
            )
            return

        kept = exact_text[:best_length]
        lost = exact_text[best_length:]
        self.stdout.write(
            f"         findable up to {best_length}/{len(exact_text)} chars "
            f"in chunk {best_chunk.chunk_index} ({best_chunk.char_count} chars)"
        )
        self.stdout.write(f"         cut AFTER : ...{kept[-60:]!r}")
        self.stdout.write(f"         cut BEFORE: {lost[:60]!r}...")
        self.stdout.write(
            "         -> trim the selector to the part before the cut, or "
            "choose another sentence in the same chunk"
        )

    def _locate(self, claim: str, start_anchor: str, end_anchor: str):
        """Find the anchors in any seeded chunk and compute the offsets.

        Searches every chunk rather than assuming which one holds the text --
        the chunker may have split a document anywhere, and guessing the chunk
        is the same mistake the locator already makes.
        """
        for chunk in DfChunk.objects.exclude(
            processing_version=CURATED_VERSION
        ).iterator():
            text = chunk.normalised_text
            start = text.find(start_anchor)
            if start < 0:
                continue
            end_at = text.find(end_anchor, start + len(start_anchor))
            if end_at < 0:
                # Start matched but the end did not FOLLOW it in this chunk.
                # Usually means the chunker split the evidence across a
                # boundary -- worth reporting, because it is a real finding
                # about chunk size rather than a curation typo.
                self.stdout.write(
                    self.style.WARNING(
                        f"         start anchor found in chunk {chunk.chunk_index} "
                        f"but end anchor does not follow it (split by chunking?)"
                    )
                )
                continue
            return chunk, start, end_at + len(end_anchor)

        self.stdout.write(
            self.style.ERROR(
                f"  anchors not found in any chunk: {start_anchor[:40]!r} ... "
                f"{end_anchor[:40]!r}"
            )
        )
        return None


def _snapshot_from_sibling(chunk: DfChunk, claim: str) -> dict:
    """Reuse the provenance the seeder already froze for this document.

    A curated atom cites the SAME artifact as the locator's atom, so it must
    carry the same source_ref -- otherwise two atoms over one document would
    disagree about where that document came from.
    """
    sibling = DfAtom.objects.filter(chunk__artifact=chunk.artifact).first()
    if sibling and sibling.source_ref_snapshot:
        return dict(sibling.source_ref_snapshot)
    return {
        "url": chunk.artifact.source_url,
        "encoding": chunk.artifact.encoding_used,
        "content_hash": chunk.artifact.content_hash,
    }
