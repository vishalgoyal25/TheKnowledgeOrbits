"""Evidence layer: decoded text, and the atomic claims extracted from it.

``DfChunk`` -- a span-addressable slice of one artifact's decoded text.
``DfAtom``  -- one verifiable claim + the exact character span that supports it.

Why atoms instead of chunks
---------------------------
A chunk is ~1,200 chars ~ 300 tokens, mostly irrelevant surrounding prose. An
atom is ~30 tokens, every one load-bearing. Ten chunks cost 3,000 tokens of
mostly noise; eight atoms cost 240. It is also MORE accurate, because the model
is not given material it can rationalise from (01_AGENT_ARCHITECTURE.md 3.3).

Why the span is the product
---------------------------
``char_start``/``char_end`` are offsets into ``DfChunk.normalised_text``. That
makes verification a DETERMINISTIC operation first: re-read the span, confirm
the claim is literally supported. A function returns False and an LLM cannot
argue with it. Everything else in this platform rests on those two integers
being correct, which is why:

* text is normalised ONCE, at ingest, and never again;
* ``DfChunk.text_hash`` pins the exact string the offsets were computed against;
* offsets are always computed BY CODE, never read off a screen by a human
  (00_MASTER_RECAP.md 16.6.3).

Offsets are PYTHON CHARACTER offsets, not byte offsets. ``text[start:end]``
slices code points. Computing them against UTF-8 bytes shifts every span after
the first non-ASCII character -- the single most likely real bug in this file,
and the reason the test suite includes Devanagari text.
"""

import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .sources import DfArtifact


class DfChunk(models.Model):
    """One slice of decoded artifact text, addressable by character offset.

    DERIVED, so it carries ``processing_version``: a new parser produces
    different boundaries, and both versions must be able to coexist while a
    migration proceeds gradually.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the chunk",
    )
    artifact = models.ForeignKey(
        DfArtifact,
        on_delete=models.PROTECT,
        related_name="chunks",
        help_text=(
            "The artifact this text came from. PROTECT: a chunk whose artifact "
            "vanished is an uncitable orphan, and published questions may "
            "depend on it."
        ),
    )
    chunk_index = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Zero-based position of this chunk within the artifact",
    )
    normalised_text = models.TextField(
        help_text=(
            "The decoded, normalised text. THE offsets on every child atom "
            "index into exactly this string. Normalise once at ingest and never "
            "again -- a later normalisation would shift every span already "
            "computed (Contract 1)."
        ),
    )
    text_hash = models.CharField(
        max_length=64,
        help_text=(
            "SHA-256 of normalised_text, hex. The span checker compares this "
            "before trusting any offset: if the text was re-normalised after "
            "offsets were computed, every offset is silently wrong and this "
            "mismatch is the only way to detect it."
        ),
    )
    char_count = models.IntegerField(
        help_text=(
            "len(normalised_text) in CHARACTERS, not bytes. Denormalised so a "
            "bounds check never has to load the full text -- the checker runs "
            "~600 times per paper."
        ),
    )
    processing_version = models.IntegerField(
        default=1,
        help_text=(
            "Which parser produced this chunk. A bump creates NEW rows with NEW "
            "UUIDs rather than editing these, which is the only reason "
            "embeddings can coexist across versions despite "
            "content_embedding's unique (content_type, content_id)."
        ),
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Row creation timestamp"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Row last-modified timestamp"
    )

    class Meta:
        db_table = "df_chunk"
        ordering = ["artifact", "chunk_index"]
        constraints = [
            # Idempotency by construction: re-running the parser at the same
            # version cannot duplicate a chunk, so a crashed run is safe to
            # retry without checking first (09.2 -- the database enforces it).
            models.UniqueConstraint(
                fields=["artifact", "chunk_index", "processing_version"],
                name="df_chunk_artifact_index_version_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(char_count__gte=0),
                name="df_chunk_char_count_nonneg",
            ),
        ]
        indexes = [
            # Retrieval and re-processing both filter on the active version.
            models.Index(
                fields=["processing_version"],
                name="df_chunk_version_idx",
            ),
            models.Index(fields=["text_hash"], name="df_chunk_hash_idx"),
        ]
        verbose_name = "Data Factory chunk"
        verbose_name_plural = "Data Factory chunks"

    def __str__(self) -> str:
        return f"chunk {self.chunk_index} of {self.artifact_id} (v{self.processing_version})"


class DfAtom(models.Model):
    """One verifiable claim, one exact span, one source.

    An atom is an OBSERVATION, not a fact. Two T1 sources that disagree produce
    two atoms linked as contradicting -- which is why there is no merged
    ``claim`` row (06_DESIGN.md decision 5.2). Corroboration, contradiction and
    composition all arrive in Act II as ``df_atom_link``.
    """

    # A newly extracted atom has NOT been verified. PENDING is distinct from
    # UNPROVEN and conflating them would be a real bug: UNPROVEN is a VERDICT
    # ("the verifier looked and could not prove it") and kills a counting-format
    # question, whereas PENDING only means "not yet examined". 06_DESIGN.md 1.2
    # lists three states; this fourth one is the extraction-time default.
    STATE_PENDING = "PENDING"
    STATE_TRUE = "TRUE"
    STATE_FALSE = "FALSE"
    STATE_UNPROVEN = "UNPROVEN"
    VERIFICATION_STATE_CHOICES = [
        (STATE_PENDING, "Pending - extracted, not yet verified"),
        (STATE_TRUE, "True - the cited span supports the claim"),
        (STATE_FALSE, "False - the cited span contradicts the claim"),
        (STATE_UNPROVEN, "Unproven - the span neither supports nor contradicts"),
    ]

    # States an atom may hold and still be offered to a product. FALSE and
    # UNPROVEN are retrievable for explanation purposes but never citable.
    CITABLE_STATES = (STATE_TRUE,)

    # Stop re-verifying an atom that has already failed this many times; it is
    # cheaper to leave it than to keep spending tokens on it
    # (01_AGENT_ARCHITECTURE.md 2.5, memory item 2).
    MAX_VERIFICATION_ATTEMPTS = 3

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the atom",
    )
    chunk = models.ForeignKey(
        DfChunk,
        on_delete=models.PROTECT,
        related_name="atoms",
        help_text=(
            "The chunk whose text this claim's span indexes into. PROTECT: an "
            "atom without its chunk cannot be verified or explained, and "
            "published questions cite it."
        ),
    )
    claim_text = models.TextField(
        help_text=(
            "ONE verifiable assertion, in plain prose. Not a paragraph, not a "
            "summary. If it needs 'and' to join two independently checkable "
            "facts, it is two atoms."
        ),
    )
    char_start = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text=(
            "Inclusive start offset into chunk.normalised_text, in CHARACTERS. "
            "Computed by code, never by hand."
        ),
    )
    char_end = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text=(
            "Exclusive end offset, so text[char_start:char_end] is the "
            "supporting span. char_end == char_count is valid and means the "
            "span reaches the end of the chunk."
        ),
    )
    source_ref_snapshot = models.JSONField(
        help_text=(
            "FROZEN citation as it was at extraction: url, publisher, "
            "published_at, retrieved_at, tier. Deliberately duplicated from "
            "df_artifact and NEVER refreshed -- a citation sold to a student "
            "must not change under them if a source is later re-graded. It is "
            "not a cache; drift from the canonical row is the feature. Also "
            "makes an atom self-sufficient for display, avoiding three joins on "
            "the hottest read path in the system."
        ),
    )
    verification_state = models.CharField(
        max_length=10,
        choices=VERIFICATION_STATE_CHOICES,
        default=STATE_PENDING,
        help_text="Result of the last verification attempt. PENDING until first examined.",
    )
    verification_failure_count = models.IntegerField(
        default=0,
        help_text=(
            "Times verification has failed for this atom. The retriever skips "
            "atoms at or above MAX_VERIFICATION_ATTEMPTS so tokens are not "
            "burned retrying known-bad extractions."
        ),
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When verification_state was last set. Null while PENDING.",
    )
    valid_from = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "When this claim became true. Null means timeless or unknown-start "
            "(a static fact), which is treated as always-valid."
        ),
    )
    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "When it stopped being true. NULL MEANS STILL TRUE. This window is "
            "what makes temporal fairness a filter rather than a heuristic -- a "
            "student is never penalised for information valid at exam time "
            "(00_MASTER_RECAP.md 14.4)."
        ),
    )
    confidence = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="0.0-1.0 extraction confidence. Distinct from verification_state.",
    )
    processing_version = models.IntegerField(
        default=1,
        help_text="Which extractor produced this atom. See DfChunk.processing_version.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Row creation timestamp"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Row last-modified timestamp"
    )

    class Meta:
        db_table = "df_atom"
        ordering = ["chunk", "char_start"]
        constraints = [
            # 09.2: the DATABASE enforces this, not the code. These hold even if
            # the span checker is bypassed, a fixture is hand-written, or a
            # future bulk_create skips validation -- which is exactly when a
            # corrupt span would otherwise get in.
            models.CheckConstraint(
                condition=models.Q(char_start__gte=0),
                name="df_atom_char_start_nonneg",
            ),
            models.CheckConstraint(
                condition=models.Q(char_end__gt=models.F("char_start")),
                name="df_atom_span_nonempty",
            ),
            models.CheckConstraint(
                condition=models.Q(verification_failure_count__gte=0),
                name="df_atom_failcount_nonneg",
            ),
        ]
        indexes = [
            # The retriever's hot filter: active version + usable state.
            models.Index(
                fields=["processing_version", "verification_state"],
                name="df_atom_version_state_idx",
            ),
            # Temporal filtering for as-of-date retrieval (14.4).
            models.Index(
                fields=["valid_from", "valid_until"],
                name="df_atom_validity_idx",
            ),
        ]
        verbose_name = "Data Factory atom"
        verbose_name_plural = "Data Factory atoms"

    def __str__(self) -> str:
        preview = self.claim_text[:60]
        return f"[{self.verification_state}] {preview}"

    @property
    def is_citable(self) -> bool:
        """Whether this atom may back a published claim.

        State only. The source tier is the OTHER half of the test and lives in
        ``source_ref_snapshot["tier"]``; a caller needing both must check both,
        because a TRUE atom from a T3 source still cannot be cited.
        """
        return self.verification_state in self.CITABLE_STATES

    @property
    def span_length(self) -> int:
        """Characters in the supporting span."""
        return self.char_end - self.char_start
