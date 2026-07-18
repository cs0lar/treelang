from unittest.mock import AsyncMock

import pytest
from mcp.types import CallToolResult, ImageContent, ListToolsResult, TextContent, Tool

from treelang import MCPToolProvider, ToolExecutionError, ToolNotFoundError


@pytest.fixture
def session():
    return AsyncMock()


@pytest.mark.asyncio
async def test_call_tool_decodes_single_and_multiple_text_values(session):
    provider = MCPToolProvider(session)
    session.call_tool.side_effect = [
        CallToolResult(content=[TextContent(type="text", text='{"value": 3}')]),
        CallToolResult(
            content=[
                TextContent(type="text", text="true"),
                TextContent(type="text", text="'literal'"),
            ]
        ),
    ]

    assert (await provider.call_tool("one", {})).content == {"value": 3}
    assert (await provider.call_tool("many", {})).content == [True, "literal"]


@pytest.mark.asyncio
async def test_call_tool_prefers_structured_content(session):
    provider = MCPToolProvider(session)
    session.call_tool.return_value = CallToolResult(
        content=[TextContent(type="text", text="ignored")],
        structuredContent={"result": 42},
    )

    assert (await provider.call_tool("tool", {})).content == {"result": 42}


@pytest.mark.asyncio
async def test_call_tool_handles_empty_and_non_text_content(session):
    provider = MCPToolProvider(session)
    session.call_tool.side_effect = [
        CallToolResult(content=[]),
        CallToolResult(
            content=[ImageContent(type="image", data="aW1hZ2U=", mimeType="image/png")]
        ),
    ]

    assert (await provider.call_tool("empty", {})).content is None
    image = (await provider.call_tool("image", {})).content[0]
    assert image["type"] == "image"
    assert image["mimeType"] == "image/png"


@pytest.mark.asyncio
async def test_call_tool_raises_domain_error_for_provider_failure(session):
    provider = MCPToolProvider(session)
    session.call_tool.return_value = CallToolResult(
        content=[TextContent(type="text", text="permission denied")], isError=True
    )

    with pytest.raises(ToolExecutionError, match="permission denied"):
        await provider.call_tool("restricted", {})


@pytest.mark.asyncio
async def test_list_tools_is_cached_and_always_returns_a_list(session):
    provider = MCPToolProvider(session)
    session.list_tools.return_value = ListToolsResult(
        tools=[
            Tool(
                name="ping",
                description="Ping",
                inputSchema={"type": "object"},
            )
        ]
    )

    first = await provider.list_tools()
    second = await provider.list_tools()

    assert (
        first == second == [{"name": "ping", "description": "Ping", "properties": {}}]
    )
    session.list_tools.assert_awaited_once()


@pytest.mark.asyncio
async def test_missing_tool_raises_domain_error(session):
    provider = MCPToolProvider(session)
    session.list_tools.return_value = ListToolsResult(tools=[])

    with pytest.raises(ToolNotFoundError, match="missing"):
        await provider.get_tool_definition("missing")
