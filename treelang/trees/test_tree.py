import unittest
import asyncio
from unittest.mock import AsyncMock, patch
from treelang.trees.tree import (
    AST,
    TreeNode,
    TreeProgram,
    TreeFunction,
    TreeValue,
    ClientSession,
)


class TestTreeNode(unittest.TestCase):
    def test_tree_node_init(self):
        node = TreeNode("test")
        self.assertEqual(node.type, "test")

    def test_tree_node_eval(self):
        node = TreeNode("test")
        with self.assertRaises(NotImplementedError):
            asyncio.run(node.eval())


class TestTreeProgram(unittest.TestCase):
    def test_tree_program_init(self):
        body = [TreeNode("test")]
        program = TreeProgram(body, "test_program", "description")
        self.assertEqual(program.type, "program")
        self.assertEqual(program.body, body)
        self.assertEqual(program.name, "test_program")
        self.assertEqual(program.description, "description")

    @patch("asyncio.gather", return_value="result")
    def test_tree_program_eval(self, mock_gather):
        body = [TreeNode("test")]
        program = TreeProgram(body, "test_program")
        result = asyncio.run(program.eval())
        self.assertEqual(result, "result")
        mock_gather.assert_called_once_with(*[node.eval() for node in body])


class TestTreeFunction(unittest.TestCase):
    def test_tree_function_init(self):
        params = [TreeNode("param")]
        session = AsyncMock(spec=ClientSession)
        function = TreeFunction("test_function", params, session)
        self.assertEqual(function.type, "function")
        self.assertEqual(function.name, "test_function")
        self.assertEqual(function.params, params)
        self.assertEqual(function.session, session)

    @patch(
        "treelang.trees.tree.ClientSession.list_tools", return_value=AsyncMock(tools=[])
    )
    def test_tree_function_is_tool_available(self, mock_list_tools):
        params = [TreeNode("param")]
        session = AsyncMock(spec=ClientSession)
        function = TreeFunction("test_function", params, session)
        result = asyncio.run(function.is_tool_available())
        self.assertFalse(result)

    @patch("treelang.trees.tree.ClientSession.call_tool", return_value=AsyncMock())
    @patch("treelang.trees.tree.TreeFunction.is_tool_available", return_value=True)
    def test_tree_function_eval(self, mock_is_tool_available, mock_call_tool):
        params = [TreeValue("param", 42)]
        session = AsyncMock(spec=ClientSession)
        function = TreeFunction("test_function", params, session)
        result = asyncio.run(function.eval())
        self.assertIsNotNone(result)
        mock_is_tool_available.assert_called_once()
        mock_call_tool.assert_called_once_with("test_function", {"param": 42})


class TestTreeValue(unittest.TestCase):
    def test_tree_value_init(self):
        value = TreeValue("test_value", 42)
        self.assertEqual(value.type, "value")
        self.assertEqual(value.name, "test_value")
        self.assertEqual(value.value, 42)

    def test_tree_value_eval(self):
        value = TreeValue("test_value", 42)
        result = asyncio.run(value.eval())
        self.assertEqual(result, 42)


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

        # Mock the eval function to call the appropriate function based on the name
        async def mock_call_tool(name, params):
            if name == "add":
                return add(**params)
            elif name == "mul":
                return mul(**params)
            return None

        with patch("treelang.trees.tree.ClientSession.call_tool", new=mock_call_tool):
            with patch(
                "treelang.trees.tree.TreeFunction.is_tool_available",
                new=AsyncMock(return_value=True),
            ):
                program = AST.parse(self.ast)
                result = asyncio.run(AST.eval(program))
                self.assertIsNotNone(result)
                self.assertEqual(result, (12 * 6) + 4)

    def test_visit(self):
        node = TreeNode("test")
        op = AsyncMock()
        AST.visit(node, op)
        op.assert_called_once_with(node)

    def test_repr(self):
        ast = TreeProgram(
            body=[TreeFunction(name="foo", params=[]), TreeValue(name="z", value=10)]
        )
        result = AST.repr(ast)
        self.assertEqual(result, '{"foo_1": {}, "z": [10]}')


if __name__ == "__main__":
    unittest.main()
