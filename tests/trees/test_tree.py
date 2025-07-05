import unittest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from treelang.ai.provider import ToolOutput, ToolProvider
import mcp.types as types
from treelang.trees.tree import (
    AST,
    TreeConditional,
    TreeFilter,
    TreeLambda,
    TreeMap,
    TreeNode,
    TreeProgram,
    TreeFunction,
    TreeReduce,
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


class TestTreeLambda(unittest.IsolatedAsyncioTestCase):
    async def test_tree_lambda_init(self):
        params = ["x", "y"]
        body = TreeFunction("add", [TreeValue("x", None), TreeValue("y", None)])
        lam = TreeLambda(params, body)
        self.assertEqual(lam.type, "lambda")
        self.assertEqual(lam.params, params)
        self.assertEqual(lam.body, body)

    async def test_tree_lambda_eval_returns_callable(self):
        params = ["x"]
        body = TreeFunction("negate", [TreeValue("x", None)])
        lam = TreeLambda(params, body)
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {
            "name": "negate",
            "description": "Negates a number",
            "properties": {"x": {"type": "integer"}},
        }
        provider.call_tool.return_value = ToolOutput(content=-5)
        func = await lam.eval(provider)
        self.assertTrue(callable(func))
        result = await func(5)
        self.assertEqual(result, -5)
        provider.get_tool_definition.assert_called_once_with("negate")
        provider.call_tool.assert_called_once_with("negate", {"x": 5})

    async def test_tree_lambda_eval_multiple_params(self):
        params = ["a", "b"]
        body = TreeFunction("add", [TreeValue("a", None), TreeValue("b", None)])
        lam = TreeLambda(params, body)
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {
            "name": "add",
            "description": "Adds two numbers",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        }
        provider.call_tool.return_value = ToolOutput(content=7)
        func = await lam.eval(provider)
        result = await func(3, 4)
        self.assertEqual(result, 7)
        provider.get_tool_definition.assert_called_once_with("add")
        provider.call_tool.assert_called_once_with("add", {"a": 3, "b": 4})

    async def test_tree_lambda_eval_updates_body_params(self):
        params = ["x"]
        value_node = TreeValue("x", None)
        body = TreeFunction("identity", [value_node])
        lam = TreeLambda(params, body)
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {
            "name": "identity",
            "description": "Returns the input",
            "properties": {"x": {"type": "integer"}},
        }
        provider.call_tool.return_value = ToolOutput(content=123)
        func = await lam.eval(provider)
        await func(123)
        self.assertEqual(value_node.value, 123)


class TestTreeMap(unittest.IsolatedAsyncioTestCase):
    async def test_tree_map_init(self):
        function = TreeLambda(["x"], TreeFunction("identity", [TreeValue("x", None)]))
        iterable = TreeValue("items", [[1], [2], [3]])
        tree_map = TreeMap(function, iterable)
        self.assertEqual(tree_map.type, "map")
        self.assertEqual(tree_map.function, function)
        self.assertEqual(tree_map.iterable, iterable)

    async def test_tree_map_eval_applies_function(self):
        # Lambda: x -> x * 2
        class DummyProvider(ToolProvider):
            async def get_tool_definition(self, name):
                return {
                    "name": "double",
                    "description": "Doubles a number",
                    "properties": {"x": {"type": "integer"}},
                }

            async def call_tool(self, name, arguments):
                return ToolOutput(content=arguments["x"] * 2)

            async def list_tools(self):
                return AsyncMock(
                    tools=[
                        {
                            "name": "double",
                            "description": "Doubles a number",
                            "properties": {"x": {"type": "integer"}},
                        }
                    ]
                )

        function = TreeLambda(["x"], TreeFunction("double", [TreeValue("x", None)]))
        iterable = TreeValue("items", [1, 2, 3])
        tree_map = TreeMap(function, iterable)
        provider = DummyProvider()
        result = await tree_map.eval(provider)
        self.assertEqual(result, [2, 4, 6])

    async def test_tree_map_eval_non_iterable_raises(self):
        function = TreeLambda(["x"], TreeFunction("identity", [TreeValue("x", None)]))
        iterable = TreeValue("items", 123)  # Not a list
        tree_map = TreeMap(function, iterable)
        provider = AsyncMock(spec=ToolProvider)
        with self.assertRaises(TypeError):
            await tree_map.eval(provider)

    async def test_tree_map_eval_function_not_callable_raises(self):
        class DummyProvider(ToolProvider):
            async def get_tool_definition(self, name):
                return {
                    "name": "broken",
                    "description": "Not a function",
                    "properties": {"x": {"type": "integer"}},
                }

            async def call_tool(self, name, arguments):
                return ToolOutput(content=None)

            async def list_tools(self):
                return AsyncMock(
                    tools=[
                        {
                            "name": "broken",
                            "description": "Not a function",
                            "properties": {"x": {"type": "integer"}},
                        }
                    ]
                )

        # Patch TreeLambda.eval to return a non-callable
        function = TreeLambda(["x"], TreeFunction("broken", [TreeValue("x", None)]))
        function.eval = AsyncMock(return_value=42)
        iterable = TreeValue("items", [[1]])
        tree_map = TreeMap(function, iterable)
        provider = DummyProvider()
        with self.assertRaises(TypeError):
            await tree_map.eval(provider)

    async def test_tree_map_eval_empty_iterable(self):
        function = TreeLambda(["x"], TreeFunction("identity", [TreeValue("x", None)]))
        iterable = TreeValue("items", [])
        tree_map = TreeMap(function, iterable)
        provider = AsyncMock(spec=ToolProvider)

        # Patch function.eval to return a dummy callable
        async def dummy_func(x):
            return x

        function.eval = AsyncMock(return_value=dummy_func)
        result = await tree_map.eval(provider)
        self.assertEqual(result, [])


class TestTreeFilter(unittest.IsolatedAsyncioTestCase):
    async def test_tree_filter_init(self):
        function = TreeLambda(["x"], TreeFunction("is_even", [TreeValue("x", None)]))
        iterable = TreeValue("items", [1, 2, 3, 4])
        tree_filter = TreeFilter(function, iterable)

        self.assertEqual(tree_filter.type, "filter")
        self.assertEqual(tree_filter.function, function)
        self.assertEqual(tree_filter.iterable, iterable)

    async def test_tree_filter_eval_filters_items(self):
        class DummyProvider(ToolProvider):
            async def get_tool_definition(self, name):
                return {
                    "name": "is_even",
                    "description": "Checks if a number is even",
                    "properties": {"x": {"type": "integer"}},
                }

            async def call_tool(self, name, arguments):
                return ToolOutput(content=arguments["x"] % 2 == 0)

            async def list_tools(self):
                return AsyncMock(
                    tools=[
                        {
                            "name": "is_even",
                            "description": "Checks if a number is even",
                            "properties": {"x": {"type": "integer"}},
                        }
                    ]
                )

        function = TreeLambda(["x"], TreeFunction("is_even", [TreeValue("x", None)]))
        iterable = TreeValue("items", [1, 2, 3, 4, 5, 6])
        tree_filter = TreeFilter(function, iterable)
        provider = DummyProvider()
        result = await tree_filter.eval(provider)
        self.assertEqual(result, [2, 4, 6])

    async def test_tree_filter_eval_non_iterable_raises(self):
        function = TreeLambda(["x"], TreeFunction("is_even", [TreeValue("x", None)]))
        iterable = TreeValue("items", 123)  # Not a list
        tree_filter = TreeFilter(function, iterable)
        provider = AsyncMock(spec=ToolProvider)
        with self.assertRaises(TypeError):
            await tree_filter.eval(provider)

    async def test_tree_filter_eval_empty_iterable(self):
        function = TreeLambda(["x"], TreeFunction("is_even", [TreeValue("x", None)]))
        iterable = TreeValue("items", [])
        tree_filter = TreeFilter(function, iterable)
        provider = AsyncMock(spec=ToolProvider)

        # Patch function.eval to return a dummy callable
        async def dummy_func(x):
            return True

        function.eval = AsyncMock(return_value=dummy_func)
        result = await tree_filter.eval(provider)
        self.assertEqual(result, [])

    async def test_tree_filter_eval_function_returns_false(self):
        function = TreeLambda(
            ["x"], TreeFunction("always_false", [TreeValue("x", None)])
        )
        iterable = TreeValue("items", [1, 2, 3])
        tree_filter = TreeFilter(function, iterable)
        provider = AsyncMock(spec=ToolProvider)

        async def always_false(x):
            return False

        function.eval = AsyncMock(return_value=always_false)
        result = await tree_filter.eval(provider)
        self.assertEqual(result, [])


class TestTreeReduce(unittest.IsolatedAsyncioTestCase):
    async def test_tree_reduce_init(self):
        function = TreeLambda(
            ["acc", "item"],
            TreeFunction("add", [TreeValue("acc", None), TreeValue("item", None)]),
        )
        iterable = TreeValue("items", [1, 2, 3])
        tree_reduce = TreeReduce(function, iterable)

        self.assertEqual(tree_reduce.type, "reduce")
        self.assertEqual(tree_reduce.function, function)
        self.assertEqual(tree_reduce.iterable, iterable)

    async def test_tree_reduce_eval_empty_iterable(self):
        function = TreeLambda(
            ["acc", "item"],
            TreeFunction("add", [TreeValue("acc", None), TreeValue("item", None)]),
        )
        iterable = TreeValue("items", [])
        tree_reduce = TreeReduce(function, iterable)
        provider = AsyncMock(spec=ToolProvider)

        # Patch function.eval to return a dummy callable
        async def dummy_func(acc, item):
            return acc + item

        function.eval = AsyncMock(return_value=dummy_func)
        result = await tree_reduce.eval(provider)
        self.assertIsNone(result)

    async def test_tree_reduce_eval_applies_function(self):
        class DummyProvider(ToolProvider):
            async def get_tool_definition(self, name):
                return {
                    "name": "add",
                    "description": "Adds two numbers",
                    "properties": {
                        "acc": {"type": "integer"},
                        "item": {"type": "integer"},
                    },
                }

            async def call_tool(self, name, arguments):
                return ToolOutput(content=arguments["acc"] + arguments["item"])

            async def list_tools(self):
                return AsyncMock(
                    tools=[
                        {
                            "name": "add",
                            "description": "Adds two numbers",
                            "properties": {
                                "acc": {"type": "integer"},
                                "item": {"type": "integer"},
                            },
                        }
                    ]
                )

        function = TreeLambda(
            ["acc", "item"],
            TreeFunction("add", [TreeValue("acc", None), TreeValue("item", None)]),
        )
        iterable = TreeValue("items", [1, 2, 3])
        tree_reduce = TreeReduce(function, iterable)
        provider = DummyProvider()
        result = await tree_reduce.eval(provider)
        self.assertEqual(result, 6)  # (1 + 2) + 3


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

    def test_parse_lambda(self):
        ast_dict = {
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
        result = AST.parse(ast_dict)
        self.assertIsInstance(result, TreeLambda)
        self.assertEqual(result.params, ["x", "y"])
        self.assertIsInstance(result.body, TreeFunction)
        self.assertEqual(result.body.name, "add")

    def test_parse_map(self):
        ast_dict = {
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
            "iterable": {"type": "value", "name": "numbers", "value": [1, 2, 3]},
        }
        result = AST.parse(ast_dict)
        self.assertIsInstance(result, TreeMap)
        self.assertIsInstance(result.function, TreeLambda)
        self.assertIsInstance(result.iterable, TreeValue)

    def test_parse_filter(self):
        ast_dict = {
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
            "iterable": {"type": "value", "name": "numbers", "value": [1, 2, 3, 4]},
        }
        result = AST.parse(ast_dict)
        self.assertIsInstance(result, TreeFilter)
        self.assertIsInstance(result.function, TreeLambda)
        self.assertIsInstance(result.iterable, TreeValue)

    def test_parse_reduce(self):
        ast_dict = {
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
            "iterable": {"type": "value", "name": "numbers", "value": [1, 2, 3]},
        }
        result = AST.parse(ast_dict)
        self.assertIsInstance(result, TreeReduce)
        self.assertIsInstance(result.function, TreeLambda)
        self.assertIsInstance(result.iterable, TreeValue)

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
                                {"type": "value", "name": "acc", "value": None},
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

    def test_visit_with_lambda(self):
        params = ["x", "y"]
        body = TreeFunction("add", [TreeValue("x", None), TreeValue("y", None)])
        lam = TreeLambda(params, body)

        op = Mock()
        AST.visit(lam, op)

        # Assert that the visitor function was called for the lambda node and its children
        op.assert_any_call(lam)
        op.assert_any_call(body)
        # the lambda node, the function node and two values should be visited
        self.assertEqual(op.call_count, 4)

    def test_visit_with_map(self):
        function = TreeLambda(["x"], TreeFunction("double", [TreeValue("x", None)]))
        iterable = TreeValue("items", [1, 2, 3])
        tree_map = TreeMap(function, iterable)

        op = Mock()
        AST.visit(tree_map, op)

        # Assert that the visitor function was called for the map node and its children
        op.assert_any_call(tree_map)
        op.assert_any_call(function)
        op.assert_any_call(iterable)
        self.assertEqual(op.call_count, 5)

    def test_visit_with_filter(self):
        function = TreeLambda(["x"], TreeFunction("is_even", [TreeValue("x", None)]))
        iterable = TreeValue("items", [1, 2, 3, 4])
        tree_filter = TreeFilter(function, iterable)

        op = Mock()
        AST.visit(tree_filter, op)

        # Assert that the visitor function was called for the filter node and its children
        op.assert_any_call(tree_filter)
        op.assert_any_call(function)
        op.assert_any_call(iterable)
        self.assertEqual(op.call_count, 5)

    def test_visit_with_reduce(self):
        function = TreeLambda(
            ["acc", "item"],
            TreeFunction("add", [TreeValue("acc", None), TreeValue("item", None)]),
        )
        iterable = TreeValue("items", [1, 2, 3])
        tree_reduce = TreeReduce(function, iterable)

        op = Mock()
        AST.visit(tree_reduce, op)

        # Assert that the visitor function was called for the reduce node and its children
        op.assert_any_call(tree_reduce)
        op.assert_any_call(function)
        op.assert_any_call(iterable)
        self.assertEqual(op.call_count, 6)

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

    def test_repr_with_lambda(self):
        ast = TreeProgram(
            body=[
                TreeLambda(
                    params=["x", "y"],
                    body=TreeFunction(
                        name="add",
                        params=[
                            TreeValue(name="x", value=None),
                            TreeValue(name="y", value=None),
                        ],
                    ),
                )
            ]
        )
        result = AST.repr(ast)
        expected = '{"lambda_1": {"add_1": {"x": [], "y": []}}}'
        self.assertEqual(result, expected)

    def test_repr_with_map(self):
        ast = TreeProgram(
            body=[
                TreeMap(
                    function=TreeLambda(
                        params=["x"],
                        body=TreeFunction(
                            name="double", params=[TreeValue(name="x", value=None)]
                        ),
                    ),
                    iterable=TreeValue(name="items", value=[1, 2, 3]),
                )
            ]
        )
        result = AST.repr(ast)
        expected = (
            '{"map_1": {"lambda_1": {"double_1": {"x": []}}, "items": [[1, 2, 3]]}}'
        )
        self.assertEqual(result, expected)

    def test_repr_with_filter(self):
        ast = TreeProgram(
            body=[
                TreeFilter(
                    function=TreeLambda(
                        params=["x"],
                        body=TreeFunction(
                            name="is_even", params=[TreeValue(name="x", value=None)]
                        ),
                    ),
                    iterable=TreeValue(name="items", value=[1, 2, 3, 4]),
                )
            ]
        )
        result = AST.repr(ast)
        expected = '{"filter_1": {"lambda_1": {"is_even_1": {"x": []}}, "items": [[1, 2, 3, 4]]}}'
        self.assertEqual(result, expected)

    def test_repr_with_reduce(self):
        ast = TreeProgram(
            body=[
                TreeReduce(
                    function=TreeLambda(
                        params=["acc", "item"],
                        body=TreeFunction(
                            name="add",
                            params=[
                                TreeValue(name="acc", value=None),
                                TreeValue(name="item", value=None),
                            ],
                        ),
                    ),
                    iterable=TreeValue(name="items", value=[1, 2, 3]),
                )
            ]
        )
        result = AST.repr(ast)
        expected = '{"reduce_1": {"lambda_1": {"add_1": {"acc": [], "item": []}}, "items": [[1, 2, 3]]}}'
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
