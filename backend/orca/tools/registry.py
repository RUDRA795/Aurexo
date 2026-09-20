from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import time
from typing import Any, Awaitable, Callable, Type

from pydantic import BaseModel, Field, ValidationError

from orca.schemas.orca_contract import DataQuality, Evidence, ToolDefinition, ToolName, utc_now
from orca.telemetry.tracer import trace_span


class ToolStatus(str, Enum):
    SUCCESS = "success"
    NO_DATA = "no_data"
    UNAVAILABLE = "unavailable"
    OUT_OF_DOMAIN = "out_of_domain"
    AUTH_REQUIRED = "auth_required"
    TIMEOUT = "timeout"
    ERROR = "error"
    FALLBACK = "fallback"
    DEGRADED = "degraded"
    SKIPPED = "skipped"


class ToolExecutionResult(BaseModel):
    """Uniform normalized output returned by all ORCA operational tools."""
    tool_name: str
    status: ToolStatus
    evidence: list[Evidence] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    timestamps: dict[str, str] = Field(default_factory=dict)
    duration_ms: float = 0.0
    quality: DataQuality = DataQuality.GOOD
    errors: list[str] = Field(default_factory=list)
    fallback_applied: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseMarineTool(ABC):
    """Abstract typed boundary for all ORCA operational tools."""
    name: str
    description: str
    parameter_schema: Type[BaseModel]

    def is_applicable(self, lat: float | None = None, lon: float | None = None, **kwargs: Any) -> bool:
        """Evaluate whether this tool is geographically and operationally applicable for given parameters."""
        return True

    @abstractmethod
    async def execute(self, params: Any) -> ToolExecutionResult:
        raise NotImplementedError


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    handler: Callable[..., Awaitable[ToolExecutionResult]]
    parameter_schema: Type[BaseModel] | None = None
    definition: ToolDefinition | None = None
    applicability_checker: Callable[..., bool] | None = None


class ToolRegistry:
    """Registry managing typed marine capability tools with parameter validation and normalization."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register_tool(self, tool: BaseMarineTool) -> None:
        """Register a BaseMarineTool instance."""
        name_key = tool.name.lower()
        if name_key in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")

        self._tools[name_key] = RegisteredTool(
            name=tool.name,
            description=tool.description,
            handler=tool.execute,
            parameter_schema=tool.parameter_schema,
            applicability_checker=getattr(tool, "is_applicable", None),
        )

    def register(
        self,
        definition: ToolDefinition,
        handler: Callable[..., Awaitable[Any]],
        parameter_schema: Type[BaseModel] | None = None,
    ) -> None:
        """Backwards-compatible registration via ToolDefinition."""
        name_str = definition.name.value if hasattr(definition.name, "value") else str(definition.name)
        name_key = name_str.lower()
        if name_key in self._tools:
            raise ValueError(f"Tool already registered: {name_str}")

        async def _wrapped_handler(params: Any) -> ToolExecutionResult:
            start_iso = utc_now().isoformat()
            t0 = time.perf_counter()
            try:
                res = await handler(params)
                elapsed = (time.perf_counter() - t0) * 1000.0
                if isinstance(res, ToolExecutionResult):
                    return res

                # Normalize evidence returns
                evidence_list = []
                if isinstance(res, Evidence):
                    evidence_list = [res]
                elif isinstance(res, list) and all(isinstance(x, Evidence) for x in res):
                    evidence_list = res

                return ToolExecutionResult(
                    tool_name=name_str,
                    status=ToolStatus.SUCCESS,
                    evidence=evidence_list,
                    timestamps={"started_at": start_iso, "completed_at": utc_now().isoformat()},
                    duration_ms=round(elapsed, 2),
                    metadata={"raw_result": str(res)[:200]},
                )
            except Exception as exc:
                elapsed = (time.perf_counter() - t0) * 1000.0
                return ToolExecutionResult(
                    tool_name=name_str,
                    status=ToolStatus.ERROR,
                    errors=[str(exc)],
                    timestamps={"started_at": start_iso, "completed_at": utc_now().isoformat()},
                    duration_ms=round(elapsed, 2),
                )

        self._tools[name_key] = RegisteredTool(
            name=name_str,
            description=definition.description,
            handler=_wrapped_handler,
            parameter_schema=parameter_schema,
            definition=definition,
        )

    def get(self, name: str | ToolName) -> RegisteredTool:
        name_str = name.value if hasattr(name, "value") else str(name)
        name_key = name_str.lower()
        try:
            return self._tools[name_key]
        except KeyError as exc:
            raise KeyError(f"Tool not registered: {name_str}") from exc

    def has(self, name: str | ToolName) -> bool:
        name_str = name.value if hasattr(name, "value") else str(name)
        return name_str.lower() in self._tools

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def definitions(self) -> list[ToolDefinition]:
        return [
            item.definition
            for item in self._tools.values()
            if item.definition is not None
        ]

    async def execute_tool(self, tool_name: str | ToolName, parameters: dict[str, Any]) -> ToolExecutionResult:
        """Validate parameters and execute tool with OpenTelemetry tracing and error normalization."""
        name_str = tool_name.value if hasattr(tool_name, "value") else str(tool_name)
        tool_entry = self.get(name_str)

        # 0. Check geographic/operational applicability before parameter validation or HTTP requests
        if tool_entry.applicability_checker is not None:
            lat = parameters.get("lat") if isinstance(parameters, dict) else getattr(parameters, "lat", None)
            lon = parameters.get("lon") if isinstance(parameters, dict) else getattr(parameters, "lon", None)
            if lat is None and isinstance(parameters, dict):
                lat = parameters.get("origin_lat")
                lon = parameters.get("origin_lon")
            if lat is not None and lon is not None:
                if not tool_entry.applicability_checker(lat=lat, lon=lon):
                    return ToolExecutionResult(
                        tool_name=name_str,
                        status=ToolStatus.OUT_OF_DOMAIN,
                        errors=[f"Location ({lat}, {lon}) is out of operational domain for tool '{name_str}'"],
                        quality=DataQuality.UNRELIABLE,
                    )

        # 1. Parameter validation against typed schema
        validated_params: Any = parameters
        if tool_entry.parameter_schema is not None:
            try:
                if isinstance(parameters, dict):
                    validated_params = tool_entry.parameter_schema(**parameters)
                elif isinstance(parameters, tool_entry.parameter_schema):
                    validated_params = parameters
                else:
                    raise ValueError(f"Parameters must match schema {tool_entry.parameter_schema.__name__}")
            except ValidationError as val_err:
                return ToolExecutionResult(
                    tool_name=name_str,
                    status=ToolStatus.ERROR,
                    errors=[f"Parameter validation error: {val_err}"],
                    quality=DataQuality.UNRELIABLE,
                )

        # 2. OpenTelemetry span wrapping execution
        start_iso = utc_now().isoformat()
        t0 = time.perf_counter()
        with trace_span(f"tool.{name_str}", attributes={"parameters": str(parameters)[:200]}):
            try:
                result = await tool_entry.handler(validated_params)
                elapsed = (time.perf_counter() - t0) * 1000.0
                if isinstance(result, ToolExecutionResult):
                    result.duration_ms = round(elapsed, 2)
                    if not result.timestamps.get("started_at"):
                        result.timestamps["started_at"] = start_iso
                    if not result.timestamps.get("completed_at"):
                        result.timestamps["completed_at"] = utc_now().isoformat()
                    return result

                return ToolExecutionResult(
                    tool_name=name_str,
                    status=ToolStatus.SUCCESS,
                    timestamps={"started_at": start_iso, "completed_at": utc_now().isoformat()},
                    duration_ms=round(elapsed, 2),
                )
            except Exception as exc:
                elapsed = (time.perf_counter() - t0) * 1000.0
                return ToolExecutionResult(
                    tool_name=name_str,
                    status=ToolStatus.ERROR,
                    errors=[str(exc)],
                    timestamps={"started_at": start_iso, "completed_at": utc_now().isoformat()},
                    duration_ms=round(elapsed, 2),
                )
