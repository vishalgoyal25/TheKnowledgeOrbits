"""
Data Migration: Set Existing Content as Public

Run this script ONCE after applying ownership migrations.
"""

from typing import Any

import os
import sys
import django

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.base")
django.setup()

from engines.article_generation.models import Article  # noqa: E402
from engines.assessment.models import Quiz  # noqa: E402


from rich.console import Console  # noqa: E402

console = Console()


def migrate_articles() -> Any:
    """Mark all existing articles as public."""

    # Articles without created_by are system/admin articles
    articles = Article.objects.filter(created_by__isnull=True)
    count = articles.count()

    # Set as public
    articles.update(is_public=True)

    console.print(f"[green]✅ Migrated {count} articles to public[/green]")


def migrate_quizzes() -> Any:
    """Mark all existing quizzes as public."""

    # Quizzes without created_by are system/admin quizzes
    quizzes = Quiz.objects.filter(created_by__isnull=True)
    count = quizzes.count()

    # Set as public
    quizzes.update(is_public=True)

    console.print(f"[green]✅ Migrated {count} quizzes to public[/green]")


if __name__ == "__main__":
    console.print("[bold cyan]Starting content ownership migration...[/bold cyan]")
    console.print("=" * 50)

    migrate_articles()
    migrate_quizzes()

    console.print("=" * 50)
    console.print("[bold green]✅ Migration complete![/bold green]")
    console.print("")
    console.print("[bold]Summary:[/bold]")
    console.print(
        f"  - Public articles: [blue]{Article.objects.filter(is_public=True).count()}[/blue]"
    )
    console.print(
        f"  - Private articles: [blue]{Article.objects.filter(is_public=False).count()}[/blue]"
    )
    console.print(
        f"  - Public quizzes: [blue]{Quiz.objects.filter(is_public=True).count()}[/blue]"
    )
    console.print(
        f"  - Private quizzes: [blue]{Quiz.objects.filter(is_public=False).count()}[/blue]"
    )
