from abc import ABC, abstractmethod
import json
from typing import Any, Dict, List

from mcp import ClientSession
from pydantic import BaseModel


class ToolOutput(BaseModel):
    content: Any


class ToolProvider(ABC):
    @abstractmethod
    async def get_tool_definition(self, name: str) -> Dict[str, Any]:
        """Method to provide a tool."""
        pass

    @abstractmethod
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolOutput:
        """Method to provide the name of the tool."""
        pass

    @abstractmethod
    async def list_tools(self) -> List[Any]:
        """Method to list all tools."""
        pass


class MCPToolProvider(ToolProvider):
    def __init__(self, session: ClientSession):
        self.session = session

    async def get_tool_definition(self, name: str) -> Dict[str, Any]:
        response = await self.session.list_tools()
        tools = response.tools

        return next((tool.inputSchema for tool in tools if tool.name == name), None)

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolOutput:
        output = await self.session.call_tool(name, arguments)

        if isinstance(output.content, list) and len(output.content):
            if output.content[0].text.startswith("Error"):
                raise RuntimeError(
                    f"Error calling tool {self.name}: {output.content[0].text}"
                )
            # return the result attempting to transform it into its appropriate type
            content = (
                output.content[0].text
                if len(output.content) == 1
                else "[" + ",".join([out.text for out in output.content]) + "]"
            )
            return json.loads(content)

    async def list_tools(self) -> List[Any]:
        response = await self.session.list_tools()
        return response.tools
