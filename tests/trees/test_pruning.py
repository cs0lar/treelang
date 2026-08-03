from typing import Any

import pytest
from pydantic import ValidationError

from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.trees.execution_v2 import execute_v2
from treelang.trees.pruning import ConservativeTreePruner, prune_tree
from treelang.trees.schemas.v1 import TreeProgram as TreeProgramV1
from treelang.trees.schemas.v1 import TreeValue
from treelang.trees.schemas.v2 import (
    TreeCall,
    TreeConditional,
    TreeFunctionDefinition,
    TreeLiteral,
    TreeProgram,
    TreeToolCall,
    TreeVariable,
)
from treelang.trees.transforms import TreeChangeKind, TreePath


class RecordingProvider(ToolProvider):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self):
        tools = [
            {"name": "identity", "properties": {"value": {}}},
            {"name": "unused", "properties": {}},
        ]
        self.tools = {tool["name"]: tool for tool in tools}
        return tools

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "identity":
            return ToolOutput(content=arguments["value"])
        return ToolOutput(content="unused")


def function(name: str, body, params=None):
    return TreeFunctionDefinition(name=name, params=params or [], body=body)


def test_v1_pruning_is_an_identity_noop():
    tree = TreeProgramV1(body=[TreeValue(name="answer", value=42)], mode="single")

    result = prune_tree(tree)

    assert result.tree is tree
    assert result.lineage == ()
    assert not result.changed


def test_pruner_removes_unreachable_definitions_transitively():
    tree = TreeProgram(
        definitions=[
            function(
                "entry",
                TreeCall(function="helper", arguments=[TreeVariable(name="value")]),
                ["value"],
            ),
            function("unused", TreeLiteral(value=0)),
            function("helper", TreeVariable(name="value"), ["value"]),
            function("also_unused", TreeCall(function="unused")),
        ],
        body=[TreeCall(function="entry", arguments=[TreeLiteral(value=42)])],
    )

    result = ConservativeTreePruner().prune(tree)

    assert [definition.name for definition in result.tree.definitions] == [
        "entry",
        "helper",
    ]
    assert [change.path for change in result.changes] == [
        TreePath(("definitions", 1)),
        TreePath(("definitions", 3)),
    ]
    assert all(change.kind is TreeChangeKind.REMOVE for change in result.changes)


def test_pruner_preserves_reachable_recursive_definition_cycles():
    tree = TreeProgram(
        definitions=[
            function("first", TreeCall(function="second")),
            function("second", TreeCall(function="first")),
            function("unused", TreeLiteral(value=None)),
        ],
        body=[TreeCall(function="first")],
    )

    result = prune_tree(tree)

    assert [definition.name for definition in result.tree.definitions] == [
        "first",
        "second",
    ]


@pytest.mark.parametrize(
    ("condition", "expected"),
    [(True, "chosen"), (False, "fallback")],
)
@pytest.mark.asyncio
async def test_pruner_simplifies_literal_boolean_conditionals_and_preserves_result(
    condition, expected
):
    tree = TreeProgram(
        definitions=[function("dead", TreeLiteral(value="unreachable"))],
        body=[
            TreeToolCall(
                tool="identity",
                arguments={
                    "value": TreeConditional(
                        condition=TreeLiteral(value=condition),
                        true_branch=TreeLiteral(value="chosen"),
                        false_branch=TreeLiteral(value="fallback"),
                    )
                },
            )
        ],
    )
    original_json = tree.model_dump_json()
    original_provider = RecordingProvider()
    pruned_provider = RecordingProvider()

    before = await execute_v2(tree, original_provider)
    result = prune_tree(tree)
    after = await execute_v2(result.tree, pruned_provider)

    assert before == after == expected
    assert original_provider.calls == pruned_provider.calls
    assert tree.model_dump_json() == original_json
    assert result.tree.body == [
        TreeToolCall(tool="identity", arguments={"value": TreeLiteral(value=expected)})
    ]
    assert result.changes[0].path == TreePath(("body", 0, "arguments", "value"))
    assert result.changes[0].kind is TreeChangeKind.REPLACE


def test_simplification_removes_definitions_referenced_only_by_dead_branch():
    tree = TreeProgram(
        definitions=[function("dead", TreeLiteral(value="unused"))],
        body=[
            TreeConditional(
                condition=TreeLiteral(value=True),
                true_branch=TreeLiteral(value="kept"),
                false_branch=TreeCall(function="dead"),
            )
        ],
    )

    result = prune_tree(tree)

    assert result.tree.body == [TreeLiteral(value="kept")]
    assert result.tree.definitions == []
    assert [record.name for record in result.lineage] == [
        "simplify-literal-conditionals",
        "remove-unreachable-functions",
    ]
    assert [change.kind for change in result.changes] == [
        TreeChangeKind.REPLACE,
        TreeChangeKind.REMOVE,
    ]


def test_non_boolean_literals_and_dynamic_conditions_are_not_folded():
    dynamic = TreeConditional(
        condition=TreeLiteral(value=1),
        true_branch=TreeLiteral(value=True),
        false_branch=TreeLiteral(value=False),
    )
    tree = TreeProgram(body=[dynamic])

    result = prune_tree(tree)

    assert result.tree.body == [dynamic]
    assert not result.changed


def test_pruning_is_idempotent_and_reports_no_second_pass_changes():
    tree = TreeProgram(
        definitions=[function("unused", TreeLiteral(value=0))],
        body=[
            TreeConditional(
                condition=TreeLiteral(value=True),
                true_branch=TreeLiteral(value=42),
                false_branch=TreeToolCall(tool="unused"),
            )
        ],
    )

    first = prune_tree(tree)
    second = prune_tree(first.tree)

    assert first.tree == second.tree
    assert first.changed
    assert not second.changed


def test_pruner_rejects_an_invalid_complete_v2_program():
    tree = TreeProgram(body=[TreeCall(function="missing")])

    with pytest.raises(ValidationError, match="Unknown user function"):
        prune_tree(tree)
