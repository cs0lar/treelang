from abc import ABC, abstractmethod
import json
from typing import Any, Callable, Dict, List

from mcp import ClientSession
from pydantic import BaseModel


class ToolOutput(BaseModel):
    content: Any


class ToolProvider(ABC):

    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = None

    async def get_tool_definition(self, name: str) -> Dict[str, Any]:
        """Method to provide the definition of a tool."""
        if self.tools is None:
            await self.list_tools()

        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found.")

        return self.tools[name]

    @abstractmethod
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolOutput:
        """Method to provide the name of the tool."""
        pass

    @abstractmethod
    async def list_tools(self) -> List[Dict[str, Any]]:
        """Method to list all tools."""
        pass


class MCPToolProvider(ToolProvider):
    def __init__(self, session: ClientSession):
        super().__init__()
        self.session = session

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
            return ToolOutput(content=json.loads(content))

    async def list_tools(self) -> List[Dict[str, Any]]:
        if self.tools is None:
            response = await self.session.list_tools()
            tools = []
            for tool in response.tools:
                tools.append(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "properties": tool.inputSchema["properties"],
                    }
                )
            self.tools = {tool["name"]: tool for tool in tools}
            return tools
        else:
            return self.tools.values()


try:
    """
    Example of a non-MCP tool provider using LlamaIndex for tools provision.
    In order to use this, you need to install LlamaIndex and have it available in your environment:
    
    `pip install llama-index`
    
    """
    from llama_index.tools import FunctionTool

    class LlamIndexToolProvider(ToolProvider):
        def __init__(self, fns: List[Callable[..., Any]]):
            super().__init__()
            self.fn_tools = [FunctionTool.from_defaults(fn=fn) for fn in fns]

        async def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolOutput:
            if name not in self.tools:
                raise ValueError(f"Tool '{name}' not found.")
            return self.tools[name].fn(**arguments)

        async def list_tools(self) -> List[Dict[str, Any]]:
            if self.tools is None:
                tools = []
                for fn in self.fn_tool:
                    meta = fn.to_openai_tool()
                    tools.append(
                        {
                            "name": meta["function"]["name"],
                            "description": meta["function"]["description"],
                            "properties": meta["function"]["parameters"],
                        }
                    )
                self.tools = {tool["name"]: tool for tool in tools}
                return tools    
            else:
                return self.tools.values()

except ImportError:
    # LlamaIndex is not available
    pass
