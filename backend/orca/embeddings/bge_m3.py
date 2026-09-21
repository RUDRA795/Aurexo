from __future__ import annotations

import logging
from typing import Any, Sequence

from orca.embeddings.base import (
    EmbeddingDimensionMismatchError,
    EmbeddingProvider,
    EmbeddingProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class BgeM3EmbeddingProvider(EmbeddingProvider):
    """Production multilingual embedding provider based on BAAI/bge-m3 (1024-dimensional).

    Non-negotiable integrity constraints:
    - Never falls back to pseudo-random or mock embeddings.
    - If model runtime, PyTorch, or weights are unavailable, raises EmbeddingProviderUnavailableError.
    - dimension is strictly 1024.
    - Supports multilingual texts up to 8192 tokens.
    """

    MODEL_NAME = "BAAI/bge-m3"
    MODEL_DIMENSION = 1024
    MODEL_VERSION = "v1.0"
    MAX_TOKENS = 8192

    def __init__(
        self,
        model_path_or_name: str | None = None,
        *,
        device: str | None = None,
        backend: Any | None = None,
    ) -> None:
        self._target_model = model_path_or_name or self.MODEL_NAME
        self._device = device
        self._backend = backend
        self._initialized = False
        self._load_error: str | None = None

        if backend is not None:
            self._initialized = True

    @property
    def dimension(self) -> int:
        return self.MODEL_DIMENSION

    @property
    def model_name(self) -> str:
        return self._target_model

    @property
    def version(self) -> str:
        return self.MODEL_VERSION

    @property
    def is_available(self) -> bool:
        """Check if the real BGE-M3 model backend is available and loaded."""
        if self._initialized and self._backend is not None:
            return True
        if self._load_error is not None:
            return False
        # Try probing the runtime without raising
        try:
            self._ensure_loaded()
            return self._backend is not None
        except EmbeddingProviderUnavailableError:
            return False

    def _ensure_loaded(self) -> None:
        if self._initialized and self._backend is not None:
            return

        if self._load_error is not None:
            raise EmbeddingProviderUnavailableError(
                f"BGE-M3 model runtime unavailable: {self._load_error}"
            )

        # Attempt to load through standard sentence-transformers or fastembed
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading BGE-M3 embedding model from %s...", self._target_model)
            self._backend = SentenceTransformer(
                self._target_model,
                device=self._device,
            )
            self._initialized = True
        except ImportError as exc:
            self._load_error = (
                "sentence_transformers runtime is not installed in the environment. "
                "Explicit UNAVAILABLE status reported (no synthetic fallback allowed)."
            )
            raise EmbeddingProviderUnavailableError(self._load_error) from exc
        except Exception as exc:
            self._load_error = (
                f"Failed to load BGE-M3 weights from '{self._target_model}': {exc}. "
                "Explicit UNAVAILABLE status reported (no synthetic fallback allowed)."
            )
            raise EmbeddingProviderUnavailableError(self._load_error) from exc

    async def embed_text(self, text: str) -> list[float]:
        """Generate real 1024-d embedding vector for input text."""
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text string.")

        self._ensure_loaded()
        try:
            # sentence-transformers encode returns numpy ndarray
            vec = self._backend.encode(text, normalize_embeddings=True)
            res = [float(x) for x in vec]
            if len(res) != self.MODEL_DIMENSION:
                raise EmbeddingDimensionMismatchError(
                    f"BGE-M3 expected {self.MODEL_DIMENSION} dimensions, got {len(res)}"
                )
            return res
        except EmbeddingDimensionMismatchError:
            raise
        except Exception as exc:
            raise EmbeddingProviderUnavailableError(
                f"BGE-M3 inference failed during embed_text: {exc}"
            ) from exc

    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Generate real 1024-d embedding vectors for a batch of text strings."""
        if not texts:
            return []

        for i, t in enumerate(texts):
            if not t or not t.strip():
                raise ValueError(f"Cannot embed empty text at batch index {i}.")

        self._ensure_loaded()
        try:
            vecs = self._backend.encode(list(texts), normalize_embeddings=True)
            results = [[float(x) for x in v] for v in vecs]
            for r in results:
                if len(r) != self.MODEL_DIMENSION:
                    raise EmbeddingDimensionMismatchError(
                        f"BGE-M3 expected {self.MODEL_DIMENSION} dimensions, got {len(r)}"
                    )
            return results
        except EmbeddingDimensionMismatchError:
            raise
        except Exception as exc:
            raise EmbeddingProviderUnavailableError(
                f"BGE-M3 inference failed during embed_batch: {exc}"
            ) from exc
