"""
Global pytest fixtures for TheKnowledgeOrbits.
"""

import os
import sys
from typing import Any
from unittest.mock import MagicMock

# CRITICAL: Set Django settings BEFORE any Django imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")

import django  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402

# ===== THE VIRTUAL ML BRIDGE (CI OPTIMIZATION) =====


def _get_mock_vector(sentences: Any) -> np.ndarray:
    """Helper to generate synthetic embedding vectors."""
    if isinstance(sentences, str):
        return np.random.rand(384).astype(np.float32)
    count = len(sentences) if hasattr(sentences, "__len__") else 1
    return np.random.rand(count, 384).astype(np.float32)


# Mock SentenceTransformers
try:
    import sentence_transformers  # noqa: F401
except ImportError:
    mock_st_module = MagicMock()
    mock_model_instance = MagicMock()
    # Configure the instance to return real numpy data that .tolist() can be called on
    mock_model_instance.encode.side_effect = _get_mock_vector

    mock_model_class = MagicMock(return_value=mock_model_instance)
    mock_st_module.SentenceTransformer = mock_model_class
    sys.modules["sentence_transformers"] = mock_st_module

# Mock OpenAI & Groq
try:
    import openai  # noqa: F401
except ImportError:
    sys.modules["openai"] = MagicMock()

try:
    import groq  # noqa: F401
except ImportError:
    sys.modules["groq"] = MagicMock()

# Initialize Django
django.setup()

from rest_framework.test import APIClient  # noqa: E402

# ===== FIXTURES =====


@pytest.fixture(autouse=True)
def mock_ml_models(monkeypatch: Any) -> None:
    """
    Global autouse fixture to ensure all ML services use our virtual bridge.
    """
    # 1. Patch SentenceTransformer
    # We use sys.modules directly to avoid F811 redefinition errors
    st_module = sys.modules.get("sentence_transformers")
    if st_module:
        try:
            # If it's a real module, path it. If it's our mock, it's already patched.
            if not isinstance(st_module, MagicMock):
                mock_instance = MagicMock()
                mock_instance.encode.side_effect = _get_mock_vector
                monkeypatch.setattr(
                    "sentence_transformers.SentenceTransformer",
                    MagicMock(return_value=mock_instance),
                )
        except Exception:
            pass

    # 2. Patch OpenAI & Groq using sys.modules to avoid F811
    openai_mod = sys.modules.get("openai")
    if openai_mod:
        monkeypatch.setattr(openai_mod, "OpenAI", MagicMock())

    groq_mod = sys.modules.get("groq")
    if groq_mod:
        monkeypatch.setattr(groq_mod, "Groq", MagicMock())

    # 3. Suppress heavy logging
    import structlog  # noqa: E402

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(20),
    )


@pytest.fixture
def api_client() -> Any:
    """Unauthenticated DRF test client."""
    return APIClient()


@pytest.fixture
def db_fixture(db: Any) -> Any:
    """Database fixture - ensures test database is available."""
    return db
