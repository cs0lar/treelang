import asyncio
from typing import Any, List, Union, Dict
from collections.abc import Callable
from mcp import ClientSession


class TreeNode:
    """
    Represents a node in the abstract syntax tree (AST).

    Attributes:
        type (str): The type of the AST node.

    Methods:
        eval(): Evaluates the AST node. This method should be implemented by subclasses.
    """

    def __init__(self, node_type: str) -> None:
        self.type = node_type

    async def eval(self) -> Any:
        raise NotImplementedError()


class TreeProgram(TreeNode):
    """
    Represents a program in the abstract syntax tree (AST).

    Attributes:
        body (List[TreeNode]): The list of statements in the program.
        name str: optional name for this program.
        description str: optional description for this program.

    Methods:
        eval(): Evaluates the program by evaluating each statement in the body.
    """

    def __init__(
        self, body: List[TreeNode], name: str, description: str = None
    ) -> None:
        super().__init__("program")
        self.body = body
        self.name = name
        self.description = description

    async def eval(self) -> Any:
        return await asyncio.gather(*[node.eval() for node in self.body])


class TreeFunction(TreeNode):
    """
    Represents a function in the abstract syntax tree (AST).

    Attributes:
        name (str): The name of the function.
        params (List[str]): The list of parameters of the function.
        session (ClientSession): The session object to interact with the MCP server.

    Methods:
        eval(): Evaluates the function by evaluating each statement in the body.
    """

    def __init__(
        self, name: str, params: List[TreeNode], session: ClientSession
    ) -> None:
        super().__init__("function")
        self.name = name
        self.params = params
        self.session = session

    async def is_tool_available(self) -> bool:
        response = await self.session.list_tools()
        tools = response.tools
        return any(tool.name == self.name for tool in tools)

    async def eval(self) -> Any:
        if not await self.is_tool_available():
            raise ValueError(f"Tool {self.name} is not available")

        return await self.session.call_tool(
            self.name, {node.name: await node.eval() for node in self.params}
        )


class TreeValue(TreeNode):
    """
    Represents a value in the abstract syntax tree (AST).

    Attributes:
        value (Any): The value of the node.

    Methods:
        eval(): Evaluates the value by returning the value.
    """

    def __init__(self, name: str, value: Any) -> None:
        super().__init__("value")
        self.name = name
        self.value = value

    async def eval(self) -> Any:
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
    async def eval(cls, ast: TreeNode) -> Any:
        """
        Evaluates the given AST.

        Args:
            ast TreeNode: The AST to evaluate.

        Returns:
            Any: The result of evaluating the AST.
        """
        return await ast.eval()

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
            for argument in ast.arguments:
                cls.visit(
                    argument, op
                )  # Recursively visit each argument of the function

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
                args = "{" + ", ".join(["%s"] * len(node.arguments)) + "}"
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
