"""Command-line tools for Treelang programs."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, NoReturn

from pydantic import ValidationError

from treelang import __version__, json_schema_text
from treelang.ai.anthropic import AnthropicTransport
from treelang.ai.arborist import OpenAIArborist
from treelang.ai.config import ArboristConfig
from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.ai.responses import EvalType
from treelang.ai.tool import ToolDefinition, normalize_tool_definition
from treelang.ai.transport import ModelTransport, OpenAITransport
from treelang.exceptions import (
    ASTExecutionError,
    ExecutionLimitError,
    ModelAuthenticationError,
    ModelTransportError,
    ProviderResponseError,
    ReplayMismatchError,
    ToolExecutionError,
    TreelangError,
)
from treelang.replay import ToolReplayEntry, ToolReplayProvider
from treelang.trees.budget import ExecutionLimits
from treelang.trees.execution_v2 import execute_v2
from treelang.trees.schemas.v1 import AST as ASTV1
from treelang.trees.schemas.v1 import TreeProgram as TreeProgramV1
from treelang.trees.schemas.v2 import AST as ASTV2
from treelang.trees.schemas.v2 import TreeProgram as TreeProgramV2
from treelang.trees.tree import AST

type Program = TreeProgramV1 | TreeProgramV2
type SchemaVersion = Literal["1.0", "2.0"]

EXIT_INPUT = 2
EXIT_EXECUTION = 3
EXIT_PROVIDER = 4
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"


class StaticToolProvider(ToolProvider):
    """Expose definitions for generation while refusing execution."""

    def __init__(self, tools: Sequence[ToolDefinition] = ()) -> None:
        super().__init__()
        normalized = [normalize_tool_definition(tool) for tool in tools]
        self.tools = {tool["name"]: tool for tool in normalized}

    async def list_tools(self) -> list[ToolDefinition]:
        return list(self.tools.values()) if self.tools else []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolOutput:
        raise ToolExecutionError(
            f"CLI has no implementation for tool '{name}'; use a replay fixture"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="treelang", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    schema = commands.add_parser("schema", help="print a canonical JSON Schema")
    schema.add_argument("--schema-version", choices=("1.0", "2.0"), default="1.0")
    schema.add_argument("--output", type=Path)

    validate = commands.add_parser("validate", help="validate and normalize a program")
    _add_io_arguments(validate)

    inspect = commands.add_parser("inspect", help="inspect a validated program")
    _add_io_arguments(inspect)
    inspect.add_argument(
        "--format", choices=("tree", "json"), default="tree", dest="output_format"
    )

    execute = commands.add_parser("execute", help="execute a validated program")
    _add_io_arguments(execute)
    execute.add_argument("--replay", type=Path, help="tool replay fixture")
    _add_limit_arguments(execute)

    replay = commands.add_parser(
        "replay", help="execute and fully consume a deterministic tool replay"
    )
    _add_io_arguments(replay)
    replay.add_argument("--fixture", type=Path, required=True)
    _add_limit_arguments(replay)

    generate = commands.add_parser(
        "generate", help="generate a validated program with a model provider"
    )
    generate.add_argument("prompt", nargs="?", default="-")
    generate.add_argument("--output", type=Path)
    generate.add_argument(
        "--provider", choices=("openai", "anthropic"), default="openai"
    )
    generate.add_argument("--model")
    generate.add_argument("--schema-version", choices=("1.0", "2.0"), default="1.0")
    generate.add_argument("--tools", type=Path, help="JSON array of tool definitions")
    generate.add_argument("--timeout", type=float)
    return parser


def _add_io_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", nargs="?", default="-")
    parser.add_argument("--output", type=Path)


def _add_limit_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-nodes", type=int)
    parser.add_argument("--max-depth", type=int)
    parser.add_argument("--max-call-depth", type=int)
    parser.add_argument("--max-tool-calls", type=int)
    parser.add_argument("--max-concurrency", type=int)
    parser.add_argument("--timeout", type=float, dest="timeout_seconds")


def _read_text(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8")


def _read_json(source: str | Path) -> Any:
    if isinstance(source, Path):
        text = source.read_text(encoding="utf-8")
    else:
        text = _read_text(source)
    return json.loads(text)


def _parse_program(value: Any) -> tuple[SchemaVersion, Program]:
    if not isinstance(value, dict):
        raise ValueError("Program input must be a JSON object")
    if value.get("schema_version", "1.0") == "2.0":
        return "2.0", ASTV2.model_validate(value).root
    return "1.0", ASTV1.model_validate(value).root


def _write_text(value: str, output: Path | None) -> None:
    content = value if value.endswith("\n") else f"{value}\n"
    if output is None:
        sys.stdout.write(content)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=_json_default)


def _json_default(value: Any) -> Any:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _render_tree(program: Program) -> str:
    value = program.model_dump(mode="json", exclude_none=True)
    lines: list[str] = []

    def render(item: Any, indent: int, edge: str | None = None) -> None:
        prefix = "  " * indent
        edge_text = f"{edge}: " if edge else ""
        if isinstance(item, dict) and isinstance(item.get("type"), str):
            label = item["type"]
            identity = item.get("name") or item.get("function") or item.get("tool")
            if identity:
                label = f"{label} {identity}"
            if item["type"] in {"value", "literal", "variable"}:
                scalar = item.get("value", item.get("name"))
                label = f"{label} = {scalar!r}"
            lines.append(f"{prefix}{edge_text}{label}")
            for key, child in item.items():
                if key in {"type", "schema_version", "name", "function", "tool"}:
                    continue
                if isinstance(child, dict):
                    render(child, indent + 1, key)
                elif isinstance(child, list):
                    lines.append(f"{'  ' * (indent + 1)}{key}:")
                    for index, entry in enumerate(child):
                        render(entry, indent + 2, str(index))
                elif key != "value" and child is not None:
                    lines.append(f"{'  ' * (indent + 1)}{key}: {child!r}")
            return
        lines.append(f"{prefix}{edge_text}{item!r}")

    render(value, 0)
    return "\n".join(lines)


def _load_tools(path: Path | None) -> list[ToolDefinition]:
    if path is None:
        return []
    value = _read_json(path)
    if not isinstance(value, list):
        raise ValueError("Tool definitions must be a JSON array")
    return [_normalize_tool_input(tool) for tool in value]


def _normalize_tool_input(value: Any) -> ToolDefinition:
    try:
        return normalize_tool_definition(value)
    except ProviderResponseError as error:
        raise ValueError(str(error)) from error


def _load_replay(path: Path) -> ToolReplayProvider:
    value = _read_json(path)
    if not isinstance(value, dict):
        raise ValueError("Replay fixture must be a JSON object")
    tools = value.get("tools")
    calls = value.get("calls")
    if not isinstance(tools, list) or not isinstance(calls, list):
        raise ValueError("Replay fixture requires 'tools' and 'calls' arrays")
    definitions = [_normalize_tool_input(tool) for tool in tools]
    entries: list[ToolReplayEntry] = []
    for call in calls:
        if (
            not isinstance(call, dict)
            or not isinstance(call.get("name"), str)
            or not isinstance(call.get("arguments"), dict)
            or "output" not in call
        ):
            raise ValueError("Replay calls require name, arguments, and output")
        entries.append(
            ToolReplayEntry(
                name=call["name"],
                arguments=call["arguments"],
                output=call["output"],
            )
        )
    return ToolReplayProvider(definitions, entries)


def _execution_limits(arguments: argparse.Namespace) -> ExecutionLimits:
    return ExecutionLimits(
        max_nodes=arguments.max_nodes,
        max_depth=arguments.max_depth,
        max_call_depth=arguments.max_call_depth,
        max_tool_calls=arguments.max_tool_calls,
        max_concurrency=arguments.max_concurrency,
        timeout_seconds=arguments.timeout_seconds,
    )


async def _execute(
    version: SchemaVersion,
    program: Program,
    provider: ToolProvider,
    limits: ExecutionLimits,
) -> Any:
    if version == "2.0":
        assert isinstance(program, TreeProgramV2)
        return await execute_v2(program, provider, limits=limits)
    assert isinstance(program, TreeProgramV1)
    return await AST.eval(program, provider, limits=limits)


def _model_runtime(
    provider: str,
    model: str | None,
    schema_version: SchemaVersion,
    timeout: float | None,
) -> tuple[ArboristConfig, ModelTransport]:
    if provider == "openai":
        environment = ArboristConfig.from_env(model)
        selected_timeout = timeout if timeout is not None else environment.timeout
        config = ArboristConfig(
            model=environment.model,
            api_key=environment.api_key,
            timeout=selected_timeout,
            schema_version=schema_version,
        )
        if not config.api_key:
            raise ModelAuthenticationError(
                "OPENAI_API_KEY is not configured", provider="openai"
            )
        return config, OpenAITransport(
            api_key=config.api_key,
            timeout=config.timeout,
        )
    selected_model = model or os.getenv("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL
    timeout_value = os.getenv("ANTHROPIC_TIMEOUT")
    selected_timeout = (
        timeout
        if timeout is not None
        else float(timeout_value)
        if timeout_value
        else None
    )
    config = ArboristConfig(
        model=selected_model,
        timeout=selected_timeout,
        schema_version=schema_version,
    )
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ModelAuthenticationError(
            "ANTHROPIC_API_KEY is not configured", provider="anthropic"
        )
    return config, AnthropicTransport(
        api_key=api_key,
        timeout=selected_timeout,
    )


async def _run(arguments: argparse.Namespace) -> int:
    if arguments.command == "schema":
        _write_text(json_schema_text(arguments.schema_version), arguments.output)
        return 0
    if arguments.command in {"validate", "inspect", "execute", "replay"}:
        version, program = _parse_program(_read_json(arguments.input))

    if arguments.command == "validate":
        _write_text(
            program.model_dump_json(indent=2, exclude_none=True), arguments.output
        )
        return 0
    if arguments.command == "inspect":
        content = (
            program.model_dump_json(indent=2, exclude_none=True)
            if arguments.output_format == "json"
            else _render_tree(program)
        )
        _write_text(content, arguments.output)
        return 0
    if arguments.command in {"execute", "replay"}:
        fixture = (
            arguments.fixture if arguments.command == "replay" else arguments.replay
        )
        replay_provider = _load_replay(fixture) if fixture else None
        provider: ToolProvider = replay_provider or StaticToolProvider()
        result = await _execute(
            version, program, provider, _execution_limits(arguments)
        )
        if arguments.command == "replay":
            assert replay_provider is not None
            replay_provider.assert_consumed()
        _write_text(_json_text({"result": result}), arguments.output)
        return 0
    if arguments.command == "generate":
        prompt = sys.stdin.read() if arguments.prompt == "-" else arguments.prompt
        if not prompt.strip():
            raise ValueError("Generation prompt cannot be empty")
        tools = _load_tools(arguments.tools)
        schema_version: SchemaVersion = arguments.schema_version
        config, transport = _model_runtime(
            arguments.provider,
            arguments.model,
            schema_version,
            arguments.timeout,
        )
        response = await OpenAIArborist(
            model=config.model,
            provider=StaticToolProvider(tools),
            config=config,
            transport=transport,
        ).eval(prompt, EvalType.TREE)
        _write_text(
            response.content.model_dump_json(indent=2, exclude_none=True),
            arguments.output,
        )
        return 0
    raise AssertionError(f"Unhandled command {arguments.command}")


def _fail(category: str, message: str, status: int) -> NoReturn:
    sys.stderr.write(_json_text({"error": {"category": category, "message": message}}))
    sys.stderr.write("\n")
    raise SystemExit(status)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Treelang CLI and return its stable process status."""
    arguments = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(arguments))
    except ReplayMismatchError as error:
        _fail("execution", str(error), EXIT_EXECUTION)
    except (ModelTransportError, ProviderResponseError, ImportError) as error:
        _fail("provider", str(error), EXIT_PROVIDER)
    except (
        ASTExecutionError,
        ExecutionLimitError,
        ToolExecutionError,
        TreelangError,
    ) as error:
        _fail("execution", str(error), EXIT_EXECUTION)
    except (json.JSONDecodeError, ValidationError, OSError, ValueError) as error:
        _fail("input", str(error), EXIT_INPUT)


if __name__ == "__main__":
    raise SystemExit(main())
