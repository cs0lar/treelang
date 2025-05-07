from typing import Any, List

from treelang.ai.provider import ToolProvider


class BaseToolSelector:
    """
    Base class for tool selectors. It allows clients to filter or select
    tools based on their own criteria.

    Methods:
    select: Selects tools based on the client's criteria.

    """

    async def select(self, provider: ToolProvider, **kwargs) -> List[Any]:
        """
        It selects a subset of all the available tools registered on the MCP server
        corresponding to the given session.

        Args:
            provider: ToolProvider object - a tool provider containing information on the available tools.

        Returns:
            List of types.Tool objects - a list of selected tools.
        """
        raise NotImplementedError()


class AllToolsSelector(BaseToolSelector):
    """
    The most basic Selector which just returns all tools available in the system.
    """

    async def select(self, provider: ToolProvider, **kwargs) -> List[Any]:
        return await provider.list_tools()
