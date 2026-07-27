"""Supported deterministic fixtures and integration contract suites."""

from treelang.testing.contracts import (
    CompletionContract,
    ModelTransportContract,
    StreamContract,
    ToolCallContract,
    ToolProviderContract,
)
from treelang.testing.fakes import (
    FakeCompletion,
    FakeModelTransport,
    FakeStream,
    FakeToolProvider,
    FakeToolResult,
    ToolCall,
)

__all__ = [
    "CompletionContract",
    "FakeCompletion",
    "FakeModelTransport",
    "FakeStream",
    "FakeToolProvider",
    "FakeToolResult",
    "ModelTransportContract",
    "StreamContract",
    "ToolCall",
    "ToolCallContract",
    "ToolProviderContract",
]
