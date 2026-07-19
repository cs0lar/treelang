"""Treelang's supported public API."""

from importlib.metadata import PackageNotFoundError, version

from treelang.ai.provider import MCPToolProvider, ToolOutput, ToolProvider
from treelang.ai.tool import ToolDefinition, ToolProperty
from treelang.exceptions import (
    ASTCompilationError,
    ASTExecutionError,
    ASTValidationError,
    ProviderResponseError,
    ToolExecutionError,
    ToolNotFoundError,
    TreelangError,
)
from treelang.observability import NoOpTraceSink, Observability, TraceSink
from treelang.trees.schemas import CURRENT_SCHEMA_VERSION, ast_examples, ast_json_schema
from treelang.trees.schemas.v1 import (
    TreeConditional,
    TreeFilter,
    TreeFunction,
    TreeLambda,
    TreeMap,
    TreeNode,
    TreeProgram,
    TreeReduce,
    TreeValue,
)
from treelang.trees.tree import AST

try:
    __version__ = version("treelang")
except PackageNotFoundError:  # pragma: no cover - only possible from an unpackaged tree
    __version__ = "0+unknown"

__all__ = [
    "AST",
    "ASTCompilationError",
    "ASTExecutionError",
    "ASTValidationError",
    "CURRENT_SCHEMA_VERSION",
    "MCPToolProvider",
    "NoOpTraceSink",
    "Observability",
    "ProviderResponseError",
    "ToolExecutionError",
    "ToolDefinition",
    "ToolNotFoundError",
    "ToolOutput",
    "ToolProperty",
    "ToolProvider",
    "TraceSink",
    "TreeConditional",
    "TreeFilter",
    "TreeFunction",
    "TreeLambda",
    "TreeMap",
    "TreeNode",
    "TreeProgram",
    "TreeReduce",
    "TreeValue",
    "TreelangError",
    "__version__",
    "ast_examples",
    "ast_json_schema",
]
