"""Deterministic transports and providers for offline evaluation."""

import inspect
import json
from collections.abc import AsyncIterator, Callable
from typing import Any, cast

from evaluation.data.tools import tools
from evaluation.models import EvaluationCase
from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.ai.tool import ToolDefinition, ToolProperty
from treelang.ai.transport import ModelRequest


class OfflineToolProvider(ToolProvider):
    """Invoke the curated evaluation functions in-process."""

    def __init__(self, functions: list[Callable[..., Any]] | None = None) -> None:
        super().__init__()
        selected = functions or [
            cast(Callable[..., Any], function) for function in tools
        ]
        self.functions: dict[str, Callable[..., Any]] = {
            function.__name__: function for function in selected
        }

    async def list_tools(self) -> list[ToolDefinition]:
        if self.tools is None:
            definitions = [
                self._definition(function) for function in self.functions.values()
            ]
            self.tools = {definition["name"]: definition for definition in definitions}
        return list(self.tools.values())

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolOutput:
        return ToolOutput(content=self.functions[name](**arguments))

    @staticmethod
    def _definition(function: Callable[..., Any]) -> ToolDefinition:
        properties: dict[str, ToolProperty] = {
            parameter_name: {}
            for parameter_name in inspect.signature(function).parameters
        }
        return {
            "name": function.__name__,
            "description": inspect.getdoc(function),
            "properties": properties,
        }


class OfflineModelTransport:
    """Return curated AST responses by exact user query."""

    def __init__(self, cases: list[EvaluationCase]) -> None:
        self.responses = {
            case.question: (
                case.ast if isinstance(case.ast, str) else json.dumps(case.ast)
            )
            for case in cases
        }

    async def complete(self, request: ModelRequest) -> str:
        messages = request.get("messages", [])
        query = next(
            message["content"]
            for message in reversed(messages)
            if message.get("role") == "user"
        )
        return self.responses[query]

    def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        async def empty() -> AsyncIterator[str]:
            if False:  # pragma: no cover - establishes the async-generator type
                yield ""

        return empty()
