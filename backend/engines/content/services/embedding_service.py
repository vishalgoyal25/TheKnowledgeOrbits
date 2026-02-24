"""
Embedding Service

Generates 384-dimensional embeddings using sentence-transformers (local)
or HuggingFace Inference API (cloud).
"""

import os
from typing import Any, Dict, List

import requests
import structlog

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """
    Service for generating semantic embeddings.
    Hybrid approach: Local ML for development, API for Cloud.

    Model: all-MiniLM-L6-v2 (384 dimensions)
    """

    MODEL_NAME = "all-MiniLM-L6-v2"
    HF_API_URL = f"https://router.huggingface.co/hf-inference/models/sentence-transformers/{MODEL_NAME}/pipeline/feature-extraction"
    EMBEDDING_DIM = 384

    # Lazy-load the local model to avoid massive RAM usage unless needed
    _local_model = None

    @classmethod
    def _get_local_model(cls) -> Any:
        """Lazy load local sentence-transformers model."""
        if cls._local_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                cls._local_model = SentenceTransformer(cls.MODEL_NAME)
                logger.info("local_embedding_model_loaded", model=cls.MODEL_NAME)
            except ImportError:
                logger.error("sentence_transformers_not_installed")
                raise ImportError("Run: pip install sentence-transformers")
        return cls._local_model

    @classmethod
    def _generate_api_embedding(cls, texts: List[str]) -> List[List[float]]:
        """Generate embeddings via HuggingFace Inference API."""
        api_token = os.getenv("HF_API_TOKEN")
        if not api_token:
            logger.error("hf_api_token_missing")
            # Fallback to local if token is missing
            return cls._generate_local_embeddings(texts)

        headers = {"Authorization": f"Bearer {api_token}"}

        try:
            response = requests.post(
                cls.HF_API_URL,
                headers=headers,
                json={"inputs": texts, "options": {"wait_for_model": True}},
                timeout=20,
            )

            if response.status_code == 200:
                result = response.json()
                # API returns a list of lists for multiple inputs
                return result
            else:
                logger.error(
                    "hf_api_error", status=response.status_code, body=response.text
                )
                raise Exception(f"HuggingFace API error: {response.text}")

        except Exception as e:
            logger.error("hf_api_exception", error=str(e))
            raise e

    @classmethod
    def generate_embedding(cls, text: str) -> List[float]:
        """Entry point for single text embedding."""
        return cls.generate_embeddings_batch([text])[0]

    @classmethod
    def generate_embeddings_batch(cls, texts: List[str]) -> List[List[float]]:
        """Entry point for batch embedding (Hybrid Logic)."""
        if not texts:
            return []

        # Maintain 1-to-1 mapping by tracking indices of valid strings
        results: List[List[float]] = [
            [0.0] * cls.EMBEDDING_DIM for _ in range(len(texts))
        ]
        valid_indices = [i for i, t in enumerate(texts) if t and len(t.strip()) > 0]

        if not valid_indices:
            return results

        valid_texts = [texts[i] for i in valid_indices]
        use_api = os.getenv("USE_EMBEDDING_API", "False").lower() == "true"

        if use_api:
            logger.debug("generating_embeddings_via_api", count=len(valid_indices))
            try:
                valid_embeddings = cls._generate_api_embedding(valid_texts)
            except Exception as e:
                logger.warning("hf_api_failed_falling_back_locally", error=str(e))
                valid_embeddings = cls._generate_local_embeddings(valid_texts)
        else:
            logger.debug("generating_embeddings_locally", count=len(valid_indices))
            valid_embeddings = cls._generate_local_embeddings(valid_texts)

        # Map back to original indices
        for i, idx in enumerate(valid_indices):
            results[idx] = valid_embeddings[i]

        return results

    @classmethod
    def _generate_local_embeddings(cls, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local sentence-transformers."""
        model = cls._get_local_model()
        embeddings_np = model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings_np]

    @classmethod
    def create_embedding_record(
        cls, content_type: str, content_id: str, text: str
    ) -> Dict[str, Any]:
        """Create dictionary for the Embedding model."""
        vector = cls.generate_embedding(text)
        return {
            "content_type": content_type,
            "content_id": content_id,
            "vector": vector,
            "model_name": cls.MODEL_NAME,
        }
