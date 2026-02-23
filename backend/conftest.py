"""
Global pytest fixtures for TheKnowledgeOrbits.
"""

import os
from typing import Any

import pytest

# CRITICAL: Set Django settings BEFORE any Django imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")

import sys  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

# Import Django and setup
import django  # noqa: E402

# Safe mock for ML libraries to avoid 3GB+ downloads in CI
try:
    import sentence_transformers  # noqa: F401
except ImportError:
    mock_module = MagicMock()
    sys.modules["sentence_transformers"] = mock_module
    logger = MagicMock()
    sys.modules["sentence_transformers.SentenceTransformer"] = MagicMock()

# NOW it's safe to import Django/DRF components
from rest_framework.test import APIClient  # noqa: E402

import numpy as np  # noqa: E402

django.setup()

# ===== ML Mocking for High-Velocity Testing =====


@pytest.fixture(autouse=True)
def mock_ml_models(monkeypatch: Any) -> None:
    """
    Global autouse fixture to bypass heavy ML model loading.
    Mocks sentence-transformers and prevents 3GB+ RAM usage during tests.
    """
    # 1. Mock SentenceTransformers
    mock_st = MagicMock()

    def mock_encode(sentences: Any, **kwargs: Any) -> Any:
        """Returns synthetic 384-dim vectors instead of calling actual model."""
        if isinstance(sentences, str):
            return np.random.rand(384).astype(np.float32)
        return np.random.rand(len(sentences), 384).astype(np.float32)

    mock_st.return_value.encode.side_effect = mock_encode

    # Apply monkeypatch to the class import in services
    monkeypatch.setattr("sentence_transformers.SentenceTransformer", mock_st)

    # 2. Mock OpenAI/Groq if needed (prevent network calls)
    mock_openai = MagicMock()
    monkeypatch.setattr("openai.OpenAI", mock_openai)

    # 3. Suppress heavy logging during tests
    import structlog

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO and above
    )


@pytest.fixture
def api_client() -> Any:
    """
    Unauthenticated DRF test client.
    """
    return APIClient()


@pytest.fixture
def db_fixture(db) -> Any:  # type: ignore
    """
    Database fixture - ensures test database is available.
    """
    return db
