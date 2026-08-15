"""Depth-first traversal helpers for supported Treelang AST nodes."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

from treelang.trees.schemas.v1 import (
    TreeConditional,
    TreeFilter,
    TreeFunction,
    TreeLambda,
    TreeMap,
    TreeProgram,
    TreeReduce,
)
from treelang.trees.schemas.v1 import (
    TreeNode as TreeNodeV1,
)
from treelang.trees.schemas.v2 import (
    TreeCall,
    TreeFunctionDefinition,
    TreeLiteral,
    TreeMemo,
    TreeToolCall,
    TreeVariable,
)
from treelang.trees.schemas.v2 import (
    TreeConditional as TreeConditionalV2,
)
from treelang.trees.schemas.v2 import (
    TreeProgram as TreeProgramV2,
)

type TreeNodeV2 = (
    TreeProgramV2
    | TreeFunctionDefinition
    | TreeLiteral
    | TreeVariable
    | TreeCall
    | TreeToolCall
    | TreeConditionalV2
    | TreeMemo
)
type TraversableNode = TreeNodeV1 | TreeNodeV2

Visitor = Callable[[TraversableNode], None]
AsyncVisitor = Callable[[TraversableNode], Awaitable[None]]
VisitorV1 = Callable[[TreeNodeV1], None]
AsyncVisitorV1 = Callable[[TreeNodeV1], Awaitable[None]]
VisitorV2 = Callable[[TreeNodeV2], None]
AsyncVisitorV2 = Callable[[TreeNodeV2], Awaitable[None]]


def visit(node: TraversableNode, operation: Visitor | VisitorV1 | VisitorV2) -> None:
    """Visit *node* and its descendants depth first."""
    compatible_operation = cast(Visitor, operation)
    compatible_operation(node)
    for child in children(node):
        visit(child, compatible_operation)


async def avisit(
    node: TraversableNode,
    operation: Visitor
    | VisitorV1
    | VisitorV2
    | AsyncVisitor
    | AsyncVisitorV1
    | AsyncVisitorV2,
) -> None:
    """Visit with an async operation, falling back to synchronous traversal."""
    if not asyncio.iscoroutinefunction(operation):
        visit(node, cast(Visitor, operation))
        return

    compatible_operation = cast(AsyncVisitor, operation)
    await compatible_operation(node)
    for child in children(node):
        await avisit(child, compatible_operation)


def children(node: TraversableNode) -> tuple[TraversableNode, ...]:
    """Return the immediate children of a supported AST node."""
    if isinstance(node, TreeProgram):
        return tuple(node.body)
    if isinstance(node, TreeConditional):
        branches = (node.condition, node.true_branch)
        return branches if node.false_branch is None else (*branches, node.false_branch)
    if isinstance(node, TreeLambda):
        return (node.body,)
    if isinstance(node, (TreeMap, TreeFilter, TreeReduce)):
        return (node.function, node.iterable)
    if isinstance(node, TreeFunction):
        return tuple(node.params)
    if isinstance(node, TreeProgramV2):
        return (*node.definitions, *node.body)
    if isinstance(node, TreeFunctionDefinition):
        return (node.body,)
    if isinstance(node, TreeCall):
        return tuple(node.arguments)
    if isinstance(node, TreeToolCall):
        return tuple(node.arguments.values())
    if isinstance(node, TreeConditionalV2):
        return (node.condition, node.true_branch, node.false_branch)
    if isinstance(node, TreeMemo):
        return (node.expression,)
    return ()


__all__ = [
    "AsyncVisitor",
    "AsyncVisitorV1",
    "AsyncVisitorV2",
    "TraversableNode",
    "Visitor",
    "VisitorV1",
    "VisitorV2",
    "avisit",
    "children",
    "visit",
]
