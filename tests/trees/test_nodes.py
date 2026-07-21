import asyncio
import unittest
from unittest.mock import AsyncMock

from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.exceptions import ASTValidationError, ProviderResponseError
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


class TestTreeNode(unittest.TestCase):
    def test_tree_node_init(self):
        node = TreeNode()
        self.assertEqual(node.type, "node")

    def test_tree_node_eval(self):
        node = TreeNode()
        provider = AsyncMock(spec=ToolProvider)
        with self.assertRaises(NotImplementedError):
            asyncio.run(node.eval(provider))


class TestTreeProgram(unittest.TestCase):
    def test_tree_program_init(self):
        body = [TreeValue(name="x", value=10)]
        program = TreeProgram(
            body=body, name="test_program", description="description", mode="single"
        )
        self.assertEqual(program.type, "program")
        self.assertEqual(program.body, body)
        self.assertEqual(program.name, "test_program")
        self.assertEqual(program.description, "description")

    def test_tree_program_eval(self):
        body = [TreeValue(name="x", value="result")]
        provider = AsyncMock(spec=ToolProvider)
        program = TreeProgram(
            body=body, name="test_program", description="description", mode="single"
        )
        result = asyncio.run(program.eval(provider))
        self.assertEqual(result, "result")


class TestTreeFunction(unittest.TestCase):
    def test_tree_function_init(self):
        params = [TreeValue(name="param", value=42)]
        function = TreeFunction(name="test_function", params=params)
        self.assertEqual(function.type, "function")
        self.assertEqual(function.name, "test_function")
        self.assertEqual(function.params, params)

    def test_tree_function_eval(self):
        params = [TreeValue(name="param", value=42)]
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {
            "name": "test_function",
            "description": "test_description",
            "properties": {"param": {}},
        }
        function = TreeFunction(name="test_function", params=params)
        result = asyncio.run(function.eval(provider))
        self.assertIsNotNone(result)
        provider.get_tool_definition.assert_called_once_with("test_function")
        provider.call_tool.assert_called_once_with("test_function", {"param": 42})

    def test_tree_function_rejects_tool_arity_mismatch(self):
        function = TreeFunction(
            name="test_function", params=[TreeValue(name="param", value=42)]
        )
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {
            "name": "test_function",
            "properties": {"first": {}, "second": {}},
        }

        with self.assertRaisesRegex(ASTValidationError, "expects 2 parameters, got 1"):
            asyncio.run(function.eval(provider))

    def test_tree_function_rejects_invalid_tool_definition(self):
        function = TreeFunction(name="test_function", params=[])
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {"name": "test_function"}

        with self.assertRaisesRegex(ProviderResponseError, "properties definition"):
            asyncio.run(function.eval(provider))

    def test_tree_function_does_not_mutate_prefixed_name(self):
        function = TreeFunction(name="functions.test_function", params=[])
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {
            "name": "test_function",
            "properties": {},
        }
        provider.call_tool.return_value = ToolOutput(content="ok")

        self.assertEqual(asyncio.run(function.eval(provider)), "ok")
        self.assertEqual(function.name, "functions.test_function")
        provider.call_tool.assert_awaited_once_with("test_function", {})


class TestTreeFunctionCancellation(unittest.IsolatedAsyncioTestCase):
    async def test_cancellation_propagates_to_provider_call(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()

        class BlockingProvider(ToolProvider):
            async def list_tools(self):
                return []

            async def get_tool_definition(self, name):
                return {"name": name, "properties": {}}

            async def call_tool(self, name, arguments):
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

        task = asyncio.create_task(
            TreeFunction(name="blocking", params=[]).eval(BlockingProvider())
        )
        await started.wait()
        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(cancelled.is_set())


class TestTreeValue(unittest.TestCase):
    def test_tree_value_init(self):
        value = TreeValue(name="test_value", value=42)
        self.assertEqual(value.type, "value")
        self.assertEqual(value.name, "test_value")
        self.assertEqual(value.value, 42)

    def test_tree_value_eval(self):
        value = TreeValue(name="test_value", value=42)
        provider = AsyncMock(spec=ToolProvider)
        result = asyncio.run(value.eval(provider))
        self.assertEqual(result, 42)


class TestTreeConditional(unittest.TestCase):
    def test_tree_conditional_init(self):
        condition = TreeValue(name="condition", value=True)
        true_branch = TreeValue(name="true_branch", value="True Result")
        false_branch = TreeValue(name="false_branch", value="False Result")
        conditional = TreeConditional(
            condition=condition, true_branch=true_branch, false_branch=false_branch
        )

        self.assertEqual(conditional.type, "conditional")
        self.assertEqual(conditional.condition, condition)
        self.assertEqual(conditional.true_branch, true_branch)
        self.assertEqual(conditional.false_branch, false_branch)

    def test_tree_conditional_eval_true_branch(self):
        condition = TreeValue(name="condition", value=True)
        true_branch = TreeValue(name="true_branch", value="True Result")
        false_branch = TreeValue(name="false_branch", value="False Result")
        conditional = TreeConditional(
            condition=condition, true_branch=true_branch, false_branch=false_branch
        )

        provider = AsyncMock(spec=ToolProvider)
        result = asyncio.run(conditional.eval(provider))
        self.assertEqual(result, "True Result")

    def test_tree_conditional_eval_false_branch(self):
        condition = TreeValue(name="condition", value=False)
        true_branch = TreeValue(name="true_branch", value="True Result")
        false_branch = TreeValue(name="false_branch", value="False Result")
        conditional = TreeConditional(
            condition=condition, true_branch=true_branch, false_branch=false_branch
        )

        provider = AsyncMock(spec=ToolProvider)
        result = asyncio.run(conditional.eval(provider))
        self.assertEqual(result, "False Result")

    def test_tree_conditional_eval_no_false_branch(self):
        condition = TreeValue(name="condition", value=False)
        true_branch = TreeValue(name="true_branch", value="True Result")
        conditional = TreeConditional(condition=condition, true_branch=true_branch)
        provider = AsyncMock(spec=ToolProvider)
        result = asyncio.run(conditional.eval(provider))
        self.assertIsNone(result)


class TestTreeLambda(unittest.IsolatedAsyncioTestCase):
    async def test_tree_lambda_init(self):
        params = ["x", "y"]
        body = TreeFunction(
            name="add",
            params=[TreeValue(name="x", value=None), TreeValue(name="y", value=None)],
        )
        lam = TreeLambda(params=params, body=body)
        self.assertEqual(lam.type, "lambda")
        self.assertEqual(lam.params, params)
        self.assertEqual(lam.body, body)

    async def test_tree_lambda_eval_returns_callable(self):
        params = ["x"]
        body = TreeFunction(name="negate", params=[TreeValue(name="x", value=None)])
        lam = TreeLambda(params=params, body=body)
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {
            "name": "negate",
            "description": "Negates a number",
            "properties": {"x": {"type": "integer"}},
        }
        provider.call_tool.return_value = ToolOutput(content=-5)
        func = await lam.eval(provider)
        self.assertTrue(callable(func))
        result = await func(x=5)
        self.assertEqual(result, -5)
        provider.get_tool_definition.assert_called_once_with("negate")
        provider.call_tool.assert_called_once_with("negate", {"x": 5})

    async def test_tree_lambda_eval_multiple_params(self):
        params = ["a", "b"]
        body = TreeFunction(
            name="add",
            params=[TreeValue(name="a", value=None), TreeValue(name="b", value=None)],
        )
        lam = TreeLambda(params=params, body=body)
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {
            "name": "add",
            "description": "Adds two numbers",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        }
        provider.call_tool.return_value = ToolOutput(content=7)
        func = await lam.eval(provider)
        result = await func(a=3, b=4)
        self.assertEqual(result, 7)
        provider.get_tool_definition.assert_called_once_with("add")
        provider.call_tool.assert_called_once_with("add", {"a": 3, "b": 4})

    async def test_tree_lambda_eval_does_not_mutate_body_params(self):
        params = ["x"]
        value_node = TreeValue(name="x", value=None)
        body = TreeFunction(name="identity", params=[value_node])
        lam = TreeLambda(params=params, body=body)
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {
            "name": "identity",
            "description": "Returns the input",
            "properties": {"x": {"type": "integer"}},
        }
        provider.call_tool.return_value = ToolOutput(content=123)
        func = await lam.eval(provider)
        await func(x=123)
        self.assertIsNone(value_node.value)

    async def test_tree_lambda_concurrent_calls_have_isolated_bindings(self):
        value_node = TreeValue(name="x", value=None)
        lam = TreeLambda(
            params=["x"], body=TreeFunction(name="identity", params=[value_node])
        )

        class OverlappingProvider(ToolProvider):
            async def list_tools(self):
                return []

            async def get_tool_definition(self, name):
                return {"name": name, "properties": {"x": {}}}

            async def call_tool(self, name, arguments):
                await asyncio.sleep(0)
                return ToolOutput(content=arguments["x"])

        func = await lam.eval(OverlappingProvider())
        self.assertEqual(await asyncio.gather(func(x=1), func(x=2)), [1, 2])
        self.assertIsNone(value_node.value)


class TestTreeMap(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._original_eval = TreeLambda.eval

    def tearDown(self):
        TreeLambda.eval = self._original_eval

    async def test_tree_map_init(self):
        function = TreeLambda(
            params=["x"],
            body=TreeFunction(
                name="identity", params=[TreeValue(name="x", value=None)]
            ),
        )
        iterable = TreeValue(name="items", value=[[1], [2], [3]])
        tree_map = TreeMap(function=function, iterable=iterable)
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

        function = TreeLambda(
            params=["x"],
            body=TreeFunction(name="double", params=[TreeValue(name="x", value=None)]),
        )
        iterable = TreeValue(name="items", value=[1, 2, 3])
        tree_map = TreeMap(function=function, iterable=iterable)
        provider = DummyProvider()
        result = await tree_map.eval(provider)
        self.assertEqual(result, [2, 4, 6])

    async def test_tree_map_eval_non_iterable_raises(self):
        function = TreeLambda(
            params=["x"],
            body=TreeFunction(
                name="identity", params=[TreeValue(name="x", value=None)]
            ),
        )
        iterable = TreeValue(name="items", value=123)  # Not a list
        tree_map = TreeMap(function=function, iterable=iterable)
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
        TreeLambda.eval = AsyncMock(return_value=42)
        function = TreeLambda(
            params=["x"],
            body=TreeFunction(name="broken", params=[TreeValue(name="x", value=None)]),
        )
        iterable = TreeValue(name="items", value=[[1]])
        tree_map = TreeMap(function=function, iterable=iterable)
        provider = DummyProvider()
        with self.assertRaises(TypeError):
            await tree_map.eval(provider)

    async def test_tree_map_eval_empty_iterable(self):
        function = TreeLambda(
            params=["x"],
            body=TreeFunction(
                name="identity", params=[TreeValue(name="x", value=None)]
            ),
        )
        iterable = TreeValue(name="items", value=[])
        tree_map = TreeMap(function=function, iterable=iterable)
        provider = AsyncMock(spec=ToolProvider)

        # Patch function.eval to return a dummy callable
        async def dummy_func(x):
            return x

        TreeLambda.eval = AsyncMock(return_value=dummy_func)
        result = await tree_map.eval(provider)
        self.assertEqual(result, [])


class TestTreeFilter(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._original_eval = TreeLambda.eval

    def tearDown(self):
        TreeLambda.eval = self._original_eval

    async def test_tree_filter_init(self):
        function = TreeLambda(
            params=["x"],
            body=TreeFunction(name="is_even", params=[TreeValue(name="x", value=None)]),
        )
        iterable = TreeValue(name="items", value=[1, 2, 3, 4])
        tree_filter = TreeFilter(function=function, iterable=iterable)

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

        function = TreeLambda(
            params=["x"],
            body=TreeFunction(name="is_even", params=[TreeValue(name="x", value=None)]),
        )
        iterable = TreeValue(name="items", value=[1, 2, 3, 4, 5, 6])
        tree_filter = TreeFilter(function=function, iterable=iterable)
        provider = DummyProvider()
        result = await tree_filter.eval(provider)
        self.assertEqual(result, [2, 4, 6])

    async def test_tree_filter_eval_non_iterable_raises(self):
        function = TreeLambda(
            params=["x"],
            body=TreeFunction(name="is_even", params=[TreeValue(name="x", value=None)]),
        )
        iterable = TreeValue(name="items", value=123)  # Not a list
        tree_filter = TreeFilter(function=function, iterable=iterable)
        provider = AsyncMock(spec=ToolProvider)
        with self.assertRaises(TypeError):
            await tree_filter.eval(provider)

    async def test_tree_filter_eval_empty_iterable(self):
        function = TreeLambda(
            params=["x"],
            body=TreeFunction(name="is_even", params=[TreeValue(name="x", value=None)]),
        )
        iterable = TreeValue(name="items", value=[])
        tree_filter = TreeFilter(function=function, iterable=iterable)
        provider = AsyncMock(spec=ToolProvider)

        # Patch function.eval to return a dummy callable
        async def dummy_func(x):
            return True

        TreeLambda.eval = AsyncMock(return_value=dummy_func)
        result = await tree_filter.eval(provider)
        self.assertEqual(result, [])

    async def test_tree_filter_eval_function_returns_false(self):
        function = TreeLambda(
            params=["x"],
            body=TreeFunction(
                name="always_false", params=[TreeValue(name="x", value=None)]
            ),
        )
        iterable = TreeValue(name="items", value=[1, 2, 3])
        tree_filter = TreeFilter(function=function, iterable=iterable)
        provider = AsyncMock(spec=ToolProvider)

        async def always_false(x):
            return False

        TreeLambda.eval = AsyncMock(return_value=always_false)
        result = await tree_filter.eval(provider)
        self.assertEqual(result, [])


class TestTreeReduce(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._original_eval = TreeLambda.eval

    def tearDown(self):
        TreeLambda.eval = self._original_eval

    async def test_tree_reduce_init(self):
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
        self.assertEqual(tree_reduce.type, "reduce")
        self.assertEqual(tree_reduce.function, function)
        self.assertEqual(tree_reduce.iterable, iterable)

    async def test_tree_reduce_eval_empty_iterable(self):
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
        iterable = TreeValue(name="items", value=[])
        tree_reduce = TreeReduce(function=function, iterable=iterable)
        provider = AsyncMock(spec=ToolProvider)

        # Patch function.eval to return a dummy callable
        async def dummy_func(acc, item):
            return acc + item

        TreeLambda.eval = AsyncMock(return_value=dummy_func)
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
            params=["acc", "item"],
            body=TreeFunction(
                name="add",
                params=[
                    TreeValue(name="acc", value=0),
                    TreeValue(name="item", value=None),
                ],
            ),
        )
        iterable = TreeValue(name="items", value=[1, 2, 3])
        tree_reduce = TreeReduce(function=function, iterable=iterable)
        provider = DummyProvider()
        result = await tree_reduce.eval(provider)
        self.assertEqual(result, 6)  # (1 + 2) + 3

    async def test_tree_reduce_null_accumulator_uses_first_item(self):
        provider = AsyncMock(spec=ToolProvider)
        provider.get_tool_definition.return_value = {
            "name": "add",
            "properties": {"acc": {"type": "number"}, "item": {"type": "number"}},
        }
        provider.call_tool.side_effect = lambda _, arguments: ToolOutput(
            content=float(arguments["acc"]) + float(arguments["item"])
        )
        tree_reduce = TreeReduce(
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
            iterable=TreeValue(
                name="populations", value=[5_312_000, 5_078_000, 2_514_000]
            ),
        )

        result = await tree_reduce.eval(provider)

        self.assertEqual(result, 12_904_000)
        self.assertEqual(provider.call_tool.await_count, 2)
        self.assertEqual(
            provider.call_tool.await_args_list[0].args,
            ("add", {"acc": 5_312_000, "item": 5_078_000}),
        )
