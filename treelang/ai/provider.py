import ast
import json
from abc import ABC, abstractmethod
from typing import Any

from mcp import ClientSession
from mcp.types import TextContent
from pydantic import BaseModel

from treelang.ai.tool import ToolDefinition, normalize_tool_definition
from treelang.exceptions import (
    ProviderResponseError,
    ToolExecutionError,
    ToolNotFoundError,
)


class ToolOutput(BaseModel):
    """Provider-neutral value returned by one successful tool invocation."""

    content: Any


class ToolProvider(ABC):
    """Provider-neutral interface for tool discovery and invocation."""

    def __init__(self) -> None:
        self.tools: dict[str, ToolDefinition] | None = None

    async def get_tool_definition(self, name: str) -> ToolDefinition:
        """Return normalized metadata for one named tool."""
        if self.tools is None:
            await self.list_tools()

        if self.tools is None:
            raise ProviderResponseError("Provider did not populate its tool registry")

        if name not in self.tools:
            raise ToolNotFoundError(f"Tool '{name}' not found.")

        return normalize_tool_definition(self.tools[name], expected_name=name)

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolOutput:
        """Invoke a named tool with validated keyword arguments."""
        raise NotImplementedError

    @abstractmethod
    async def list_tools(self) -> list[ToolDefinition]:
        """Return normalized metadata for every available tool."""
        raise NotImplementedError


class MCPToolProvider(ToolProvider):
    """Tool provider backed by an initialized MCP client session."""

    def __init__(self, session: ClientSession) -> None:
        super().__init__()
        self.session = session

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolOutput:
        output = await self.session.call_tool(name, arguments)

        text_items = [
            item.text for item in output.content if isinstance(item, TextContent)
        ]
        if output.isError:
            detail = "; ".join(text_items) or "provider returned an unspecified error"
            raise ToolExecutionError(f"Error calling tool {name}: {detail}")

        if output.structuredContent is not None:
            return ToolOutput(content=output.structuredContent)

        if not output.content:
            return ToolOutput(content=None)

        if len(text_items) != len(output.content):
            content = [item.model_dump(mode="json") for item in output.content]
            return ToolOutput(content=content)

        decoded = [self._decode_text(item) for item in text_items]
        return ToolOutput(content=decoded[0] if len(decoded) == 1 else decoded)

    @staticmethod
    def _decode_text(value: str) -> Any:
        text = value.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                return ast.literal_eval(text)
            except (ValueError, SyntaxError):
                return value

    async def list_tools(self) -> list[ToolDefinition]:
        if self.tools is None:
            response = await self.session.list_tools()
            tools: list[ToolDefinition] = []
            for tool in response.tools:
                tools.append(
                    normalize_tool_definition(
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "properties": tool.inputSchema.get("properties", {}),
                        },
                        expected_name=tool.name,
                    )
                )
            self.tools = {tool["name"]: tool for tool in tools}
            return tools
        return list(self.tools.values())
