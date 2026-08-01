"""Deterministic composition of independently valid schema v2 programs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from treelang.exceptions import TreeTransformationError
from treelang.trees.schemas.v2 import (
    AST,
    Expression,
    TreeCall,
    TreeConditional,
    TreeFunctionDefinition,
    TreeProgram,
    TreeToolCall,
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


def compose_programs(
    programs: Sequence[TreeProgram],
    *,
    mode: Literal["single", "parallel"] = "single",
    name: str | None = None,
    description: str | None = None,
    limits: TransformationLimits | None = None,
) -> TransformResult[TreeProgram]:
    """Combine independent programs with hygienic user-function names."""

    if len(programs) < 2:
        raise TreeTransformationError("Composition requires at least two programs")
    if mode not in ("single", "parallel"):
        raise TreeTransformationError("Composition mode must be 'single' or 'parallel'")

    occupied: set[str] = set()
    definitions: list[TreeFunctionDefinition] = []
    body: list[Expression] = []
    changes: list[TreeChange] = []

    for program_index, raw_program in enumerate(programs):
        program = AST(root=raw_program).root
        mapping = _definition_mapping(program, occupied)
        definition_offset = len(definitions)
        for source_index, definition in enumerate(program.definitions):
            renamed = mapping[definition.name]
            output_index = len(definitions)
            rewritten = definition.model_copy(
                update={
                    "name": renamed,
                    "body": _rename_calls(definition.body, mapping),
                }
            )
            definitions.append(rewritten)
            changes.append(
                TreeChange(
                    kind=TreeChangeKind.INSERT,
                    path=TreePath(("definitions", output_index)),
                    description=(
                        f"Insert definition from program {program_index}, "
                        f"source index {source_index}."
                    ),
                )
            )
            if renamed != definition.name:
                changes.append(
                    TreeChange(
                        kind=TreeChangeKind.RENAME,
                        path=TreePath(("definitions", output_index)),
                        description=(
                            f"Rename function '{definition.name}' to '{renamed}'."
                        ),
                    )
                )
        occupied.update(
            definition.name for definition in definitions[definition_offset:]
        )

        for source_index, expression in enumerate(program.body):
            output_index = len(body)
            body.append(_rename_calls(expression, mapping))
            changes.append(
                TreeChange(
                    kind=TreeChangeKind.INSERT,
                    path=TreePath(("body", output_index)),
                    description=(
                        f"Insert body expression from program {program_index}, "
                        f"source index {source_index}."
                    ),
                )
            )

    combined = TreeProgram(
        definitions=definitions,
        body=body,
        mode=mode,
        name=name,
        description=description,
    )
    validated = validate_transformed_program(combined, limits)
    return TransformResult(
        tree=validated,
        lineage=(
            TransformationRecord(name="compose-programs", changes=tuple(changes)),
        ),
    )


def _definition_mapping(program: TreeProgram, occupied: set[str]) -> dict[str, str]:
    remaining = {definition.name for definition in program.definitions}
    allocated = set(occupied)
    mapping: dict[str, str] = {}
    for definition in program.definitions:
        original = definition.name
        remaining.remove(original)
        renamed = original
        if renamed in allocated:
            suffix = 2
            while f"{original}_{suffix}" in allocated | remaining:
                suffix += 1
            renamed = f"{original}_{suffix}"
        mapping[original] = renamed
        allocated.add(renamed)
    return mapping


def _rename_calls(expression: Expression, mapping: dict[str, str]) -> Expression:
    if isinstance(expression, TreeCall):
        return expression.model_copy(
            update={
                "function": mapping[expression.function],
                "arguments": [
                    _rename_calls(argument, mapping)
                    for argument in expression.arguments
                ],
            }
        )
    if isinstance(expression, TreeToolCall):
        return expression.model_copy(
            update={
                "arguments": {
                    name: _rename_calls(argument, mapping)
                    for name, argument in expression.arguments.items()
                }
            }
        )
    if isinstance(expression, TreeConditional):
        return expression.model_copy(
            update={
                "condition": _rename_calls(expression.condition, mapping),
                "true_branch": _rename_calls(expression.true_branch, mapping),
                "false_branch": _rename_calls(expression.false_branch, mapping),
            }
        )
    return expression


__all__ = ["compose_programs"]
