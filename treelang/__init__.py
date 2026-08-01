"""Treelang's supported public API."""

from importlib.metadata import PackageNotFoundError, version

from treelang.ai.anthropic import AnthropicTransport
from treelang.ai.capabilities import (
    CapabilityAwareTransport,
    DefaultModelCapabilityNegotiator,
    ModelCapabilities,
    ModelCapabilityNegotiator,
    StructuredOutputSelection,
)
from treelang.ai.provider import MCPToolProvider, ToolOutput, ToolProvider
from treelang.ai.tool import ToolDefinition, ToolProperty
from treelang.ai.transport import ModelTransport, ModelUsage, UsageAwareTransport
from treelang.exceptions import (
    ASTCompilationError,
    ASTExecutionError,
    ASTValidationError,
    ExecutionLimitError,
    ModelAuthenticationError,
    ModelConnectionError,
    ModelRateLimitError,
    ModelTimeoutError,
    ModelTransportError,
    ProviderResponseError,
    ReplayMismatchError,
    StructuredOutputUnsupportedError,
    ToolExecutionError,
    ToolNotFoundError,
    TreelangError,
    TreeTransformationError,
)
from treelang.observability import NoOpTraceSink, Observability, TraceSink
from treelang.replay import (
    ModelReplayEntry,
    ModelReplayTransport,
    ToolReplayEntry,
    ToolReplayProvider,
)
from treelang.schema_artifacts import (
    SUPPORTED_SCHEMA_VERSIONS,
    json_schema_text,
    load_json_schema,
)
from treelang.trees.budget import ExecutionLimits
from treelang.trees.composition import compose_programs
from treelang.trees.grafting import graft_expression, wrap_expression
from treelang.trees.policy import BranchOutcome, ExecutionPolicy, RetryPolicy
from treelang.trees.pruning import ConservativeTreePruner, prune_tree
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
from treelang.trees.transforms import (
    TransformationLimits,
    TransformationRecord,
    TransformResult,
    TreeChange,
    TreeChangeKind,
    TreePath,
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
    "AnthropicTransport",
    "BranchOutcome",
    "CapabilityAwareTransport",
    "compose_programs",
    "ConservativeTreePruner",
    "CURRENT_SCHEMA_VERSION",
    "DefaultModelCapabilityNegotiator",
    "ExecutionLimitError",
    "ExecutionLimits",
    "ExecutionPolicy",
    "MCPToolProvider",
    "ModelAuthenticationError",
    "ModelCapabilities",
    "ModelCapabilityNegotiator",
    "ModelConnectionError",
    "ModelRateLimitError",
    "ModelReplayEntry",
    "ModelReplayTransport",
    "ModelTimeoutError",
    "ModelTransport",
    "ModelTransportError",
    "ModelUsage",
    "NoOpTraceSink",
    "Observability",
    "ProviderResponseError",
    "ReplayMismatchError",
    "RetryPolicy",
    "StructuredOutputUnsupportedError",
    "StructuredOutputSelection",
    "SUPPORTED_SCHEMA_VERSIONS",
    "ToolExecutionError",
    "ToolDefinition",
    "ToolNotFoundError",
    "ToolOutput",
    "ToolProperty",
    "ToolProvider",
    "ToolReplayEntry",
    "ToolReplayProvider",
    "TraceSink",
    "TransformationLimits",
    "TransformResult",
    "TransformationRecord",
    "TreeConditional",
    "TreeChange",
    "TreeChangeKind",
    "TreeFilter",
    "TreeFunction",
    "TreeLambda",
    "TreeMap",
    "TreeNode",
    "TreePath",
    "TreeProgram",
    "TreeReduce",
    "TreeValue",
    "TreelangError",
    "TreeTransformationError",
    "UsageAwareTransport",
    "__version__",
    "ast_examples",
    "ast_json_schema",
    "graft_expression",
    "json_schema_text",
    "load_json_schema",
    "prune_tree",
    "wrap_expression",
]
