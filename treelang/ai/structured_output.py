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

    properties = result.get("properties")
    if isinstance(properties, Mapping):
        result["required"] = list(properties)
        result["additionalProperties"] = False
    return result


__all__ = ["strict_ast_schema", "strict_response_format"]
