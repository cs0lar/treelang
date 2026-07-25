"""Ordered deterministic model and tool replay fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.ai.tool import ToolDefinition, normalize_tool_definition
from treelang.ai.transport import ModelRequest
from treelang.exceptions import ReplayMismatchError


@dataclass(frozen=True, slots=True)
class ToolReplayEntry:
    """One expected provider invocation and its deterministic output."""

    name: str
    arguments: dict[str, Any]
    output: Any


class ToolReplayProvider(ToolProvider):
    """Replay an ordered sequence of tool calls and reject any drift."""

    def __init__(
        self,
        tools: Sequence[ToolDefinition],
        entries: Sequence[ToolReplayEntry],
    ) -> None:
        super().__init__()
        normalized = [normalize_tool_definition(tool) for tool in tools]
        self.tools = {tool["name"]: tool for tool in normalized}
        self._entries = list(deepcopy(entries))
        self._index = 0

    async def list_tools(self) -> list[ToolDefinition]:
        return list(self.tools.values()) if self.tools else []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolOutput:
        if self._index >= len(self._entries):
            raise ReplayMismatchError(f"Unexpected tool call '{name}' after replay end")
        entry = self._entries[self._index]
        self._index += 1
        if entry.name != name or entry.arguments != arguments:
            raise ReplayMismatchError(
                f"Tool replay entry {self._index} did not match call '{name}'"
            )
        return ToolOutput(content=deepcopy(entry.output))

    def assert_consumed(self) -> None:
        """Raise when expected calls remain unconsumed."""
        remaining = len(self._entries) - self._index
        if remaining:
            raise ReplayMismatchError(f"Tool replay has {remaining} unconsumed entries")


@dataclass(frozen=True, slots=True)
class ModelReplayEntry:
    """One expected model request and completion or stream response."""

    request: dict[str, Any]
    response: str | tuple[str, ...]
    kind: Literal["complete", "stream"] = "complete"


class ModelReplayTransport:
    """Replay ordered model requests without credentials or network access."""

    def __init__(self, entries: Sequence[ModelReplayEntry]) -> None:
        self._entries = list(deepcopy(entries))
        self._index = 0

    def _next(self, request: ModelRequest, kind: Literal["complete", "stream"]) -> Any:
        if self._index >= len(self._entries):
            raise ReplayMismatchError(
                f"Unexpected model {kind} request after replay end"
            )
        entry = self._entries[self._index]
        self._index += 1
        if entry.kind != kind or entry.request != dict(request):
            raise ReplayMismatchError(
                f"Model replay entry {self._index} did not match {kind} request"
            )
        return deepcopy(entry.response)

    async def complete(self, request: ModelRequest) -> str:
        response = self._next(request, "complete")
        if not isinstance(response, str):
            raise ReplayMismatchError("Completion replay response must be text")
        return response

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        response = self._next(request, "stream")
        if not isinstance(response, tuple):
            raise ReplayMismatchError("Stream replay response must be a tuple")
        for chunk in response:
            yield chunk

    def assert_consumed(self) -> None:
        """Raise when expected requests remain unconsumed."""
        remaining = len(self._entries) - self._index
        if remaining:
            raise ReplayMismatchError(
                f"Model replay has {remaining} unconsumed entries"
            )


__all__ = [
    "ModelReplayEntry",
    "ModelReplayTransport",
    "ToolReplayEntry",
    "ToolReplayProvider",
]
