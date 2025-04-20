import unittest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from mcp import ClientSession
import mcp.types as types
from treelang.trees.tree import (
    AST,
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
                    content = add(**arguments)
                elif name == "mul":
                    content = mul(**arguments)
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=str(content))]
                )

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
            self.assertEqual(int(result), (12 * 6) + 4)

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
        session = AsyncMock(spec=ClientSession)
        session.list_tools.return_value = types.ListToolsResult(
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
        tool_function = await AST.tool(self.ast, session)

        self.assertEqual(tool_function.__name__, "add_tool")
        self.assertEqual(tool_function.__doc__, "Adds two numbers")
        self.assertTrue(callable(tool_function))
        self.assertIn("a", tool_function.__signature__.parameters)
        self.assertIn("b", tool_function.__signature__.parameters)

    async def test_tool_execution(self):
        async def mock_call_tool(name, arguments):
            if name == "add":
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text=str(arguments["a"] + arguments["b"])
                        )
                    ]
                )

        session = AsyncMock(spec=ClientSession)
        session.list_tools.return_value = types.ListToolsResult(
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
        session.call_tool = mock_call_tool

        tool_function = await AST.tool(self.ast, session)
        result = await tool_function(a=5, b=10)
        self.assertEqual(result, 15)

    async def test_tool_missing_parameters(self):
        session = AsyncMock(spec=ClientSession)
        session.list_tools.return_value = types.ListToolsResult(
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
        tool_function = await AST.tool(self.ast, session)

        with self.assertRaises(TypeError):
            await tool_function(a=5)

    async def test_tool_invalid_ast(self):
        invalid_ast = TreeValue(name="invalid", value=42)
        session = AsyncMock(spec=ClientSession)

        with self.assertRaises(ValueError):
            await AST.tool(invalid_ast, session)

    async def test_tool_runtime_error(self):
        async def mock_call_tool(name, arguments):
            if name == "add":
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text="Error: Something went wrong"
                        )
                    ]
                )

        session = AsyncMock(spec=ClientSession)
        session.list_tools.return_value = types.ListToolsResult(
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
        session.call_tool = mock_call_tool

        tool_function = await AST.tool(self.ast, session)

        with self.assertRaises(RuntimeError):
            await tool_function(a=5, b=10)


if __name__ == "__main__":
    unittest.main()
