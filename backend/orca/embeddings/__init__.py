from __future__ import annotations

import os
from typing import Literal

from orca.embeddings.base import (
    EmbeddingDimensionMismatchError,
    EmbeddingProvider,
    EmbeddingProviderUnavailableError,
)
from orca.embeddings.bge_m3 import BgeM3EmbeddingProvider
from orca.embeddings.mock import DeterministicMockEmbeddingProvider


def get_embedding_provider(
    provider_name: str | None = None,
    *,
    dimension: int = 1536,
) -> EmbeddingProvider:
    """Factory to instantiate the appropriate EmbeddingProvider.

    Environment variable ORCA_EMBEDDING_PROVIDER controls default:
    - 'mock' or 'deterministic': DeterministicMockEmbeddingProvider
    - 'bge-m3' or 'production': BgeM3EmbeddingProvider
    """
    name = (provider_name or os.getenv("ORCA_EMBEDDING_PROVIDER", "mock")).lower().strip()
    if name in ("bge-m3", "bgem3", "production"):
        return BgeM3EmbeddingProvider()
    return DeterministicMockEmbeddingProvider(dimension=dimension)


__all__ = [
    "EmbeddingProvider",
    "EmbeddingProviderUnavailableError",
    "EmbeddingDimensionMismatchError",
    "DeterministicMockEmbeddingProvider",
    "BgeM3EmbeddingProvider",
    "get_embedding_provider",
]
