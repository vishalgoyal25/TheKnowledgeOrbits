import structlog
from django.core.management.base import BaseCommand
from engines.content.models import Document, Chunk, Embedding, IngestionJob, Asset
from engines.knowledge.models import ChunkTopicMap

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Cleans the entire Content Engine data perfectly to allow for fresh massive ingestion."

    def handle(self, *args, **kwargs):
        self.stdout.write(
            self.style.WARNING("Starting Massive Content Engine Cleanup...")
        )

        # In PostgreSQL, cascaded deletes handle most of this, but it's safe to do manually.
        Asset.objects.all().delete()
        ChunkTopicMap.objects.all().delete()
        Embedding.objects.filter(content_type="chunk").delete()
        Chunk.objects.all().delete()
        IngestionJob.objects.all().delete()
        Document.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS("All tables in the Content Engine cleaned perfectly.")
        )
