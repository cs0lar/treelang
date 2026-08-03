"""Shared validation and structural limits for schema v2 transformations."""

from __future__ import annotations

from pydantic import ValidationError

from treelang.exceptions import TreeTransformationError
from treelang.trees.schemas.v2 import (
    AST,
    Expression,
    TreeCall,
    TreeConditional,
    TreeMemo,
    TreeProgram,
    TreeToolCall,
)
from treelang.trees.transforms import TransformationLimits


def validate_transformed_program(
    program: TreeProgram, limits: TransformationLimits | None
) -> TreeProgram:
    """Validate a complete program and enforce optional static limits."""

    try:
        validated = AST(root=program).root
    except ValidationError as error:
        details = error.errors(include_url=False, include_input=False)
        message = str(details[0]["msg"]) if details else "validation failed"
        raise TreeTransformationError(
            f"Transformation produced an invalid schema v2 program: {message}"
        ) from error
    _enforce_limits(validated, limits or TransformationLimits())
    return validated


def _enforce_limits(program: TreeProgram, limits: TransformationLimits) -> None:
    nodes = 1 + len(program.definitions)
    max_depth = 1
    for definition in program.definitions:
        expression_nodes, expression_depth = _expression_size(definition.body, 3)
        nodes += expression_nodes
        max_depth = max(max_depth, expression_depth)
    for expression in program.body:
        expression_nodes, expression_depth = _expression_size(expression, 2)
        nodes += expression_nodes
        max_depth = max(max_depth, expression_depth)
    if limits.max_nodes is not None and nodes > limits.max_nodes:
        raise TreeTransformationError(
            f"Transformed program exceeds max_nodes ({limits.max_nodes}); got {nodes}"
        )
    if limits.max_depth is not None and max_depth > limits.max_depth:
        raise TreeTransformationError(
            f"Transformed program exceeds max_depth ({limits.max_depth}); got {max_depth}"
        )


def _expression_size(expression: Expression, depth: int) -> tuple[int, int]:
    children: list[Expression]
    if isinstance(expression, TreeCall):
        children = expression.arguments
    elif isinstance(expression, TreeToolCall):
        children = list(expression.arguments.values())
    elif isinstance(expression, TreeConditional):
        children = [
            expression.condition,
            expression.true_branch,
            expression.false_branch,
        ]
    elif isinstance(expression, TreeMemo):
        children = [expression.expression]
    else:
        children = []
    nodes = 1
    max_depth = depth
    for child in children:
        child_nodes, child_depth = _expression_size(child, depth + 1)
        nodes += child_nodes
        max_depth = max(max_depth, child_depth)
    return nodes, max_depth


__all__ = ["validate_transformed_program"]
