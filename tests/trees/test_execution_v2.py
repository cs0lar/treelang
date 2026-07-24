import asyncio

import pytest

from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.exceptions import ASTValidationError, ExecutionLimitError
from treelang.trees.budget import ExecutionLimits
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


class ArithmeticProvider(ToolProvider):
    def __init__(self) -> None:
        super().__init__()
        self.tools = {
            "less_than_or_equal": {
                "name": "less_than_or_equal",
                "properties": {"a": {}, "b": {}},
            },
            "subtract": {
                "name": "subtract",
                "properties": {"a": {}, "b": {}},
            },
            "multiply": {
                "name": "multiply",
                "properties": {"a": {}, "b": {}},
            },
            "add": {"name": "add", "properties": {"a": {}, "b": {}}},
            "constant": {"name": "constant", "properties": {}},
            "not": {"name": "not", "properties": {"value": {}}},
            "wait": {"name": "wait", "properties": {"value": {}}},
        }

    async def list_tools(self):
        return list(self.tools.values()) if self.tools else []

    async def call_tool(self, name, arguments):
        if name == "less_than_or_equal":
            value = arguments["a"] <= arguments["b"]
        elif name == "subtract":
            value = arguments["a"] - arguments["b"]
        elif name == "multiply":
            value = arguments["a"] * arguments["b"]
        elif name == "add":
            value = arguments["a"] + arguments["b"]
        elif name == "constant":
            value = 42
        elif name == "not":
            value = not arguments["value"]
        else:
            await asyncio.sleep(0.01)
            value = arguments["value"]
        return ToolOutput(content=value)


def factorial_program(value: int) -> TreeProgram:
    return TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name="factorial",
                params=["n"],
                body=TreeConditional(
                    condition=TreeToolCall(
                        tool="less_than_or_equal",
                        arguments={
                            "a": TreeVariable(name="n"),
                            "b": TreeLiteral(value=1),
                        },
                    ),
                    true_branch=TreeLiteral(value=1),
                    false_branch=TreeToolCall(
                        tool="multiply",
                        arguments={
                            "a": TreeVariable(name="n"),
                            "b": TreeCall(
                                function="factorial",
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
                        },
                    ),
                ),
            )
        ],
        body=[TreeCall(function="factorial", arguments=[TreeLiteral(value=value)])],
    )


@pytest.mark.asyncio
async def test_executes_direct_recursion():
    result = await execute_v2(
        factorial_program(6),
        ArithmeticProvider(),
        limits=ExecutionLimits(max_call_depth=6),
    )

    assert result == 720


@pytest.mark.asyncio
async def test_executes_zero_and_multiple_argument_user_calls():
    program = TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name="answer",
                params=[],
                body=TreeToolCall(tool="constant"),
            ),
            TreeFunctionDefinition(
                name="add",
                params=["left", "right"],
                body=TreeToolCall(
                    tool="add",
                    arguments={
                        "a": TreeVariable(name="left"),
                        "b": TreeVariable(name="right"),
                    },
                ),
            ),
        ],
        body=[
            TreeCall(
                function="add",
                arguments=[
                    TreeCall(function="answer"),
                    TreeLiteral(value=8),
                ],
            )
        ],
    )

    assert await execute_v2(program, ArithmeticProvider()) == 50


@pytest.mark.asyncio
async def test_call_depth_is_inclusive_and_independent_of_structural_depth():
    provider = ArithmeticProvider()
    assert (
        await execute_v2(
            factorial_program(5),
            provider,
            limits=ExecutionLimits(max_call_depth=5, max_depth=6),
        )
        == 120
    )

    with pytest.raises(ExecutionLimitError) as captured:
        await execute_v2(
            factorial_program(5),
            provider,
            limits=ExecutionLimits(max_call_depth=4),
        )

    assert captured.value.resource == "call_depth"
    assert captured.value.limit == 4


@pytest.mark.asyncio
async def test_deep_recursion_does_not_use_the_python_call_stack():
    countdown = TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name="countdown",
                params=["n"],
                body=TreeConditional(
                    condition=TreeToolCall(
                        tool="less_than_or_equal",
                        arguments={
                            "a": TreeVariable(name="n"),
                            "b": TreeLiteral(value=0),
                        },
                    ),
                    true_branch=TreeLiteral(value=0),
                    false_branch=TreeCall(
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
        body=[TreeCall(function="countdown", arguments=[TreeLiteral(value=1100)])],
    )

    assert (
        await execute_v2(
            countdown,
            ArithmeticProvider(),
            limits=ExecutionLimits(max_call_depth=1101, max_nodes=10_000),
        )
        == 0
    )


@pytest.mark.asyncio
async def test_executes_mutual_recursion():
    program = TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name="even",
                params=["n"],
                body=TreeConditional(
                    condition=TreeToolCall(
                        tool="less_than_or_equal",
                        arguments={
                            "a": TreeVariable(name="n"),
                            "b": TreeLiteral(value=0),
                        },
                    ),
                    true_branch=TreeLiteral(value=True),
                    false_branch=TreeCall(
                        function="odd",
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
            ),
            TreeFunctionDefinition(
                name="odd",
                params=["n"],
                body=TreeToolCall(
                    tool="not",
                    arguments={
                        "value": TreeCall(
                            function="even",
                            arguments=[TreeVariable(name="n")],
                        )
                    },
                ),
            ),
        ],
        body=[TreeCall(function="even", arguments=[TreeLiteral(value=10)])],
    )

    assert await execute_v2(program, ArithmeticProvider()) is True


@pytest.mark.asyncio
async def test_conditionals_are_lazy():
    program = TreeProgram(
        definitions=[],
        body=[
            TreeConditional(
                condition=TreeLiteral(value=True),
                true_branch=TreeLiteral(value="selected"),
                false_branch=TreeToolCall(tool="missing"),
            )
        ],
    )

    assert await execute_v2(program, ArithmeticProvider()) == "selected"


@pytest.mark.asyncio
async def test_validates_tool_argument_names_before_calling():
    program = TreeProgram(
        definitions=[],
        body=[
            TreeToolCall(
                tool="multiply",
                arguments={"a": TreeLiteral(value=2)},
            )
        ],
    )

    with pytest.raises(ASTValidationError, match="expects arguments"):
        await execute_v2(program, ArithmeticProvider())


@pytest.mark.asyncio
async def test_shares_node_and_tool_budgets_across_recursion():
    with pytest.raises(ExecutionLimitError, match="tool_calls"):
        await execute_v2(
            factorial_program(3),
            ArithmeticProvider(),
            limits=ExecutionLimits(max_tool_calls=2),
        )
    with pytest.raises(ExecutionLimitError, match="nodes"):
        await execute_v2(
            factorial_program(3),
            ArithmeticProvider(),
            limits=ExecutionLimits(max_nodes=5),
        )


@pytest.mark.asyncio
async def test_parallel_program_honors_concurrency_limit():
    class TrackingProvider(ArithmeticProvider):
        def __init__(self):
            super().__init__()
            self.active = 0
            self.maximum = 0

        async def call_tool(self, name, arguments):
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            try:
                return await super().call_tool(name, arguments)
            finally:
                self.active -= 1

    provider = TrackingProvider()
    program = TreeProgram(
        definitions=[],
        body=[
            TreeToolCall(tool="wait", arguments={"value": TreeLiteral(value=index)})
            for index in range(3)
        ],
        mode="parallel",
    )

    assert await execute_v2(
        program, provider, limits=ExecutionLimits(max_concurrency=1)
    ) == [0, 1, 2]
    assert provider.maximum == 1


@pytest.mark.asyncio
async def test_wall_clock_timeout_cancels_tool():
    program = TreeProgram(
        definitions=[],
        body=[TreeToolCall(tool="wait", arguments={"value": TreeLiteral(value=1)})],
    )

    with pytest.raises(ExecutionLimitError) as captured:
        await execute_v2(
            program,
            ArithmeticProvider(),
            limits=ExecutionLimits(timeout_seconds=0.001),
        )

    assert captured.value.resource == "wall_clock_seconds"


@pytest.mark.asyncio
async def test_wall_clock_timeout_stops_tool_free_infinite_recursion():
    program = TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name="forever",
                params=[],
                body=TreeCall(function="forever"),
            )
        ],
        body=[TreeCall(function="forever")],
    )

    with pytest.raises(ExecutionLimitError) as captured:
        await execute_v2(
            program,
            ArithmeticProvider(),
            limits=ExecutionLimits(timeout_seconds=0.001),
        )

    assert captured.value.resource == "wall_clock_seconds"


@pytest.mark.asyncio
async def test_provider_timeout_and_external_cancellation_propagate():
    class BlockingProvider(ArithmeticProvider):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.raise_timeout = True

        async def call_tool(self, name, arguments):
            if self.raise_timeout:
                raise TimeoutError("provider timed out")
            self.started.set()
            await asyncio.Event().wait()

    program = TreeProgram(
        definitions=[],
        body=[TreeToolCall(tool="constant")],
    )
    provider = BlockingProvider()
    with pytest.raises(TimeoutError, match="provider timed out"):
        await execute_v2(
            program,
            provider,
            limits=ExecutionLimits(timeout_seconds=10),
        )

    provider.raise_timeout = False
    task = asyncio.create_task(
        execute_v2(
            program,
            provider,
            limits=ExecutionLimits(timeout_seconds=10),
        )
    )
    await provider.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
