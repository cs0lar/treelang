import pytest
from pydantic import ValidationError

from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.exceptions import TreeTransformationError
from treelang.trees.composition import compose_programs
from treelang.trees.execution_v2 import execute_v2
from treelang.trees.schemas.v2 import (
    TreeCall,
    TreeConditional,
    TreeFunctionDefinition,
    TreeLiteral,
    TreeProgram,
    TreeToolCall,
    TreeVariable,
)
from treelang.trees.transforms import TransformationLimits, TreeChangeKind, TreePath


class NoToolsProvider(ToolProvider):
    async def list_tools(self):
        self.tools = {}
        return []

    async def call_tool(self, name, arguments):  # pragma: no cover - safety guard
        return ToolOutput(content=None)


def identity_program(name: str, value: int) -> TreeProgram:
    return TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name=name,
                params=["value"],
                body=TreeVariable(name="value"),
            )
        ],
        body=[TreeCall(function=name, arguments=[TreeLiteral(value=value)])],
    )


def test_composition_preserves_program_and_body_order():
    first = identity_program("first", 1)
    second = identity_program("second", 2)

    result = compose_programs(
        [first, second],
        mode="parallel",
        name="Combined",
        description="Run both independent programs.",
    )

    assert result.tree.mode == "parallel"
    assert result.tree.name == "Combined"
    assert result.tree.description == "Run both independent programs."
    assert [definition.name for definition in result.tree.definitions] == [
        "first",
        "second",
    ]
    assert [expression.function for expression in result.tree.body] == [
        "first",
        "second",
    ]
    assert [change.path for change in result.changes] == [
        TreePath(("definitions", 0)),
        TreePath(("body", 0)),
        TreePath(("definitions", 1)),
        TreePath(("body", 1)),
    ]


@pytest.mark.asyncio
async def test_composed_program_preserves_independent_execution_results():
    first = TreeProgram(body=[TreeLiteral(value=1)])
    second = TreeProgram(body=[TreeLiteral(value=2)])
    provider = NoToolsProvider()

    before = [
        await execute_v2(first, provider),
        await execute_v2(second, provider),
    ]
    combined = compose_programs([first, second], mode="parallel")

    assert await execute_v2(combined.tree, provider) == before


def test_collision_renames_definition_and_all_recursive_calls():
    first = identity_program("repeat", 1)
    recursive = TreeFunctionDefinition(
        name="repeat",
        params=["value"],
        body=TreeConditional(
            condition=TreeLiteral(value=True),
            true_branch=TreeVariable(name="value"),
            false_branch=TreeCall(
                function="repeat", arguments=[TreeVariable(name="value")]
            ),
        ),
    )
    second = TreeProgram(
        definitions=[recursive],
        body=[TreeCall(function="repeat", arguments=[TreeLiteral(value=2)])],
    )

    result = compose_programs([first, second])

    renamed = result.tree.definitions[1]
    assert renamed.name == "repeat_2"
    assert renamed.params == ["value"]
    assert isinstance(renamed.body, TreeConditional)
    assert renamed.body.false_branch == TreeCall(
        function="repeat_2", arguments=[TreeVariable(name="value")]
    )
    assert result.tree.body[1] == TreeCall(
        function="repeat_2", arguments=[TreeLiteral(value=2)]
    )
    assert [change.kind for change in result.changes].count(TreeChangeKind.RENAME) == 1


def test_collision_suffixes_reserve_untouched_incoming_names():
    first = identity_program("step", 1)
    second = TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name="step",
                body=TreeCall(function="step_2"),
            ),
            TreeFunctionDefinition(name="step_2", body=TreeLiteral(value=2)),
        ],
        body=[TreeCall(function="step")],
    )

    result = compose_programs([first, second])

    assert [definition.name for definition in result.tree.definitions] == [
        "step",
        "step_3",
        "step_2",
    ]
    assert result.tree.definitions[1].body == TreeCall(function="step_2")
    assert result.tree.body[-1] == TreeCall(function="step_3")


def test_composition_does_not_rename_tool_names_or_lexical_variables():
    first = identity_program("lookup", 1)
    second = TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name="lookup",
                params=["lookup"],
                body=TreeToolCall(
                    tool="lookup",
                    arguments={"value": TreeVariable(name="lookup")},
                ),
            )
        ],
        body=[TreeCall(function="lookup", arguments=[TreeLiteral(value=2)])],
    )

    result = compose_programs([first, second])
    definition = result.tree.definitions[1]

    assert definition.name == "lookup_2"
    assert definition.params == ["lookup"]
    assert definition.body == TreeToolCall(
        tool="lookup", arguments={"value": TreeVariable(name="lookup")}
    )


def test_composition_is_deterministic_and_does_not_mutate_inputs():
    first = identity_program("same", 1)
    second = identity_program("same", 2)
    originals = [first.model_dump_json(), second.model_dump_json()]

    one = compose_programs([first, second])
    two = compose_programs([first, second])

    assert one == two
    assert [first.model_dump_json(), second.model_dump_json()] == originals


def test_composition_requires_two_valid_programs_and_a_valid_mode():
    valid = TreeProgram(body=[TreeLiteral(value=1)])

    with pytest.raises(TreeTransformationError, match="at least two"):
        compose_programs([valid])
    with pytest.raises(TreeTransformationError, match="mode"):
        compose_programs([valid, valid], mode="invalid")

    invalid = TreeProgram(body=[TreeCall(function="missing")])
    with pytest.raises(ValidationError, match="Unknown user function"):
        compose_programs([valid, invalid])


def test_composition_enforces_resulting_structural_limits():
    first = TreeProgram(body=[TreeLiteral(value=1)])
    second = TreeProgram(body=[TreeLiteral(value=2)])

    accepted = compose_programs(
        [first, second], limits=TransformationLimits(max_nodes=3, max_depth=2)
    )
    assert len(accepted.tree.body) == 2

    with pytest.raises(TreeTransformationError, match="max_nodes"):
        compose_programs([first, second], limits=TransformationLimits(max_nodes=2))
