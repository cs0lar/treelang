import asyncio
import random
from collections.abc import Callable
from inspect import Parameter, Signature
from typing import Any, Dict, List, Union

from treelang.ai.provider import ToolProvider
from treelang.trees.schemas.v1 import AST as ASTSchema
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
            return ASTSchema.model_validate(ast)
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
        op(ast)  # Apply the operation to the current node

        if isinstance(ast, TreeProgram):
            for statement in ast.body:
                cls.visit(
                    statement, op
                )  # Recursively visit each statement in the program

        if isinstance(ast, TreeConditional):
            cls.visit(ast.condition, op)
            cls.visit(ast.true_branch, op)  # Recursively visit the true branch
            if ast.false_branch:
                # Recursively visit the false branch
                cls.visit(ast.false_branch, op)

        if isinstance(ast, TreeLambda):
            cls.visit(ast.body, op)

        if any(
            [
                isinstance(ast, node_type)
                for node_type in [TreeMap, TreeFilter, TreeReduce]
            ]
        ):
            cls.visit(ast.function, op)
            cls.visit(ast.iterable, op)

        elif isinstance(ast, TreeFunction):
            for param in ast.params:
                # Recursively visit each parameter of the function
                cls.visit(param, op)

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
            # Apply the asynchronous operation to the current node
            await op(ast)
        else:
            return cls.visit(ast, op)  # Fallback to synchronous visit

        if isinstance(ast, TreeProgram):
            for statement in ast.body:
                await cls.avisit(
                    statement, op
                )  # Recursively visit each statement in the program

        if isinstance(ast, TreeConditional):
            await cls.avisit(ast.condition, op)
            await cls.avisit(ast.true_branch, op)
            if ast.false_branch:
                await cls.avisit(ast.false_branch, op)

        if isinstance(ast, TreeLambda):
            await cls.avisit(ast.body, op)

        if any(
            [
                isinstance(ast, node_type)
                for node_type in [TreeMap, TreeFilter, TreeReduce]
            ]
        ):
            await cls.avisit(ast.function, op)
            await cls.avisit(ast.iterable, op)

        elif isinstance(ast, TreeFunction):
            for param in ast.params:
                await cls.avisit(
                    param, op
                )  # Recursively visit each parameter of the function

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
                    # be mindful of duplicate arguments names
                    if key in arg_names:
                        # we add a random suffix to the key
                        key = key + f"_{random.randint(1, 1000)}"
                        # rename the parameter in the properties dict
                        properties = {
                            key if k == node.name else k: v
                            for k, v in properties.items()
                        }
                        node.name = key
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
            raise ValueError(
                f"Invalid function signature for {ast.name}") from e

        # convert the AST to a callable function
        async def wrapper(*args, **kwargs):
            try:
                # bind the arguments to our tool signature
                bound_args = tool_signature.bind(*args, **kwargs)
                # apply the default values if any
                bound_args.apply_defaults()
            except TypeError as e:
                raise TypeError(
                    f"Argument binding failed for {ast.name}(): {e}") from e
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
                return await ast.eval(provider)
            except Exception as e:
                raise RuntimeError(f"Error executing {ast.name}(): {e}") from e

        # set the function's signature and metadata
        wrapper.__name__ = ast.name
        wrapper.__doc__ = ast.description
        wrapper.__signature__ = tool_signature

        return wrapper
