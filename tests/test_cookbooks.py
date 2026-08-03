import sys
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import nbformat
import pytest
from mcp import StdioServerParameters

from scripts.check_cookbooks import (
    MCP_OPERATION_TIMEOUT_SECONDS,
    NOTEBOOK_KERNEL_STARTUP_TIMEOUT_SECONDS,
    CookbookTimeoutError,
    CookbookValidationError,
    await_cookbook_operation,
    cookbook_mcp_session,
    executable_notebook_paths,
    execute_notebook,
    notebook_paths,
    validate_notebook,
)
from treelang.ai.provider import MCPToolProvider

COOKBOOK = Path(__file__).parents[1] / "cookbook"


def test_committed_notebooks_are_clean_and_compile():
    notebooks = notebook_paths(COOKBOOK)

    assert {path.name for path in notebooks} == {
        "calculator.ipynb",
        "custom-provider.ipynb",
        "gamestats.ipynb",
        "memory.ipynb",
        "quickstart.ipynb",
    }
    for notebook in notebooks:
        validate_notebook(notebook)


def test_credential_free_tutorials_execute_end_to_end():
    notebooks = executable_notebook_paths(COOKBOOK)

    assert {path.name for path in notebooks} == {
        "custom-provider.ipynb",
        "quickstart.ipynb",
    }
    for notebook in notebooks:
        execute_notebook(notebook)


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


def test_notebook_execution_has_startup_and_overall_deadlines(tmp_path, monkeypatch):
    notebook = nbformat.v4.new_notebook()
    path = tmp_path / "stalled.ipynb"
    nbformat.write(notebook, path)
    received = {}

    class StalledNotebookClient:
        def __init__(self, notebook, **kwargs):
            received.update(kwargs)

        async def async_execute(self):
            await anyio.sleep_forever()

    monkeypatch.setattr("scripts.check_cookbooks.NotebookClient", StalledNotebookClient)

    with pytest.raises(
        CookbookTimeoutError,
        match=r"stalled\.ipynb: timed out during notebook execution after 0\.01 seconds",
    ):
        execute_notebook(path, overall_timeout_seconds=0.01)

    assert received["startup_timeout"] == NOTEBOOK_KERNEL_STARTUP_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_mcp_timeout_closes_session_and_stdio(monkeypatch):
    closed = []

    @asynccontextmanager
    async def fake_stdio_client(parameters):
        try:
            yield object(), object()
        finally:
            closed.append("stdio")

    class StalledSession:
        def __init__(self, read, write):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            closed.append("session")

        async def initialize(self):
            await anyio.sleep_forever()

    monkeypatch.setattr("scripts.check_cookbooks.stdio_client", fake_stdio_client)
    monkeypatch.setattr("scripts.check_cookbooks.ClientSession", StalledSession)
    parameters = StdioServerParameters(command=sys.executable, args=[])

    with pytest.raises(
        CookbookTimeoutError,
        match=r"stalled\.py: timed out during initialization after 0\.01 seconds",
    ):
        async with cookbook_mcp_session(
            parameters, server="stalled.py", timeout_seconds=0.01
        ) as session:
            await await_cookbook_operation(
                session.initialize(),
                target="stalled.py",
                operation="initialization",
                timeout_seconds=0.01,
            )

    assert closed == ["session", "stdio"]


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

    async with cookbook_mcp_session(parameters, server=server) as session:
        await await_cookbook_operation(
            session.initialize(), target=server, operation="initialization"
        )
        provider = MCPToolProvider(session)
        definitions = await await_cookbook_operation(
            provider.list_tools(), target=server, operation="tool discovery"
        )
        names = {definition["name"] for definition in definitions}

        for name, arguments, expected in calls:
            assert name in names
            result = await await_cookbook_operation(
                provider.call_tool(name, arguments),
                target=server,
                operation=f"tool call {name!r}",
                timeout_seconds=MCP_OPERATION_TIMEOUT_SECONDS,
            )
            assert result.content == expected
