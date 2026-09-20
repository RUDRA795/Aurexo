from __future__ import annotations

import asyncio
from contextlib import contextmanager
import functools
import re
from typing import Any, Callable, Generator, List, Sequence

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExportResult, SpanExporter
from opentelemetry.trace import StatusCode, Tracer


SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "secret",
    "token",
    "credential",
    "auth",
    "api_key",
    "apikey",
    "cookie",
    "private_key",
)


def is_sensitive_key(key: str) -> bool:
    """Check if an attribute key name contains sensitive information markers."""
    k = key.lower()
    return any(pattern in k for pattern in SENSITIVE_KEY_SUBSTRINGS)


def sanitize_string(val: str) -> str:
    """Sanitize sensitive strings like credentials in URLs, query parameters, and Bearer tokens."""
    if not isinstance(val, str):
        return val

    # Basic auth in URLs: https://user:pass@example.com
    val = re.sub(r"(https?://[^:]+:)([^@]+)(@)", r"\1[REDACTED]\3", val)

    # Authorization tokens / Bearer tokens
    val = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.\~]+", r"\1[REDACTED]", val, flags=re.IGNORECASE)

    # Sensitive query params: ?token=..., &api_key=..., &password=...
    val = re.sub(
        r"([?&](?:api_?key|token|auth|secret|password)=)[^&]+",
        r"\1[REDACTED]",
        val,
        flags=re.IGNORECASE,
    )
    return val


def redact_attribute_value(key: str, value: Any) -> Any:
    """Recursively redact values associated with sensitive keys or sanitize string values."""
    if is_sensitive_key(key):
        return "[REDACTED]"

    if isinstance(value, str):
        return sanitize_string(value)
    elif isinstance(value, dict):
        return {k: redact_attribute_value(k, v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [redact_attribute_value(key, v) for v in value]
    elif isinstance(value, (int, float, bool)):
        return value
    return str(value)


def sanitize_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """Sanitize and redact a dictionary of span attributes."""
    sanitized: dict[str, Any] = {}
    for k, v in attributes.items():
        val = redact_attribute_value(k, v)
        # OpenTelemetry accepts int, float, bool, str, or sequences thereof
        if isinstance(val, (int, float, bool, str)):
            sanitized[k] = val
        elif isinstance(val, (list, tuple)) and all(isinstance(x, (int, float, bool, str)) for x in val):
            sanitized[k] = val
        else:
            sanitized[k] = str(val)
    return sanitized


class InMemorySpanExporter(SpanExporter):
    """Deterministic in-memory span exporter for testing and offline verification."""

    def __init__(self) -> None:
        self._spans: List[ReadableSpan] = []
        self._is_shutdown = False

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if self._is_shutdown:
            return SpanExportResult.FAILURE
        self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def get_finished_spans(self) -> List[ReadableSpan]:
        """Return a copy of all recorded spans."""
        return list(self._spans)

    def clear(self) -> None:
        """Clear recorded spans."""
        self._spans.clear()

    def shutdown(self) -> None:
        """Shutdown exporter."""
        self._is_shutdown = True


_TRACER_PROVIDER: TracerProvider | None = None


def setup_telemetry(
    service_name: str = "orca-service",
    exporter: SpanExporter | None = None,
    force_reset: bool = False,
) -> TracerProvider:
    """Initialize OpenTelemetry TracerProvider with optional exporter.

    If exporter is provided, adds a SimpleSpanProcessor for immediate span export.
    """
    global _TRACER_PROVIDER
    if _TRACER_PROVIDER is not None and not force_reset:
        return _TRACER_PROVIDER

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(exporter))

    try:
        trace.set_tracer_provider(provider)
    except Exception:
        pass
    trace._TRACER_PROVIDER = provider
    _TRACER_PROVIDER = provider
    return provider


def get_tracer(name: str = "orca") -> Tracer:
    """Return an OpenTelemetry Tracer instance."""
    return trace.get_tracer(name)


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    tracer_name: str = "orca",
) -> Generator[trace.Span, None, None]:
    """Context manager for tracing operations with automatic attribute sanitization and error capture."""
    tracer = get_tracer(tracer_name)
    safe_attrs = sanitize_attributes(attributes or {})

    with tracer.start_as_current_span(name, attributes=safe_attrs) as span:
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, description=str(exc))
            raise


def traced(
    span_name: str | None = None,
    tracer_name: str = "orca",
    record_args: bool = True,
) -> Callable:
    """Decorator to trace synchronous or asynchronous functions with automatic secret redaction."""

    def decorator(func: Callable) -> Callable:
        name = span_name or f"{func.__module__}.{func.__qualname__}"

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                attrs: dict[str, Any] = {"function.name": func.__name__}
                if record_args:
                    # Sanitize any string/dict kwargs passed
                    for k, v in kwargs.items():
                        attrs[f"arg.{k}"] = redact_attribute_value(k, v)
                with trace_span(name, attributes=attrs, tracer_name=tracer_name):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                attrs: dict[str, Any] = {"function.name": func.__name__}
                if record_args:
                    for k, v in kwargs.items():
                        attrs[f"arg.{k}"] = redact_attribute_value(k, v)
                with trace_span(name, attributes=attrs, tracer_name=tracer_name):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator
