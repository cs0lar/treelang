"""Treelang's supported public API."""

from importlib.metadata import PackageNotFoundError, version

from treelang.ai.capabilities import (
    CapabilityAwareTransport,
    DefaultModelCapabilityNegotiator,
    ModelCapabilities,
    ModelCapabilityNegotiator,
    StructuredOutputSelection,
)
from treelang.ai.provider import MCPToolProvider, ToolOutput, ToolProvider
from treelang.ai.tool import ToolDefinition, ToolProperty
from treelang.exceptions import (
    ASTCompilationError,
    ASTExecutionError,
    ASTValidationError,
    ExecutionLimitError,
    ProviderResponseError,
    ReplayMismatchError,
    StructuredOutputUnsupportedError,
    ToolExecutionError,
    ToolNotFoundError,
    TreelangError,
)
from treelang.observability import NoOpTraceSink, Observability, TraceSink
from treelang.replay import (
    ModelReplayEntry,
    ModelReplayTransport,
    ToolReplayEntry,
    ToolReplayProvider,
)
from treelang.trees.budget import ExecutionLimits
from treelang.trees.policy import BranchOutcome, ExecutionPolicy, RetryPolicy
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
    "BranchOutcome",
    "CapabilityAwareTransport",
    "CURRENT_SCHEMA_VERSION",
    "DefaultModelCapabilityNegotiator",
    "ExecutionLimitError",
    "ExecutionLimits",
    "ExecutionPolicy",
    "MCPToolProvider",
    "ModelReplayEntry",
    "ModelReplayTransport",
    "ModelCapabilities",
    "ModelCapabilityNegotiator",
    "NoOpTraceSink",
    "Observability",
    "ProviderResponseError",
    "ReplayMismatchError",
    "RetryPolicy",
    "StructuredOutputUnsupportedError",
    "StructuredOutputSelection",
    "ToolExecutionError",
    "ToolDefinition",
    "ToolNotFoundError",
    "ToolOutput",
    "ToolProperty",
    "ToolProvider",
    "ToolReplayEntry",
    "ToolReplayProvider",
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
