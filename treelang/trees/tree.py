import asyncio
import json
from inspect import Signature, Parameter
import random
from typing import Any, List, Union, Dict
from collections.abc import Callable
from mcp import ClientSession
from mcp.types import AnyFunction


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
            if output.content[0].text.startswith("Error"):
                raise RuntimeError(
                    f"Error calling tool {self.name}: {output.content[0].text}"
                )
            # return the result attempting to transform it into its appropriate type
            content = (
                output.content[0].text
                if len(output.content) == 1
                else "[" + ",".join([out.text for out in output.content]) + "]"
            )
            return json.loads(content)
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
    async def avisit(cls, ast: TreeNode, op: Callable[[TreeNode], None]) -> None:
        """
        Performs an asynchronous depth-first visit of the AST and applies the given operation to each node.

        Args:
            ast (TreeNode): The root node of the AST.
            op (Callable[[TreeNode], None]): The operation to apply to each node.

        Returns:
            None
        """
        if asyncio.iscoroutinefunction(op):
            await op(ast)  # Apply the asynchronous operation to the current node
        else:
            return cls.visit(ast, op)  # Fallback to synchronous visit

        if isinstance(ast, TreeProgram):
            for statement in ast.body:
                await cls.avisit(
                    statement, op
                )  # Recursively visit each statement in the program

        elif isinstance(ast, TreeFunction):
            for param in ast.params:
                await cls.avisit(
                    param, op
                )  # Recursively visit each parameter of the function

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

    @staticmethod
    async def tool(ast: TreeNode, session: ClientSession) -> AnyFunction:
        """
        Converts the given AST into a callable function that can be
        added as a tool to the MCP server.

        Args:
            ast (TreeNode): The AST to convert.

        Returns:
            AnyFunction: The callable function representation of the AST.
        """
        if not isinstance(ast, TreeProgram):
            raise ValueError("AST root must be a TreeProgram")

        tool_signature = None

        # map json types from tool definitions to python types
        types_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        # the program must have a name and description
        if not ast.name:
            raise ValueError("AST program must have a name")
        if not ast.description:
            raise ValueError("AST program must have a description")

        # extract the programs' parameters from the tree
        param_objects = []

        # the arguments of the new tool are to be gathered from
        # the leaves of the tree
        def inject(
            param_objs: List[Parameter],
            props: List[Dict[str, Any]],
            arg_names: List[str],
        ) -> Callable[[TreeNode], None]:
            async def _f(node: TreeNode):
                if isinstance(node, TreeFunction):
                    other_dfn = await node.get_tool_definition(session)
                    # let's get this function's parameters into the props stack
                    props.append(other_dfn.inputSchema["properties"])

                if isinstance(node, TreeValue):
                    # since this is a leaf node, we can add it to the parameters
                    # of the new tool
                    if node.name not in props[-1]:
                        # if we are here, we are are now processing
                        # a function node up the tree and we can
                        # pop the properties stack
                        props.pop()

                    properties = props[-1]

                    key = node.name
                    # be mindful of duplicate arguments names
                    if key in arg_names:
                        key = key + f"_{random.randint(1, 1000)}"
                    arg_names.append(key)
                    param_objs.append(
                        Parameter(
                            key,
                            Parameter.KEYWORD_ONLY,
                            annotation=types_map.get(
                                properties[node.name]["type"], Any
                            ),
                        )
                    )

            return _f

        await AST.avisit(ast, inject(param_objects, [], []))

        try:
            tool_signature = Signature(
                parameters=param_objects,
            )
        except ValueError as e:
            raise ValueError(f"Invalid function signature for {ast.name}") from e

        # convert the AST to a callable function
        async def wrapper(*args, **kwargs):
            try:
                # bind the arguments to our tool signature
                bound_args = tool_signature.bind(*args, **kwargs)
                # apply the default values if any
                bound_args.apply_defaults()
            except TypeError as e:
                raise TypeError(f"Argument binding failed for {ast.name}(): {e}") from e
            # evaluating this tool is equivalent to evaluating the AST
            # thus, we need to inject the arguments'values into the AST
            try:

                def inject(*vargs, **vwargs) -> Callable[[TreeNode], None]:
                    def _f(node: TreeNode) -> None:
                        if isinstance(node, TreeValue):
                            if vwargs and node.name in vwargs:
                                node.value = vwargs[node.name]
                            elif vargs:
                                node.value = vargs.pop()

                    return _f

                AST.visit(ast, inject(*bound_args.args, **bound_args.kwargs))
                # finally, evaluate the AST
                return await ast.eval(session)
            except Exception as e:
                raise RuntimeError(f"Error executing {ast.name}(): {e}") from e

        # set the function's signature and metadata
        wrapper.__name__ = ast.name
        wrapper.__doc__ = ast.description
        wrapper.__signature__ = tool_signature

        return wrapper
