import asyncio

import pytest

from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.exceptions import ExecutionLimitError
from treelang.trees.budget import ExecutionLimits
from treelang.trees.schemas.v1 import (
    TreeFunction,
    TreeLambda,
    TreeMap,
    TreeProgram,
    TreeReduce,
    TreeValue,
)
from treelang.trees.tree import AST


class ArithmeticProvider(ToolProvider):
    async def list_tools(self):
        return []

    async def get_tool_definition(self, name):
        properties = {
            "identity": {"value": {}},
            "add": {"acc": {}, "item": {}},
        }[name]
        return {"name": name, "properties": properties}

    async def call_tool(self, name, arguments):
        if name == "identity":
            return ToolOutput(content=arguments["value"])
        return ToolOutput(content=arguments["acc"] + arguments["item"])


def value_program(value=42):
    return TreeProgram(
        body=[TreeValue(name="value", value=value)],
        mode="single",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_nodes", 0),
        ("max_depth", -1),
        ("max_call_depth", 0),
        ("max_tool_calls", True),
        ("max_concurrency", 1.5),
        ("timeout_seconds", 0),
        ("timeout_seconds", float("nan")),
    ],
)
def test_limits_require_positive_values(field, value):
    with pytest.raises(ValueError, match=field):
        ExecutionLimits(**{field: value})


@pytest.mark.asyncio
async def test_node_limit_is_inclusive():
    program = value_program()
    provider = ArithmeticProvider()

    assert await AST.eval(program, provider, limits=ExecutionLimits(max_nodes=2)) == 42
    with pytest.raises(ExecutionLimitError) as captured:
        await AST.eval(program, provider, limits=ExecutionLimits(max_nodes=1))

    assert captured.value.resource == "nodes"
    assert captured.value.limit == 1


@pytest.mark.asyncio
async def test_depth_limit_is_inclusive():
    program = TreeProgram(
        body=[
            TreeFunction(
                name="identity",
                params=[
                    TreeFunction(
                        name="identity",
                        params=[TreeValue(name="value", value=7)],
                    )
                ],
            )
        ],
        mode="single",
    )
    provider = ArithmeticProvider()

    assert await AST.eval(program, provider, limits=ExecutionLimits(max_depth=4)) == 7
    with pytest.raises(ExecutionLimitError) as captured:
        await AST.eval(program, provider, limits=ExecutionLimits(max_depth=3))

    assert captured.value.resource == "depth"


@pytest.mark.asyncio
async def test_tool_call_limit_counts_repeated_reduce_invocations():
    tree = TreeReduce(
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
        iterable=TreeValue(name="items", value=[1, 2, 3]),
    )

    with pytest.raises(ExecutionLimitError) as captured:
        await AST.eval(
            tree,
            ArithmeticProvider(),
            limits=ExecutionLimits(max_tool_calls=1),
        )

    assert captured.value.resource == "tool_calls"
    assert captured.value.limit == 1


@pytest.mark.asyncio
async def test_node_limit_counts_each_lambda_body_invocation():
    tree = TreeMap(
        function=TreeLambda(
            params=["value"],
            body=TreeFunction(
                name="identity",
                params=[TreeValue(name="value", value=None)],
            ),
        ),
        iterable=TreeValue(name="items", value=[1, 2]),
    )
    provider = ArithmeticProvider()

    assert await AST.eval(tree, provider, limits=ExecutionLimits(max_nodes=7)) == [1, 2]
    with pytest.raises(ExecutionLimitError):
        await AST.eval(tree, provider, limits=ExecutionLimits(max_nodes=6))


@pytest.mark.asyncio
async def test_timeout_cancels_an_in_progress_tool_call():
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class BlockingProvider(ArithmeticProvider):
        async def get_tool_definition(self, name):
            return {"name": name, "properties": {}}

        async def call_tool(self, name, arguments):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    tree = TreeFunction(name="blocking", params=[])
    with pytest.raises(ExecutionLimitError) as captured:
        await AST.eval(
            tree,
            BlockingProvider(),
            limits=ExecutionLimits(timeout_seconds=0.01),
        )

    assert started.is_set()
    assert cancelled.is_set()
    assert captured.value.resource == "wall_clock_seconds"


@pytest.mark.asyncio
async def test_external_cancellation_still_propagates():
    started = asyncio.Event()

    class BlockingProvider(ArithmeticProvider):
        async def get_tool_definition(self, name):
            return {"name": name, "properties": {}}

        async def call_tool(self, name, arguments):
            started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(
        AST.eval(
            TreeFunction(name="blocking", params=[]),
            BlockingProvider(),
            limits=ExecutionLimits(timeout_seconds=10),
        )
    )
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_provider_timeout_is_not_reported_as_budget_exhaustion():
    class TimedOutProvider(ArithmeticProvider):
        async def get_tool_definition(self, name):
            return {"name": name, "properties": {}}

        async def call_tool(self, name, arguments):
            raise TimeoutError("provider timed out")

    with pytest.raises(TimeoutError, match="provider timed out"):
        await AST.eval(
            TreeFunction(name="timed_out", params=[]),
            TimedOutProvider(),
            limits=ExecutionLimits(timeout_seconds=10),
        )


@pytest.mark.asyncio
async def test_concurrency_limit_caps_parallel_program_branches():
    class OverlappingProvider(ArithmeticProvider):
        def __init__(self):
            super().__init__()
            self.active = 0
            self.max_active = 0

        async def get_tool_definition(self, name):
            return {"name": name, "properties": {}}

        async def call_tool(self, name, arguments):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            try:
                await asyncio.sleep(0.01)
                return ToolOutput(content=name)
            finally:
                self.active -= 1

    provider = OverlappingProvider()
    program = TreeProgram(
        body=[TreeFunction(name=f"tool_{index}", params=[]) for index in range(4)],
        mode="parallel",
    )

    assert await AST.eval(
        program,
        provider,
        limits=ExecutionLimits(max_concurrency=2),
    ) == ["tool_0", "tool_1", "tool_2", "tool_3"]
    assert provider.max_active == 2


@pytest.mark.asyncio
async def test_concurrent_invocations_do_not_share_counters():
    tree = TreeFunction(
        name="identity",
        params=[TreeValue(name="value", value=3)],
    )
    limits = ExecutionLimits(max_tool_calls=1)

    assert await asyncio.gather(
        AST.eval(tree, ArithmeticProvider(), limits=limits),
        AST.eval(tree, ArithmeticProvider(), limits=limits),
    ) == [3, 3]


@pytest.mark.asyncio
async def test_compiled_tool_preserves_limit_error():
    program = TreeProgram(
        body=[
            TreeFunction(
                name="identity",
                params=[TreeValue(name="value", value=None)],
            )
        ],
        mode="single",
        name="identity_tool",
        description="Return one value.",
    )
    tool = await AST.tool(
        program,
        ArithmeticProvider(),
        limits=ExecutionLimits(max_nodes=2),
    )

    with pytest.raises(ExecutionLimitError) as captured:
        await tool(value=3)

    assert captured.value.resource == "nodes"
