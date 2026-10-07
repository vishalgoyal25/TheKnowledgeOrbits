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

Anchors, not literal spans
---------------------------
Government pages carry curly apostrophes (U+2019), backticks used as
apostrophes, and non-breaking spaces. A literal span fails to match on a
character nobody can see. Two short anchors at the edges cannot.
"""

import json
from pathlib import Path

import structlog
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from engines.data_factory.models import DfAtom, DfChunk
from engines.data_factory.services.span_checker import check_span

logger = structlog.get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_SPANS = (
    _REPO_ROOT / "FEATURES" / "DATA_FACTORY" / "act0" / "gate1_curated_spans.json"
)

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

    def add_arguments(self, parser):
        parser.add_argument("--spans", type=Path, default=DEFAULT_SPANS)
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Remove existing curated atoms (version 99) before writing.",
        )

    def handle(self, *args, **options):
        path: Path = options["spans"]
        if not path.exists():
            raise CommandError(f"Curated spans not found: {path}")

        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = payload.get("spans", [])

        if options["reset"]:
            removed, _ = DfAtom.objects.filter(
                processing_version=CURATED_VERSION
            ).delete()
            self.stdout.write(self.style.WARNING(f"removed {removed} curated atoms"))

        written = skipped = failed = 0

        for entry in entries:
            qid = entry.get("question_id", "?")
            claim = entry.get("claim", "")
            start_anchor = entry.get("start_anchor", "")
            end_anchor = entry.get("end_anchor", "")

            if not (claim and start_anchor and end_anchor):
                self.stdout.write(self.style.ERROR(f"  {qid}: incomplete entry"))
                failed += 1
                continue

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
            if not check.ok:
                self.stdout.write(
                    self.style.ERROR(f"  {qid}: span check failed - {check.detail}")
                )
                failed += 1
                continue

            with transaction.atomic():
                _, made = DfAtom.objects.get_or_create(
                    chunk=chunk,
                    claim_text=claim,
                    processing_version=CURATED_VERSION,
                    defaults={
                        "char_start": start,
                        "char_end": end,
                        "source_ref_snapshot": {
                            **(_snapshot_from_sibling(chunk, claim)),
                            "curated": True,
                        },
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
