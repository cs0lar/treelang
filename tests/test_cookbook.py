import json
from pathlib import Path

import pytest

from cookbook.calculator import mcp as calculator_mcp
from cookbook.gamestats import mcp as gamestats_mcp


@pytest.mark.parametrize(
    ("notebook_name", "server_name"),
    [
        ("calculator.ipynb", "calculator.py"),
        ("gamestats.ipynb", "gamestats.py"),
        ("memory.ipynb", "calculator.py"),
    ],
)
def test_notebooks_await_execution_and_resolve_cookbook_server(
    notebook_name, server_name
):
    notebook = json.loads(
        (Path("cookbook") / notebook_name).read_text(encoding="utf-8")
    )
    source = "\n".join(
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    )

    assert "await main()" in source
    assert "create_task(main())" not in source
    assert 'if cookbook_dir.name != "cookbook"' in source
    assert f'path = cookbook_dir / "{server_name}"' in source

    if notebook_name == "calculator.ipynb":
        assert "conditional_tree = response.content" in source
        assert (
            "conditional_result = await AST.eval(conditional_tree, provider)" in source
        )


@pytest.mark.parametrize("server", [calculator_mcp, gamestats_mcp])
def test_cookbook_servers_return_unwrapped_tool_values(server):
    assert all(
        tool.fn_metadata.output_schema is None
        for tool in server._tool_manager._tools.values()
    )
