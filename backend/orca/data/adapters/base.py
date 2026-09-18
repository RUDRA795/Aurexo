from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

from orca.schemas.orca_contract import AccessMethod, SourceMetadata


class MarineAdapterError(Exception):
    """Base exception for all marine data adapter errors."""
    pass


class SourceUnavailableError(MarineAdapterError):
    """Raised when an external marine source cannot be reached or returns an error."""
    pass


class NetworkTimeoutError(SourceUnavailableError):
    """Raised when an external data source times out."""
    pass


class StaleDataError(MarineAdapterError):
    """Raised when data retrieved from a source violates freshness policies."""
    pass


class SchemaValidationError(MarineAdapterError):
    """Raised when external data cannot be parsed into the expected schema."""
    pass


class BaseMarineAdapter(ABC):
    """Base class for all real marine source adapters."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 12.0,
        verify_ssl: bool = False,
    ):
        self.timeout_seconds = float(os.getenv("ORCA_HTTP_TIMEOUT", str(timeout_seconds)))
        self.verify_ssl = os.getenv("ORCA_VERIFY_SSL", str(verify_ssl)).lower() in ("true", "1")

    def create_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout_seconds,
            verify=self.verify_ssl,
            follow_redirects=True,
            headers={"User-Agent": "ORCA-Marine-Intelligence/1.0 (Government-Research)"},
        )
