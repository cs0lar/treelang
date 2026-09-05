"""Typed metadata contracts shared by tool providers and AST execution."""

import json
from collections.abc import Mapping
from copy import deepcopy
from functools import lru_cache
from typing import Any, NotRequired, Required, TypedDict, cast

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from treelang.exceptions import ASTValidationError, ProviderResponseError

type JsonSchema = dict[str, Any]


class ToolProperty(TypedDict, total=False):
    """JSON Schema metadata used for one tool argument."""

    type: str | list[str]
    description: str
    enum: list[Any]
    default: Any
    const: Any
    minimum: int | float
    maximum: int | float
    exclusiveMinimum: int | float
    exclusiveMaximum: int | float
    multipleOf: int | float
    minLength: int
    maxLength: int
    pattern: str
    format: str
    minItems: int
    maxItems: int
    uniqueItems: bool
    items: Any
    minProperties: int
    maxProperties: int
    properties: dict[str, Any]
    required: list[str]
    additionalProperties: bool | dict[str, Any]


class ToolDefinition(TypedDict, total=False):
    """Provider-neutral metadata for one callable tool."""

    name: Required[str]
    properties: Required[dict[str, ToolProperty]]
    description: NotRequired[str | None]
    input_schema: NotRequired[dict[str, Any]]
    effects: NotRequired["ToolEffects"]


class ToolEffects(TypedDict, total=False):
    """Optional behavioral guarantees used by safe transformations."""

    pure: bool
    deterministic: bool
    idempotent: bool


def normalize_tool_definition(
    value: object, *, expected_name: str | None = None
) -> ToolDefinition:
    """Validate and copy mapping-based provider metadata.

    ``expected_name`` preserves compatibility with custom providers that omit the
    redundant name field from a direct lookup result.
    """
    if not isinstance(value, Mapping):
        raise ProviderResponseError("Tool definition must be a mapping")

    raw_name = value.get("name", expected_name)
    if not isinstance(raw_name, str) or not raw_name:
        raise ProviderResponseError("Tool definition has no valid name")
    if expected_name is not None and raw_name != expected_name:
        raise ProviderResponseError(
            f"Provider returned tool '{raw_name}' when '{expected_name}' was requested"
        )

    raw_description = value.get("description")
    if raw_description is not None and not isinstance(raw_description, str):
        raise ProviderResponseError(
            f"Tool '{raw_name}' has no valid description definition"
        )

    raw_effects = value.get("effects")
    effects: ToolEffects | None = None
    if raw_effects is not None:
        if not isinstance(raw_effects, Mapping) or any(
            name not in {"pure", "deterministic", "idempotent"}
            or not isinstance(effect, bool)
            for name, effect in raw_effects.items()
        ):
            raise ProviderResponseError(f"Tool '{raw_name}' has invalid effects")
        effects = cast(ToolEffects, dict(raw_effects))

    raw_input_schema = value.get("input_schema")
    if raw_input_schema is not None:
        if not isinstance(raw_input_schema, Mapping):
            raise ProviderResponseError(
                f"Tool '{raw_name}' has no valid input schema definition"
            )
        input_schema = deepcopy(dict(raw_input_schema))
        raw_properties = input_schema.get("properties", {})
    else:
        input_schema = None
        raw_properties = value.get("properties")
    if not isinstance(raw_properties, Mapping):
        raise ProviderResponseError(
            f"Tool '{raw_name}' has no valid properties definition"
        )

    properties: dict[str, ToolProperty] = {}
    for property_name, raw_property in raw_properties.items():
        if not isinstance(property_name, str) or not property_name:
            raise ProviderResponseError(
                f"Tool '{raw_name}' contains an invalid property name"
            )
        if not isinstance(raw_property, Mapping):
            raise ProviderResponseError(
                f"Tool '{raw_name}' property '{property_name}' must be a mapping"
            )
        property_metadata = dict(raw_property)
        property_type = property_metadata.get("type")
        if property_type is not None and not (
            isinstance(property_type, str)
            or (
                isinstance(property_type, list)
                and all(isinstance(item, str) for item in property_type)
            )
        ):
            raise ProviderResponseError(
                f"Tool '{raw_name}' property '{property_name}' has an invalid type"
            )
        property_description = property_metadata.get("description")
        if property_description is not None and not isinstance(
            property_description, str
        ):
            raise ProviderResponseError(
                f"Tool '{raw_name}' property '{property_name}' has an invalid description"
            )
        property_enum = property_metadata.get("enum")
        if property_enum is not None and not isinstance(property_enum, list):
            raise ProviderResponseError(
                f"Tool '{raw_name}' property '{property_name}' has an invalid enum"
            )
        properties[property_name] = cast(ToolProperty, property_metadata)

    if input_schema is not None:
        input_schema["properties"] = properties
        _validate_input_schema(raw_name, input_schema)
    else:
        _validate_input_schema(
            raw_name,
            {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        )

    definition: ToolDefinition = {"name": raw_name, "properties": properties}
    if "description" in value:
        definition["description"] = raw_description
    if input_schema is not None:
        definition["input_schema"] = input_schema
    if effects is not None:
        definition["effects"] = effects
    return definition


def tool_input_schema(tool: ToolDefinition) -> JsonSchema:
    """Return a complete object schema, preserving legacy provider semantics."""
    if "input_schema" in tool:
        return deepcopy(tool["input_schema"])
    properties = deepcopy(dict(tool["properties"]))
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def render_tool_catalog(tools: list[ToolDefinition]) -> str:
    """Render selected tools as deterministic, lossless compiler vocabulary."""
    catalog = [
        {
            "name": tool["name"],
            "description": tool.get("description"),
            "input_schema": tool_input_schema(tool),
        }
        for tool in tools
    ]
    return (
        "AVAILABLE TREELANG OPERATIONS\n"
        "Use these operations only to construct the requested Treelang AST. "
        "Do not call them during generation.\n"
        f"{json.dumps(catalog, indent=2)}"
    )


def validate_tool_arguments(tool: ToolDefinition, arguments: Mapping[str, Any]) -> None:
    """Validate evaluated arguments without exposing their values in errors."""
    schema = tool_input_schema(tool)
    validator = _validator_for(tool["name"], schema)
    error = next(iter(validator.iter_errors(dict(arguments))), None)
    if error is None:
        return
    path_parts = [str(part) for part in error.absolute_path]
    path = ".".join(path_parts) if path_parts else "<root>"
    keyword = str(error.validator or "schema")
    raise ASTValidationError(
        f"Tool '{tool['name']}' input at '{path}' violates the '{keyword}' constraint"
    )


def _validate_input_schema(name: str, schema: JsonSchema) -> None:
    if schema.get("type") not in (None, "object"):
        raise ProviderResponseError(
            f"Tool '{name}' input schema must describe an object"
        )
    _reject_external_references(name, schema)
    try:
        _validator_for(name, schema)
    except SchemaError as error:
        keyword = str(error.validator or "schema")
        raise ProviderResponseError(
            f"Tool '{name}' has an invalid input schema ({keyword})"
        ) from error


def _validator_for(name: str, schema: JsonSchema) -> Draft202012Validator:
    try:
        canonical = json.dumps(
            schema,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise ProviderResponseError(
            f"Tool '{name}' input schema must be JSON serializable"
        ) from error
    return _cached_validator(canonical)


@lru_cache(maxsize=256)
def _cached_validator(canonical: str) -> Draft202012Validator:
    schema = json.loads(canonical)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _reject_external_references(name: str, value: Any) -> None:
    if isinstance(value, Mapping):
        reference = value.get("$ref")
        if isinstance(reference, str) and not reference.startswith("#/"):
            raise ProviderResponseError(
                f"Tool '{name}' input schema contains an external reference"
            )
        for child in value.values():
            _reject_external_references(name, child)
    elif isinstance(value, list):
        for child in value:
            _reject_external_references(name, child)
