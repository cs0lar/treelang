import asyncio
from typing import Any

import pytest

from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.exceptions import ExecutionLimitError, ToolExecutionError
from treelang.trees.budget import ExecutionLimits
from treelang.trees.execution_v2 import execute_v2
from treelang.trees.policy import BranchOutcome, ExecutionPolicy, RetryPolicy
from treelang.trees.schemas.v1 import TreeFunction, TreeProgram, TreeValue
from treelang.trees.schemas.v2 import (
    TreeLiteral,
    TreeToolCall,
)
from treelang.trees.schemas.v2 import (
    TreeProgram as TreeProgramV2,
)
from treelang.trees.tree import AST


class ResilienceProvider(ToolProvider):
    def __init__(self) -> None:
        super().__init__()
        self.tools = {
            "flaky": {"name": "flaky", "properties": {"value": {}}},
            "fail": {"name": "fail", "properties": {}},
            "wait": {"name": "wait", "properties": {"value": {}}},
        }
        self.calls: dict[str, int] = {}
        self.wait_started = asyncio.Event()
        self.wait_cancelled = asyncio.Event()

    async def list_tools(self):
        return list(self.tools.values()) if self.tools else []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolOutput:
        self.calls[name] = self.calls.get(name, 0) + 1
        if name == "flaky" and self.calls[name] == 1:
            raise ToolExecutionError("temporary")
        if name == "fail":
            await self.wait_started.wait()
            raise ToolExecutionError("failed")
        if name == "wait":
            self.wait_started.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                self.wait_cancelled.set()
                raise
        return ToolOutput(content=arguments.get("value"))


def function(name: str, value: Any | None = None) -> TreeFunction:
    params = [] if name == "fail" else [TreeValue(name="value", value=value)]
    return TreeFunction(name=name, params=params)


def retry_policy(*tools: str, attempts: int = 2, delay: float = 0) -> ExecutionPolicy:
    return ExecutionPolicy(
        retry=RetryPolicy(
            max_attempts=attempts,
            delay_seconds=delay,
            idempotent_tools=frozenset(tools),
        )
    )


@pytest.mark.asyncio
async def test_v1_retries_only_explicitly_idempotent_tools():
    provider = ResilienceProvider()

    assert (
        await AST.eval(
            function("flaky", 7),
            provider,
            policy=retry_policy("flaky"),
        )
        == 7
    )
    assert provider.calls == {"flaky": 2}

    provider = ResilienceProvider()
    with pytest.raises(ToolExecutionError, match="temporary"):
        await AST.eval(function("flaky", 7), provider, policy=retry_policy("other"))
    assert provider.calls == {"flaky": 1}


@pytest.mark.asyncio
async def test_each_retry_attempt_consumes_the_tool_call_budget():
    provider = ResilienceProvider()

    with pytest.raises(ExecutionLimitError) as captured:
        await AST.eval(
            function("flaky", 7),
            provider,
            limits=ExecutionLimits(max_tool_calls=1),
            policy=retry_policy("flaky"),
        )

    assert captured.value.resource == "tool_calls"
    assert provider.calls == {"flaky": 1}


@pytest.mark.asyncio
async def test_v2_uses_the_same_retry_contract():
    provider = ResilienceProvider()
    program = TreeProgramV2(
        body=[
            TreeToolCall(
                tool="flaky",
                arguments={"value": TreeLiteral(value=9)},
            )
        ]
    )

    assert await execute_v2(program, provider, policy=retry_policy("flaky")) == 9
    assert provider.calls == {"flaky": 2}


@pytest.mark.asyncio
async def test_cancellation_interrupts_retry_backoff():
    provider = ResilienceProvider()
    task = asyncio.create_task(
        AST.eval(
            function("flaky", 7),
            provider,
            policy=retry_policy("flaky", delay=10),
        )
    )
    while provider.calls.get("flaky", 0) == 0:
        await asyncio.sleep(0)

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert provider.calls == {"flaky": 1}


@pytest.mark.asyncio
async def test_parallel_fail_fast_cancels_unfinished_siblings():
    provider = ResilienceProvider()
    program = TreeProgram(
        body=[function("fail"), function("wait", "late")],
        mode="parallel",
    )

    with pytest.raises(ToolExecutionError, match="failed"):
        await AST.eval(program, provider)

    assert provider.wait_cancelled.is_set()


@pytest.mark.asyncio
async def test_parallel_collection_returns_ordered_branch_outcomes():
    provider = ResilienceProvider()
    provider.wait_started.set()
    program = TreeProgram(
        body=[function("flaky", 3), function("fail")],
        mode="parallel",
    )
    policy = ExecutionPolicy(parallel_failures="collect")

    result = await AST.eval(program, provider, policy=policy)

    assert result == [
        BranchOutcome(
            success=False,
            error_type="ToolExecutionError",
            error_message="temporary",
        ),
        BranchOutcome(
            success=False,
            error_type="ToolExecutionError",
            error_message="failed",
        ),
    ]


@pytest.mark.asyncio
async def test_parallel_collection_keeps_a_list_for_one_branch():
    provider = ResilienceProvider()
    program = TreeProgram(
        body=[function("flaky", 3)],
        mode="parallel",
    )

    result = await AST.eval(
        program,
        provider,
        policy=ExecutionPolicy(parallel_failures="collect"),
    )

    assert result == [
        BranchOutcome(
            success=False,
            error_type="ToolExecutionError",
            error_message="temporary",
        )
    ]


@pytest.mark.asyncio
async def test_partial_collection_is_rejected_for_single_programs():
    provider = ResilienceProvider()
    program = TreeProgram(body=[function("flaky", 3)], mode="single")

    with pytest.raises(ValueError, match="parallel program"):
        await AST.eval(
            program,
            provider,
            policy=ExecutionPolicy(parallel_failures="collect"),
        )

    assert provider.calls == {}
