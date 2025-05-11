import unittest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from treelang.ai.provider import ToolOutput, ToolProvider
import mcp.types as types
from treelang.trees.tree import (
    AST,
    TreeConditional,
    TreeNode,
    TreeProgram,
    TreeFunction,
    TreeValue,
)


class TestTreeNode(unittest.TestCase):
    def test_tree_node_init(self):
        node = TreeNode("test")
        self.assertEqual(node.type, "test")

    def test_tree_node_eval(self):
        node = TreeNode("test")
        provider = AsyncMock(spec=ToolProvider)
        with self.assertRaises(NotImplementedError):
            asyncio.run(node.eval(provider))


class TestTreeProgram(unittest.TestCase):
    def test_tree_program_init(self):
        body = [TreeNode("test")]
        program = TreeProgram(body, "test_program", "description")
        self.assertEqual(program.type, "program")
        self.assertEqual(program.body, body)
        self.assertEqual(program.name, "test_program")
        self.assertEqual(program.description, "description")

    def test_tree_program_eval(self):
        body = [TreeValue("x", "result")]
        provider = AsyncMock(spec=ToolProvider)
        program = TreeProgram(body, "test_program")
        result = asyncio.run(program.eval(provider))
        self.assertEqual(result, "result")


class TestTreeFunction(unittest.TestCase):
    def test_tree_function_init(self):
        params = [TreeNode("param")]
        function = TreeFunction("test_function", params)
        self.assertEqual(function.type, "function")
        self.assertEqual(function.name, "test_function")
        self.assertEqual(function.params, params)

    def test_tree_function_eval(self):
        params = [TreeValue("param", 42)]
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {
            "name": "test_function",
            "description": "test_description",
            "properties": {"param": {}},
        }
        function = TreeFunction("test_function", params)
        result = asyncio.run(function.eval(provider))
        self.assertIsNotNone(result)
        provider.get_tool_definition.assert_called_once_with("test_function")
        provider.call_tool.assert_called_once_with("test_function", {"param": 42})


class TestTreeValue(unittest.TestCase):
    def test_tree_value_init(self):
        value = TreeValue("test_value", 42)
        self.assertEqual(value.type, "value")
        self.assertEqual(value.name, "test_value")
        self.assertEqual(value.value, 42)

    def test_tree_value_eval(self):
        value = TreeValue("test_value", 42)
        provider = AsyncMock(spec=ToolProvider)
        result = asyncio.run(value.eval(provider))
        self.assertEqual(result, 42)


class TestTreeConditional(unittest.TestCase):
    def test_tree_conditional_init(self):
        condition = TreeValue("condition", True)
        true_branch = TreeValue("true_branch", "True Result")
        false_branch = TreeValue("false_branch", "False Result")
        conditional = TreeConditional(condition, true_branch, false_branch)

        self.assertEqual(conditional.type, "conditional")
        self.assertEqual(conditional.condition, condition)
        self.assertEqual(conditional.true_branch, true_branch)
        self.assertEqual(conditional.false_branch, false_branch)

    def test_tree_conditional_eval_true_branch(self):
        condition = TreeValue("condition", True)
        true_branch = TreeValue("true_branch", "True Result")
        false_branch = TreeValue("false_branch", "False Result")
        conditional = TreeConditional(condition, true_branch, false_branch)

        provider = AsyncMock(spec=ToolProvider)
        result = asyncio.run(conditional.eval(provider))
        self.assertEqual(result, "True Result")

    def test_tree_conditional_eval_false_branch(self):
        condition = TreeValue("condition", False)
        true_branch = TreeValue("true_branch", "True Result")
        false_branch = TreeValue("false_branch", "False Result")
        conditional = TreeConditional(condition, true_branch, false_branch)

        provider = AsyncMock(spec=ToolProvider)
        result = asyncio.run(conditional.eval(provider))
        self.assertEqual(result, "False Result")

    def test_tree_conditional_eval_no_false_branch(self):
        condition = TreeValue("condition", False)
        true_branch = TreeValue("true_branch", "True Result")
        conditional = TreeConditional(condition, true_branch)

        provider = AsyncMock(spec=ToolProvider)
        result = asyncio.run(conditional.eval(provider))
        self.assertIsNone(result)


class TestAST(unittest.TestCase):
    def setUp(self):
        self.ast = [
            {
                "type": "program",
                "body": [
                    {
                        "type": "function",
                        "name": "add",
                        "params": [
                            {"type": "value", "name": "a", "value": 4},
                            {
                                "type": "function",
                                "name": "mul",
                                "params": [
                                    {"type": "value", "name": "a", "value": 6},
                                    {"type": "value", "name": "b", "value": 12},
                                ],
                            },
                        ],
                    }
                ],
            }
        ]

    def test_parse_program(self):
        ast_dict = {"type": "program", "body": []}
        result = AST.parse(ast_dict)
        self.assertIsInstance(result, TreeProgram)

    def test_parse_function(self):
        ast_dict = {"type": "function", "name": "test_function", "params": []}
        result = AST.parse(ast_dict)
        self.assertIsInstance(result, TreeFunction)
        self.assertEqual(result.name, "test_function")

    def test_parse_conditional(self):
        ast_dict = {
            "type": "conditional",
            "condition": {"type": "value", "name": "condition", "value": True},
            "true_branch": {
                "type": "value",
                "name": "true_branch",
                "value": "True Result",
            },
            "false_branch": {
                "type": "value",
                "name": "false_branch",
                "value": "False Result",
            },
        }
        result = AST.parse(ast_dict)
        self.assertIsInstance(result, TreeConditional)
        self.assertIsInstance(result.condition, TreeValue)
        self.assertIsInstance(result.true_branch, TreeValue)
        self.assertIsInstance(result.false_branch, TreeValue)
        self.assertEqual(result.condition.value, True)
        self.assertEqual(result.true_branch.value, "True Result")
        self.assertEqual(result.false_branch.value, "False Result")

    def test_parse_value(self):
        ast_dict = {"type": "value", "name": "test_value", "value": 42}
        result = AST.parse(ast_dict)
        self.assertIsInstance(result, TreeValue)

    def test_parse_unknown(self):
        ast_dict = {"type": "unknown"}
        with self.assertRaises(ValueError):
            AST.parse(ast_dict)

    def test_eval(self):
        def add(a, b):
            return a + b

        def mul(a, b):
            return a * b

        class MockToolProvider(ToolProvider):
            async def call_tool(name, arguments):
                if name == "add":
                    content = add(**arguments)
                elif name == "mul":
                    content = mul(**arguments)
                return ToolOutput(content=content)

            async def list_tools():
                return AsyncMock(
                    tools=[
                        {
                            "name": "add",
                            "description": "test_description",
                            "properties": {"a": {}, "b": {}},
                        },
                        {
                            "name": "mul",
                            "description": "test_description",
                            "properties": {"a": {}, "b": {}},
                        },
                    ]
                )

            async def get_tool_definition(name):
                if name == "add":
                    return {
                        "name": "add",
                        "description": "test_description",
                        "properties": {"a": {}, "b": {}},
                    }
                elif name == "mul":
                    return {
                        "name": "mul",
                        "description": "test_description",
                        "properties": {"a": {}, "b": {}},
                    }
                else:
                    raise ValueError(f"Tool {name} not found")

        with patch(
            "treelang.trees.tree.ToolProvider", new=MockToolProvider
        ) as provider:
            [program] = AST.parse(self.ast)
            result = asyncio.run(AST.eval(program, provider))
            self.assertIsNotNone(result)
            self.assertEqual(int(result), (12 * 6) + 4)

    def test_eval_with_conditional(self):
        class MockToolProvider(ToolProvider):
            async def call_tool(self, name, arguments):
                if name == "isPositive":
                    return ToolOutput(content=arguments["x"] > 0)
                elif name == "print":
                    return ToolOutput(content=f"Message: {arguments['message']}")
                raise ValueError(f"Unknown tool: {name}")

            async def list_tools():
                return AsyncMock(
                    tools=[
                        {
                            "name": "isPositive",
                            "description": "Checks if a number is positive",
                            "properties": {"x": {}},
                        },
                        {
                            "name": "print",
                            "description": "Prints a message",
                            "properties": {"message": {}},
                        },
                    ]
                )

            async def get_tool_definition(self, name):
                if name == "isPositive":
                    return {
                        "name": "isPositive",
                        "description": "Checks if a number is positive",
                        "properties": {"x": {}},
                    }
                elif name == "print":
                    return {
                        "name": "print",
                        "description": "Prints a message",
                        "properties": {"message": {}},
                    }
                else:
                    raise ValueError(f"Tool {name} not found")

        ast_dict = {
            "type": "program",
            "body": [
                {
                    "type": "conditional",
                    "condition": {
                        "type": "function",
                        "name": "isPositive",
                        "params": [{"type": "value", "name": "x", "value": -5}],
                    },
                    "true_branch": {
                        "type": "function",
                        "name": "print",
                        "params": [
                            {"type": "value", "name": "message", "value": "Positive"}
                        ],
                    },
                    "false_branch": {
                        "type": "function",
                        "name": "print",
                        "params": [
                            {"type": "value", "name": "message", "value": "Negative"}
                        ],
                    },
                }
            ],
        }

        provider = MockToolProvider()
        program = AST.parse(ast_dict)
        result = asyncio.run(AST.eval(program, provider))
        self.assertEqual(result, "Message: Negative")

    def test_visit(self):
        node = TreeNode("test")
        op = Mock()
        AST.visit(node, op)
        op.assert_called_once_with(node)

    def test_visit_with_conditional(self):
        condition = TreeValue("condition", True)
        true_branch = TreeValue("true_branch", "True Result")
        false_branch = TreeValue("false_branch", "False Result")
        conditional = TreeConditional(condition, true_branch, false_branch)

        op = Mock()
        AST.visit(conditional, op)

        # Assert that the visitor function was called for the conditional node and its children
        op.assert_any_call(conditional)
        op.assert_any_call(condition)
        op.assert_any_call(true_branch)
        op.assert_any_call(false_branch)
        self.assertEqual(op.call_count, 4)  # Ensure all nodes were visited

    def test_repr(self):
        ast = TreeProgram(
            body=[
                TreeFunction(name="foo", params=[]),
                TreeValue(name="z", value=10),
            ]
        )
        result = AST.repr(ast)
        self.assertEqual(result, '{"foo_1": {}, "z": [10]}')

    def test_repr_with_conditional(self):
        ast = TreeProgram(
            body=[
                TreeConditional(
                    condition=TreeFunction(
                        name="isPositive", params=[TreeValue(name="x", value=-5)]
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
            ]
        )
        result = AST.repr(ast)
        expected = (
            '{"conditional_1": {"isPositive_1": {"x": [-5]}, '
            '"print_1": {"message": ["Positive"]}, '
            '"print_2": {"message": ["Negative"]}}}'
        )
        self.assertEqual(result, expected)


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


if __name__ == "__main__":
    unittest.main()
