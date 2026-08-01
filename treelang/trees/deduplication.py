"""Safe common-subexpression elimination for declared pure tools."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence

from treelang.ai.tool import ToolDefinition, normalize_tool_definition
from treelang.trees.schemas.v2 import (
    AST,
    Expression,
    TreeCall,
    TreeConditional,
    TreeMemo,
    TreeProgram,
    TreeToolCall,
    TreeVariable,
)
from treelang.trees.transformation_validation import validate_transformed_program
from treelang.trees.transforms import (
    TransformationLimits,
    TransformationRecord,
    TransformResult,
    TreeChange,
    TreeChangeKind,
    TreePath,
)


def deduplicate_pure_tool_calls(
    program: TreeProgram,
    tools: Sequence[ToolDefinition],
    *,
    limits: TransformationLimits | None = None,
) -> TransformResult[TreeProgram]:
    """Memoize repeated closed calls to declared pure deterministic tools."""

    source = AST(root=program).root
    safe = {
        tool["name"]
        for raw in tools
        if (tool := normalize_tool_definition(raw)).get("effects", {}).get("pure")
        and tool.get("effects", {}).get("deterministic")
    }
    counts: Counter[str] = Counter()
    for expression in [
        *(definition.body for definition in source.definitions),
        *source.body,
    ]:
        _count(expression, safe, counts)
    changes: list[TreeChange] = []
    definitions = [
        definition.model_copy(
            update={
                "body": _rewrite(
                    definition.body,
                    TreePath(("definitions", index, "body")),
                    safe,
                    counts,
                    changes,
                )
            }
        )
        for index, definition in enumerate(source.definitions)
    ]
    body = [
        _rewrite(expression, TreePath(("body", index)), safe, counts, changes)
        for index, expression in enumerate(source.body)
    ]
    transformed = source.model_copy(update={"definitions": definitions, "body": body})
    return TransformResult(
        tree=validate_transformed_program(transformed, limits),
        lineage=(
            TransformationRecord(
                name="deduplicate-pure-tool-calls", changes=tuple(changes)
            ),
        ),
    )


def _fingerprint(expression: Expression) -> str:
    payload = json.dumps(
        expression.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _safe(expression: Expression, tools: set[str]) -> bool:
    if isinstance(expression, TreeVariable | TreeCall | TreeMemo):
        return False
    if isinstance(expression, TreeToolCall):
        return expression.tool in tools and all(
            _safe(item, tools) for item in expression.arguments.values()
        )
    if isinstance(expression, TreeConditional):
        return all(
            _safe(item, tools)
            for item in (
                expression.condition,
                expression.true_branch,
                expression.false_branch,
            )
        )
    return True


def _children(expression: Expression) -> list[tuple[str | int, Expression]]:
    if isinstance(expression, TreeCall):
        return [(index, item) for index, item in enumerate(expression.arguments)]
    if isinstance(expression, TreeToolCall):
        return list(expression.arguments.items())
    if isinstance(expression, TreeConditional):
        return [
            ("condition", expression.condition),
            ("true_branch", expression.true_branch),
            ("false_branch", expression.false_branch),
        ]
    if isinstance(expression, TreeMemo):
        return [("expression", expression.expression)]
    return []


def _count(expression: Expression, tools: set[str], counts: Counter[str]) -> None:
    if isinstance(expression, TreeToolCall) and _safe(expression, tools):
        counts[_fingerprint(expression)] += 1
    for _, child in _children(expression):
        _count(child, tools, counts)


def _rewrite(
    expression: Expression,
    path: TreePath,
    tools: set[str],
    counts: Counter[str],
    changes: list[TreeChange],
) -> Expression:
    rewritten: Expression
    if isinstance(expression, TreeCall):
        rewritten = expression.model_copy(
            update={
                "arguments": [
                    _rewrite(
                        item,
                        path.child("arguments").child(index),
                        tools,
                        counts,
                        changes,
                    )
                    for index, item in enumerate(expression.arguments)
                ]
            }
        )
    elif isinstance(expression, TreeToolCall):
        rewritten = expression.model_copy(
            update={
                "arguments": {
                    name: _rewrite(
                        item,
                        path.child("arguments").child(name),
                        tools,
                        counts,
                        changes,
                    )
                    for name, item in expression.arguments.items()
                }
            }
        )
    elif isinstance(expression, TreeConditional):
        rewritten = expression.model_copy(
            update={
                "condition": _rewrite(
                    expression.condition,
                    path.child("condition"),
                    tools,
                    counts,
                    changes,
                ),
                "true_branch": _rewrite(
                    expression.true_branch,
                    path.child("true_branch"),
                    tools,
                    counts,
                    changes,
                ),
                "false_branch": _rewrite(
                    expression.false_branch,
                    path.child("false_branch"),
                    tools,
                    counts,
                    changes,
                ),
            }
        )
    else:
        rewritten = expression
    if isinstance(expression, TreeToolCall) and _safe(expression, tools):
        fingerprint = _fingerprint(expression)
        if counts[fingerprint] > 1:
            changes.append(
                TreeChange(
                    TreeChangeKind.REPLACE,
                    path,
                    "Memoize repeated pure deterministic tool call.",
                )
            )
            return TreeMemo(key=f"cse_{fingerprint[:16]}", expression=rewritten)
    return rewritten


__all__ = ["deduplicate_pure_tool_calls"]
