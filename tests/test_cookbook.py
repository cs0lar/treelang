import json
from pathlib import Path

import pytest


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
