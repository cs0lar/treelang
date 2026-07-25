import pytest

from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.exceptions import ASTValidationError
from treelang.trees.budget import ExecutionLimits
from treelang.trees.execution import ExecutionContext
from treelang.trees.execution_v2 import execute_v2
from treelang.trees.schemas.v1 import (
    TreeFunction,
    TreeLambda,
    TreeMap,
    TreeValue,
)
from treelang.trees.schemas.v2 import (
    TreeCall,
    TreeFunctionDefinition,
    TreeLiteral,
    TreeProgram,
    TreeToolCall,
    TreeVariable,
)


class ValidatingProvider(ToolProvider):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def list_tools(self):
        return []

    async def get_tool_definition(self, name):
        return {
            "name": name,
            "properties": {"value": {"type": "integer", "minimum": 0}},
            "input_schema": {
                "type": "object",
                "properties": {
                    "value": {"type": "integer", "minimum": 0},
                },
                "required": ["value"],
                "additionalProperties": False,
            },
        }

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return ToolOutput(content=arguments["value"])


@pytest.mark.asyncio
async def test_v1_rejects_before_provider_call_or_tool_budget_consumption():
    provider = ValidatingProvider()
    context = ExecutionContext.with_limits(ExecutionLimits(max_tool_calls=1))
    invalid = TreeFunction(
        name="identity",
        params=[TreeValue(name="value", value="private-invalid-value")],
    )

    with pytest.raises(ASTValidationError) as captured:
        await invalid.eval(provider, context)

    assert "private-invalid-value" not in str(captured.value)
    assert context.budget.tool_calls == 0
    assert provider.calls == []

    valid = TreeFunction(
        name="identity",
        params=[TreeValue(name="value", value=1)],
    )
    assert await valid.eval(provider, context) == 1
    assert context.budget.tool_calls == 1


@pytest.mark.asyncio
async def test_v1_validates_values_produced_by_lambda_bindings():
    provider = ValidatingProvider()
    tree = TreeMap(
        function=TreeLambda(
            params=["value"],
            body=TreeFunction(
                name="identity",
                params=[TreeValue(name="value", value=None)],
            ),
        ),
        iterable=TreeValue(name="values", value=[1, "invalid"]),
    )

    with pytest.raises(ASTValidationError, match="'value'.*'type'"):
        await tree.eval(provider)

    assert provider.calls == [("identity", {"value": 1})]


@pytest.mark.asyncio
async def test_v2_validates_tool_values_inside_recursive_user_calls():
    provider = ValidatingProvider()
    program = TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name="forward",
                params=["item"],
                body=TreeToolCall(
                    tool="identity",
                    arguments={"value": TreeVariable(name="item")},
                ),
            )
        ],
        body=[
            TreeCall(
                function="forward",
                arguments=[TreeLiteral(value="invalid")],
            )
        ],
    )

    with pytest.raises(ASTValidationError, match="'value'.*'type'"):
        await execute_v2(program, provider)

    assert provider.calls == []


@pytest.mark.asyncio
async def test_v1_allows_omitted_optional_trailing_input():
    class OptionalProvider(ValidatingProvider):
        async def get_tool_definition(self, name):
            return {
                "name": name,
                "properties": {
                    "value": {"type": "integer"},
                    "note": {"type": "string", "default": "unused"},
                },
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "integer"},
                        "note": {"type": "string", "default": "unused"},
                    },
                    "required": ["value"],
                    "additionalProperties": False,
                },
            }

    provider = OptionalProvider()
    tree = TreeFunction(
        name="identity",
        params=[TreeValue(name="value", value=7)],
    )

    assert await tree.eval(provider) == 7
    assert provider.calls == [("identity", {"value": 7})]
