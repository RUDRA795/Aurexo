from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence


class BaseReranker(ABC):
    """Abstract interface for optional cross-encoder or neural reranking."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: Sequence[Any],
        top_k: int | None = None,
    ) -> tuple[list[Any], bool]:
        """Rerank candidates. Returns (reranked_candidates, was_reranked_flag)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Indicate whether the reranker model/runtime is loaded and active."""
        raise NotImplementedError


class NoOpReranker(BaseReranker):
    """Safe pass-through reranker when no neural cross-encoder is configured."""

    @property
    def is_available(self) -> bool:
        return False

    async def rerank(
        self,
        query: str,
        candidates: Sequence[Any],
        top_k: int | None = None,
    ) -> tuple[list[Any], bool]:
        # Return unmodified candidates without falsely claiming reranking occurred
        k = top_k or len(candidates)
        return list(candidates[:k]), False
