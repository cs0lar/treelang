from collections.abc import Callable
from inspect import Parameter, Signature
from typing import Any, Dict, List, Union

from treelang.ai.provider import ToolProvider
from treelang.exceptions import ASTCompilationError, ASTExecutionError
from treelang.trees.execution import ExecutionContext
from treelang.trees.schemas.v1 import AST as ASTSchema
from treelang.trees.schemas.v1 import (
    TreeFunction,
    TreeLambda,
    TreeMap,
    TreeNode,
    TreeProgram,
    TreeValue,
)
from treelang.trees.traversal import avisit, visit


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
        try:
            return ASTSchema.model_validate(ast).root
        except Exception as e:
            raise ValueError(f"Failed to parse AST: {e}") from e

    @classmethod
    async def eval(cls, ast: TreeNode, provider: ToolProvider) -> Any:
        """
        Evaluates the given AST.

        Args:
            ast TreeNode: The AST to evaluate.
            provider ToolProvider: The provider to use for evaluation.

        Returns:
            Any: The result of evaluating the AST.
        """
        return await ast.eval(provider)

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
        visit(ast, op)

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
        await avisit(ast, op)

    @classmethod
    def repr(cls, ast: TreeNode) -> str:
        """
        Returns a string representation of the AST.

        Args:
            ast (TreeNode): The AST to represent.

        Returns:
            str: The string representation of the AST.
        """
        return ast.model_dump_json(indent=2)

    @staticmethod
    async def tool(ast: TreeNode, provider: ToolProvider) -> Callable[..., Any]:
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
        param_bindings: list[tuple[str, TreeValue]] = []

        # the arguments of the new tool are to be gathered from
        # the leaves of the tree
        def inject(
            param_objs: List[Parameter],
            props: List[Dict[str, Any]],
            arg_names: List[str],
        ) -> Callable[[TreeNode], None]:
            async def _f(node: TreeNode):
                # for now we do not support higher order functions here
                if any(isinstance(node, t) for t in [TreeLambda, TreeMap]):
                    raise ValueError(
                        "Higher order functions (lambdas, maps) are not yet supported in tool creation"
                    )
                if isinstance(node, TreeFunction):
                    other_dfn = await provider.get_tool_definition(node.name)
                    # let's get this function's parameters into the props stack
                    props.append(other_dfn["properties"])

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
                    suffix = 2
                    while key in arg_names:
                        key = f"{node.name}_{suffix}"
                        suffix += 1
                    arg_names.append(key)
                    param_bindings.append((key, node))
                    param_objs.append(
                        Parameter(
                            key,
                            Parameter.KEYWORD_ONLY,
                            annotation=types_map.get(
                                properties[node.name].get("type"), Any
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
            raise ASTCompilationError(
                f"Invalid function signature for {ast.name}"
            ) from e

        # convert the AST to a callable function
        async def wrapper(*args, **kwargs):
            try:
                # bind the arguments to our tool signature
                bound_args = tool_signature.bind(*args, **kwargs)
                # apply the default values if any
                bound_args.apply_defaults()
            except TypeError as e:
                raise TypeError(f"Argument binding failed for {ast.name}(): {e}") from e
            try:
                context = ExecutionContext().bind_nodes(
                    {
                        id(node): bound_args.arguments[parameter_name]
                        for parameter_name, node in param_bindings
                    }
                )
                return await ast.eval(provider, context)
            except Exception as e:
                raise ASTExecutionError(f"Error executing {ast.name}(): {e}") from e

        # set the function's signature and metadata
        wrapper.__name__ = ast.name
        wrapper.__doc__ = ast.description
        wrapper.__signature__ = tool_signature

        return wrapper
