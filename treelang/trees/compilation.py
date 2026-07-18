"""Compile version 1 AST programs into async Python callables."""

from collections.abc import Awaitable, Callable
from inspect import Parameter, Signature
from typing import Any

from treelang.ai.provider import ToolProvider
from treelang.exceptions import ASTCompilationError, ASTExecutionError
from treelang.trees.execution import ExecutionContext
from treelang.trees.schemas.v1 import (
    TreeFunction,
    TreeLambda,
    TreeMap,
    TreeNode,
    TreeProgram,
    TreeValue,
)
from treelang.trees.traversal import avisit

CompiledTool = Callable[..., Awaitable[Any]]

JSON_TYPE_ANNOTATIONS: dict[str, object] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


async def compile_tool(ast: TreeNode, provider: ToolProvider) -> CompiledTool:
    """Compile a program AST into a keyword-only async callable."""
    if not isinstance(ast, TreeProgram):
        raise ValueError("AST root must be a TreeProgram")
    if not ast.name:
        raise ValueError("AST program must have a name")
    if not ast.description:
        raise ValueError("AST program must have a description")

    program_name = ast.name
    program_description = ast.description
    parameters: list[Parameter] = []
    bindings: list[tuple[str, TreeValue]] = []
    property_stack: list[dict[str, Any]] = []
    argument_names: list[str] = []

    async def collect_parameter(node: TreeNode) -> None:
        if isinstance(node, (TreeLambda, TreeMap)):
            raise ValueError(
                "Higher order functions (lambdas, maps) are not yet supported "
                "in tool creation"
            )

        if isinstance(node, TreeFunction):
            definition = await provider.get_tool_definition(node.name)
            properties = definition["properties"]
            property_stack.append(properties)

        if not isinstance(node, TreeValue):
            return

        if node.name not in property_stack[-1]:
            property_stack.pop()

        properties = property_stack[-1]
        parameter_name = _unique_name(node.name, argument_names)
        argument_names.append(parameter_name)
        bindings.append((parameter_name, node))
        try:
            parameter = Parameter(
                parameter_name,
                Parameter.KEYWORD_ONLY,
                annotation=JSON_TYPE_ANNOTATIONS.get(
                    properties[node.name].get("type"), Any
                ),
            )
        except ValueError as error:
            raise ASTCompilationError(
                f"Invalid function signature for {program_name}"
            ) from error
        parameters.append(parameter)

    await avisit(ast, collect_parameter)

    try:
        signature = Signature(parameters=parameters)
    except ValueError as error:
        raise ASTCompilationError(
            f"Invalid function signature for {program_name}"
        ) from error

    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            bound_args = signature.bind(*args, **kwargs)
            bound_args.apply_defaults()
        except TypeError as error:
            raise TypeError(
                f"Argument binding failed for {program_name}(): {error}"
            ) from error

        try:
            context = ExecutionContext().bind_nodes(
                {
                    id(node): bound_args.arguments[parameter_name]
                    for parameter_name, node in bindings
                }
            )
            return await ast.eval(provider, context)
        except Exception as error:
            raise ASTExecutionError(
                f"Error executing {program_name}(): {error}"
            ) from error

    wrapper.__name__ = program_name
    wrapper.__doc__ = program_description
    setattr(wrapper, "__signature__", signature)
    return wrapper


def _unique_name(name: str, existing_names: list[str]) -> str:
    candidate = name
    suffix = 2
    while candidate in existing_names:
        candidate = f"{name}_{suffix}"
        suffix += 1
    return candidate
