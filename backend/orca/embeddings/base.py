from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProviderUnavailableError(RuntimeError):
    """Raised when an embedding provider cannot be loaded or is unavailable."""
    pass


class EmbeddingDimensionMismatchError(ValueError):
    """Raised when an embedding vector dimension does not match expected size."""
    pass


class EmbeddingProvider(ABC):
    """Abstract base contract for text embedding providers."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate an embedding vector for a single text string."""
        raise NotImplementedError

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of text strings."""
        raise NotImplementedError

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality of generated embeddings."""
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier name of the underlying embedding model."""
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        """Version string of the embedding model."""
        raise NotImplementedError

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if model runtime and weights are ready for inference."""
        raise NotImplementedError
