from typing import List
from mcp import ClientSession
import mcp.types as types


class BaseToolSelector:
    """
    Base class for tool selectors. It allows clients to filter or select
    tools based on their own criteria.

    Methods:
    select: Selects tools based on the client's criteria.

    """

    async def select(self, session: ClientSession, **kwargs) -> List[types.Tool]:
        """
        It selects a subset of all the available tools registered on the MCP server
        corresponding to the given session.

        Args:
            session: ClientSession object - an MCP session object containing information on the available tools.

        Returns:
            List of types.Tool objects - a list of selected tools.
        """
        raise NotImplementedError()


class AllToolsSelector(BaseToolSelector):
    """
    The most basic Selector which just returns all tools available in the system.
    """

    async def select(self, session: ClientSession, **kwargs) -> List[types.Tool]:
        response = await session.list_tools()
        return response.tools
