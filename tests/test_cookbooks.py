import sys
from pathlib import Path

import nbformat
import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client

from scripts.check_cookbooks import (
    CookbookValidationError,
    notebook_paths,
    validate_notebook,
)
from treelang.ai.provider import MCPToolProvider

COOKBOOK = Path(__file__).parents[1] / "cookbook"


def test_committed_notebooks_are_clean_and_compile():
    notebooks = notebook_paths(COOKBOOK)

    assert {path.name for path in notebooks} == {
        "calculator.ipynb",
        "gamestats.ipynb",
        "memory.ipynb",
    }
    for notebook in notebooks:
        validate_notebook(notebook)


def test_notebook_validation_rejects_execution_state(tmp_path):
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                "answer = 42",
                execution_count=1,
                outputs=[nbformat.v4.new_output("stream", text="42\n")],
            )
        ]
    )
    path = tmp_path / "executed.ipynb"
    nbformat.write(notebook, path)

    with pytest.raises(CookbookValidationError, match="execution state"):
        validate_notebook(path)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("server", "calls"),
    [
        (
            "calculator.py",
            [
                ("add", {"a": 2, "b": 3}, 5),
                ("power", {"a": 4, "b": 2}, 16),
            ],
        ),
        (
            "gamestats.py",
            [
                ("get_players", {"platform": "Steam"}, [11, 8, 41]),
                ("average", {"values": [12, 18, 30]}, 20),
            ],
        ),
    ],
)
async def test_cookbook_mcp_servers(server, calls):
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(COOKBOOK / server)],
        env=None,
    )

    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            provider = MCPToolProvider(session)
            definitions = await provider.list_tools()
            names = {definition["name"] for definition in definitions}

            for name, arguments, expected in calls:
                assert name in names
                assert (await provider.call_tool(name, arguments)).content == expected
