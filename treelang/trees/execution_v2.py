"""Explicit-stack execution for validated version 2 programs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Mapping

from treelang.ai.provider import ToolProvider
from treelang.ai.tool import normalize_tool_definition, validate_tool_arguments
from treelang.exceptions import ExecutionLimitError
from treelang.trees.budget import ExecutionBudget, ExecutionLimits
from treelang.trees.policy import ExecutionPolicy, call_tool, run_program
from treelang.trees.schemas.v2 import (
    AST,
    Expression,
    TreeCall,
    TreeConditional,
    TreeFunctionDefinition,
    TreeLiteral,
    TreeProgram,
    TreeToolCall,
    TreeVariable,
)


@dataclass(slots=True)
class _EvalFrame:
    expression: Expression
    bindings: Mapping[str, Any]
    depth: int
    call_depth: int


@dataclass(slots=True)
class _ConditionalFrame:
    true_branch: Expression
    false_branch: Expression
    bindings: Mapping[str, Any]
    depth: int
    call_depth: int


@dataclass(slots=True)
class _CallArgumentsFrame:
    definition: TreeFunctionDefinition
    arguments: list[Expression]
    bindings: Mapping[str, Any]
    next_index: int = 1
    values: list[Any] = field(default_factory=list)
    depth: int = 1
    call_depth: int = 0


@dataclass(slots=True)
class _ToolArgumentsFrame:
    tool: str
    arguments: list[tuple[str, Expression]]
    bindings: Mapping[str, Any]
    next_index: int = 1
    values: list[Any] = field(default_factory=list)
    depth: int = 1
    call_depth: int = 0


type _Frame = _EvalFrame | _ConditionalFrame | _CallArgumentsFrame | _ToolArgumentsFrame


class _Interpreter:
    def __init__(
        self,
        program: TreeProgram,
        provider: ToolProvider,
        budget: ExecutionBudget,
        policy: ExecutionPolicy,
    ) -> None:
        self.definitions = {
            definition.name: definition for definition in program.definitions
        }
        self.provider = provider
        self.budget = budget
        self.policy = policy

    async def evaluate(self, expression: Expression, *, depth: int = 2) -> Any:
        """Evaluate one expression without growing the Python call stack."""
        frames: list[_Frame] = [_EvalFrame(expression, {}, depth, 0)]
        values: list[Any] = []
        processed_frames = 0

        while frames:
            processed_frames += 1
            if processed_frames % 256 == 0:
                # Tool-free recursion must still observe cancellation and the
                # invocation wall-clock deadline.
                await asyncio.sleep(0)
            frame = frames.pop()
            if isinstance(frame, _EvalFrame):
                self.budget.consume_node(frame.depth)
                node = frame.expression
                if isinstance(node, TreeLiteral):
                    values.append(node.value)
                elif isinstance(node, TreeVariable):
                    values.append(frame.bindings[node.name])
                elif isinstance(node, TreeConditional):
                    frames.append(
                        _ConditionalFrame(
                            node.true_branch,
                            node.false_branch,
                            frame.bindings,
                            frame.depth,
                            frame.call_depth,
                        )
                    )
                    frames.append(
                        _EvalFrame(
                            node.condition,
                            frame.bindings,
                            frame.depth + 1,
                            frame.call_depth,
                        )
                    )
                elif isinstance(node, TreeCall):
                    definition = self.definitions[node.function]
                    next_call_depth = frame.call_depth + 1
                    self.budget.check_call_depth(next_call_depth)
                    if not node.arguments:
                        frames.append(
                            self._function_body_frame(definition, [], next_call_depth)
                        )
                    else:
                        frames.append(
                            _CallArgumentsFrame(
                                definition=definition,
                                arguments=node.arguments,
                                bindings=frame.bindings,
                                depth=frame.depth,
                                call_depth=next_call_depth,
                            )
                        )
                        frames.append(
                            _EvalFrame(
                                node.arguments[0],
                                frame.bindings,
                                frame.depth + 1,
                                frame.call_depth,
                            )
                        )
                elif isinstance(node, TreeToolCall):
                    arguments = list(node.arguments.items())
                    if not arguments:
                        values.append(await self._call_tool(node.tool, {}))
                    else:
                        frames.append(
                            _ToolArgumentsFrame(
                                tool=node.tool,
                                arguments=arguments,
                                bindings=frame.bindings,
                                depth=frame.depth,
                                call_depth=frame.call_depth,
                            )
                        )
                        frames.append(
                            _EvalFrame(
                                arguments[0][1],
                                frame.bindings,
                                frame.depth + 1,
                                frame.call_depth,
                            )
                        )
                else:  # pragma: no cover - the discriminated schema is exhaustive
                    raise TypeError(f"Unsupported v2 expression: {type(node).__name__}")
                continue

            if isinstance(frame, _ConditionalFrame):
                condition = values.pop()
                branch = frame.true_branch if condition else frame.false_branch
                frames.append(
                    _EvalFrame(
                        branch,
                        frame.bindings,
                        frame.depth + 1,
                        frame.call_depth,
                    )
                )
                continue

            if isinstance(frame, _CallArgumentsFrame):
                frame.values.append(values.pop())
                if frame.next_index < len(frame.arguments):
                    argument = frame.arguments[frame.next_index]
                    frame.next_index += 1
                    frames.append(frame)
                    frames.append(
                        _EvalFrame(
                            argument,
                            frame.bindings,
                            frame.depth + 1,
                            frame.call_depth - 1,
                        )
                    )
                else:
                    frames.append(
                        self._function_body_frame(
                            frame.definition, frame.values, frame.call_depth
                        )
                    )
                continue

            frame.values.append(values.pop())
            if frame.next_index < len(frame.arguments):
                argument = frame.arguments[frame.next_index][1]
                frame.next_index += 1
                frames.append(frame)
                frames.append(
                    _EvalFrame(
                        argument,
                        frame.bindings,
                        frame.depth + 1,
                        frame.call_depth,
                    )
                )
            else:
                names = [name for name, _ in frame.arguments]
                values.append(
                    await self._call_tool(
                        frame.tool, dict(zip(names, frame.values, strict=True))
                    )
                )

        if len(values) != 1:  # pragma: no cover - interpreter invariant
            raise RuntimeError("Version 2 interpreter produced an invalid value stack")
        return values[0]

    @staticmethod
    def _function_body_frame(
        definition: TreeFunctionDefinition,
        values: list[Any],
        call_depth: int,
    ) -> _EvalFrame:
        bindings = dict(zip(definition.params, values, strict=True))
        # Definition bodies retain their static program-relative depth on every
        # invocation; recursive depth is accounted independently.
        return _EvalFrame(definition.body, bindings, 2, call_depth)

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        raw_tool = await self.provider.get_tool_definition(name)
        tool = normalize_tool_definition(raw_tool, expected_name=name)
        validate_tool_arguments(tool, arguments)
        return (
            await call_tool(self.provider, name, arguments, self.budget, self.policy)
        ).content


async def execute_v2(
    ast: AST | TreeProgram,
    provider: ToolProvider,
    *,
    limits: ExecutionLimits | None = None,
    policy: ExecutionPolicy | None = None,
) -> Any:
    """Validate and execute a version 2 program with one shared budget."""
    program = ast.root if isinstance(ast, AST) else AST(root=ast).root
    budget = ExecutionBudget(limits or ExecutionLimits())
    execution_policy = policy or ExecutionPolicy()
    budget.consume_node(1)
    interpreter = _Interpreter(program, provider, budget, execution_policy)

    async def run() -> Any:
        operations = [
            lambda expression=expression: interpreter.evaluate(expression)
            for expression in program.body
        ]
        results = await run_program(operations, program.mode, budget, execution_policy)
        if execution_policy.parallel_failures == "collect":
            return results
        return results[0] if len(results) == 1 else results

    timeout = budget.limits.timeout_seconds
    if timeout is None:
        return await run()
    deadline = asyncio.timeout(timeout)
    try:
        async with deadline:
            return await run()
    except TimeoutError:
        if deadline.expired():
            raise ExecutionLimitError("wall_clock_seconds", timeout) from None
        raise


__all__ = ["execute_v2"]
