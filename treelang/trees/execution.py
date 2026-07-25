"""Typed execution for version 1 AST nodes."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Mapping

from treelang.ai.provider import ToolProvider
from treelang.ai.tool import normalize_tool_definition, validate_tool_arguments
from treelang.exceptions import (
    ASTValidationError,
    ExecutionLimitError,
    ProviderResponseError,
)
from treelang.trees.budget import ExecutionBudget, ExecutionLimits
from treelang.trees.policy import ExecutionPolicy, call_tool, run_program
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
from treelang.trees.traversal import visit

LambdaCallable = Callable[..., Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Immutable bindings for one AST invocation.

    Named bindings are used by lambdas. Node bindings are used by compiled tools,
    where duplicate leaf names must remain independently addressable.
    """

    names: Mapping[str, Any] = field(default_factory=dict)
    nodes: Mapping[int, Any] = field(default_factory=dict)
    budget: ExecutionBudget = field(default_factory=ExecutionBudget)
    policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)
    depth: int = 0

    @classmethod
    def with_limits(
        cls,
        limits: ExecutionLimits | None = None,
        policy: ExecutionPolicy | None = None,
    ) -> "ExecutionContext":
        return cls(
            budget=ExecutionBudget(limits or ExecutionLimits()),
            policy=policy or ExecutionPolicy(),
        )

    def bind_names(self, values: Mapping[str, Any]) -> "ExecutionContext":
        return ExecutionContext(
            names={**self.names, **values},
            nodes=self.nodes,
            budget=self.budget,
            policy=self.policy,
            depth=self.depth,
        )

    def bind_nodes(self, values: Mapping[int, Any]) -> "ExecutionContext":
        return ExecutionContext(
            names=self.names,
            nodes={**self.nodes, **values},
            budget=self.budget,
            policy=self.policy,
            depth=self.depth,
        )

    def enter_node(self) -> "ExecutionContext":
        depth = self.depth + 1
        self.budget.consume_node(depth)
        return ExecutionContext(
            names=self.names,
            nodes=self.nodes,
            budget=self.budget,
            policy=self.policy,
            depth=depth,
        )

    def value_for(self, node: object, name: str, default: Any) -> Any:
        if id(node) in self.nodes:
            return self.nodes[id(node)]
        return self.names.get(name, default)


async def evaluate(
    node: TreeNode,
    provider: ToolProvider,
    context: ExecutionContext | None = None,
) -> Any:
    """Evaluate one AST node without mutating its schema model."""
    context = (context or ExecutionContext()).enter_node()
    if isinstance(node, TreeValue):
        return _evaluate_value(node, context)
    if isinstance(node, TreeFunction):
        return await _evaluate_function(node, provider, context)
    if isinstance(node, TreeProgram):
        return await _evaluate_program(node, provider, context)
    if isinstance(node, TreeConditional):
        return await _evaluate_conditional(node, provider, context)
    if isinstance(node, TreeLambda):
        return _evaluate_lambda(node, provider, context)
    if isinstance(node, TreeMap):
        return await _evaluate_map(node, provider, context)
    if isinstance(node, TreeFilter):
        return await _evaluate_filter(node, provider, context)
    if isinstance(node, TreeReduce):
        return await _evaluate_reduce(node, provider, context)
    raise NotImplementedError(f"Unsupported AST node: {type(node).__name__}")


async def execute(
    node: TreeNode,
    provider: ToolProvider,
    limits: ExecutionLimits | None = None,
    context: ExecutionContext | None = None,
    policy: ExecutionPolicy | None = None,
) -> Any:
    """Evaluate a root node with one shared budget and wall-clock deadline."""
    runtime_context = context or ExecutionContext.with_limits(limits, policy)
    timeout = runtime_context.budget.limits.timeout_seconds
    if timeout is None:
        return await node.eval(provider, runtime_context)
    deadline = asyncio.timeout(timeout)
    try:
        async with deadline:
            return await node.eval(provider, runtime_context)
    except TimeoutError:
        if deadline.expired():
            raise ExecutionLimitError("wall_clock_seconds", timeout) from None
        raise


def _evaluate_value(node: TreeValue, context: ExecutionContext | None) -> Any:
    if context is None:
        return node.value
    return context.value_for(node, node.name, node.value)


async def _evaluate_function(
    node: TreeFunction,
    provider: ToolProvider,
    context: ExecutionContext | None,
) -> Any:
    tool_name = node.name.removeprefix("functions.")
    raw_tool = await provider.get_tool_definition(tool_name)
    if not raw_tool:
        raise ProviderResponseError(f"Tool {tool_name} is not available")
    tool = normalize_tool_definition(raw_tool, expected_name=tool_name)
    properties = tool["properties"]
    property_names = list(properties)
    if "input_schema" not in tool and len(node.params) != len(property_names):
        raise ASTValidationError(
            f"Function '{tool_name}' expects {len(property_names)} parameters, "
            f"got {len(node.params)}"
        )
    if len(node.params) > len(property_names):
        raise ASTValidationError(
            f"Function '{tool_name}' accepts at most {len(property_names)} parameters, "
            f"got {len(node.params)}"
        )

    if context is None:  # pragma: no cover - evaluate() always supplies a context
        context = ExecutionContext()
    results = await context.budget.run_all(
        [partial(param.eval, provider, context) for param in node.params]
    )
    arguments = dict(zip(property_names[: len(results)], results, strict=True))
    validate_tool_arguments(tool, arguments)
    output = await call_tool(
        provider, tool_name, arguments, context.budget, context.policy
    )
    return output.content


async def _evaluate_program(
    node: TreeProgram,
    provider: ToolProvider,
    context: ExecutionContext | None,
) -> Any:
    if context is None:  # pragma: no cover - evaluate() always supplies a context
        context = ExecutionContext()
    results = await run_program(
        [partial(child.eval, provider, context) for child in node.body],
        node.mode,
        context.budget,
        context.policy,
    )
    if context.policy.parallel_failures == "collect":
        return results
    return results[0] if len(results) == 1 else results


async def _evaluate_conditional(
    node: TreeConditional,
    provider: ToolProvider,
    context: ExecutionContext | None,
) -> Any:
    condition = await node.condition.eval(provider, context)
    if condition:
        return await node.true_branch.eval(provider, context)
    if node.false_branch is not None:
        return await node.false_branch.eval(provider, context)
    return None


def _evaluate_lambda(
    node: TreeLambda,
    provider: ToolProvider,
    context: ExecutionContext | None,
) -> LambdaCallable:
    base_context = context or ExecutionContext()

    async def invoke(**kwargs: Any) -> Any:
        return await node.body.eval(provider, base_context.bind_names(kwargs))

    return invoke


async def _evaluate_map(
    node: TreeMap,
    provider: ToolProvider,
    context: ExecutionContext | None,
) -> Any:
    items = await node.iterable.eval(provider, context)
    if not isinstance(items, list):
        raise TypeError("Map expects an iterable (list) as input")

    function = await node.function.eval(provider, context)
    parameter_name = node.function.params[0]
    return [await function(**{parameter_name: item}) for item in items]


async def _evaluate_filter(
    node: TreeFilter,
    provider: ToolProvider,
    context: ExecutionContext | None,
) -> Any:
    items = await node.iterable.eval(provider, context)
    if not isinstance(items, list):
        raise TypeError("Filter expects an iterable (list) as input")

    function = await node.function.eval(provider, context)
    parameter_name = node.function.params[0]
    return [item for item in items if await function(**{parameter_name: item})]


async def _evaluate_reduce(
    node: TreeReduce,
    provider: ToolProvider,
    context: ExecutionContext | None,
) -> Any:
    items = await node.iterable.eval(provider, context)
    if not isinstance(items, list):
        raise TypeError("Reduce expects an iterable (list) as input")
    if not items:
        return None

    accumulator_name = node.function.params[0]
    accumulator_nodes: list[TreeValue] = []
    visit(
        node.function.body,
        lambda child: (
            accumulator_nodes.append(child)
            if isinstance(child, TreeValue) and child.name == accumulator_name
            else None
        ),
    )
    accumulator_node = accumulator_nodes[0]
    accumulator: Any = _evaluate_value(accumulator_node, context)
    remaining_items = items
    if accumulator is None:
        accumulator = items[0]
        remaining_items = items[1:]
    function = await node.function.eval(provider, context)

    for item in remaining_items:
        arguments = dict(zip(node.function.params, [accumulator, item], strict=True))
        accumulator = await function(**arguments)
    return accumulator
