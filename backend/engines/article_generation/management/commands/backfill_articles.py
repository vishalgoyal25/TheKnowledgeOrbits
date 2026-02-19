from django.core.management.base import BaseCommand
from engines.article_generation.models import Article
from engines.content.services.embedding_service import EmbeddingService
from engines.content.models import Embedding
import structlog

logger = structlog.get_logger(__name__)

class Command(BaseCommand):
    help = 'Backfill embeddings for existing AI-generated articles'

    def handle(self, *args, **options):
        self.stdout.write("Starting backfill for article embeddings...")
        
        articles = Article.objects.all()
        count = 0
        skipped = 0
        
        for article in articles:
            # Check if embedding already exists
            if Embedding.objects.filter(content_type='article', content_id=article.id).exists():
                skipped += 1
                continue
                
            try:
                # Generate embedding
                embedding_text = f"{article.title}\n{article.summary}\n{article.content[:1000]}"
                vector = EmbeddingService.generate_embedding(embedding_text)
                
                Embedding.objects.create(
                    content_type='article',
                    content_id=article.id,
                    vector=vector,
                    model_name=EmbeddingService.MODEL_NAME
                )
                self.stdout.write(f"Generated embedding for: {article.title}")
                count += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed for {article.title}: {str(e)}"))
        
        self.stdout.write(self.style.SUCCESS(f"Done! Created {count} embeddings. Skipped {skipped}."))
