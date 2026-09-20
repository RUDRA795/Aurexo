from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class TranslationError(Exception):
    """Base exception for translation errors."""
    pass


class TranslationUnavailableError(TranslationError):
    """Raised when translation service credentials or network are unavailable."""
    pass


class UnsupportedLanguageError(TranslationError):
    """Raised when the requested language is not supported."""
    pass


class TranslationRequest(BaseModel):
    """Request model for translating advisory or marine intelligence text."""
    text: str = Field(..., min_length=1, description="Source text to translate")
    source_language: str = Field(default="en", description="ISO 639-1 code (e.g. en)")
    target_language: str = Field(..., min_length=2, max_length=5, description="ISO 639-1 code (e.g. ml, kn, hi, ta)")
    domain: str = Field(default="marine_advisory", description="Domain context")


class TranslationResult(BaseModel):
    """Result model containing translated text and complete provenance."""
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    provider: str
    is_mock: bool = False
    latency_ms: float = 0.0
    translated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provenance: dict[str, Any] = Field(default_factory=dict)


class TranslationProvider(ABC):
    """Abstract base class for translation service providers."""

    @abstractmethod
    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate text according to request parameters."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is configured and available for requests."""
        pass
