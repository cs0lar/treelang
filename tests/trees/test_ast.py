import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.trees.schemas.v1 import (
    TreeConditional,
    TreeFilter,
    TreeFunction,
    TreeLambda,
    TreeMap,
    TreeNode,
    TreeProgram,
    TreeReduce,
    TreeValue,
)
from treelang.trees.tree import AST


class TestAST(unittest.TestCase):
    def setUp(self):
        self.ast = [
            {
                "type": "program",
                "mode": "single",
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
        ast_dict = {"type": "program", "body": [], "mode": "single"}
        result = AST.parse(ast_dict)
        self.assertIsInstance(result, TreeProgram)

    def test_parse_function(self):
        ast_dict = {
            "type": "program",
            "mode": "single",
            "body": [
                {
                    "type": "function",
                    "name": "test_function",
                    "params": [],
                }
            ],
        }
        result = AST.parse(ast_dict)
        self.assertIsInstance(result.body[0], TreeFunction)
        self.assertEqual(result.body[0].name, "test_function")

    def test_parse_conditional(self):
        ast_dict = {
            "type": "program",
            "mode": "single",
            "body": [
                {
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
            ],
        }
        result = AST.parse(ast_dict)
        self.assertIsInstance(result, TreeProgram)
        conditional_node = result.body[0]
        self.assertIsInstance(conditional_node, TreeConditional)
        self.assertIsInstance(conditional_node.condition, TreeValue)
        self.assertIsInstance(conditional_node.true_branch, TreeValue)
        self.assertIsInstance(conditional_node.false_branch, TreeValue)
        self.assertEqual(conditional_node.condition.value, True)
        self.assertEqual(conditional_node.true_branch.value, "True Result")
        self.assertEqual(conditional_node.false_branch.value, "False Result")

    def test_parse_lambda(self):
        ast_dict = {
            "type": "program",
            "mode": "single",
            "body": [
                {
                    "type": "lambda",
                    "params": ["x", "y"],
                    "body": {
                        "type": "function",
                        "name": "add",
                        "params": [
                            {"type": "value", "name": "x", "value": None},
                            {"type": "value", "name": "y", "value": None},
                        ],
                    },
                }
            ],
        }
        result = AST.parse(ast_dict)
        lambda_node = result.body[0]
        self.assertIsInstance(lambda_node, TreeLambda)
        self.assertEqual(lambda_node.params, ["x", "y"])
        self.assertIsInstance(lambda_node.body, TreeFunction)
        self.assertEqual(lambda_node.body.name, "add")

    def test_parse_map(self):
        ast_dict = {
            "type": "program",
            "mode": "single",
            "body": [
                {
                    "type": "map",
                    "function": {
                        "type": "lambda",
                        "params": ["x"],
                        "body": {
                            "type": "function",
                            "name": "square",
                            "params": [{"type": "value", "name": "x", "value": 0}],
                        },
                    },
                    "iterable": {
                        "type": "value",
                        "name": "numbers",
                        "value": [1, 2, 3],
                    },
                }
            ],
        }
        result = AST.parse(ast_dict)
        map_node = result.body[0]
        self.assertIsInstance(map_node, TreeMap)
        self.assertIsInstance(map_node.function, TreeLambda)
        self.assertIsInstance(map_node.iterable, TreeValue)

    def test_parse_filter(self):
        ast_dict = {
            "type": "program",
            "mode": "single",
            "body": [
                {
                    "type": "filter",
                    "function": {
                        "type": "lambda",
                        "params": ["x"],
                        "body": {
                            "type": "function",
                            "name": "is_even",
                            "params": [{"type": "value", "name": "x", "value": 0}],
                        },
                    },
                    "iterable": {
                        "type": "value",
                        "name": "numbers",
                        "value": [1, 2, 3, 4],
                    },
                }
            ],
        }
        result = AST.parse(ast_dict)
        filter_node = result.body[0]
        self.assertIsInstance(filter_node, TreeFilter)
        self.assertIsInstance(filter_node.function, TreeLambda)
        self.assertIsInstance(filter_node.iterable, TreeValue)

    def test_parse_reduce(self):
        ast_dict = {
            "type": "program",
            "mode": "single",
            "body": [
                {
                    "type": "reduce",
                    "function": {
                        "type": "lambda",
                        "params": ["acc", "item"],
                        "body": {
                            "type": "function",
                            "name": "add",
                            "params": [
                                {"type": "value", "name": "acc", "value": 0},
                                {"type": "value", "name": "item", "value": 0},
                            ],
                        },
                    },
                    "iterable": {
                        "type": "value",
                        "name": "numbers",
                        "value": [1, 2, 3],
                    },
                }
            ],
        }
        result = AST.parse(ast_dict)
        reduce_node = result.body[0]
        self.assertIsInstance(reduce_node, TreeReduce)
        self.assertIsInstance(reduce_node.function, TreeLambda)
        self.assertIsInstance(reduce_node.iterable, TreeValue)

    def test_parse_value(self):
        ast_dict = {
            "type": "program",
            "mode": "single",
            "body": [{"type": "value", "name": "test_value", "value": 42}],
        }
        result = AST.parse(ast_dict)
        value_node = result.body[0]
        self.assertIsInstance(value_node, TreeValue)

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
            "mode": "single",
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

    def test_eval_with_lambda(self):
        class MockToolProvider(ToolProvider):
            async def call_tool(self, name, arguments):
                if name == "add":
                    return ToolOutput(content=arguments["a"] + arguments["b"])
                raise ValueError(f"Unknown tool: {name}")

            async def list_tools(self):
                return AsyncMock(
                    tools=[
                        {
                            "name": "add",
                            "description": "Adds two numbers",
                            "properties": {"a": {}, "b": {}},
                        }
                    ]
                )

            async def get_tool_definition(self, name):
                if name == "add":
                    return {
                        "name": "add",
                        "description": "Adds two numbers",
                        "properties": {"a": {}, "b": {}},
                    }
                else:
                    raise ValueError(f"Tool {name} not found")

        ast_dict = {
            "type": "program",
            "mode": "single",
            "body": [
                {
                    "type": "lambda",
                    "params": ["x", "y"],
                    "body": {
                        "type": "function",
                        "name": "add",
                        "params": [
                            {"type": "value", "name": "x", "value": None},
                            {"type": "value", "name": "y", "value": None},
                        ],
                    },
                }
            ],
        }
        provider = MockToolProvider()
        program = AST.parse(ast_dict)
        result = asyncio.run(AST.eval(program, provider))
        self.assertTrue(callable(result))

    def test_eval_with_map(self):
        class MockToolProvider(ToolProvider):
            async def call_tool(self, name, arguments):
                if name == "double":
                    return ToolOutput(content=arguments["x"] * 2)
                raise ValueError(f"Unknown tool: {name}")

            async def list_tools(self):
                return AsyncMock(
                    tools=[
                        {
                            "name": "double",
                            "description": "Doubles a number",
                            "properties": {"x": {}},
                        }
                    ]
                )

            async def get_tool_definition(self, name):
                if name == "double":
                    return {
                        "name": "double",
                        "description": "Doubles a number",
                        "properties": {"x": {}},
                    }
                else:
                    raise ValueError(f"Tool {name} not found")

        ast_dict = {
            "type": "program",
            "mode": "single",
            "body": [
                {
                    "type": "map",
                    "function": {
                        "type": "lambda",
                        "params": ["x"],
                        "body": {
                            "type": "function",
                            "name": "double",
                            "params": [{"type": "value", "name": "x", "value": None}],
                        },
                    },
                    "iterable": {
                        "type": "value",
                        "name": "numbers",
                        "value": [1, 2, 3],
                    },
                }
            ],
        }
        provider = MockToolProvider()
        program = AST.parse(ast_dict)
        result = asyncio.run(AST.eval(program, provider))
        self.assertEqual(result, [2, 4, 6])

    def test_eval_with_filter(self):
        class MockToolProvider(ToolProvider):
            async def call_tool(self, name, arguments):
                if name == "is_even":
                    return ToolOutput(content=arguments["x"] % 2 == 0)
                raise ValueError(f"Unknown tool: {name}")

            async def list_tools(self):
                return AsyncMock(
                    tools=[
                        {
                            "name": "is_even",
                            "description": "Checks if a number is even",
                            "properties": {"x": {}},
                        }
                    ]
                )

            async def get_tool_definition(self, name):
                if name == "is_even":
                    return {
                        "name": "is_even",
                        "description": "Checks if a number is even",
                        "properties": {"x": {}},
                    }
                else:
                    raise ValueError(f"Tool {name} not found")

        ast_dict = {
            "type": "program",
            "mode": "single",
            "body": [
                {
                    "type": "filter",
                    "function": {
                        "type": "lambda",
                        "params": ["x"],
                        "body": {
                            "type": "function",
                            "name": "is_even",
                            "params": [{"type": "value", "name": "x", "value": None}],
                        },
                    },
                    "iterable": {
                        "type": "value",
                        "name": "numbers",
                        "value": [1, 2, 3, 4],
                    },
                }
            ],
        }
        provider = MockToolProvider()
        program = AST.parse(ast_dict)
        result = asyncio.run(AST.eval(program, provider))
        self.assertEqual(result, [2, 4])

    def test_eval_with_reduce(self):
        class MockToolProvider(ToolProvider):
            async def call_tool(self, name, arguments):
                if name == "add":
                    return ToolOutput(content=arguments["acc"] + arguments["item"])
                raise ValueError(f"Unknown tool: {name}")

            async def list_tools(self):
                return AsyncMock(
                    tools=[
                        {
                            "name": "add",
                            "description": "Adds two numbers",
                            "properties": {"acc": {}, "item": {}},
                        }
                    ]
                )

            async def get_tool_definition(self, name):
                if name == "add":
                    return {
                        "name": "add",
                        "description": "Adds two numbers",
                        "properties": {"acc": {}, "item": {}},
                    }
                else:
                    raise ValueError(f"Tool {name} not found")

        ast_dict = {
            "type": "program",
            "mode": "single",
            "body": [
                {
                    "type": "reduce",
                    "function": {
                        "type": "lambda",
                        "params": ["acc", "item"],
                        "body": {
                            "type": "function",
                            "name": "add",
                            "params": [
                                {"type": "value", "name": "acc", "value": 0},
                                {"type": "value", "name": "item", "value": None},
                            ],
                        },
                    },
                    "iterable": {
                        "type": "value",
                        "name": "numbers",
                        "value": [1, 2, 3],
                    },
                }
            ],
        }
        provider = MockToolProvider()
        program = AST.parse(ast_dict)
        result = asyncio.run(AST.eval(program, provider))
        self.assertEqual(result, 6)

    def test_visit(self):
        node = TreeNode()
        op = Mock()
        AST.visit(node, op)
        op.assert_called_once_with(node)

    def test_visit_with_conditional(self):
        condition = TreeValue(name="condition", value=True)
        true_branch = TreeValue(name="true_branch", value="True Result")
        false_branch = TreeValue(name="false_branch", value="False Result")
        conditional = TreeConditional(
            condition=condition, true_branch=true_branch, false_branch=false_branch
        )

        op = Mock()
        AST.visit(conditional, op)

        # Assert that the visitor function was called for the conditional node and its children
        op.assert_any_call(conditional)
        op.assert_any_call(condition)
        op.assert_any_call(true_branch)
        op.assert_any_call(false_branch)
        self.assertEqual(op.call_count, 4)  # Ensure all nodes were visited

    def test_visit_with_lambda(self):
        params = ["x", "y"]
        body = TreeFunction(
            name="add",
            params=[TreeValue(name="x", value=None), TreeValue(name="y", value=None)],
        )
        lam = TreeLambda(params=params, body=body)

        op = Mock()
        AST.visit(lam, op)

        # Assert that the visitor function was called for the lambda node and its children
        op.assert_any_call(lam)
        op.assert_any_call(body)
        # the lambda node, the function node and two values should be visited
        self.assertEqual(op.call_count, 4)

    def test_visit_with_map(self):
        function = TreeLambda(
            params=["x"],
            body=TreeFunction(name="double", params=[TreeValue(name="x", value=None)]),
        )
        iterable = TreeValue(name="items", value=[1, 2, 3])
        tree_map = TreeMap(function=function, iterable=iterable)

        op = Mock()
        AST.visit(tree_map, op)

        # Assert that the visitor function was called for the map node and its children
        op.assert_any_call(tree_map)
        op.assert_any_call(function)
        op.assert_any_call(iterable)
        self.assertEqual(op.call_count, 5)

    def test_visit_with_filter(self):
        function = TreeLambda(
            params=["x"],
            body=TreeFunction(name="is_even", params=[TreeValue(name="x", value=None)]),
        )
        iterable = TreeValue(name="items", value=[1, 2, 3, 4])
        tree_filter = TreeFilter(function=function, iterable=iterable)

        op = Mock()
        AST.visit(tree_filter, op)

        # Assert that the visitor function was called for the filter node and its children
        op.assert_any_call(tree_filter)
        op.assert_any_call(function)
        op.assert_any_call(iterable)
        self.assertEqual(op.call_count, 5)

    def test_visit_with_reduce(self):
        function = TreeLambda(
            params=["acc", "item"],
            body=TreeFunction(
                name="add",
                params=[
                    TreeValue(name="acc", value=None),
                    TreeValue(name="item", value=None),
                ],
            ),
        )
        iterable = TreeValue(name="items", value=[1, 2, 3])
        tree_reduce = TreeReduce(function=function, iterable=iterable)
        op = Mock()
        AST.visit(tree_reduce, op)

        # Assert that the visitor function was called for the reduce node and its children
        op.assert_any_call(tree_reduce)
        op.assert_any_call(function)
        op.assert_any_call(iterable)
        self.assertEqual(op.call_count, 6)
