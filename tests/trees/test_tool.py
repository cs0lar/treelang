import asyncio
import unittest
from unittest.mock import AsyncMock

import mcp.types as types

from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.exceptions import ASTCompilationError
from treelang.trees.schemas.v1 import (
    TreeConditional,
    TreeFunction,
    TreeLambda,
    TreeProgram,
    TreeValue,
)
from treelang.trees.tree import AST


class TestToolMethod(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ast = TreeProgram(
            body=[
                TreeFunction(
                    name="add",
                    params=[
                        TreeValue(name="a", value=None),
                        TreeValue(name="b", value=None),
                    ],
                )
            ],
            mode="single",
            name="add_tool",
            description="Adds two numbers",
        )

    async def test_tool_creation(self):
        provider = AsyncMock(spec=ToolProvider)
        provider.list_tools.return_value = [
            {
                "name": "add",
                "description": "Adds two numbers",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            }
        ]

        provider.get_tool_definition.return_value = {
            "name": "add",
            "description": "Adds two numbers",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
        }

        tool_function = await AST.tool(self.ast, provider)

        self.assertEqual(tool_function.__name__, "add_tool")
        self.assertEqual(tool_function.__doc__, "Adds two numbers")
        self.assertTrue(callable(tool_function))
        self.assertIn("a", tool_function.__signature__.parameters)
        self.assertIn("b", tool_function.__signature__.parameters)

    async def test_duplicate_parameters_are_stable_without_mutating_ast(self):
        ast = TreeProgram(
            body=[
                TreeFunction(
                    name="subtract",
                    params=[
                        TreeValue(name="value", value=None),
                        TreeValue(name="value", value=None),
                    ],
                )
            ],
            mode="single",
            name="subtract_tool",
            description="Subtracts two values",
        )
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {
            "name": "subtract",
            "properties": {"value": {"type": "integer"}},
        }
        provider.call_tool.side_effect = lambda _, arguments: ToolOutput(
            content=arguments["value"]
        )

        first = await AST.tool(ast, provider)
        second = await AST.tool(ast, provider)

        self.assertEqual(list(first.__signature__.parameters), ["value", "value_2"])
        self.assertEqual(list(second.__signature__.parameters), ["value", "value_2"])
        self.assertEqual([node.name for node in ast.body[0].params], ["value", "value"])

    async def test_tool_with_conditional_creation(self):
        provider = AsyncMock(spec=ToolProvider)

        ast = TreeProgram(
            body=[
                TreeConditional(
                    condition=TreeFunction(
                        name="isPositive",
                        params=[TreeValue(name="x", value=None)],
                    ),
                    true_branch=TreeFunction(
                        name="print",
                        params=[TreeValue(name="message", value="Positive")],
                    ),
                    false_branch=TreeFunction(
                        name="print",
                        params=[TreeValue(name="message", value="Negative")],
                    ),
                )
            ],
            mode="single",
            name="is_positive_tool",
            description="Checks if a number is positive",
        )

        provider.list_tools.return_value = [
            {
                "name": "isPositive",
                "description": "Checks if a number is positive",
                "properties": {"x": {"type": "integer"}},
            },
            {
                "name": "print",
                "description": "Prints a message",
                "properties": {"message": {"type": "string"}},
            },
        ]

        def mock_get_tool_definition(name):
            if name == "isPositive":
                return {
                    "name": "isPositive",
                    "description": "Checks if a number is positive",
                    "properties": {"x": {"type": "integer"}},
                }
            elif name == "print":
                return {
                    "name": "print",
                    "description": "Prints a message",
                    "properties": {"message": {"type": "string"}},
                }
            else:
                raise ValueError(f"Tool {name} not found")

        provider.get_tool_definition.side_effect = mock_get_tool_definition

        tool_function = await AST.tool(ast, provider)

        self.assertEqual(tool_function.__name__, "is_positive_tool")
        self.assertEqual(tool_function.__doc__, "Checks if a number is positive")
        self.assertTrue(callable(tool_function))
        self.assertIn("x", tool_function.__signature__.parameters)
        self.assertIn("message", tool_function.__signature__.parameters)

    async def test_tool_execution(self):
        async def mock_call_tool(name, arguments):
            if name == "add":
                return ToolOutput(content=arguments["a"] + arguments["b"])

        provider = AsyncMock(spec=ToolProvider)
        provider.list_tools.return_value = types.ListToolsResult(
            tools=[
                types.Tool(
                    name="add",
                    description="Adds two numbers",
                    inputSchema={
                        "properties": {
                            "a": {"type": "integer"},
                            "b": {"type": "integer"},
                        }
                    },
                )
            ]
        )

        provider.get_tool_definition.return_value = {
            "name": "add",
            "description": "Adds two numbers",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
        }

        provider.call_tool = mock_call_tool

        tool_function = await AST.tool(self.ast, provider)
        result = await tool_function(a=5, b=10)
        self.assertEqual(result, 15)

    async def test_concurrent_tool_calls_have_isolated_bindings(self):
        values = self.ast.body[0].params

        class OverlappingProvider(ToolProvider):
            async def list_tools(self):
                return []

            async def get_tool_definition(self, name):
                await asyncio.sleep(0)
                return {"name": name, "properties": {"a": {}, "b": {}}}

            async def call_tool(self, name, arguments):
                await asyncio.sleep(0)
                return ToolOutput(content=(arguments["a"], arguments["b"]))

        tool_function = await AST.tool(self.ast, OverlappingProvider())
        results = await asyncio.gather(tool_function(a=1, b=2), tool_function(a=3, b=4))

        self.assertEqual(results, [(1, 2), (3, 4)])
        self.assertEqual([node.value for node in values], [None, None])

    async def test_tool_with_conditional_execution(self):
        async def mock_call_tool(name, arguments):
            if name == "isPositive":
                return ToolOutput(content=arguments["x"] > 0)
            elif name == "print":
                return ToolOutput(content=f"Message: {arguments['message']}")
            raise ValueError(f"Unknown tool: {name}")

        provider = AsyncMock(spec=ToolProvider)
        provider.list_tools.return_value = [
            {
                "name": "isPositive",
                "description": "Checks if a number is positive",
                "properties": {"x": {"type": "integer"}},
            },
            {
                "name": "print",
                "description": "Prints a message",
                "properties": {"message": {"type": "string"}},
            },
        ]

        provider.get_tool_definition.side_effect = lambda name: {
            "name": name,
            "description": f"{name} description",
            "properties": (
                {"x": {"type": "integer"}}
                if name == "isPositive"
                else {"message": {"type": "string"}}
            ),
        }

        provider.call_tool = mock_call_tool

        ast = TreeProgram(
            body=[
                TreeConditional(
                    condition=TreeFunction(
                        name="isPositive",
                        params=[TreeValue(name="x", value=None)],
                    ),
                    true_branch=TreeFunction(
                        name="print",
                        params=[TreeValue(name="message", value="True")],
                    ),
                    false_branch=TreeFunction(
                        name="print",
                        params=[TreeValue(name="message", value="False")],
                    ),
                )
            ],
            mode="single",
            name="is_positive_tool",
            description="Checks if a number is positive",
        )

        tool_function = await AST.tool(ast, provider)
        params = tool_function.__signature__.parameters.keys()
        args = zip(params, [-5, "Pos", "Neg"])
        result = await tool_function(**dict(args))
        self.assertEqual(result, "Message: Neg")
        args = zip(params, [5, "Positive", "Negative"])
        result = await tool_function(**dict(args))
        self.assertEqual(result, "Message: Positive")

    async def test_tool_missing_parameters(self):
        provider = AsyncMock(spec=ToolProvider)
        provider.list_tools.return_value = [
            {
                "name": "add",
                "description": "Adds two numbers",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            }
        ]

        provider.get_tool_definition.return_value = {
            "name": "add",
            "description": "Adds two numbers",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
        }

        tool_function = await AST.tool(self.ast, provider)

        with self.assertRaises(TypeError):
            await tool_function(a=5)

    async def test_tool_invalid_ast(self):
        invalid_ast = TreeValue(name="invalid", value=42)
        provider = AsyncMock(spec=ToolProvider)

        with self.assertRaises(ValueError):
            await AST.tool(invalid_ast, provider)

    async def test_tool_requires_program_metadata(self):
        provider = AsyncMock(spec=ToolProvider)
        missing_name = self.ast.model_copy(update={"name": None})
        missing_description = self.ast.model_copy(update={"description": None})

        with self.assertRaisesRegex(ValueError, "must have a name"):
            await AST.tool(missing_name, provider)
        with self.assertRaisesRegex(ValueError, "must have a description"):
            await AST.tool(missing_description, provider)

    async def test_tool_rejects_higher_order_programs(self):
        ast = TreeProgram(
            body=[
                TreeLambda(
                    params=["x"],
                    body=TreeFunction(
                        name="identity", params=[TreeValue(name="x", value=None)]
                    ),
                )
            ],
            mode="single",
            name="higher_order",
            description="Unsupported higher-order program",
        )

        with self.assertRaisesRegex(ValueError, "Higher order functions"):
            await AST.tool(ast, AsyncMock(spec=ToolProvider))

    async def test_tool_wraps_invalid_python_signature(self):
        ast = TreeProgram(
            body=[
                TreeFunction(
                    name="identity",
                    params=[TreeValue(name="not valid", value=None)],
                )
            ],
            mode="single",
            name="invalid_signature",
            description="Contains an invalid Python parameter name",
        )
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {
            "name": "identity",
            "properties": {"not valid": {"type": "string"}},
        }

        with self.assertRaisesRegex(ASTCompilationError, "Invalid function signature"):
            await AST.tool(ast, provider)

    async def test_tool_runtime_error(self):
        async def mock_call_tool(name, arguments):
            if name == "add":
                raise RuntimeError("Tool execution failed")
            return ToolOutput(content=arguments["a"] + arguments["b"])

        provider = AsyncMock(spec=ToolProvider)
        provider.list_tools.return_value = [
            {
                "name": "add",
                "description": "Adds two numbers",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            }
        ]

        provider.get_tool_definition.return_value = {
            "name": "add",
            "description": "Adds two numbers",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
        }

        provider.call_tool = mock_call_tool

        tool_function = await AST.tool(self.ast, provider)

        with self.assertRaises(RuntimeError):
            await tool_function(a=5, b=10)
