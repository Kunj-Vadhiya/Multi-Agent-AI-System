"""
Embedding Service module for RAG (Version 7).

Provides modular, configurable embedding generation:
- Local open-source ONNX embeddings via FastEmbed (default: BAAI/bge-small-en-v1.5)
  (completely free, local, no external paid API required).
- Resilient fallback to deterministic feature hashing if models cannot be initialized.
- Extensible base interface allowing future providers (e.g., HuggingFace, OpenAI, Cohere).
"""

import hashlib
import logging
import math
from abc import ABC, abstractmethod
from typing import List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class BaseEmbeddingProvider(ABC):
    """Abstract interface for embedding generation providers."""

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """Generate a normalized embedding vector for a search query string."""
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate normalized embedding vectors for a list of document chunk texts."""
        pass


class FastEmbedEmbeddingProvider(BaseEmbeddingProvider):
    """
    Local embedding provider utilizing FastEmbed and ONNX Runtime.
    Fast, efficient, and requires no external API keys.
    """

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL
        logger.info("Initializing FastEmbed embedding model: '%s'...", self.model_name)
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=self.model_name)
        logger.info("FastEmbed embedding model '%s' loaded successfully.", self.model_name)

    def embed_query(self, query: str) -> List[float]:
        if not query.strip():
            return [0.0] * 384
        embeddings_gen = self._model.embed([query])
        raw = list(embeddings_gen)[0]
        return [float(x) for x in raw]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        cleaned = [t if t.strip() else " " for t in texts]
        embeddings_gen = self._model.embed(cleaned)
        return [[float(x) for x in emb] for emb in embeddings_gen]


class DeterministicHashEmbeddingProvider(BaseEmbeddingProvider):
    """
    Fallback deterministic feature-hashing embedding provider.
    Ensures embedding operations never crash even in restricted offline test environments.
    """

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def _hash_text(self, text: str) -> List[float]:
        vec = [0.0] * self.dimension
        words = text.lower().split()
        if not words:
            return vec

        for word in words:
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            sign = 1.0 if ((h >> 4) % 2 == 0) else -1.0
            vec[idx] += sign

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_query(self, query: str) -> List[float]:
        return self._hash_text(query)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_text(t) for t in texts]


class EmbeddingService:
    """
    Configurable embedding service managing active provider.
    """

    def __init__(self, provider: Optional[BaseEmbeddingProvider] = None) -> None:
        if provider is not None:
            self._provider = provider
        else:
            try:
                self._provider = FastEmbedEmbeddingProvider()
            except Exception as err:
                logger.warning(
                    "FastEmbed initialization failed (%s). Falling back to DeterministicHashEmbeddingProvider.",
                    err,
                )
                self._provider = DeterministicHashEmbeddingProvider()

    def embed_query(self, query: str) -> List[float]:
        """Embed a search query string."""
        return self._provider.embed_query(query)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of document strings."""
        return self._provider.embed_documents(texts)


# Singleton instance
_embedding_service_instance: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create singleton EmbeddingService."""
    global _embedding_service_instance
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance
