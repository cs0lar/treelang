"""Strict structured-output request construction for Treelang schemas."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal, Mapping, Sequence

from treelang.ai.tool import ToolDefinition
from treelang.trees.schemas.v1 import AST as ASTV1
from treelang.trees.schemas.v2 import AST as ASTV2

type SchemaVersion = Literal["1.0", "2.0"]

_UNSUPPORTED_KEYWORDS = {
    "default",
    "discriminator",
    "patternProperties",
    "propertyNames",
    "title",
}


def strict_ast_schema(
    schema_version: SchemaVersion,
    tools: Sequence[ToolDefinition],
) -> dict[str, Any]:
    """Project the runtime schema into the provider's strict JSON Schema subset."""
    source = (
        ASTV2.model_json_schema()
        if schema_version == "2.0"
        else ASTV1.model_json_schema()
    )
    schema = deepcopy(source)
    _remove_free_form_json_objects(schema)
    if schema_version == "2.0":
        _specialize_v2_tool_calls(schema, tools)
    return _strictify(schema)


def strict_response_format(
    schema_version: SchemaVersion,
    tools: Sequence[ToolDefinition],
) -> dict[str, Any]:
    """Build a Chat Completions strict structured-output response format."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": f"treelang_ast_v{schema_version[0]}",
            "strict": True,
            "schema": strict_ast_schema(schema_version, tools),
        },
    }


def _remove_free_form_json_objects(schema: dict[str, Any]) -> None:
    json_value = schema.get("$defs", {}).get("JsonValue")
    if not isinstance(json_value, dict):
        return
    alternatives = json_value.get("anyOf")
    if not isinstance(alternatives, list):
        return
    json_value["anyOf"] = [
        alternative
        for alternative in alternatives
        if not (
            isinstance(alternative, dict)
            and alternative.get("type") == "object"
            and isinstance(alternative.get("additionalProperties"), dict)
        )
    ]


def _specialize_v2_tool_calls(
    schema: dict[str, Any], tools: Sequence[ToolDefinition]
) -> None:
    definitions = schema.get("$defs", {})
    expression = definitions.get("Expression")
    if not isinstance(expression, dict):
        return

    tool_reference = "#/$defs/TreeToolCall"
    alternatives = expression.get("oneOf", [])
    if not tools:
        expression["oneOf"] = [
            alternative
            for alternative in alternatives
            if not (
                isinstance(alternative, dict)
                and alternative.get("$ref") == tool_reference
            )
        ]
        definitions.pop("TreeToolCall", None)
        return

    variants = [_tool_call_variant(tool) for tool in tools]
    definitions["TreeToolCall"] = {"anyOf": variants}


def _tool_call_variant(tool: ToolDefinition) -> dict[str, Any]:
    argument_names = list(tool["properties"])
    argument_properties = {
        name: {"$ref": "#/$defs/Expression"} for name in argument_names
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "type": {"type": "string", "const": "tool_call"},
            "tool": {"type": "string", "const": tool["name"]},
            "arguments": {
                "type": "object",
                "additionalProperties": False,
                "properties": argument_properties,
                "required": argument_names,
            },
        },
        "required": ["type", "tool", "arguments"],
    }


def strict_ast_schema_supported(tools: Sequence[ToolDefinition]) -> bool:
    """Whether the strict projection can express what these tools accept.

    Strict JSON Schema has no way to describe a free-form object, so the
    projection drops that alternative from ``JsonValue`` -- and a tool with an
    object-typed parameter then has no way to be given a value at all. The
    model satisfies the schema, the tree parses, and the walk rejects it on a
    type constraint, which is the one failure the provider cannot report and
    the caller cannot retry.

    Declining strict for the whole request is the honest answer until the
    projection learns to build closed object shapes out of the tool schemas
    themselves, the way ``_specialize_v2_tool_calls`` already does for tool
    calls.
    """
    return not any(
        _accepts_object(parameter)
        for tool in tools
        for parameter in tool.get("properties", {}).values()
    )


def _accepts_object(parameter: Any) -> bool:
    if not isinstance(parameter, Mapping):
        return False
    parameter_type = parameter.get("type")
    if (
        parameter_type == "object"
        or (isinstance(parameter_type, list) and "object" in parameter_type)
        or "properties" in parameter
    ):
        return True
    nested = [
        *parameter.get("anyOf", []),
        *parameter.get("oneOf", []),
        *parameter.get("allOf", []),
    ]
    return any(_accepts_object(alternative) for alternative in nested)


def _strictify(value: Any) -> Any:
    if isinstance(value, list):
        return [_strictify(item) for item in value]
    if not isinstance(value, dict):
        return value

    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in _UNSUPPORTED_KEYWORDS:
            continue
        normalized_key = "anyOf" if key == "oneOf" else key
        result[normalized_key] = _strictify(item)

    # A `$ref` must stand alone: the provider rejects the whole schema for a
    # sibling keyword, and the root carries `description` straight off the
    # pydantic model. `$defs` is the one companion that has to survive, since
    # dropping it would strand every reference in the document.
    if "$ref" in result:
        return {key: item for key, item in result.items() if key in ("$ref", "$defs")}

    properties = result.get("properties")
    if isinstance(properties, Mapping):
        result["required"] = list(properties)
        result["additionalProperties"] = False
    return result


__all__ = [
    "strict_ast_schema",
    "strict_ast_schema_supported",
    "strict_response_format",
]
