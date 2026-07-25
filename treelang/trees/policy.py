"""Execution resilience policy shared by schema versions."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Literal

from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.exceptions import ToolExecutionError
from treelang.trees.budget import ExecutionBudget

type AsyncOperation = Callable[[], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry transient failures only for tools declared safe to repeat."""

    max_attempts: int = 1
    delay_seconds: float = 0
    idempotent_tools: frozenset[str] = field(default_factory=frozenset)
    retryable_exceptions: tuple[type[Exception], ...] = (
        ToolExecutionError,
        TimeoutError,
    )

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or self.max_attempts < 1
        ):
            raise ValueError("max_attempts must be a positive integer")
        if (
            isinstance(self.delay_seconds, bool)
            or not isinstance(self.delay_seconds, (int, float))
            or self.delay_seconds < 0
        ):
            raise ValueError("delay_seconds must be a non-negative number")
        if not all(
            isinstance(error, type) and issubclass(error, Exception)
            for error in self.retryable_exceptions
        ):
            raise ValueError("retryable_exceptions must contain Exception types")


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    """Opt-in retry and parallel partial-failure behavior."""

    retry: RetryPolicy = field(default_factory=RetryPolicy)
    parallel_failures: Literal["raise", "collect"] = "raise"

    def __post_init__(self) -> None:
        if self.parallel_failures not in ("raise", "collect"):
            raise ValueError("parallel_failures must be 'raise' or 'collect'")


@dataclass(frozen=True, slots=True)
class BranchOutcome:
    """Serializable outcome for one parallel branch in collection mode."""

    success: bool
    value: Any = None
    error_type: str | None = None
    error_message: str | None = None

    @classmethod
    def succeeded(cls, value: Any) -> BranchOutcome:
        return cls(success=True, value=value)

    @classmethod
    def failed(cls, error: Exception) -> BranchOutcome:
        return cls(
            success=False,
            error_type=type(error).__name__,
            error_message=str(error),
        )


async def call_tool(
    provider: ToolProvider,
    name: str,
    arguments: dict[str, Any],
    budget: ExecutionBudget,
    policy: ExecutionPolicy,
) -> ToolOutput:
    """Call a tool under the configured retry and accounting contract."""
    retry = policy.retry
    attempts = retry.max_attempts if name in retry.idempotent_tools else 1
    for attempt in range(1, attempts + 1):
        budget.consume_tool_call()
        try:
            return await provider.call_tool(name, arguments)
        except retry.retryable_exceptions:
            if attempt == attempts:
                raise
            if retry.delay_seconds:
                await asyncio.sleep(retry.delay_seconds)
    raise AssertionError("retry loop exhausted without returning or raising")


async def run_program(
    operations: Sequence[AsyncOperation],
    mode: Literal["single", "parallel"],
    budget: ExecutionBudget,
    policy: ExecutionPolicy,
) -> list[Any] | list[BranchOutcome]:
    """Run root operations with explicit partial-failure behavior."""
    if policy.parallel_failures == "raise":
        return await budget.run_all(operations)
    if mode != "parallel":
        raise ValueError("Partial-failure collection requires a parallel program")

    async def capture(operation: AsyncOperation) -> BranchOutcome:
        try:
            return BranchOutcome.succeeded(await operation())
        except Exception as error:
            return BranchOutcome.failed(error)

    return await budget.run_all(
        [partial(capture, operation) for operation in operations]
    )


__all__ = ["BranchOutcome", "ExecutionPolicy", "RetryPolicy"]
