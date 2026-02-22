"""
Embedding Service

Generates 384-dimensional embeddings using sentence-transformers.
Used for semantic search and RAG retrieval.
"""

from typing import List, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """
    Service for generating semantic embeddings.

    Model: all-MiniLM-L6-v2 (384 dimensions)
    Purpose: Enable semantic search across chunks.
    """

    MODEL_NAME = "all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384

    # Lazy-load the model to avoid import issues during testing
    _model = None

    @classmethod
    def _get_model(cls) -> Any:
        """Lazy load sentence-transformers model."""
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                cls._model = SentenceTransformer(cls.MODEL_NAME)
                logger.info("embedding_model_loaded", model=cls.MODEL_NAME)
            except ImportError:
                logger.error("sentence_transformers_not_installed")
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Run: pip install sentence-transformers"
                )
        return cls._model

    @classmethod
    def generate_embedding(cls, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of 384 floats (embedding vector)
        """
        if not text or len(text.strip()) == 0:
            logger.warning("empty_text_for_embedding")
            return [0.0] * cls.EMBEDDING_DIM

        model = cls._get_model()

        # Generate embedding
        embedding = model.encode(text, convert_to_numpy=True)

        # Convert to list
        embedding_list = embedding.tolist()

        logger.debug(
            "embedding_generated",
            text_length=len(text),
            embedding_dim=len(embedding_list),
        )

        return embedding_list  # type: ignore

    @classmethod
    def generate_embeddings_batch(cls, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch processing).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            logger.warning("empty_batch_for_embeddings")
            return []

        model = cls._get_model()

        # Filter empty texts
        valid_texts = [t for t in texts if t and len(t.strip()) > 0]

        if not valid_texts:
            logger.warning("no_valid_texts_in_batch")
            return [[0.0] * cls.EMBEDDING_DIM] * len(texts)

        # Generate embeddings in batch
        embeddings = model.encode(valid_texts, convert_to_numpy=True)

        # Convert to list of lists
        embeddings_list = [emb.tolist() for emb in embeddings]

        logger.info(
            "batch_embeddings_generated",
            batch_size=len(valid_texts),
            embedding_dim=cls.EMBEDDING_DIM,
        )

        return embeddings_list

    @classmethod
    def create_embedding_record(
        cls, content_type: str, content_id: str, text: str
    ) -> Dict[str, Any]:
        """
        Create embedding record dictionary.

        Args:
            content_type: Type of content ('chunk', 'article', etc.)
            content_id: UUID of the content
            text: Text to embed

        Returns:
            Dictionary ready for Embedding model creation
        """
        embedding_vector = cls.generate_embedding(text)

        return {
            "content_type": content_type,
            "content_id": content_id,
            "vector": embedding_vector,
            "model_name": cls.MODEL_NAME,
        }
