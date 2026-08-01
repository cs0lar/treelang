"""Immutable expression grafting for schema version 2 programs."""

from __future__ import annotations

from typing import cast

from pydantic import ValidationError

from treelang.exceptions import TreeTransformationError
from treelang.trees.schemas.v2 import (
    AST,
    Expression,
    TreeCall,
    TreeConditional,
    TreeExpression,
    TreeFunctionDefinition,
    TreeProgram,
    TreeToolCall,
    TreeVariable,
)
from treelang.trees.transforms import (
    TransformationLimits,
    TransformationRecord,
    TransformResult,
    TreeChange,
    TreeChangeKind,
    TreePath,
)


def graft_expression(
    program: TreeProgram,
    graft: Expression,
    *,
    at: TreePath,
    limits: TransformationLimits | None = None,
) -> TransformResult[TreeProgram]:
    """Replace the expression at ``at`` with ``graft`` and validate the result."""

    source = AST(root=program).root
    transformed, found = _replace_in_program(source, at, graft)
    if not found:
        raise TreeTransformationError(
            f"Tree path '{at}' does not identify a schema v2 expression"
        )
    validated = _validate_result(transformed, limits)
    return TransformResult(
        tree=validated,
        lineage=(
            TransformationRecord(
                name="graft-expression",
                changes=(
                    TreeChange(
                        kind=TreeChangeKind.REPLACE,
                        path=at,
                        description="Replace expression with validated graft.",
                    ),
                ),
            ),
        ),
    )


def wrap_expression(
    program: TreeProgram,
    wrapper: Expression,
    *,
    at: TreePath,
    placeholder: str = "graft",
    limits: TransformationLimits | None = None,
) -> TransformResult[TreeProgram]:
    """Replace placeholder variables in ``wrapper`` with the expression at ``at``."""

    try:
        TreeVariable(name=placeholder)
    except ValidationError as error:
        raise TreeTransformationError(
            f"Invalid wrapper placeholder name '{placeholder}'"
        ) from error

    source = AST(root=program).root
    target = _expression_at(source, at)
    if target is None:
        raise TreeTransformationError(
            f"Tree path '{at}' does not identify a schema v2 expression"
        )
    wrapped, replacements = _substitute_placeholder(wrapper, placeholder, target)
    if replacements == 0:
        raise TreeTransformationError(
            f"Wrapper does not reference placeholder variable '{placeholder}'"
        )
    transformed, found = _replace_in_program(source, at, wrapped)
    if not found:  # pragma: no cover - target lookup establishes this invariant
        raise RuntimeError("Located expression disappeared during wrapping")
    validated = _validate_result(transformed, limits)
    return TransformResult(
        tree=validated,
        lineage=(
            TransformationRecord(
                name="wrap-expression",
                changes=(
                    TreeChange(
                        kind=TreeChangeKind.REPLACE,
                        path=at,
                        description=(
                            f"Wrap expression using placeholder '{placeholder}'."
                        ),
                    ),
                ),
            ),
        ),
    )


def _validate_result(
    program: TreeProgram, limits: TransformationLimits | None
) -> TreeProgram:
    try:
        validated = AST(root=program).root
    except ValidationError as error:
        raise TreeTransformationError(
            "Transformation produced an invalid schema v2 program: "
            f"{_validation_message(error)}"
        ) from error
    _enforce_limits(validated, limits or TransformationLimits())
    return validated


def _replace_in_program(
    program: TreeProgram, target: TreePath, replacement: Expression
) -> tuple[TreeProgram, bool]:
    found = False
    definitions: list[TreeFunctionDefinition] = []
    for index, definition in enumerate(program.definitions):
        definition_body, replaced = _replace_expression(
            definition.body,
            TreePath(("definitions", index, "body")),
            target,
            replacement,
        )
        found = found or replaced
        definitions.append(definition.model_copy(update={"body": definition_body}))
    program_body: list[Expression] = []
    for index, expression in enumerate(program.body):
        rewritten, replaced = _replace_expression(
            expression, TreePath(("body", index)), target, replacement
        )
        found = found or replaced
        program_body.append(rewritten)
    return (
        program.model_copy(update={"definitions": definitions, "body": program_body}),
        found,
    )


def _replace_expression(
    expression: Expression,
    path: TreePath,
    target: TreePath,
    replacement: Expression,
) -> tuple[Expression, bool]:
    if path == target:
        return replacement, True
    if isinstance(expression, TreeCall):
        found = False
        call_arguments: list[Expression] = []
        for index, argument in enumerate(expression.arguments):
            rewritten, replaced = _replace_expression(
                argument,
                path.child("arguments").child(index),
                target,
                replacement,
            )
            found = found or replaced
            call_arguments.append(rewritten)
        return expression.model_copy(update={"arguments": call_arguments}), found
    if isinstance(expression, TreeToolCall):
        found = False
        tool_arguments: dict[str, Expression] = {}
        for name, argument in expression.arguments.items():
            rewritten, replaced = _replace_expression(
                argument,
                path.child("arguments").child(name),
                target,
                replacement,
            )
            found = found or replaced
            tool_arguments[name] = rewritten
        return expression.model_copy(update={"arguments": tool_arguments}), found
    if isinstance(expression, TreeConditional):
        condition, condition_found = _replace_expression(
            expression.condition, path.child("condition"), target, replacement
        )
        true_branch, true_found = _replace_expression(
            expression.true_branch, path.child("true_branch"), target, replacement
        )
        false_branch, false_found = _replace_expression(
            expression.false_branch, path.child("false_branch"), target, replacement
        )
        return (
            expression.model_copy(
                update={
                    "condition": condition,
                    "true_branch": true_branch,
                    "false_branch": false_branch,
                }
            ),
            condition_found or true_found or false_found,
        )
    return expression, False


def _expression_at(program: TreeProgram, target: TreePath) -> Expression | None:
    current: object = program
    for segment in target.segments:
        if isinstance(current, TreeProgram) and segment in {"body", "definitions"}:
            current = getattr(current, segment)
        elif isinstance(current, TreeFunctionDefinition) and segment == "body":
            current = current.body
        elif isinstance(current, (TreeCall, TreeToolCall)) and segment == "arguments":
            current = current.arguments
        elif isinstance(current, TreeConditional) and segment in {
            "condition",
            "true_branch",
            "false_branch",
        }:
            current = getattr(current, segment)
        elif isinstance(current, list) and isinstance(segment, int):
            if segment >= len(current):
                return None
            current = current[segment]
        elif isinstance(current, dict) and isinstance(segment, str):
            if segment not in current:
                return None
            current = current[segment]
        else:
            return None
    return cast(Expression, current) if isinstance(current, TreeExpression) else None


def _substitute_placeholder(
    expression: Expression, placeholder: str, replacement: Expression
) -> tuple[Expression, int]:
    if isinstance(expression, TreeVariable) and expression.name == placeholder:
        return replacement, 1
    if isinstance(expression, TreeCall):
        count = 0
        call_arguments: list[Expression] = []
        for argument in expression.arguments:
            rewritten, replaced = _substitute_placeholder(
                argument, placeholder, replacement
            )
            count += replaced
            call_arguments.append(rewritten)
        return expression.model_copy(update={"arguments": call_arguments}), count
    if isinstance(expression, TreeToolCall):
        count = 0
        tool_arguments: dict[str, Expression] = {}
        for name, argument in expression.arguments.items():
            rewritten, replaced = _substitute_placeholder(
                argument, placeholder, replacement
            )
            count += replaced
            tool_arguments[name] = rewritten
        return expression.model_copy(update={"arguments": tool_arguments}), count
    if isinstance(expression, TreeConditional):
        condition, condition_count = _substitute_placeholder(
            expression.condition, placeholder, replacement
        )
        true_branch, true_count = _substitute_placeholder(
            expression.true_branch, placeholder, replacement
        )
        false_branch, false_count = _substitute_placeholder(
            expression.false_branch, placeholder, replacement
        )
        return (
            expression.model_copy(
                update={
                    "condition": condition,
                    "true_branch": true_branch,
                    "false_branch": false_branch,
                }
            ),
            condition_count + true_count + false_count,
        )
    return expression, 0


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
    if isinstance(expression, (TreeCall, TreeToolCall)):
        children = (
            list(expression.arguments.values())
            if isinstance(expression, TreeToolCall)
            else expression.arguments
        )
    elif isinstance(expression, TreeConditional):
        children = [
            expression.condition,
            expression.true_branch,
            expression.false_branch,
        ]
    else:
        children = []
    nodes = 1
    max_depth = depth
    for child in children:
        child_nodes, child_depth = _expression_size(child, depth + 1)
        nodes += child_nodes
        max_depth = max(max_depth, child_depth)
    return nodes, max_depth


def _validation_message(error: ValidationError) -> str:
    details = error.errors(include_url=False, include_input=False)
    return str(details[0]["msg"]) if details else "validation failed"


__all__ = ["graft_expression", "wrap_expression"]
