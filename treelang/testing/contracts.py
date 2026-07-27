"""Framework-neutral contract suites for model and tool integrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from treelang.ai.provider import ToolProvider
from treelang.ai.tool import ToolDefinition, normalize_tool_definition
from treelang.ai.transport import (
    ModelRequest,
    ModelTransport,
    ModelUsage,
    UsageAwareTransport,
)


@dataclass(frozen=True, slots=True)
class CompletionContract:
    """Expected completion behavior for one model request."""

    request: ModelRequest
    response: str
    usage: ModelUsage = ModelUsage()


@dataclass(frozen=True, slots=True)
class StreamContract:
    """Expected streaming behavior for one model request."""

    request: ModelRequest
    chunks: tuple[str, ...]
    usage: ModelUsage = ModelUsage()


@dataclass(frozen=True, slots=True)
class ModelTransportContract:
    """Verify normalized completion, streaming, and usage behavior."""

    completion: CompletionContract
    stream: StreamContract

    async def verify(
        self,
        transport: ModelTransport,
        usage_reporter: UsageAwareTransport,
    ) -> None:
        completion = await transport.complete(self.completion.request)
        if not isinstance(completion, str):
            raise AssertionError("Model completion must return text")
        if completion != self.completion.response:
            raise AssertionError(
                f"Completion {completion!r} != {self.completion.response!r}"
            )
        self._assert_usage(usage_reporter, self.completion.usage, "completion")

        chunks = [chunk async for chunk in transport.stream(self.stream.request)]
        if not all(isinstance(chunk, str) and chunk for chunk in chunks):
            raise AssertionError("Model stream must yield non-empty text chunks")
        if chunks != list(self.stream.chunks):
            raise AssertionError(f"Stream chunks {chunks!r} != {self.stream.chunks!r}")
        self._assert_usage(usage_reporter, self.stream.usage, "stream")

    @staticmethod
    def _assert_usage(
        reporter: UsageAwareTransport,
        expected: ModelUsage,
        operation: str,
    ) -> None:
        actual = reporter.consume_usage()
        if actual != expected:
            raise AssertionError(f"{operation} usage {actual!r} != {expected!r}")
        if reporter.consume_usage() != ModelUsage():
            raise AssertionError(f"{operation} usage must clear after consumption")


@dataclass(frozen=True, slots=True)
class ToolCallContract:
    """Expected provider output for one tool invocation."""

    name: str
    arguments: dict[str, Any]
    output: Any


@dataclass(frozen=True, slots=True)
class ToolProviderContract:
    """Verify discovery, direct lookup, and provider-neutral tool output."""

    tools: tuple[ToolDefinition, ...]
    calls: tuple[ToolCallContract, ...] = ()

    async def verify(self, provider: ToolProvider) -> None:
        expected = [normalize_tool_definition(tool) for tool in self.tools]
        discovered = [
            normalize_tool_definition(tool) for tool in await provider.list_tools()
        ]
        if discovered != expected:
            raise AssertionError(f"Discovered tools {discovered!r} != {expected!r}")
        for tool in expected:
            direct = normalize_tool_definition(
                await provider.get_tool_definition(tool["name"]),
                expected_name=tool["name"],
            )
            if direct != tool:
                raise AssertionError(
                    f"Direct definition for {tool['name']!r} differs from discovery"
                )
        for call in self.calls:
            output = await provider.call_tool(call.name, call.arguments)
            if output.content != call.output:
                raise AssertionError(
                    f"Tool {call.name!r} output {output.content!r} != {call.output!r}"
                )


__all__ = [
    "CompletionContract",
    "ModelTransportContract",
    "StreamContract",
    "ToolCallContract",
    "ToolProviderContract",
]
