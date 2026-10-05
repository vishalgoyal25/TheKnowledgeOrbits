"""
engines/data_factory/tests/test_models.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Act 0, phase 0.1 -- the evidence spine.
Spec: 00_MASTER_RECAP.md 16.6.5 parts B (model constraints) and C (end-to-end).

What each group pins:
  identity      UUID primary keys, never auto-increment (CLAUDE.md 4.2)
  🔴 CHECKs     the DATABASE rejects a corrupt span, not just Python (9.2)
  versioning    the same chunk index CAN coexist across processing_versions
  provenance    source_ref_snapshot survives a JSONB round-trip intact
  PROTECT       evidence cannot be deleted out from under a citation
  🔴 end-to-end the real BUR-4 case: source -> artifact -> chunk -> atom ->
                span checker, with offsets computed by code

⚠️ Shipped tests in other engines use `pytest.raises(Exception)  # IntegrityError`.
These catch IntegrityError specifically: a bare Exception would also pass on a
typo-induced AttributeError and prove nothing about the constraint.
"""

import uuid

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from engines.data_factory.models import DfArtifact, DfAtom, DfChunk, DfSource
from engines.data_factory.services.span_checker import check_span
from engines.data_factory.services.span_checker import text_hash as compute_text_hash

# The worked Act 0 example. Same text as test_span_checker, deliberately: the
# end-to-end test must exercise the identical case the unit tests cover, so a
# divergence between them is a real finding rather than two different fixtures
# drifting apart.
BUR_TEXT = (
    "India submitted its Fourth Biennial Update Report (BUR-4) to the UNFCCC in "
    "December 2024. The report recorded a decrease of around 8% in GHG emissions "
    "in 2020 over 2019, excluding LULUCF. Energy remained the largest contributor."
)
BUR_CLAIM = "India's GHG emissions decreased by around 8% in 2020 over 2019."


def make_source(**overrides) -> DfSource:
    """A minimal valid T1 source. Plain helper rather than factory_boy: the
    chain is three objects deep and explicit construction reads better than
    indirection at this size.
    """
    defaults = {
        "name": f"PIB test source {uuid.uuid4().hex[:8]}",
        "tier": DfSource.TIER_T1,
        "adapter": "rss",
        "endpoint": f"https://example.invalid/feed/{uuid.uuid4().hex[:8]}",
    }
    return DfSource.objects.create(**{**defaults, **overrides})


def make_artifact(source: DfSource | None = None, **overrides) -> DfArtifact:
    defaults = {
        "source": source or make_source(),
        "content_hash": uuid.uuid4().hex + uuid.uuid4().hex,  # 64 hex chars
        "source_url": "https://example.invalid/release/1",
        "encoding_used": "utf-8",
        "retrieved_at": timezone.now(),
    }
    return DfArtifact.objects.create(**{**defaults, **overrides})


def make_chunk(
    artifact: DfArtifact | None = None, text: str = BUR_TEXT, **overrides
) -> DfChunk:
    art = artifact or make_artifact()
    defaults = {
        "artifact": art,
        "chunk_index": 0,
        "normalised_text": text,
        "text_hash": compute_text_hash(text),
        "char_count": len(text),
    }
    return DfChunk.objects.create(**{**defaults, **overrides})


# ── Identity ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_primary_keys_are_uuids_not_integers():
    """CLAUDE.md 4.2: UUID primary keys, never auto-increment.

    Asserted on every model in the chain because `default_auto_field` is set to
    BigAutoField in apps.py as a W042 silencer -- if a model ever forgot its
    explicit `id`, it would silently get an integer PK and this is what catches
    it.
    """
    chunk = make_chunk()
    atom = DfAtom.objects.create(
        chunk=chunk,
        claim_text=BUR_CLAIM,
        char_start=0,
        char_end=10,
        source_ref_snapshot={},
    )
    for obj in (chunk.artifact.source, chunk.artifact, chunk, atom):
        assert isinstance(obj.pk, uuid.UUID), f"{type(obj).__name__} has a non-UUID pk"


# ── 🔴 Database-level CHECK constraints ──────────────────────────────────────


@pytest.mark.django_db
def test_database_rejects_inverted_span_even_when_python_is_bypassed():
    """🔴 9.2: the DATABASE enforces it, not the code.

    `objects.create()` does NOT run field validators -- those only fire on
    `full_clean()`. So this reaches Postgres unvalidated, which is exactly the
    path a fixture, a bulk_create or a future data-migration script would take.
    The CHECK is the only thing standing there.
    """
    chunk = make_chunk()
    with pytest.raises(IntegrityError), transaction.atomic():
        DfAtom.objects.create(
            chunk=chunk,
            claim_text="inverted",
            char_start=50,
            char_end=10,
            source_ref_snapshot={},
        )


@pytest.mark.django_db
def test_database_rejects_empty_span():
    """char_start == char_end is a citation that shows nothing."""
    chunk = make_chunk()
    with pytest.raises(IntegrityError), transaction.atomic():
        DfAtom.objects.create(
            chunk=chunk,
            claim_text="empty",
            char_start=7,
            char_end=7,
            source_ref_snapshot={},
        )


@pytest.mark.django_db
def test_database_rejects_negative_offset():
    chunk = make_chunk()
    with pytest.raises(IntegrityError), transaction.atomic():
        DfAtom.objects.create(
            chunk=chunk,
            claim_text="negative",
            char_start=-1,
            char_end=10,
            source_ref_snapshot={},
        )


@pytest.mark.django_db
def test_database_rejects_negative_failure_count():
    chunk = make_chunk()
    with pytest.raises(IntegrityError), transaction.atomic():
        DfAtom.objects.create(
            chunk=chunk,
            claim_text="bad counter",
            char_start=0,
            char_end=5,
            source_ref_snapshot={},
            verification_failure_count=-1,
        )


# ── Versioning and uniqueness ────────────────────────────────────────────────


@pytest.mark.django_db
def test_duplicate_chunk_at_same_version_is_rejected():
    """Idempotency by construction: a re-run of the parser at the same version
    cannot duplicate a chunk, so a crashed run is safe to retry WITHOUT
    checking first.
    """
    artifact = make_artifact()
    make_chunk(artifact=artifact, chunk_index=3)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_chunk(artifact=artifact, chunk_index=3)


@pytest.mark.django_db
def test_same_chunk_index_coexists_across_processing_versions():
    """🔴 The property that makes 8.3's promise real.

    v1 and v2 of a chunk must be able to sit side by side, or "v2 runs
    alongside v1 and migrates gradually" is a slogan rather than a mechanism.
    This is also the only reason embeddings survive a version bump despite
    content_embedding's unique (content_type, content_id): the new chunk is a
    NEW row with a NEW uuid, so it gets its own vector.
    """
    artifact = make_artifact()
    v1 = make_chunk(artifact=artifact, chunk_index=0, processing_version=1)
    v2 = make_chunk(artifact=artifact, chunk_index=0, processing_version=2)
    assert v1.pk != v2.pk
    assert DfChunk.objects.filter(artifact=artifact, chunk_index=0).count() == 2


@pytest.mark.django_db
def test_duplicate_content_hash_is_rejected():
    """Dedup level 1: re-fetching an unchanged document is a no-op, not a row."""
    artifact = make_artifact()
    with pytest.raises(IntegrityError), transaction.atomic():
        make_artifact(source=artifact.source, content_hash=artifact.content_hash)


# ── Provenance ───────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_source_ref_snapshot_round_trips_as_jsonb():
    """The frozen citation must survive storage with its structure intact.

    It is read on the hottest path in the system (8-40 atoms per question) and
    rendered into explanations, so a silently stringified dict would surface as
    a broken citation in front of a paying student.
    """
    chunk = make_chunk()
    snapshot = {
        "url": "https://example.invalid/release/1",
        "publisher": "MoEFCC",
        "tier": "T1",
        "published_at": "2024-12-01T00:00:00+00:00",
        "nested": {"retrieved_via": "rss", "attempt": 2},
    }
    atom = DfAtom.objects.create(
        chunk=chunk,
        claim_text=BUR_CLAIM,
        char_start=0,
        char_end=20,
        source_ref_snapshot=snapshot,
    )
    atom.refresh_from_db()
    assert atom.source_ref_snapshot == snapshot
    assert atom.source_ref_snapshot["nested"]["attempt"] == 2


# ── PROTECT: evidence is not deletable out from under a citation ─────────────


@pytest.mark.django_db
def test_source_with_artifacts_cannot_be_deleted():
    """PROTECT, not CASCADE. Deleting a registry row must never silently
    destroy the documents backing published citations.
    """
    from django.db.models import ProtectedError

    artifact = make_artifact()
    with pytest.raises(ProtectedError):
        artifact.source.delete()


@pytest.mark.django_db
def test_chunk_with_atoms_cannot_be_deleted():
    chunk = make_chunk()
    DfAtom.objects.create(
        chunk=chunk,
        claim_text=BUR_CLAIM,
        char_start=0,
        char_end=10,
        source_ref_snapshot={},
    )
    from django.db.models import ProtectedError

    with pytest.raises(ProtectedError):
        chunk.delete()


# ── Citability: two halves, deliberately separate ───────────────────────────


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("tier", "citable"),
    [
        (DfSource.TIER_T1, True),
        (DfSource.TIER_T2, True),
        (DfSource.TIER_T3, False),
        (DfSource.TIER_T4, False),
    ],
)
def test_only_t1_and_t2_sources_are_citable(tier, citable):
    """T3 is event detection, T4 is context. Citing either would make
    verification circular -- the finding that justifies this engine.
    """
    assert make_source(tier=tier).is_citable is citable


@pytest.mark.django_db
def test_atom_citability_is_state_only_not_tier():
    """⚠️ `DfAtom.is_citable` answers HALF the question on purpose.

    A TRUE atom from a T3 source still cannot be cited. Tier lives in
    source_ref_snapshot["tier"]; a property that silently checked one half
    would be the easy way to leak T3 into a citation.
    """
    chunk = make_chunk()
    atom = DfAtom.objects.create(
        chunk=chunk,
        claim_text=BUR_CLAIM,
        char_start=0,
        char_end=10,
        source_ref_snapshot={"tier": "T3"},
        verification_state=DfAtom.STATE_TRUE,
    )
    assert atom.is_citable is True  # state says yes
    assert atom.source_ref_snapshot["tier"] == "T3"  # tier says no -- caller's job


@pytest.mark.django_db
def test_new_atom_defaults_to_pending_not_unproven():
    """🔴 PENDING and UNPROVEN must never be conflated.

    UNPROVEN is a VERDICT and kills a counting-format question. PENDING only
    means "not yet examined". Defaulting to UNPROVEN would kill every question
    before verification ever ran.
    """
    chunk = make_chunk()
    atom = DfAtom.objects.create(
        chunk=chunk,
        claim_text=BUR_CLAIM,
        char_start=0,
        char_end=10,
        source_ref_snapshot={},
    )
    assert atom.verification_state == DfAtom.STATE_PENDING
    assert atom.verification_state != DfAtom.STATE_UNPROVEN
    assert atom.verified_at is None
    assert atom.is_citable is False


@pytest.mark.django_db
def test_span_length_property():
    chunk = make_chunk()
    atom = DfAtom.objects.create(
        chunk=chunk,
        claim_text=BUR_CLAIM,
        char_start=10,
        char_end=42,
        source_ref_snapshot={},
    )
    assert atom.span_length == 32


# ── 🔴 End-to-end: the real Act 0 case, start to finish ─────────────────────


@pytest.mark.django_db
def test_bur4_case_end_to_end_source_to_verified_span():
    """🔴 One true case proving the whole chain (16.6.5 part C).

    Source -> artifact -> chunk -> atom -> span checker, with offsets computed
    BY CODE from the stored text (16.6.3). This is the shape every atom in
    Act 0 will take, and the first proof that the four tables and the checker
    agree about what a citation is.
    """
    source = make_source(name="MoEFCC BUR-4 release", tier=DfSource.TIER_T1)
    artifact = make_artifact(source=source, source_url="https://example.invalid/bur4")
    chunk = make_chunk(artifact=artifact, text=BUR_TEXT)

    # Offsets derived from the STORED text, never hand-counted.
    stored = chunk.normalised_text
    start = stored.index("The report recorded")
    end = stored.index(", excluding LULUCF")

    atom = DfAtom.objects.create(
        chunk=chunk,
        claim_text=BUR_CLAIM,
        char_start=start,
        char_end=end,
        source_ref_snapshot={
            "url": artifact.source_url,
            "publisher": source.name,
            "tier": source.tier,
            "retrieved_at": artifact.retrieved_at.isoformat(),
        },
    )

    # Re-read from the database, so the test proves the ROUND TRIP, not the
    # in-memory objects it just built.
    atom.refresh_from_db()
    chunk.refresh_from_db()

    result = check_span(
        text=chunk.normalised_text,
        char_start=atom.char_start,
        char_end=atom.char_end,
        claim_text=atom.claim_text,
        expected_text_hash=chunk.text_hash,
    )

    assert result.ok, result.detail
    assert "8%" in result.span_text
    assert not result.missing_anchors
    # The citation is complete and traceable: claim -> span -> source.
    assert atom.source_ref_snapshot["tier"] in DfSource.CITABLE_TIERS
    assert source.is_citable
