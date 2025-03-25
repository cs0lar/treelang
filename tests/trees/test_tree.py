import unittest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
import mcp.types as types
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
        session = AsyncMock(spec=ClientSession)
        with self.assertRaises(NotImplementedError):
            asyncio.run(node.eval(session))


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
        session = AsyncMock(spec=ClientSession)
        program = TreeProgram(body, "test_program")
        result = asyncio.run(program.eval(session))
        self.assertEqual(result, "result")


class TestTreeFunction(unittest.TestCase):
    def test_tree_function_init(self):
        params = [TreeNode("param")]
        function = TreeFunction("test_function", params)
        self.assertEqual(function.type, "function")
        self.assertEqual(function.name, "test_function")
        self.assertEqual(function.params, params)

    @patch(
        "treelang.trees.tree.ClientSession.list_tools", return_value=AsyncMock(tools=[])
    )
    def test_tree_function_get_tool_definition(self, mock_list_tools):
        params = [TreeNode("param")]
        session = AsyncMock(spec=ClientSession)
        function = TreeFunction("test_function", params)
        result = asyncio.run(function.get_tool_definition(session))
        self.assertIsNone(result)

    @patch(
        "treelang.trees.tree.TreeFunction.get_tool_definition",
        return_value=types.Tool(
            name="test_function",
            description="test_description",
            inputSchema={"properties": {"param": {}}},
        ),
    )
    def test_tree_function_eval(self, mock_get_tool_definition):
        params = [TreeValue("param", 42)]
        session = AsyncMock(spec=ClientSession)
        function = TreeFunction("test_function", params)
        result = asyncio.run(function.eval(session))
        self.assertIsNotNone(result)
        mock_get_tool_definition.assert_called_once()
        session.call_tool.assert_called_once_with("test_function", {"param": 42})


class TestTreeValue(unittest.TestCase):
    def test_tree_value_init(self):
        value = TreeValue("test_value", 42)
        self.assertEqual(value.type, "value")
        self.assertEqual(value.name, "test_value")
        self.assertEqual(value.value, 42)

    def test_tree_value_eval(self):
        value = TreeValue("test_value", 42)
        session = AsyncMock(spec=ClientSession)
        result = asyncio.run(value.eval(session))
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

        class MockClientSession(ClientSession):
            async def call_tool(name, arguments):
                if name == "add":
                    return add(**arguments)
                elif name == "mul":
                    return mul(**arguments)
                return None

            async def list_tools():
                return AsyncMock(
                    tools=[
                        types.Tool(
                            name="add",
                            desciption="test_description",
                            inputSchema={"properties": {"a": {}, "b": {}}},
                        ),
                        types.Tool(
                            name="mul",
                            desciption="test_description",
                            inputSchema={"properties": {"a": {}, "b": {}}},
                        ),
                    ]
                )

        with patch(
            "treelang.trees.tree.ClientSession", new=MockClientSession
        ) as session:
            [program] = AST.parse(self.ast)
            result = asyncio.run(AST.eval(program, session))
            self.assertIsNotNone(result)
            self.assertEqual(result, (12 * 6) + 4)

    def test_visit(self):
        node = TreeNode("test")
        op = Mock()
        AST.visit(node, op)
        op.assert_called_once_with(node)

    def test_repr(self):
        ast = TreeProgram(
            body=[
                TreeFunction(name="foo", params=[]),
                TreeValue(name="z", value=10),
            ]
        )
        result = AST.repr(ast)
        self.assertEqual(result, '{"foo_1": {}, "z": [10]}')


if __name__ == "__main__":
    unittest.main()
