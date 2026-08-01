"""Conservative, semantics-preserving tree pruning."""

from __future__ import annotations

from typing import overload

from treelang.trees.schemas.v1 import TreeNode
from treelang.trees.schemas.v2 import (
    AST,
    Expression,
    TreeCall,
    TreeConditional,
    TreeFunctionDefinition,
    TreeLiteral,
    TreeProgram,
    TreeToolCall,
)
from treelang.trees.transforms import (
    TransformationRecord,
    TransformResult,
    TreeChange,
    TreeChangeKind,
    TreePath,
)


class ConservativeTreePruner:
    """Apply only locally provable rewrites without evaluating external tools."""

    @overload
    def prune(self, tree: TreeProgram) -> TransformResult[TreeProgram]: ...

    @overload
    def prune(self, tree: TreeNode) -> TransformResult[TreeNode]: ...

    def prune(
        self, tree: TreeProgram | TreeNode
    ) -> TransformResult[TreeProgram] | TransformResult[TreeNode]:
        """Return a validated pruned copy, or the original version 1 tree."""

        if isinstance(tree, TreeNode):
            return TransformResult(tree=tree)

        # Validate the input as a complete program before deriving its call graph.
        program = AST(root=tree).root
        simplified, simplification_changes = _simplify_program(program)
        reachable = _reachable_definitions(simplified)
        definitions: list[TreeFunctionDefinition] = []
        removal_changes: list[TreeChange] = []
        for index, definition in enumerate(simplified.definitions):
            if definition.name in reachable:
                definitions.append(definition)
                continue
            removal_changes.append(
                TreeChange(
                    kind=TreeChangeKind.REMOVE,
                    path=TreePath(("definitions", index)),
                    description=(
                        f"Remove unreachable function definition '{definition.name}'."
                    ),
                )
            )

        pruned = simplified.model_copy(update={"definitions": definitions})
        validated = AST(root=pruned).root
        return TransformResult(
            tree=validated,
            lineage=(
                TransformationRecord(
                    name="simplify-literal-conditionals",
                    changes=tuple(simplification_changes),
                ),
                TransformationRecord(
                    name="remove-unreachable-functions",
                    changes=tuple(removal_changes),
                ),
            ),
        )


@overload
def prune_tree(tree: TreeProgram) -> TransformResult[TreeProgram]: ...


@overload
def prune_tree(tree: TreeNode) -> TransformResult[TreeNode]: ...


def prune_tree(
    tree: TreeProgram | TreeNode,
) -> TransformResult[TreeProgram] | TransformResult[TreeNode]:
    """Prune a version 2 program, preserving version 1 trees unchanged."""

    return ConservativeTreePruner().prune(tree)


def _simplify_program(program: TreeProgram) -> tuple[TreeProgram, list[TreeChange]]:
    changes: list[TreeChange] = []
    definitions = [
        definition.model_copy(
            update={
                "body": _simplify_expression(
                    definition.body,
                    TreePath(("definitions", index, "body")),
                    changes,
                )
            }
        )
        for index, definition in enumerate(program.definitions)
    ]
    body = [
        _simplify_expression(expression, TreePath(("body", index)), changes)
        for index, expression in enumerate(program.body)
    ]
    return program.model_copy(
        update={"definitions": definitions, "body": body}
    ), changes


def _simplify_expression(
    expression: Expression,
    path: TreePath,
    changes: list[TreeChange],
) -> Expression:
    if isinstance(expression, TreeCall):
        call_arguments = [
            _simplify_expression(
                argument, path.child("arguments").child(index), changes
            )
            for index, argument in enumerate(expression.arguments)
        ]
        return expression.model_copy(update={"arguments": call_arguments})

    if isinstance(expression, TreeToolCall):
        tool_arguments = {
            name: _simplify_expression(
                argument, path.child("arguments").child(name), changes
            )
            for name, argument in expression.arguments.items()
        }
        return expression.model_copy(update={"arguments": tool_arguments})

    if not isinstance(expression, TreeConditional):
        return expression

    condition = _simplify_expression(
        expression.condition, path.child("condition"), changes
    )
    if isinstance(condition, TreeLiteral) and isinstance(condition.value, bool):
        branch_name = "true_branch" if condition.value else "false_branch"
        branch = expression.true_branch if condition.value else expression.false_branch
        simplified = _simplify_expression(branch, path.child(branch_name), changes)
        changes.append(
            TreeChange(
                kind=TreeChangeKind.REPLACE,
                path=path,
                description=f"Replace literal conditional with its {branch_name}.",
            )
        )
        return simplified

    true_branch = _simplify_expression(
        expression.true_branch, path.child("true_branch"), changes
    )
    false_branch = _simplify_expression(
        expression.false_branch, path.child("false_branch"), changes
    )
    return expression.model_copy(
        update={
            "condition": condition,
            "true_branch": true_branch,
            "false_branch": false_branch,
        }
    )


def _reachable_definitions(program: TreeProgram) -> set[str]:
    calls_by_definition = {
        definition.name: _called_functions(definition.body)
        for definition in program.definitions
    }
    pending = [
        name for expression in program.body for name in _called_functions(expression)
    ]
    reachable: set[str] = set()
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        pending.extend(calls_by_definition[name] - reachable)
    return reachable


def _called_functions(expression: Expression) -> set[str]:
    if isinstance(expression, TreeCall):
        call_dependencies = {expression.function}
        for argument in expression.arguments:
            call_dependencies.update(_called_functions(argument))
        return call_dependencies
    if isinstance(expression, TreeToolCall):
        tool_dependencies: set[str] = set()
        for argument in expression.arguments.values():
            tool_dependencies.update(_called_functions(argument))
        return tool_dependencies
    if isinstance(expression, TreeConditional):
        return (
            _called_functions(expression.condition)
            | _called_functions(expression.true_branch)
            | _called_functions(expression.false_branch)
        )
    return set()


__all__ = ["ConservativeTreePruner", "prune_tree"]
