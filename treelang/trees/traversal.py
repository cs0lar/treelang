"""Depth-first traversal helpers for version 1 AST nodes."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

from treelang.trees.schemas.v1 import (
    TreeConditional,
    TreeFilter,
    TreeFunction,
    TreeLambda,
    TreeMap,
    TreeNode,
    TreeProgram,
    TreeReduce,
)

Visitor = Callable[[TreeNode], None]
AsyncVisitor = Callable[[TreeNode], Awaitable[None]]


def visit(node: TreeNode, operation: Visitor) -> None:
    """Visit *node* and its descendants depth first."""
    operation(node)
    for child in children(node):
        visit(child, operation)


async def avisit(node: TreeNode, operation: Visitor | AsyncVisitor) -> None:
    """Visit with an async operation, falling back to synchronous traversal."""
    if not asyncio.iscoroutinefunction(operation):
        visit(node, cast(Visitor, operation))
        return

    await operation(node)
    for child in children(node):
        await avisit(child, operation)


def children(node: TreeNode) -> tuple[TreeNode, ...]:
    """Return the immediate children of a version 1 AST node."""
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
    return ()
