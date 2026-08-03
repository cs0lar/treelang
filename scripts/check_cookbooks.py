"""Validate committed cookbook notebooks without running credentialed cells."""

from __future__ import annotations

import ast
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TypeVar

import anyio
import nbformat
from mcp import ClientSession, StdioServerParameters, stdio_client
from nbclient import NotebookClient

ROOT = Path(__file__).parents[1]
COOKBOOK = ROOT / "cookbook"
NOTEBOOK_CELL_TIMEOUT_SECONDS = 60
NOTEBOOK_KERNEL_STARTUP_TIMEOUT_SECONDS = 60
NOTEBOOK_EXECUTION_TIMEOUT_SECONDS = 300
MCP_OPERATION_TIMEOUT_SECONDS = 30

T = TypeVar("T")


class CookbookValidationError(ValueError):
    """Raised when a committed notebook is not safe or syntactically valid."""


class CookbookTimeoutError(TimeoutError):
    """Raised when a cookbook integration operation exceeds its deadline."""


async def await_cookbook_operation(
    awaitable: Awaitable[T],
    *,
    target: str,
    operation: str,
    timeout_seconds: float = MCP_OPERATION_TIMEOUT_SECONDS,
) -> T:
    """Await one cookbook operation with a bounded, diagnostic deadline."""
    try:
        with anyio.fail_after(timeout_seconds):
            return await awaitable
    except TimeoutError as error:
        raise CookbookTimeoutError(
            f"{target}: timed out during {operation} after {timeout_seconds:g} seconds"
        ) from error


@asynccontextmanager
async def cookbook_mcp_session(
    parameters: StdioServerParameters,
    *,
    server: str,
    timeout_seconds: float = MCP_OPERATION_TIMEOUT_SECONDS,
) -> AsyncIterator[ClientSession]:
    """Open an MCP stdio session and bound both startup and cleanup."""
    operation = "stdio startup"
    try:
        with anyio.fail_after(timeout_seconds) as stdio_scope:
            async with stdio_client(parameters) as (read, write):
                stdio_scope.deadline = float("inf")
                operation = "session startup"
                with anyio.fail_after(timeout_seconds) as session_scope:
                    async with ClientSession(read, write) as session:
                        session_scope.deadline = float("inf")
                        try:
                            yield session
                        finally:
                            operation = "context shutdown"
                            deadline = anyio.current_time() + timeout_seconds
                            session_scope.deadline = deadline
                            stdio_scope.deadline = deadline
    except CookbookTimeoutError:
        raise
    except TimeoutError as error:
        raise CookbookTimeoutError(
            f"{server}: timed out during {operation} after {timeout_seconds:g} seconds"
        ) from error


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


async def _execute_notebook(
    client: NotebookClient,
    path: Path,
    timeout_seconds: float,
) -> None:
    await await_cookbook_operation(
        client.async_execute(),
        target=str(path),
        operation="notebook execution",
        timeout_seconds=timeout_seconds,
    )


def execute_notebook(
    path: Path,
    *,
    overall_timeout_seconds: float = NOTEBOOK_EXECUTION_TIMEOUT_SECONDS,
) -> None:
    """Execute one clean tutorial in memory from the repository root."""
    notebook = nbformat.read(path, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=NOTEBOOK_CELL_TIMEOUT_SECONDS,
        startup_timeout=NOTEBOOK_KERNEL_STARTUP_TIMEOUT_SECONDS,
        kernel_name="python3",
        resources={"metadata": {"path": str(ROOT)}},
    )
    anyio.run(_execute_notebook, client, path, overall_timeout_seconds)


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
