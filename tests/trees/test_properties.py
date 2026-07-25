"""Generative invariants for parsing, traversal, and execution."""

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.exceptions import ExecutionLimitError
from treelang.trees.budget import ExecutionLimits
from treelang.trees.execution_v2 import execute_v2
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
from treelang.trees.schemas.v2 import (
    TreeCall as TreeCallV2,
)
from treelang.trees.schemas.v2 import (
    TreeConditional as TreeConditionalV2,
)
from treelang.trees.schemas.v2 import (
    TreeFunctionDefinition,
    TreeLiteral,
    TreeToolCall,
    TreeVariable,
)
from treelang.trees.schemas.v2 import (
    TreeProgram as TreeProgramV2,
)
from treelang.trees.tree import AST

PROPERTY_SETTINGS = settings(max_examples=40, deadline=None)
SMALL_INTEGERS = st.integers(min_value=-10_000, max_value=10_000)
INTEGER_LISTS = st.lists(SMALL_INTEGERS, max_size=20)
JSON_VALUES = st.recursive(
    st.none()
    | st.booleans()
    | SMALL_INTEGERS
    | st.floats(allow_nan=False, allow_infinity=False, width=32)
    | st.text(max_size=20),
    lambda children: (
        st.lists(children, max_size=5)
        | st.dictionaries(st.text(min_size=1, max_size=10), children, max_size=5)
    ),
    max_leaves=20,
)
VALUE_NODES = st.builds(TreeValue, name=st.just("value"), value=JSON_VALUES)
TRAVERSABLE_NODES = st.recursive(
    VALUE_NODES,
    lambda children: st.builds(
        TreeConditional,
        condition=children,
        true_branch=children,
        false_branch=st.one_of(st.none(), children),
    ),
    max_leaves=20,
)


class PropertyProvider(ToolProvider):
    """Small deterministic provider used by generated execution cases."""

    def __init__(self) -> None:
        super().__init__()
        integer = {"type": "integer"}
        number = {"type": "number"}
        self.tools = {
            "identity": {"name": "identity", "properties": {"value": integer}},
            "is_even": {"name": "is_even", "properties": {"value": integer}},
            "add": {
                "name": "add",
                "properties": {"acc": number, "item": number},
            },
            "less_than_or_equal": {
                "name": "less_than_or_equal",
                "properties": {"a": number, "b": number},
            },
            "subtract": {
                "name": "subtract",
                "properties": {"a": number, "b": number},
            },
        }

    async def list_tools(self):
        return list(self.tools.values()) if self.tools else []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolOutput:
        await asyncio.sleep(0)
        if name == "identity":
            result = arguments["value"]
        elif name == "is_even":
            result = arguments["value"] % 2 == 0
        elif name == "add":
            result = arguments["acc"] + arguments["item"]
        elif name == "less_than_or_equal":
            result = arguments["a"] <= arguments["b"]
        else:
            result = arguments["a"] - arguments["b"]
        return ToolOutput(content=result)


def walk_reference(node: TreeNode) -> Iterator[TreeNode]:
    """Independent reference traversal for the generated v1 node subset."""
    yield node
    if isinstance(node, TreeProgram):
        for child in node.body:
            yield from walk_reference(child)
    elif isinstance(node, TreeConditional):
        yield from walk_reference(node.condition)
        yield from walk_reference(node.true_branch)
        if node.false_branch is not None:
            yield from walk_reference(node.false_branch)


def unary_node(kind: type[TreeMap] | type[TreeFilter], values: list[int]) -> TreeNode:
    tool = "identity" if kind is TreeMap else "is_even"
    return kind(
        function=TreeLambda(
            params=["value"],
            body=TreeFunction(
                name=tool,
                params=[TreeValue(name="value", value=None)],
            ),
        ),
        iterable=TreeValue(name="items", value=values),
    )


def reduce_node(values: list[int]) -> TreeReduce:
    return TreeReduce(
        function=TreeLambda(
            params=["acc", "item"],
            body=TreeFunction(
                name="add",
                params=[
                    TreeValue(name="acc", value=None),
                    TreeValue(name="item", value=None),
                ],
            ),
        ),
        iterable=TreeValue(name="items", value=values),
    )


def countdown_program(value: int) -> TreeProgramV2:
    return TreeProgramV2(
        definitions=[
            TreeFunctionDefinition(
                name="countdown",
                params=["n"],
                body=TreeConditionalV2(
                    condition=TreeToolCall(
                        tool="less_than_or_equal",
                        arguments={
                            "a": TreeVariable(name="n"),
                            "b": TreeLiteral(value=0),
                        },
                    ),
                    true_branch=TreeLiteral(value=0),
                    false_branch=TreeCallV2(
                        function="countdown",
                        arguments=[
                            TreeToolCall(
                                tool="subtract",
                                arguments={
                                    "a": TreeVariable(name="n"),
                                    "b": TreeLiteral(value=1),
                                },
                            )
                        ],
                    ),
                ),
            )
        ],
        body=[TreeCallV2(function="countdown", arguments=[TreeLiteral(value=value)])],
    )


@PROPERTY_SETTINGS
@given(TRAVERSABLE_NODES)
def test_v1_programs_round_trip_through_parser(node: TreeNode) -> None:
    program = TreeProgram(body=[node], mode="single")
    serialized = program.model_dump(mode="json")
    parsed = AST.parse(serialized)
    assert parsed.model_dump(mode="json") == serialized
    assert parsed.hash() == program.hash()


@PROPERTY_SETTINGS
@given(st.dictionaries(st.text(max_size=12), JSON_VALUES, max_size=12))
def test_parser_fuzz_inputs_either_validate_or_fail_safely(
    payload: dict[str, Any],
) -> None:
    try:
        parsed = AST.parse(payload)
    except ValueError:
        return

    assert isinstance(parsed, TreeProgram)
    assert AST.parse(parsed.model_dump(mode="json")) == parsed


@PROPERTY_SETTINGS
@given(TRAVERSABLE_NODES)
def test_traversal_is_preorder_and_visits_every_node_once(node: TreeNode) -> None:
    visited: list[TreeNode] = []
    AST.visit(node, visited.append)
    assert visited == list(walk_reference(node))


@PROPERTY_SETTINGS
@given(st.booleans(), JSON_VALUES, JSON_VALUES)
def test_conditionals_evaluate_only_the_selected_value(
    condition: bool, true_value: Any, false_value: Any
) -> None:
    selected = true_value if condition else false_value
    failing = TreeFunction(name="unavailable", params=[])
    node = TreeConditional(
        condition=TreeValue(name="condition", value=condition),
        true_branch=TreeValue(name="true", value=selected) if condition else failing,
        false_branch=failing if condition else TreeValue(name="false", value=selected),
    )
    result = asyncio.run(node.eval(PropertyProvider()))
    assert result == selected


@PROPERTY_SETTINGS
@given(INTEGER_LISTS)
def test_map_lambda_matches_python_identity(values: list[int]) -> None:
    result = asyncio.run(unary_node(TreeMap, values).eval(PropertyProvider()))
    assert result == values


@PROPERTY_SETTINGS
@given(INTEGER_LISTS)
def test_filter_lambda_matches_python_predicate(values: list[int]) -> None:
    result = asyncio.run(unary_node(TreeFilter, values).eval(PropertyProvider()))
    assert result == [value for value in values if value % 2 == 0]


@PROPERTY_SETTINGS
@given(INTEGER_LISTS)
def test_reduce_lambda_matches_python_sum(values: list[int]) -> None:
    result = asyncio.run(reduce_node(values).eval(PropertyProvider()))
    assert result == (sum(values) if values else None)


@PROPERTY_SETTINGS
@given(st.integers(min_value=0, max_value=25))
def test_recursion_obeys_generated_call_depth(value: int) -> None:
    program = countdown_program(value)
    result = asyncio.run(
        execute_v2(
            program,
            PropertyProvider(),
            limits=ExecutionLimits(max_call_depth=value + 1, max_nodes=500),
        )
    )
    assert result == 0
    if value:
        with pytest.raises(ExecutionLimitError, match="call_depth"):
            asyncio.run(
                execute_v2(
                    program,
                    PropertyProvider(),
                    limits=ExecutionLimits(max_call_depth=value, max_nodes=500),
                )
            )


@PROPERTY_SETTINGS
@given(SMALL_INTEGERS, SMALL_INTEGERS)
def test_shared_lambda_is_isolated_across_concurrent_calls(
    left: int, right: int
) -> None:
    placeholder = TreeValue(name="value", value=None)
    node = TreeLambda(
        params=["value"],
        body=TreeFunction(name="identity", params=[placeholder]),
    )

    async def invoke() -> list[int]:
        function = await node.eval(PropertyProvider())
        return list(await asyncio.gather(function(value=left), function(value=right)))

    assert asyncio.run(invoke()) == [left, right]
    assert placeholder.value is None
