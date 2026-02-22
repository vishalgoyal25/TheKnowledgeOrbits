"""
Global pytest fixtures for TheKnowledgeOrbits.
"""

import os
import pytest

# CRITICAL: Set Django settings BEFORE any Django imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")

# Import Django and setup
import django  # noqa: E402

django.setup()

# NOW it's safe to import Django/DRF components
from rest_framework.test import APIClient  # noqa: E402


@pytest.fixture
def api_client():
    """
    Unauthenticated DRF test client.
    """
    return APIClient()


@pytest.fixture
def db_fixture(db):
    """
    Database fixture - ensures test database is available.
    """
    return db
