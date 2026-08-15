from collections.abc import Callable
from typing import Any, Dict, List, Union, overload

from treelang.ai.provider import ToolProvider
from treelang.trees.budget import ExecutionLimits
from treelang.trees.compilation import compile_tool
from treelang.trees.execution import execute
from treelang.trees.execution_v2 import execute_v2
from treelang.trees.policy import ExecutionPolicy
from treelang.trees.schemas.v1 import AST as ASTSchema
from treelang.trees.schemas.v1 import TreeNode
from treelang.trees.schemas.v2 import AST as ASTSchemaV2
from treelang.trees.schemas.v2 import TreeProgram as TreeProgramV2
from treelang.trees.traversal import (
    AsyncVisitor,
    AsyncVisitorV1,
    AsyncVisitorV2,
    TraversableNode,
    Visitor,
    VisitorV1,
    VisitorV2,
    avisit,
    visit,
)

type SupportedTree = TreeNode | TreeProgramV2


class AST:
    """
    Represents an Abstract Syntax Tree (AST) for a very simple programming language.
    """

    @overload
    @classmethod
    def parse(cls, ast: Dict[str, Any]) -> SupportedTree: ...

    @overload
    @classmethod
    def parse(cls, ast: List[Dict[str, Any]]) -> list[SupportedTree]: ...

    @classmethod
    def parse(
        cls, ast: Union[Dict[str, Any], List[Dict[str, Any]]]
    ) -> SupportedTree | list[SupportedTree]:
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
            if ast.get("schema_version") == "2.0":
                return ASTSchemaV2.model_validate(ast).root
            return ASTSchema.model_validate(ast).root
        except Exception as e:
            raise ValueError(f"Failed to parse AST: {e}") from e

    @classmethod
    async def eval(
        cls,
        ast: SupportedTree,
        provider: ToolProvider,
        *,
        limits: ExecutionLimits | None = None,
        policy: ExecutionPolicy | None = None,
    ) -> Any:
        """
        Evaluates the given AST.

        Args:
            ast TreeNode: The AST to evaluate.
            provider ToolProvider: The provider to use for evaluation.
            limits ExecutionLimits: Optional per-invocation resource limits.

        Returns:
            Any: The result of evaluating the AST.
        """
        if isinstance(ast, TreeProgramV2):
            return await execute_v2(ast, provider, limits=limits, policy=policy)
        return await execute(ast, provider, limits, policy=policy)

    @classmethod
    def visit(cls, ast: TraversableNode, op: Visitor | VisitorV1 | VisitorV2) -> None:
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
    async def avisit(
        cls,
        ast: TraversableNode,
        op: Visitor
        | VisitorV1
        | VisitorV2
        | AsyncVisitor
        | AsyncVisitorV1
        | AsyncVisitorV2,
    ) -> None:
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
    def repr(cls, ast: SupportedTree) -> str:
        """
        Returns a string representation of the AST.

        Args:
            ast (TreeNode): The AST to represent.

        Returns:
            str: The string representation of the AST.
        """
        return ast.model_dump_json(indent=2)

    @staticmethod
    async def tool(
        ast: SupportedTree,
        provider: ToolProvider,
        *,
        limits: ExecutionLimits | None = None,
        policy: ExecutionPolicy | None = None,
    ) -> Callable[..., Any]:
        """
        Converts the given AST into a callable function that can be added as a tool.

        Args:
            ast (TreeNode): The AST to convert.
            provider (ToolProvider): The provider used by the compiled tool.
            limits (ExecutionLimits): Optional limits reset for each invocation.

        Returns:
            AnyFunction: The callable function representation of the AST.

        Version 2 compilation exposes literals in named tool-call argument slots
        as overridable keyword-only defaults. Literals passed directly to a user
        function use the corresponding declared parameter name. Other literals
        remain constants, preserving version 2 lexical scope.
        """
        return await compile_tool(ast, provider, limits, policy)
