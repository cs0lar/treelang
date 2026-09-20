"""Strict structured-output request construction for Treelang schemas."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal, Mapping, Sequence

from treelang.ai.tool import ToolDefinition, tool_input_schema
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
    input_schema = tool_input_schema(tool)
    argument_properties = {
        name: _tool_argument_expression(parameter, input_schema)
        for name, parameter in tool["properties"].items()
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


def _tool_argument_expression(
    parameter: Mapping[str, Any], input_schema: Mapping[str, Any]
) -> dict[str, Any]:
    expression = {"$ref": "#/$defs/Expression"}
    if not _accepts_object(parameter, input_schema):
        return expression
    projected = _project_tool_schema(parameter, input_schema)
    if projected is None:
        return expression
    return {
        "anyOf": [
            expression,
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {"type": "string", "const": "literal"},
                    "value": projected,
                },
                "required": ["type", "value"],
            },
        ]
    }


def _project_tool_schema(
    schema: Mapping[str, Any],
    root: Mapping[str, Any],
    references: frozenset[str] = frozenset(),
) -> dict[str, Any] | None:
    reference = schema.get("$ref")
    if isinstance(reference, str):
        if reference in references:
            return None
        resolved = _resolve_local_reference(root, reference)
        if resolved is None:
            return None
        return _project_tool_schema(resolved, root, references | {reference})

    alternatives = schema.get("anyOf", schema.get("oneOf"))
    if isinstance(alternatives, list):
        projected_alternatives = [
            _project_tool_schema(alternative, root, references)
            if isinstance(alternative, Mapping)
            else None
            for alternative in alternatives
        ]
        if any(alternative is None for alternative in projected_alternatives):
            return None
        result: dict[str, Any] = {"anyOf": projected_alternatives}
        if isinstance(schema.get("description"), str):
            result["description"] = schema["description"]
        return result

    if "allOf" in schema:
        return None

    parameter_type = schema.get("type")
    if isinstance(parameter_type, list):
        projected_alternatives = [
            _project_tool_schema({**schema, "type": item}, root, references)
            for item in parameter_type
        ]
        if any(alternative is None for alternative in projected_alternatives):
            return None
        return {"anyOf": projected_alternatives}

    if parameter_type == "object" or "properties" in schema:
        properties = schema.get("properties")
        if not isinstance(properties, Mapping):
            return None
        if not properties and schema.get("additionalProperties") is not False:
            return None
        projected_properties: dict[str, Any] = {}
        for name, value in properties.items():
            if not isinstance(name, str) or not isinstance(value, Mapping):
                return None
            projected_property = _project_tool_schema(value, root, references)
            if projected_property is None:
                return None
            projected_properties[name] = projected_property
        result = {
            "type": "object",
            "properties": projected_properties,
            "required": list(projected_properties),
            "additionalProperties": False,
        }
        if isinstance(schema.get("description"), str):
            result["description"] = schema["description"]
        return result

    if parameter_type == "array":
        items = schema.get("items")
        if not isinstance(items, Mapping):
            return None
        projected_items = _project_tool_schema(items, root, references)
        if projected_items is None:
            return None
        result = deepcopy(dict(schema))
        result["items"] = projected_items
        return result

    if isinstance(parameter_type, str) and parameter_type in {
        "string",
        "integer",
        "number",
        "boolean",
        "null",
    }:
        return deepcopy(dict(schema))

    if parameter_type is not None:
        return None

    const = schema.get("const")
    enum = schema.get("enum")
    if "const" in schema:
        scalar_type = _json_scalar_type(const)
        if scalar_type is None:
            return None
        result = {"type": scalar_type, "const": const}
    elif isinstance(enum, list):
        alternatives = []
        for item in enum:
            scalar_type = _json_scalar_type(item)
            if scalar_type is None:
                return None
            alternatives.append({"type": scalar_type, "const": item})
        result = {"anyOf": alternatives}
    else:
        result = {
            "anyOf": [
                {"type": scalar_type}
                for scalar_type in ("string", "integer", "number", "boolean")
            ]
        }
    if isinstance(schema.get("description"), str):
        result["description"] = schema["description"]
    return result


def _json_scalar_type(value: Any) -> str | None:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return None


def _resolve_local_reference(
    root: Mapping[str, Any], reference: str
) -> Mapping[str, Any] | None:
    if not reference.startswith("#/"):
        return None
    value: Any = root
    for token in reference[2:].split("/"):
        if not isinstance(value, Mapping):
            return None
        value = value.get(token.replace("~1", "/").replace("~0", "~"))
    return value if isinstance(value, Mapping) else None


def strict_ast_schema_supported(
    tools: Sequence[ToolDefinition], *, schema_version: SchemaVersion = "1.0"
) -> bool:
    """Whether the strict projection can express what these tools accept.

    Strict JSON Schema has no way to describe a free-form object, so the
    projection drops that alternative from ``JsonValue`` -- and a tool with an
    object-typed parameter then has no way to be given a value at all. The
    model satisfies the schema, the tree parses, and the walk rejects it on a
    type constraint, which is the one failure the provider cannot report and
    the caller cannot retry.

    Schema v2 can specialize described object literals for the named argument
    that receives them. Schema v1 cannot associate its positional arguments
    with tool parameters, and both versions still decline free-form or
    recursively referenced object shapes that cannot be projected safely.
    """
    for tool in tools:
        input_schema = tool_input_schema(tool)
        for parameter in tool.get("properties", {}).values():
            if not _accepts_object(parameter, input_schema):
                continue
            if schema_version == "1.0":
                return False
            if _project_tool_schema(parameter, input_schema) is None:
                return False
    return True


def _accepts_object(
    parameter: Any,
    root: Mapping[str, Any],
    references: frozenset[str] = frozenset(),
) -> bool:
    if not isinstance(parameter, Mapping):
        return False
    reference = parameter.get("$ref")
    if isinstance(reference, str):
        if reference in references:
            return True
        resolved = _resolve_local_reference(root, reference)
        return resolved is None or _accepts_object(
            resolved, root, references | {reference}
        )
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
    items = parameter.get("items")
    if isinstance(items, Mapping):
        nested.append(items)
    return any(_accepts_object(alternative, root, references) for alternative in nested)


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
