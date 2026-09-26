from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any
import uuid

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentEventType(str, Enum):
    """Authoritative lifecycle and operational event taxonomy for ORCA agent execution streams."""

    # Run Lifecycle
    RUN_STARTED = "RUN_STARTED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_FAILED = "RUN_FAILED"
    RUN_CANCELLED = "RUN_CANCELLED"

    # Planning & Agent Node Lifecycle
    PLAN_CREATED = "PLAN_CREATED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_COMPLETED = "AGENT_COMPLETED"

    # Tool Execution & Resilience
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    RETRY = "RETRY"
    FALLBACK = "FALLBACK"

    # Evidence & Scientific Verification
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    EVIDENCE_CHECK = "EVIDENCE_CHECK"

    # Synthesis & Geospatial Outputs
    SYNTHESIS_STARTED = "SYNTHESIS_STARTED"
    SYNTHESIS_COMPLETED = "SYNTHESIS_COMPLETED"
    MAP_OVERLAY_UPDATED = "MAP_OVERLAY_UPDATED"

    # Real-time Web Search & Deep Research Events
    RESEARCH_STARTED = "RESEARCH_STARTED"
    SEARCH_QUERY = "SEARCH_QUERY"
    SEARCH_RESULT = "SEARCH_RESULT"
    SOURCE_OPENED = "SOURCE_OPENED"
    SOURCE_ADDED = "SOURCE_ADDED"
    DATA_SOURCE_STARTED = "DATA_SOURCE_STARTED"
    DATA_SOURCE_COMPLETED = "DATA_SOURCE_COMPLETED"
    EVIDENCE_MERGED = "EVIDENCE_MERGED"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    RESEARCH_PROGRESS = "RESEARCH_PROGRESS"
    RESEARCH_COMPLETED = "RESEARCH_COMPLETED"
    CITATION_ADDED = "CITATION_ADDED"

    # Connection / Keepalive
    HEARTBEAT = "HEARTBEAT"


# Strict security policies: substrings that must be redacted
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
    "bearer",
)

# Forbidden internal reasoning / chain-of-thought fields
FORBIDDEN_REASONING_KEYS = (
    "thought",
    "thinking",
    "reasoning",
    "chain_of_thought",
    "internal_monologue",
    "system_prompt",
    "raw_checkpoint_blob",
    "raw_netcdf",
)


def is_sensitive_key(key: str) -> bool:
    """Check if an attribute key name matches known secret or credential identifiers."""
    k = key.lower().strip()
    return any(pattern in k for pattern in SENSITIVE_KEY_SUBSTRINGS)


def is_forbidden_reasoning_key(key: str) -> bool:
    """Check if a key contains hidden internal model reasoning or chain-of-thought."""
    k = key.lower().strip()
    return any(pattern in k for pattern in FORBIDDEN_REASONING_KEYS)


def sanitize_string_value(val: str) -> tuple[str, bool]:
    """Sanitize string values removing passwords, bearer tokens, and secret parameters."""
    if not isinstance(val, str):
        return str(val), False

    redacted = False

    # 1. Basic auth credentials in URLs/URIs: scheme://user:pass@example.com
    if re.search(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^:]+:[^@]+@", val):
        val = re.sub(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^:]+:)([^@]+)(@)", r"\1[REDACTED]\3", val)
        redacted = True

    # 2. Authorization / Bearer tokens
    if re.search(r"Bearer\s+[A-Za-z0-9_\-\.\~]+", val, flags=re.IGNORECASE):
        val = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.\~]+", r"\1[REDACTED]", val, flags=re.IGNORECASE)
        redacted = True

    # 3. Sensitive URL query parameters: ?token=..., &api_key=...
    if re.search(r"[?&](?:api_?key|token|auth|secret|password)=[^&]+", val, flags=re.IGNORECASE):
        val = re.sub(
            r"([?&](?:api_?key|token|auth|secret|password)=)[^&]+",
            r"\1[REDACTED]",
            val,
            flags=re.IGNORECASE,
        )
        redacted = True

    return val, redacted


def sanitize_event_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Recursively redact secrets and eliminate hidden reasoning from event payloads.

    Guarantees:
    - Never emits forbidden chain-of-thought or model internal monologue.
    - Never leaks API keys, passwords, bearer tokens, or secret-bearing URLs.
    - Preserves typed metadata, tool statuses, latency, and scientific metrics.
    """
    if not isinstance(payload, dict):
        return {}, False

    sanitized: dict[str, Any] = {}
    was_redacted = False

    for k, v in payload.items():
        # Drop forbidden reasoning keys completely
        if is_forbidden_reasoning_key(k):
            was_redacted = True
            continue

        # Redact sensitive credential keys
        if is_sensitive_key(k):
            sanitized[k] = "[REDACTED]"
            was_redacted = True
            continue

        if isinstance(v, str):
            clean_str, r_flag = sanitize_string_value(v)
            sanitized[k] = clean_str
            if r_flag:
                was_redacted = True
        elif isinstance(v, dict):
            sub_dict, r_flag = sanitize_event_payload(v)
            sanitized[k] = sub_dict
            if r_flag:
                was_redacted = True
        elif isinstance(v, (list, tuple)):
            clean_list = []
            for item in v:
                if isinstance(item, str):
                    s_str, r_flag = sanitize_string_value(item)
                    clean_list.append(s_str)
                    if r_flag:
                        was_redacted = True
                elif isinstance(item, dict):
                    s_sub, r_flag = sanitize_event_payload(item)
                    clean_list.append(s_sub)
                    if r_flag:
                        was_redacted = True
                else:
                    clean_list.append(item)
            sanitized[k] = clean_list
        else:
            sanitized[k] = v

    return sanitized, was_redacted


class AgentEvent(BaseModel):
    """Strict typed event container for ORCA observable agent execution streams."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sequence: int = Field(default=0, ge=0)
    event_type: AgentEventType
    run_id: str
    thread_id: str
    trace_id: str
    timestamp: datetime = Field(default_factory=utc_now)

    # Execution context
    node: str | None = None
    agent: str | None = None
    tool: str | None = None
    status: str | None = None
    duration_ms: float | None = Field(default=None, ge=0.0)
    checkpoint_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    error_code: str | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    payload: dict[str, Any] = Field(default_factory=dict)
    redaction_status: str = "clean"

    @field_validator("timestamp")
    @classmethod
    def require_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @model_validator(mode="after")
    def enforce_content_policy(self) -> "AgentEvent":
        """Validate that payload is sanitized and redacted according to ORCA security policy."""
        clean_payload, redacted = sanitize_event_payload(self.payload)
        self.payload = clean_payload
        if redacted or self.redaction_status == "redacted":
            self.redaction_status = "redacted"
        return self

    def to_sse_dict(self) -> dict[str, Any]:
        """Convert event to serialized dictionary suitable for Server-Sent Events transmission."""
        return {
            "event_id": self.event_id,
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat(),
            "node": self.node,
            "agent": self.agent,
            "tool": self.tool,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "checkpoint_id": self.checkpoint_id,
            "evidence_ids": self.evidence_ids,
            "error_code": self.error_code,
            "progress": self.progress,
            "payload": self.payload,
            "redaction_status": self.redaction_status,
        }
