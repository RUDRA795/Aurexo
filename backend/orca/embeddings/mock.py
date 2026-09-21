from __future__ import annotations

import hashlib
import math
from typing import Sequence

from orca.embeddings.base import EmbeddingProvider


class DeterministicMockEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embedding generator for test and offline CI environments.

    Generates unit-normalized float vectors of fixed dimension (1536 or 1024) based on SHA-256
    digest tokens without requiring external network access, GPU, or model weights.
    """

    def __init__(self, dimension: int = 1536, version: str = "mock-v1"):
        if dimension <= 0:
            raise ValueError(f"Embedding dimension must be positive, got {dimension}.")
        self._dimension = dimension
        self._version = version

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return f"deterministic-mock-{self._dimension}d"

    @property
    def version(self) -> str:
        return self._version

    @property
    def is_available(self) -> bool:
        return True

    def embed_text_sync(self, text: str) -> list[float]:
        if not text:
            raise ValueError("Cannot embed empty text string.")

        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = [0.0] * self._dimension
        for i in range(self._dimension):
            byte_val = h[i % len(h)]
            # Spread pseudo-random values around zero
            vec[i] = float((byte_val % 31) - 15) / 15.0

        # L2-normalize vector to unit length
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [round(x / norm, 6) for x in vec]
        return vec

    async def embed_text(self, text: str) -> list[float]:
        return self.embed_text_sync(text)

    async def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_text_sync(t) for t in texts]
