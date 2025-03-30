import asyncio
import json
from typing import Any, List, Union, Dict
from collections.abc import Callable
from mcp import ClientSession


class TreeNode:
    """
    Represents a node in the abstract syntax tree (AST).

    Attributes:
        type (str): The type of the AST node.

    Methods:
        eval(ClientSession): Evaluates the AST node. This method should be implemented by subclasses.
    """

    def __init__(self, node_type: str) -> None:
        self.type = node_type

    async def eval(self, session: ClientSession) -> Any:
        raise NotImplementedError()


class TreeProgram(TreeNode):
    """
    Represents a program in the abstract syntax tree (AST).

    Attributes:
        body (List[TreeNode]): The list of statements in the program.
        name str: optional name for this program.
        description str: optional description for this program.

    Methods:
        eval(ClientSession): Evaluates the program by evaluating each statement in the body.
    """

    def __init__(
        self, body: List[TreeNode], name: str = None, description: str = None
    ) -> None:
        super().__init__("program")
        self.body = body
        self.name = name
        self.description = description

    async def eval(self, session: ClientSession) -> Any:
        result = await asyncio.gather(*[node.eval(session) for node in self.body])
        return result[0] if len(result) == 1 else result


class TreeFunction(TreeNode):
    """
    Represents a function in the abstract syntax tree (AST).

    Attributes:
        name (str): The name of the function.
        params (List[str]): The list of parameters of the function.
        session (ClientSession): The session object to interact with the MCP server.

    Methods:
        eval(ClientSession): Evaluates the function by evaluating each statement in the body.
    """

    def __init__(self, name: str, params: List[TreeNode]) -> None:
        super().__init__("function")
        self.name = name
        self.params = params

    async def get_tool_definition(self, session) -> Dict[str, Any]:
        response = await session.list_tools()
        tools = response.tools

        return next((tool for tool in tools if tool.name == self.name), None)

    async def eval(self, session: ClientSession) -> Any:
        tool = await self.get_tool_definition(session)

        if not tool:
            raise ValueError(f"Tool {self.name} is not available")

        tool_properties = tool.inputSchema["properties"].keys()

        # evaluate each parameter in order
        results = await asyncio.gather(*[param.eval(session) for param in self.params])
        # create a dictionary of parameter names and values
        params = dict(zip(tool_properties, results))
        # invoke the underlying tool
        output = await session.call_tool(self.name, params)
        # check if the output is a list of strings
        if isinstance(output.content, list) and len(output.content):
            # return the result attempting to transform it into its appropriate type
            return json.loads(output.content[0].text)
        return output.content


class TreeValue(TreeNode):
    """
    Represents a value in the abstract syntax tree (AST).

    Attributes:
        value (Any): The value of the node.

    Methods:
        eval(ClientSession): Evaluates the value by returning the value.
    """

    def __init__(self, name: str, value: Any) -> None:
        super().__init__("value")
        self.name = name
        self.value = value

    async def eval(self, session: ClientSession) -> Any:
        return self.value


class AST:
    """
    Represents an Abstract Syntax Tree (AST) for a very simple programming language.
    """

    @classmethod
    def parse(cls, ast: Union[Dict[str, Any], List[Dict[str, Any]]]) -> TreeNode:
        """
        Parses the given dictionary or list into a TreeNode.

        Args:
            ast (Union[Dict[str, Any], List[Dict[str, Any]]]): The AST dictionary or list of dictionaries to parse.

        Returns:
            TreeNode: The parsed TreeNode.

        Raises:
            ValueError: If the node type is unknown.
        """
        if isinstance(ast, List):
            return [cls.parse(node) for node in ast]
        node_type = ast.get("type")

        if node_type == "program":
            return TreeProgram(cls.parse(ast["body"]))
        if node_type == "function":
            return TreeFunction(ast["name"], cls.parse(ast["params"]))
        if node_type == "value":
            return TreeValue(ast["name"], ast["value"])

        raise ValueError(f"unknown node type: {node_type}")

    @classmethod
    async def eval(cls, ast: TreeNode, session: ClientSession) -> Any:
        """
        Evaluates the given AST.

        Args:
            ast TreeNode: The AST to evaluate.

        Returns:
            Any: The result of evaluating the AST.
        """
        return await ast.eval(session)

    @classmethod
    def visit(cls, ast: TreeNode, op: Callable[[TreeNode], None]) -> None:
        """
        Performs a depth-first visit of the AST and applies the given operation to each node.

        Args:
            ast (TreeNode): The root node of the AST.
            op (Callable[[TreeNode], None]): The operation to apply to each node.

        Returns:
            None
        """
        op(ast)  # Apply the operation to the current node

        if isinstance(ast, TreeProgram):
            for statement in ast.body:
                cls.visit(
                    statement, op
                )  # Recursively visit each statement in the program

        elif isinstance(ast, TreeFunction):
            for param in ast.params:
                cls.visit(param, op)  # Recursively visit each parameter of the function

    @classmethod
    def repr(cls, ast: TreeNode) -> str:
        """
        Returns a string representation of the given TreeNode.

        Parameters:
        - cls (class): The class containing the `repr` method.
        - ast (TreeNode): The TreeNode to be represented.

        Returns:
        - str: The string representation of the TreeNode.

        Example:
        >>> ast = TreeProgram(body=[TreeFunction(name='foo', params=['x', 'y']), TreeValue(name='z', value=10)])
        >>> AST.repr(ast)
        "{foo_1: {x, y}, z_1: [10]}"
        """
        representation = ""
        name_counts = dict()

        def _f(node: TreeNode):
            nonlocal representation
            if isinstance(node, TreeProgram):
                representation = "{" + ", ".join(["%s"] * len(node.body)) + "}"
            if isinstance(node, TreeFunction):
                name = node.name
                if name not in name_counts:
                    name_counts[name] = 0
                name_counts[name] += 1
                args = "{" + ", ".join(["%s"] * len(node.params)) + "}"
                representation = representation.replace(
                    "%s", f'"{name}_{name_counts[name]}": {args}', 1
                )
            if isinstance(node, TreeValue):
                name = node.name
                value = node.value
                if type(value) is str:
                    value = f'"{value}"'
                if type(value) is bool:
                    value = str(value).lower()
                if isinstance(value, float) and value.is_integer():
                    value = int(value)
                representation = representation.replace("%s", f'"{name}": [{value}]', 1)

        cls.visit(ast, _f)
        return representation
