import ast
import json
from abc import ABC, abstractmethod
from typing import Any

from mcp import ClientSession
from mcp.types import TextContent
from pydantic import BaseModel

from treelang.exceptions import (
    ProviderResponseError,
    ToolExecutionError,
    ToolNotFoundError,
)


class ToolOutput(BaseModel):
    content: Any


class ToolProvider(ABC):
    def __init__(self) -> None:
        self.tools: dict[str, dict[str, Any]] | None = None

    async def get_tool_definition(self, name: str) -> dict[str, Any]:
        """Method to provide the definition of a tool."""
        if self.tools is None:
            await self.list_tools()

        if self.tools is None:
            raise ProviderResponseError("Provider did not populate its tool registry")

        if name not in self.tools:
            raise ToolNotFoundError(f"Tool '{name}' not found.")

        return self.tools[name]

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolOutput:
        """Method to provide the name of the tool."""
        raise NotImplementedError

    @abstractmethod
    async def list_tools(self) -> list[dict[str, Any]]:
        """Method to list all tools."""
        raise NotImplementedError


class MCPToolProvider(ToolProvider):
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

    async def list_tools(self) -> list[dict[str, Any]]:
        if self.tools is None:
            response = await self.session.list_tools()
            tools = []
            for tool in response.tools:
                tools.append(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "properties": tool.inputSchema.get("properties", {}),
                    }
                )
            self.tools = {tool["name"]: tool for tool in tools}
            return tools
        return list(self.tools.values())
