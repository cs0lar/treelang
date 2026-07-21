from collections.abc import Callable
from typing import Any, Dict, List, Union, overload

from treelang.ai.provider import ToolProvider
from treelang.trees.compilation import compile_tool
from treelang.trees.schemas.v1 import AST as ASTSchema
from treelang.trees.schemas.v1 import TreeNode
from treelang.trees.traversal import avisit, visit


class AST:
    """
    Represents an Abstract Syntax Tree (AST) for a very simple programming language.
    """

    @overload
    @classmethod
    def parse(cls, ast: Dict[str, Any]) -> TreeNode: ...

    @overload
    @classmethod
    def parse(cls, ast: List[Dict[str, Any]]) -> list[TreeNode]: ...

    @classmethod
    def parse(
        cls, ast: Union[Dict[str, Any], List[Dict[str, Any]]]
    ) -> TreeNode | list[TreeNode]:
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
        Converts the given AST into a callable function that can be added as a tool.

        Args:
            ast (TreeNode): The AST to convert.

        Returns:
            AnyFunction: The callable function representation of the AST.
        """
        return await compile_tool(ast, provider)
