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
        """Generate embeddings via HuggingFace Inference API in sub-batches."""
        api_token = os.getenv("HF_API_TOKEN")
        if not api_token:
            logger.error("hf_api_token_missing")
            return cls._generate_local_embeddings(texts)

        headers = {"Authorization": f"Bearer {api_token}"}
        all_embeddings = []

        # Sub-batching to stay within API payload limits and prevent timeouts
        sub_batch_size = 20
        import time

        for i in range(0, len(texts), sub_batch_size):
            batch = texts[i : i + sub_batch_size]
            success = False

            for attempt in range(3):
                try:
                    response = requests.post(
                        cls.HF_API_URL,
                        headers=headers,
                        json={"inputs": batch, "options": {"wait_for_model": True}},
                        timeout=120,
                    )

                    if response.status_code == 200:
                        batch_result = response.json()
                        # Result might be a single list if batch size was 1
                        if isinstance(batch_result[0], float):
                            all_embeddings.append(batch_result)
                        else:
                            all_embeddings.extend(batch_result)
                        success = True
                        break
                    else:
                        logger.error(
                            "hf_api_error",
                            status=response.status_code,
                            body=response.text,
                        )
                        time.sleep(5)
                except requests.exceptions.Timeout:
                    logger.warning("hf_api_timeout_retrying", attempt=attempt + 1)
                    time.sleep(5)

            if not success:
                raise Exception(
                    f"Failed to generate embeddings via API after retries for batch starting at index {i}"
                )

        return all_embeddings

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

        # PROACTIVE MEMORY MANAGEMENT:
        # Default to API if token is present or we're on Render, to save RAM (512MB limit)
        is_render = os.getenv("RENDER", "False").lower() == "true"
        has_token = bool(os.getenv("HF_API_TOKEN"))

        default_use_api = "True" if (is_render or has_token) else "False"
        use_api = os.getenv("USE_EMBEDDING_API", default_use_api).lower() == "true"

        if use_api and has_token:
            logger.debug("generating_embeddings_via_api", count=len(valid_indices))
            try:
                valid_embeddings = cls._generate_api_embedding(valid_texts)
            except Exception as e:
                if not is_render:
                    logger.warning("hf_api_failed_falling_back_locally", error=str(e))
                    valid_embeddings = cls._generate_local_embeddings(valid_texts)
                else:
                    logger.error("hf_api_failed_on_render_critical", error=str(e))
                    raise e
        else:
            if is_render:
                logger.warning(
                    "local_embedding_on_render_dangerous",
                    msg="Memory limit 512MB likely to be exceeded",
                )
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
