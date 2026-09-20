from __future__ import annotations

import logging
from typing import Any

from orca.translation.base import (
    TranslationError,
    TranslationProvider,
    TranslationRequest,
    TranslationResult,
    TranslationUnavailableError,
)
from orca.translation.bhashini import BhashiniTranslationAdapter
from orca.translation.mock import MockTranslationAdapter

logger = logging.getLogger(__name__)


class TieredTranslationService(TranslationProvider):
    """Tiered translation orchestrator using Bhashini as primary and Mock dictionary as fallback."""

    def __init__(
        self,
        primary_adapter: TranslationProvider | None = None,
        fallback_adapter: TranslationProvider | None = None,
        allow_fallback: bool = True,
    ) -> None:
        self.primary = primary_adapter or BhashiniTranslationAdapter()
        self.fallback = fallback_adapter or MockTranslationAdapter()
        self.allow_fallback = allow_fallback

    def is_available(self) -> bool:
        """Check if any operational translation provider is available."""
        if self.primary.is_available():
            return True
        return self.allow_fallback and self.fallback.is_available()

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate text with tiered fallback and explicit degraded provenance tracking."""
        if self.primary.is_available():
            try:
                return await self.primary.translate(request)
            except Exception as exc:
                logger.warning("Primary Bhashini translation failed (%s); evaluating fallback.", exc)
                if not self.allow_fallback:
                    raise TranslationError(f"Primary translation failed and fallback disabled: {exc}") from exc

        if self.allow_fallback and self.fallback.is_available():
            result = await self.fallback.translate(request)
            result.provenance["fallback_reason"] = "primary_bhashini_unavailable_or_failed"
            return result

        raise TranslationUnavailableError(
            "No translation provider is available (Bhashini unconfigured and fallback disabled)."
        )
