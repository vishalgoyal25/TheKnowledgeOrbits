"""
Article Generation Engine - Model Tests

Tests for Article, ArticleSourceMap, ArticleGenerationJob models.
"""

import pytest
import uuid
from engines.article_generation.models import Article, ArticleSourceMap, ArticleGenerationJob
from engines.auth.models import User
from engines.knowledge.models import Program, Subject, Module, Topic
from engines.content.models import Document, Chunk


@pytest.fixture
def user():
    """Create test user."""
    return User.objects.create_user(email='test@example.com', password='pass')


@pytest.fixture
def topic():
    """Create test topic with full hierarchy."""
    program = Program.objects.create(name='UPSC CSE')
    subject = Subject.objects.create(name='Polity', program=program)
    module = Module.objects.create(name='Constitution', subject=subject)
    return Topic.objects.create(name='Test Topic', module=module, subject=subject)


@pytest.fixture
def document():
    """Create test document."""
    return Document.objects.create(
        title='Test Document',
        source_type='static',
        file_path='/test/path.pdf'
    )


@pytest.fixture
def chunk(document):
    """Create test chunk."""
    return Chunk.objects.create(
        document=document,
        chunk_index=0,
        chunk_text='Test chunk content about Article 370',
        source_type='static'
    )


@pytest.mark.django_db
class TestArticleModel:
    """Test Article model."""
    
    def test_create_article(self, topic):
        """Test creating article."""
        article = Article.objects.create(
            title='Test Article',
            content='Test content',
            topic=topic,
            word_count=100
        )
        
        assert article.title == 'Test Article'
        assert article.topic == topic
        assert article.read_time == 1  # 100 words / 200 = 0.5, rounded up to 1
    
    def test_article_has_uuid(self, topic):
        """Test article has UUID primary key."""
        article = Article.objects.create(
            title='Test',
            content='Content',
            topic=topic
        )
        
        assert isinstance(article.id, uuid.UUID)
        assert len(str(article.id)) == 36
    
    def test_slug_auto_generated(self, topic):
        """Test slug auto-generates from title."""
        article = Article.objects.create(
            title='My Test Article',
            content='Content',
            topic=topic
        )
        
        assert article.slug == 'my-test-article'
    
    def test_slug_unique_constraint(self, topic):
        """Test duplicate slugs get numbered."""
        Article.objects.create(title='Same Title', content='Content 1', topic=topic)
        article2 = Article.objects.create(title='Same Title', content='Content 2', topic=topic)
        
        assert article2.slug == 'same-title-1'
    
    def test_read_time_calculation(self, topic):
        """Test read time calculation."""
        article = Article.objects.create(
            title='Test',
            content='Content',
            topic=topic,
            word_count=600
        )
        
        assert article.read_time == 3  # 600 / 200 = 3
    
    def test_ownership_fields(self, topic, user):
        """Test ownership extension fields."""
        article = Article.objects.create(
            title='User Article',
            content='Content',
            topic=topic,
            created_by=user,
            is_public=False
        )
        
        assert article.created_by == user
        assert not article.is_public
        assert article.is_user_owned
    
    def test_is_user_owned_property(self, topic, user):
        """Test is_user_owned property."""
        # User-owned
        article1 = Article.objects.create(
            title='User Article',
            content='Content',
            topic=topic,
            created_by=user
        )
        assert article1.is_user_owned
        
        # System-owned
        article2 = Article.objects.create(
            title='System Article',
            content='Content',
            topic=topic,
            created_by=None
        )
        assert not article2.is_user_owned


@pytest.mark.django_db
class TestArticleSourceMapModel:
    """Test ArticleSourceMap model."""
    
    def test_create_source_map(self, topic, chunk):
        """Test creating article source map."""
        article = Article.objects.create(title='Test', content='Content', topic=topic)
        
        source_map = ArticleSourceMap.objects.create(
            article=article,
            chunk=chunk,
            relevance_weight=0.8,
            sequence_order=1
        )
        
        assert source_map.article == article
        assert source_map.chunk == chunk
        assert source_map.relevance_weight == 0.8
    
    def test_unique_article_chunk_constraint(self, topic, chunk):
        """Test article-chunk uniqueness."""
        article = Article.objects.create(title='Test', content='Content', topic=topic)
        
        ArticleSourceMap.objects.create(article=article, chunk=chunk)
        
        with pytest.raises(Exception):  # IntegrityError
            ArticleSourceMap.objects.create(article=article, chunk=chunk)
    
    def test_source_map_ordering(self, topic, chunk):
        """Test source maps ordered by sequence."""
        article = Article.objects.create(title='Test', content='Content', topic=topic)
        
        map2 = ArticleSourceMap.objects.create(article=article, chunk=chunk, sequence_order=2)
        
        # Create another chunk for different order
        chunk2 = Chunk.objects.create(
            document=chunk.document,
            chunk_index=1,
            chunk_text='Another chunk',
            source_type='static'
        )
        map1 = ArticleSourceMap.objects.create(article=article, chunk=chunk2, sequence_order=1)
        
        maps = list(article.source_chunks.all())
        assert maps[0] == map1
        assert maps[1] == map2


@pytest.mark.django_db
class TestArticleGenerationJobModel:
    """Test ArticleGenerationJob model."""
    
    def test_create_job(self, topic, user):
        """Test creating generation job."""
        job = ArticleGenerationJob.objects.create(
            topic=topic,
            requested_by=user,
            status='pending'
        )
        
        assert job.topic == topic
        assert job.status == 'pending'
    
    def test_job_status_choices(self, topic):
        """Test job status transitions."""
        job = ArticleGenerationJob.objects.create(
            topic=topic,
            status='pending'
        )
        
        job.status = 'processing'
        job.save()
        
        job.status = 'completed'
        job.save()
        
        assert job.status == 'completed'
