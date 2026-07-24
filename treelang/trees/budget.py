"""Per-invocation execution limits and accounting."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from treelang.exceptions import ExecutionLimitError

AsyncOperation = Callable[[], Awaitable[Any]]
_active_budget: ContextVar[ExecutionBudget | None] = ContextVar(
    "treelang_active_execution_budget", default=None
)


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    """Optional resource limits for one AST invocation.

    ``None`` leaves a resource unlimited. Positive values enforce an inclusive
    maximum, preserving historical behavior when no limits are supplied.
    """

    max_nodes: int | None = None
    max_depth: int | None = None
    max_call_depth: int | None = None
    max_tool_calls: int | None = None
    max_concurrency: int | None = None
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        for name in (
            "max_nodes",
            "max_depth",
            "max_call_depth",
            "max_tool_calls",
            "max_concurrency",
        ):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value <= 0
            ):
                raise ValueError(f"{name} must be a positive integer or None")
        if self.timeout_seconds is not None and (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be a positive number or None")


@dataclass(slots=True)
class ExecutionBudget:
    """Mutable counters shared by immutable contexts in one invocation."""

    limits: ExecutionLimits = field(default_factory=ExecutionLimits)
    evaluated_nodes: int = 0
    tool_calls: int = 0
    _semaphore: asyncio.Semaphore | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.limits.max_concurrency is not None:
            self._semaphore = asyncio.Semaphore(self.limits.max_concurrency)

    def consume_node(self, depth: int) -> None:
        """Account for one evaluated node at its one-based logical depth."""
        self.evaluated_nodes += 1
        if (
            self.limits.max_nodes is not None
            and self.evaluated_nodes > self.limits.max_nodes
        ):
            raise ExecutionLimitError("nodes", self.limits.max_nodes)
        if self.limits.max_depth is not None and depth > self.limits.max_depth:
            raise ExecutionLimitError("depth", self.limits.max_depth)

    def consume_tool_call(self) -> None:
        """Account for one provider tool invocation."""
        self.tool_calls += 1
        if (
            self.limits.max_tool_calls is not None
            and self.tool_calls > self.limits.max_tool_calls
        ):
            raise ExecutionLimitError("tool_calls", self.limits.max_tool_calls)

    def check_call_depth(self, depth: int) -> None:
        """Reject a user-function call stack deeper than its configured maximum."""
        if (
            self.limits.max_call_depth is not None
            and depth > self.limits.max_call_depth
        ):
            raise ExecutionLimitError("call_depth", self.limits.max_call_depth)

    async def run_all(self, operations: Sequence[AsyncOperation]) -> list[Any]:
        """Run sibling operations while respecting the invocation concurrency cap."""
        semaphore = self._semaphore
        if semaphore is None:
            return list(
                await asyncio.gather(*(operation() for operation in operations))
            )
        if _active_budget.get() is self:
            return [await operation() for operation in operations]

        async def run(operation: AsyncOperation) -> Any:
            async with semaphore:
                token = _active_budget.set(self)
                try:
                    return await operation()
                finally:
                    _active_budget.reset(token)

        return list(await asyncio.gather(*(run(operation) for operation in operations)))
