"""
Current Affairs Engine - Integration Tests

End-to-end CA workflows.
"""

import pytest
from unittest.mock import patch
from rest_framework.test import APIClient
from django.utils import timezone
from engines.current_affairs.models import CASource, CAArticle, CAChunk
from engines.current_affairs.services.ca_processor import CAProcessorService
from engines.auth.models import User


@pytest.fixture
def authenticated_user():
    user = User.objects.create_user(email='test@test.com', password='pass')
    user.is_verified = True
    user.save()
    
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
class TestCAIngestionFlow:
    """Test complete CA ingestion workflow."""
    
    def test_scrape_process_flow(self, authenticated_user):
        """Test: Scrape Article → Process → Create Chunks."""
        client, user = authenticated_user
        
        # Create source
        source = CASource.objects.create(
            name='Test Source',
            url='https://test.com/rss',
            is_active=True
        )
        
        # Create article (simulating scrape)
        article = CAArticle.objects.create(
            source=source,
            title='Breaking News',
            url='https://test.com/news1',
            content='Important news content. ' * 100,
            published_at=timezone.now()
        )
        
        # Process article
        success = CAProcessorService.process_article(article)
        assert success
        
        # Verify chunks created
        article.refresh_from_db()
        assert article.chunk_count > 0
        assert CAChunk.objects.filter(ca_article=article).count() > 0

