"""Validate committed cookbook notebooks without running credentialed cells."""

from __future__ import annotations

import ast
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).parents[1]
COOKBOOK = ROOT / "cookbook"


class CookbookValidationError(ValueError):
    """Raised when a committed notebook is not safe or syntactically valid."""


def validate_notebook(path: Path) -> None:
    """Validate one notebook's schema, cleanliness, and Python code cells."""
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)

    for index, cell in enumerate(notebook.cells, start=1):
        if cell.cell_type != "code":
            continue
        if cell.execution_count is not None or cell.outputs:
            raise CookbookValidationError(
                f"{path}: code cell {index} contains committed execution state"
            )
        try:
            compile(
                cell.source,
                f"{path}:cell-{index}",
                "exec",
                flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            )
        except SyntaxError as error:
            raise CookbookValidationError(
                f"{path}: code cell {index} does not compile: {error.msg}"
            ) from error


def notebook_paths(cookbook: Path = COOKBOOK) -> list[Path]:
    """Return the committed cookbook notebooks in deterministic order."""
    return sorted(cookbook.glob("*.ipynb"))


def executable_notebook_paths(cookbook: Path = COOKBOOK) -> list[Path]:
    """Return credential-free tutorials explicitly opted into CI execution."""
    return [
        path
        for path in notebook_paths(cookbook)
        if nbformat.read(path, as_version=4)
        .metadata.get("treelang", {})
        .get("ci_execute")
        is True
    ]


def execute_notebook(path: Path) -> None:
    """Execute one clean tutorial in memory from the repository root."""
    notebook = nbformat.read(path, as_version=4)
    NotebookClient(
        notebook,
        timeout=60,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
    ).execute()


def main() -> int:
    notebooks = notebook_paths()
    if not notebooks:
        raise CookbookValidationError(f"no notebooks found in {COOKBOOK}")
    for notebook in notebooks:
        validate_notebook(notebook)
    executable = executable_notebook_paths()
    for notebook in executable:
        execute_notebook(notebook)
    print(
        f"Validated {len(notebooks)} clean cookbook notebooks; "
        f"executed {len(executable)} credential-free tutorials"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
