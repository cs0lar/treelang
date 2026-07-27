"""Deterministic model and tool fakes for downstream tests."""

from __future__ import annotations

import inspect
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from treelang.ai.capabilities import ModelCapabilities
from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.ai.tool import ToolDefinition, normalize_tool_definition
from treelang.ai.transport import ModelRequest, ModelUsage
from treelang.exceptions import ProviderResponseError, ToolNotFoundError

type FakeToolResult = (
    Any | BaseException | Callable[[dict[str, Any]], Any | Awaitable[Any]]
)


@dataclass(frozen=True, slots=True)
class FakeCompletion:
    """One queued completion response and its normalized token usage."""

    response: str | BaseException
    usage: ModelUsage = ModelUsage()


@dataclass(frozen=True, slots=True)
class FakeStream:
    """One queued stream response and its normalized token usage."""

    chunks: tuple[str, ...] | BaseException
    usage: ModelUsage = ModelUsage()


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One tool invocation recorded by :class:`FakeToolProvider`."""

    name: str
    arguments: dict[str, Any]


class FakeModelTransport:
    """Queue deterministic model responses while recording every request."""

    def __init__(
        self,
        *,
        completions: Sequence[FakeCompletion] = (),
        streams: Sequence[FakeStream] = (),
        capabilities: ModelCapabilities | None = None,
    ) -> None:
        self.completions = deque(deepcopy(completions))
        self.streams = deque(deepcopy(streams))
        self.completion_requests: list[dict[str, Any]] = []
        self.stream_requests: list[dict[str, Any]] = []
        self._capabilities = capabilities or ModelCapabilities()
        self._usage: ContextVar[ModelUsage] = ContextVar(
            "fake_model_usage", default=ModelUsage()
        )

    def capabilities(self, model: str) -> ModelCapabilities:
        """Return explicitly configured model capabilities."""
        return self._capabilities

    async def complete(self, request: ModelRequest) -> str:
        self.completion_requests.append(deepcopy(dict(request)))
        self._usage.set(ModelUsage())
        if not self.completions:
            raise ProviderResponseError("No fake completion response remains")
        completion = self.completions.popleft()
        if isinstance(completion.response, BaseException):
            raise completion.response
        self._usage.set(completion.usage)
        return completion.response

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        self.stream_requests.append(deepcopy(dict(request)))
        self._usage.set(ModelUsage())
        if not self.streams:
            raise ProviderResponseError("No fake stream response remains")
        stream = self.streams.popleft()
        if isinstance(stream.chunks, BaseException):
            raise stream.chunks
        for chunk in stream.chunks:
            yield chunk
        self._usage.set(stream.usage)

    def consume_usage(self) -> ModelUsage:
        """Return and clear usage in the current asynchronous context."""
        usage = self._usage.get()
        self._usage.set(ModelUsage())
        return usage

    def assert_consumed(self) -> None:
        """Raise if configured model responses remain unused."""
        if self.completions or self.streams:
            raise AssertionError(
                "Fake model has "
                f"{len(self.completions)} completions and "
                f"{len(self.streams)} streams remaining"
            )


class FakeToolProvider(ToolProvider):
    """Return configured tool results and record calls without application code."""

    def __init__(
        self,
        tools: Sequence[ToolDefinition] = (),
        *,
        results: Mapping[str, FakeToolResult] | None = None,
    ) -> None:
        super().__init__()
        normalized = [normalize_tool_definition(tool) for tool in tools]
        self.tools = {tool["name"]: tool for tool in normalized}
        self.results = dict(results or {})
        self.calls: list[ToolCall] = []

    async def list_tools(self) -> list[ToolDefinition]:
        return deepcopy(list(self.tools.values())) if self.tools else []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolOutput:
        self.calls.append(ToolCall(name=name, arguments=deepcopy(arguments)))
        assert self.tools is not None
        if name not in self.tools or name not in self.results:
            raise ToolNotFoundError(f"No fake result configured for tool '{name}'")
        configured = self.results[name]
        if isinstance(configured, BaseException):
            raise configured
        value = configured(arguments) if callable(configured) else configured
        if inspect.isawaitable(value):
            value = await value
        return ToolOutput(content=deepcopy(value))


__all__ = [
    "FakeCompletion",
    "FakeModelTransport",
    "FakeStream",
    "FakeToolProvider",
    "FakeToolResult",
    "ToolCall",
]
