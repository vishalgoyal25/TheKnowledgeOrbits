"""
Book Content Engine — Migration 0002
Phase E: Hybrid RAG Infrastructure

Creates:
  - knowledge_book_chunk table (BookChunk model)
  - GIN index on search_vector   → fast BM25 keyword search
  - HNSW index on content_embedding.vector → fast semantic vector search

The HNSW index replaces/supplements the existing IVFFlat on content_embedding.
At 500k+ rows HNSW delivers sub-50ms queries vs multi-second full scans.
CONCURRENTLY means no table lock — safe to run on live Supabase.
"""

import uuid

import django.db.models.deletion
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import migrations, models


class Migration(migrations.Migration):

    # CONCURRENTLY requires running outside a transaction block.
    atomic = False

    dependencies = [
        ("book_content", "0001_initial"),
    ]

    operations = [
        # ── Table: knowledge_book_chunk ───────────────────────────────────────
        migrations.CreateModel(
            name="BookChunk",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        help_text="Unique identifier for this book chunk.",
                    ),
                ),
                (
                    "chunk_text",
                    models.TextField(
                        help_text="~1200-character semantic chunk of the parent article.",
                    ),
                ),
                (
                    "chunk_index",
                    models.IntegerField(
                        help_text="Zero-based position of this chunk within the parent article.",
                    ),
                ),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("wiki",        "Wikipedia"),
                            ("govt",        "Government Source"),
                            ("news",        "News Source"),
                            ("ncert_blend", "NCERT + Wiki Blend"),
                            ("mixed",       "Multiple Sources"),
                        ],
                        default="wiki",
                        max_length=30,
                        help_text=(
                            "Origin of the source material used to generate this chunk. "
                            "Adding new sources requires only a new string value — no migration."
                        ),
                    ),
                ),
                (
                    "quality_flag",
                    models.CharField(
                        choices=[
                            ("high",         "High Quality"),
                            ("medium",       "Medium Quality"),
                            ("low",          "Low Quality"),
                            ("needs_review", "Needs Review"),
                        ],
                        default="high",
                        max_length=20,
                        help_text="Quality assessment from ChunkingService._assess_quality().",
                    ),
                ),
                (
                    "search_vector",
                    SearchVectorField(
                        null=True,
                        help_text=(
                            "PostgreSQL tsvector for BM25 full-text search. "
                            "Populated on save. Indexed with GIN."
                        ),
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="When this chunk was created.",
                    ),
                ),
                (
                    "book_content",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="book_content.bookcontent",
                        help_text=(
                            "The BookContent article this chunk belongs to. "
                            "Topic link is implicit: BookChunk → BookContent → Topic."
                        ),
                    ),
                ),
            ],
            options={
                "db_table":  "knowledge_book_chunk",
                "ordering":  ["book_content", "chunk_index"],
            },
        ),

        # ── unique_together: (book_content, chunk_index) ──────────────────────
        migrations.AlterUniqueTogether(
            name="BookChunk",
            unique_together={("book_content", "chunk_index")},
        ),

        # ── GIN index on search_vector (BM25 keyword search) ──────────────────
        migrations.AddIndex(
            model_name="BookChunk",
            index=GinIndex(
                fields=["search_vector"],
                name="book_chunk_fts_idx",
            ),
        ),

        # ── Regular indexes ───────────────────────────────────────────────────
        migrations.AddIndex(
            model_name="BookChunk",
            index=models.Index(
                fields=["source_type"],
                name="book_chunk_source_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="BookChunk",
            index=models.Index(
                fields=["book_content", "chunk_index"],
                name="book_chunk_content_order_idx",
            ),
        ),

        # ── HNSW index on content_embedding.vector ────────────────────────────
        # Replaces untuned IVFFlat. Scales to 10M+ rows. Sub-50ms at 500k entries.
        # CONCURRENTLY = no table lock, safe on live production DB.
        # m=16, ef_construction=64 are proven defaults for 384-dim embeddings.
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS content_embedding_hnsw_idx
                ON content_embedding
                USING hnsw (vector vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """,
            reverse_sql="""
                DROP INDEX CONCURRENTLY IF EXISTS content_embedding_hnsw_idx;
            """,
        ),
    ]
