"""
Content Engine Test Factories

Using factory_boy to create test fixtures for all Content Engine models.
"""

import uuid

import factory
from factory.django import DjangoModelFactory
from faker import Faker

from engines.content.models import Asset, Chunk, Document, Embedding, IngestionJob

fake = Faker()


class DocumentFactory(DjangoModelFactory):
    """Factory for Document model."""

    class Meta:
        model = Document

    id = factory.LazyFunction(uuid.uuid4)
    title = factory.Faker("sentence", nb_words=5)
    file_path = factory.Faker("file_path", depth=3, extension="pdf")
    source_type = factory.Iterator(["static", "dynamic"])
    source_edition = factory.Faker("word")
    source_version = "1.0"
    isbn = factory.Faker("isbn13")
    publication_year = factory.Faker("year")
    metadata = factory.Dict(
        {"author": factory.Faker("name"), "publisher": factory.Faker("company")}
    )


class ChunkFactory(DjangoModelFactory):
    """Factory for Chunk model."""

    class Meta:
        model = Chunk

    id = factory.LazyFunction(uuid.uuid4)
    chunk_text = factory.Faker("text", max_nb_chars=1200)
    chunk_index = factory.Sequence(lambda n: n)
    page_number = factory.Faker("random_int", min=1, max=500)
    source_type = "static"
    document = factory.SubFactory(DocumentFactory)
    chapter_name = factory.Faker("sentence", nb_words=3)
    quality_flag = "high"
    confidence_score = 1.0


class EmbeddingFactory(DjangoModelFactory):
    """Factory for Embedding model."""

    class Meta:
        model = Embedding

    id = factory.LazyFunction(uuid.uuid4)
    content_type = "chunk"
    content_id = factory.LazyFunction(uuid.uuid4)
    vector = factory.LazyFunction(
        lambda: [fake.random.uniform(-1, 1) for _ in range(384)]
    )
    model_name = "all-MiniLM-L6-v2"


class AssetFactory(DjangoModelFactory):
    """Factory for Asset model."""

    class Meta:
        model = Asset

    id = factory.LazyFunction(uuid.uuid4)
    chunk = factory.SubFactory(ChunkFactory)
    asset_type = factory.Iterator(["table", "diagram", "formula"])
    asset_url = factory.Faker("url")
    metadata = factory.Dict(
        {"format": "png", "size": factory.Faker("random_int", min=1000, max=50000)}
    )


class IngestionJobFactory(DjangoModelFactory):
    """Factory for IngestionJob model."""

    class Meta:
        model = IngestionJob

    id = factory.LazyFunction(uuid.uuid4)
    document = factory.SubFactory(DocumentFactory)
    status = "pending"
    error_log = ""
    total_pages = factory.Faker("random_int", min=10, max=500)
    processed_pages = 0
    chunks_created = 0
