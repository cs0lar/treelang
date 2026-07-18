"""Typed metadata contracts shared by tool providers and AST execution."""

from collections.abc import Mapping
from typing import Any, NotRequired, Required, TypedDict, cast

from treelang.exceptions import ProviderResponseError


class ToolProperty(TypedDict, total=False):
    """JSON Schema metadata used for one tool argument."""

    type: str
    description: str
    enum: list[Any]
    default: Any


class ToolDefinition(TypedDict, total=False):
    """Provider-neutral metadata for one callable tool."""

    name: Required[str]
    properties: Required[dict[str, ToolProperty]]
    description: NotRequired[str | None]


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
        if property_type is not None and not isinstance(property_type, str):
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

    definition: ToolDefinition = {"name": raw_name, "properties": properties}
    if "description" in value:
        definition["description"] = raw_description
    return definition
