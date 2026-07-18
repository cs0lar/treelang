"""Typed execution for version 1 AST nodes."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Mapping

from treelang.ai.provider import ToolProvider
from treelang.exceptions import ASTValidationError, ProviderResponseError
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

LambdaCallable = Callable[..., Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Immutable bindings for one AST invocation.

    Named bindings are used by lambdas. Node bindings are used by compiled tools,
    where duplicate leaf names must remain independently addressable.
    """

    names: Mapping[str, Any] = field(default_factory=dict)
    nodes: Mapping[int, Any] = field(default_factory=dict)

    def bind_names(self, values: Mapping[str, Any]) -> "ExecutionContext":
        return ExecutionContext(names={**self.names, **values}, nodes=self.nodes)

    def bind_nodes(self, values: Mapping[int, Any]) -> "ExecutionContext":
        return ExecutionContext(names=self.names, nodes={**self.nodes, **values})

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
    tool = await provider.get_tool_definition(tool_name)
    if not tool:
        raise ProviderResponseError(f"Tool {tool_name} is not available")

    properties = tool.get("properties")
    if not isinstance(properties, dict):
        raise ProviderResponseError(
            f"Tool '{tool_name}' has no valid properties definition"
        )
    property_names = list(properties)
    if len(property_names) != len(node.params):
        raise ASTValidationError(
            f"Function '{tool_name}' expects {len(property_names)} parameters, "
            f"got {len(node.params)}"
        )

    results = await asyncio.gather(
        *[param.eval(provider, context) for param in node.params]
    )
    arguments = dict(zip(property_names, results, strict=True))
    output = await provider.call_tool(tool_name, arguments)
    return output.content


async def _evaluate_program(
    node: TreeProgram,
    provider: ToolProvider,
    context: ExecutionContext | None,
) -> Any:
    results = await asyncio.gather(
        *[child.eval(provider, context) for child in node.body]
    )
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
    accumulator_node = next(
        parameter
        for parameter in node.function.body.params
        if isinstance(parameter, TreeValue) and parameter.name == accumulator_name
    )
    accumulator: Any = _evaluate_value(accumulator_node, context)
    function = await node.function.eval(provider, context)

    for item in items:
        arguments = dict(zip(node.function.params, [accumulator, item], strict=True))
        accumulator = await function(**arguments)
    return accumulator
