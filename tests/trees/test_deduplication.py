import asyncio

import pytest

from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.ai.tool import normalize_tool_definition
from treelang.exceptions import ProviderResponseError
from treelang.trees.deduplication import deduplicate_pure_tool_calls
from treelang.trees.execution_v2 import execute_v2
from treelang.trees.schemas.v2 import (
    AST,
    TreeLiteral,
    TreeMemo,
    TreeProgram,
    TreeToolCall,
    TreeVariable,
)


class CountingProvider(ToolProvider):
    def __init__(self, effects):
        super().__init__()
        self.calls = 0
        self.effects = effects

    async def list_tools(self):
        tool = {
            "name": "constant",
            "properties": {"value": {}},
            "effects": self.effects,
        }
        self.tools = {"constant": tool}
        return [tool]

    async def call_tool(self, name, arguments):
        self.calls += 1
        await asyncio.sleep(0)
        return ToolOutput(content=arguments["value"])


def call(value=42):
    return TreeToolCall(tool="constant", arguments={"value": TreeLiteral(value=value)})


@pytest.mark.asyncio
async def test_declared_pure_deterministic_duplicates_execute_once_in_parallel():
    provider = CountingProvider({"pure": True, "deterministic": True})
    tools = await provider.list_tools()
    program = TreeProgram(body=[call(), call()], mode="parallel")

    result = deduplicate_pure_tool_calls(program, tools)
    output = await execute_v2(result.tree, provider)

    assert output == [42, 42]
    assert provider.calls == 1
    assert result.changed
    assert all(isinstance(item, TreeMemo) for item in result.tree.body)


@pytest.mark.parametrize(
    "effects",
    [
        None,
        {},
        {"pure": True},
        {"deterministic": True},
        {"pure": False, "deterministic": True},
    ],
)
def test_undeclared_or_incomplete_effects_are_never_deduplicated(effects):
    tool = {"name": "constant", "properties": {"value": {}}}
    if effects is not None:
        tool["effects"] = effects
    program = TreeProgram(body=[call(), call()])

    result = deduplicate_pure_tool_calls(program, [tool])

    assert not result.changed
    assert result.tree.body == program.body


def test_effect_metadata_is_copied_and_validated():
    effects = {"pure": True, "deterministic": True, "idempotent": True}
    normalized = normalize_tool_definition(
        {"name": "constant", "properties": {}, "effects": effects}
    )
    effects["pure"] = False

    assert normalized["effects"]["pure"] is True
    with pytest.raises(ProviderResponseError, match="effects"):
        normalize_tool_definition(
            {"name": "constant", "properties": {}, "effects": {"pure": "yes"}}
        )


def test_memo_requires_closed_consistent_expressions():
    definition = {
        "type": "function_definition",
        "name": "bad",
        "params": ["x"],
        "body": TreeMemo(key="value", expression=TreeVariable(name="x")),
    }
    with pytest.raises(ValueError, match="closed"):
        AST(root=TreeProgram(definitions=[definition], body=[TreeLiteral(value=1)]))

    with pytest.raises(ValueError, match="different expressions"):
        AST(
            root=TreeProgram(
                body=[
                    TreeMemo(key="same", expression=TreeLiteral(value=1)),
                    TreeMemo(key="same", expression=TreeLiteral(value=2)),
                ]
            )
        )
