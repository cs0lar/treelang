"""Compile supported AST programs into async Python callables."""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from inspect import Parameter, Signature
from typing import Any

from treelang.ai.provider import ToolProvider
from treelang.ai.tool import normalize_tool_definition
from treelang.exceptions import (
    ASTCompilationError,
    ASTExecutionError,
    ExecutionLimitError,
)
from treelang.trees.budget import ExecutionLimits
from treelang.trees.execution import ExecutionContext, execute
from treelang.trees.execution_v2 import execute_v2
from treelang.trees.policy import ExecutionPolicy
from treelang.trees.schemas.v1 import (
    TreeFunction,
    TreeLambda,
    TreeMap,
    TreeNode,
    TreeProgram,
    TreeValue,
)
from treelang.trees.schemas.v2 import (
    Expression,
    TreeCall,
    TreeLiteral,
    TreeMemo,
    TreeToolCall,
)
from treelang.trees.schemas.v2 import (
    TreeConditional as TreeConditionalV2,
)
from treelang.trees.schemas.v2 import (
    TreeProgram as TreeProgramV2,
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


async def compile_tool(
    ast: TreeNode | TreeProgramV2,
    provider: ToolProvider,
    limits: ExecutionLimits | None = None,
    policy: ExecutionPolicy | None = None,
) -> CompiledTool:
    """Compile a supported program AST into a keyword-only async callable."""
    if isinstance(ast, TreeProgramV2):
        return await _compile_v2_tool(ast, provider, limits, policy)
    return await _compile_v1_tool(ast, provider, limits, policy)


async def _compile_v1_tool(
    ast: TreeNode,
    provider: ToolProvider,
    limits: ExecutionLimits | None,
    policy: ExecutionPolicy | None,
) -> CompiledTool:
    """Compile a version 1 program using its legacy value-node convention."""
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
    default_templates: dict[str, Any] = {}
    property_stack: list[dict[str, Any]] = []
    argument_names: list[str] = []

    async def collect_parameter(node: TreeNode) -> None:
        if isinstance(node, (TreeLambda, TreeMap)):
            raise ValueError(
                "Higher order functions (lambdas, maps) are not yet supported "
                "in tool creation"
            )

        if isinstance(node, TreeFunction):
            definition = normalize_tool_definition(
                await provider.get_tool_definition(node.name), expected_name=node.name
            )
            properties = definition["properties"]
            property_stack.append(properties)

        if not isinstance(node, TreeValue):
            return

        if node.name not in property_stack[-1]:
            property_stack.pop()

        properties = property_stack[-1]
        parameter_name = _unique_name(node.name, argument_names)
        property_type = properties[node.name].get("type")
        argument_names.append(parameter_name)
        bindings.append((parameter_name, node))
        annotation = (
            JSON_TYPE_ANNOTATIONS.get(property_type, Any)
            if isinstance(property_type, str)
            else Any
        )
        parameter_kwargs: dict[str, Any] = {
            "name": parameter_name,
            "kind": Parameter.KEYWORD_ONLY,
            "annotation": annotation,
        }
        if node.value is not None:
            snapshot = deepcopy(node.value)
            default_templates[parameter_name] = snapshot
            parameter_kwargs["default"] = deepcopy(snapshot)
        try:
            parameter = Parameter(**parameter_kwargs)
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
            for parameter_name, template in default_templates.items():
                if parameter_name not in kwargs:
                    bound_args.arguments[parameter_name] = deepcopy(template)
        except TypeError as error:
            raise TypeError(
                f"Argument binding failed for {program_name}(): {error}"
            ) from error

        try:
            context = ExecutionContext.with_limits(limits, policy).bind_nodes(
                {
                    id(node): bound_args.arguments[parameter_name]
                    for parameter_name, node in bindings
                }
            )
            return await execute(ast, provider, context=context)
        except ExecutionLimitError:
            raise
        except Exception as error:
            raise ASTExecutionError(
                f"Error executing {program_name}(): {error}"
            ) from error

    wrapper.__name__ = program_name
    wrapper.__doc__ = program_description
    setattr(wrapper, "__signature__", signature)
    return wrapper


async def _compile_v2_tool(
    ast: TreeProgramV2,
    provider: ToolProvider,
    limits: ExecutionLimits | None,
    policy: ExecutionPolicy | None,
) -> CompiledTool:
    """Compile named v2 argument literals as overridable callable defaults."""
    if not ast.name:
        raise ValueError("AST program must have a name")
    if not ast.description:
        raise ValueError("AST program must have a description")

    program_name = ast.name
    parameters: list[Parameter] = []
    bindings: list[tuple[str, TreeLiteral]] = []
    default_templates: dict[str, Any] = {}
    argument_names: list[str] = []
    collected_literals: set[int] = set()
    definitions = {definition.name: definition for definition in ast.definitions}
    tool_properties: dict[str, dict[str, Any]] = {}

    async def properties_for(tool_name: str) -> dict[str, Any]:
        properties = tool_properties.get(tool_name)
        if properties is None:
            definition = normalize_tool_definition(
                await provider.get_tool_definition(tool_name),
                expected_name=tool_name,
            )
            properties = definition["properties"]
            tool_properties[tool_name] = properties
        return properties

    def add_parameter(
        name: str, literal: TreeLiteral, property_metadata: dict[str, Any] | None
    ) -> None:
        if id(literal) in collected_literals:
            return
        collected_literals.add(id(literal))
        parameter_name = _unique_name(name, argument_names)
        property_type = (
            property_metadata.get("type") if property_metadata is not None else None
        )
        annotation = (
            JSON_TYPE_ANNOTATIONS.get(property_type, Any)
            if isinstance(property_type, str)
            else Any
        )
        snapshot = deepcopy(literal.value)
        try:
            parameter = Parameter(
                name=parameter_name,
                kind=Parameter.KEYWORD_ONLY,
                default=deepcopy(snapshot),
                annotation=annotation,
            )
        except ValueError as error:
            raise ASTCompilationError(
                f"Invalid function signature for {program_name}"
            ) from error
        argument_names.append(parameter_name)
        parameters.append(parameter)
        bindings.append((parameter_name, literal))
        default_templates[parameter_name] = snapshot

    async def collect_expression(
        expression: Expression,
        *,
        slot_name: str | None = None,
        property_metadata: dict[str, Any] | None = None,
    ) -> None:
        if isinstance(expression, TreeLiteral):
            if slot_name is not None:
                add_parameter(slot_name, expression, property_metadata)
            return
        if isinstance(expression, TreeToolCall):
            properties = await properties_for(expression.tool)
            for name, argument in expression.arguments.items():
                await collect_expression(
                    argument,
                    slot_name=name,
                    property_metadata=properties.get(name),
                )
            return
        if isinstance(expression, TreeCall):
            definition = definitions[expression.function]
            for name, argument in zip(
                definition.params, expression.arguments, strict=True
            ):
                await collect_expression(argument, slot_name=name)
            return
        if isinstance(expression, TreeConditionalV2):
            await collect_expression(expression.condition)
            await collect_expression(expression.true_branch)
            await collect_expression(expression.false_branch)
            return
        if isinstance(expression, TreeMemo):
            await collect_expression(expression.expression)

    # Root call inputs are the primary public inputs, so collect them before
    # implementation literals inside function definitions.
    for expression in ast.body:
        await collect_expression(expression)
    for definition in ast.definitions:
        await collect_expression(definition.body)

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
            for parameter_name, template in default_templates.items():
                if parameter_name not in kwargs:
                    bound_args.arguments[parameter_name] = deepcopy(template)
        except TypeError as error:
            raise TypeError(
                f"Argument binding failed for {program_name}(): {error}"
            ) from error

        try:
            literal_bindings = {
                id(literal): bound_args.arguments[parameter_name]
                for parameter_name, literal in bindings
            }
            return await execute_v2(
                ast,
                provider,
                limits=limits,
                policy=policy,
                literal_bindings=literal_bindings,
            )
        except ExecutionLimitError:
            raise
        except Exception as error:
            raise ASTExecutionError(
                f"Error executing {program_name}(): {error}"
            ) from error

    wrapper.__name__ = program_name
    wrapper.__doc__ = ast.description
    setattr(wrapper, "__signature__", signature)
    return wrapper


def _unique_name(name: str, existing_names: list[str]) -> str:
    candidate = name
    suffix = 2
    while candidate in existing_names:
        candidate = f"{name}_{suffix}"
        suffix += 1
    return candidate
