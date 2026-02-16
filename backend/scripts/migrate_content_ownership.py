"""
Data Migration: Set Existing Content as Public

Run this script ONCE after applying ownership migrations.
"""

import os
import sys
import django

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.base')
django.setup()

from engines.article_generation.models import Article
from engines.assessment.models import Quiz


def migrate_articles():
    """Mark all existing articles as public."""
    
    # Articles without created_by are system/admin articles
    articles = Article.objects.filter(created_by__isnull=True)
    count = articles.count()
    
    # Set as public
    articles.update(is_public=True)
    
    print(f"✅ Migrated {count} articles to public")


def migrate_quizzes():
    """Mark all existing quizzes as public."""
    
    # Quizzes without created_by are system/admin quizzes
    quizzes = Quiz.objects.filter(created_by__isnull=True)
    count = quizzes.count()
    
    # Set as public
    quizzes.update(is_public=True)
    
    print(f"✅ Migrated {count} quizzes to public")


if __name__ == '__main__':
    print("Starting content ownership migration...")
    print("=" * 50)
    
    migrate_articles()
    migrate_quizzes()
    
    print("=" * 50)
    print("✅ Migration complete!")
    print()
    print("Summary:")
    print(f"  - Public articles: {Article.objects.filter(is_public=True).count()}")
    print(f"  - Private articles: {Article.objects.filter(is_public=False).count()}")
    print(f"  - Public quizzes: {Quiz.objects.filter(is_public=True).count()}")
    print(f"  - Private quizzes: {Quiz.objects.filter(is_public=False).count()}")
    