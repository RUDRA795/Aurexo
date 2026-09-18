from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from orca.schemas.orca_contract import ToolDefinition, ToolName


@dataclass(frozen=True)
class RegisteredTool:
    definition: ToolDefinition
    handler: Callable[..., Awaitable[Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[ToolName, RegisteredTool] = {}

    def register(self, definition: ToolDefinition, handler: Callable[..., Awaitable[Any]]) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Tool already registered: {definition.name.value}")
        self._tools[definition.name] = RegisteredTool(definition=definition, handler=handler)

    def get(self, name: ToolName) -> RegisteredTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Tool not registered: {name.value}") from exc

    def definitions(self) -> list[ToolDefinition]:
        return [item.definition for item in self._tools.values()]

    def as_llm_tools(self) -> list[dict[str, Any]]:
        """Vendor-neutral metadata; provider adapters convert this to their schema."""
        return [
            {
                "name": definition.name.value,
                "description": definition.description,
                "domains": definition.domains,
                "requires_location": definition.requires_location,
                "requires_time_window": definition.requires_time_window,
            }
            for definition in self.definitions()
        ]
