from collections.abc import Mapping
from typing import Any

import pytest

from treelang.ai.structured_output import (
    strict_ast_schema,
    strict_ast_schema_supported,
    strict_response_format,
)

TOOLS = [
    {
        "name": "identity",
        "description": "Return a value",
        "properties": {"value": {"type": "integer"}},
    },
    {
        "name": "constant",
        "description": "Return a constant",
        "properties": {},
    },
]


def objects(value: Any):
    if isinstance(value, Mapping):
        if value.get("type") == "object" or "properties" in value:
            yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)


@pytest.mark.parametrize("version", ["1.0", "2.0"])
def test_strict_schema_uses_supported_closed_object_shapes(version):
    schema = strict_ast_schema(version, TOOLS)
    serialized = str(schema)

    assert "discriminator" not in serialized
    assert "default" not in serialized
    assert "patternProperties" not in serialized
    assert "propertyNames" not in serialized
    assert "oneOf" not in serialized
    for value in objects(schema):
        properties = value.get("properties", {})
        assert value["additionalProperties"] is False
        assert value["required"] == list(properties)


def test_strict_schema_removes_free_form_json_objects():
    schema = strict_ast_schema("1.0", TOOLS)
    json_value = schema["$defs"]["JsonValue"]

    assert all(option.get("type") != "object" for option in json_value["anyOf"])


def test_v2_strict_schema_specializes_external_tool_calls():
    schema = strict_ast_schema("2.0", TOOLS)
    variants = schema["$defs"]["TreeToolCall"]["anyOf"]

    assert [variant["properties"]["tool"]["const"] for variant in variants] == [
        "identity",
        "constant",
    ]
    identity_arguments = variants[0]["properties"]["arguments"]
    assert identity_arguments["required"] == ["value"]
    assert identity_arguments["additionalProperties"] is False
    assert variants[1]["properties"]["arguments"]["required"] == []


def test_v2_strict_schema_disallows_tool_calls_when_no_tools_are_selected():
    schema = strict_ast_schema("2.0", [])
    alternatives = schema["$defs"]["Expression"]["anyOf"]

    assert "TreeToolCall" not in schema["$defs"]
    assert all(item.get("$ref") != "#/$defs/TreeToolCall" for item in alternatives)


def test_response_format_uses_named_strict_json_schema():
    response_format = strict_response_format("2.0", TOOLS)

    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "treelang_ast_v2"
    assert response_format["json_schema"]["strict"] is True


OBJECT_TOOLS = [
    {
        "name": "commit",
        "description": "Record a typed literal",
        "properties": {
            "object": {
                "type": "object",
                "description": "A typed literal.",
                "properties": {
                    "kind": {"type": "string", "enum": ["text", "int64"]},
                    "value": {"description": "Interpreted according to kind."},
                },
                "required": ["kind", "value"],
            }
        },
    }
]


@pytest.mark.parametrize("version", ["1.0", "2.0"])
def test_a_ref_is_left_standing_alone_because_a_sibling_voids_the_schema(version):
    """The provider rejects the whole document for one stray keyword.

    Pydantic emits the root as `{"$ref": ..., "$defs": ..., "description": ...}`
    and OpenAI answers `$ref cannot have keywords {'description'}`, so every
    strict request was refused and silently retried in compatibility mode.
    """
    schema = strict_ast_schema(version, TOOLS)

    def refs(value: Any):
        if isinstance(value, Mapping):
            if "$ref" in value:
                yield value
            for child in value.values():
                yield from refs(child)
        elif isinstance(value, list):
            for child in value:
                yield from refs(child)

    for reference in refs(schema):
        assert set(reference) <= {"$ref", "$defs"}, reference
    # `$defs` has to survive at the root, or every reference is stranded.
    assert "$defs" in schema


def test_tools_taking_an_object_cannot_be_expressed_in_the_strict_subset():
    """The check that stops a schema the model satisfies and the walk rejects.

    `JsonValue` loses its object alternative in the projection, so a tool with
    an object-typed parameter can never be given a value -- and that failure
    surfaces at walk time, which no retry and no provider error can reach.
    """
    assert strict_ast_schema_supported(TOOLS)
    assert not strict_ast_schema_supported(OBJECT_TOOLS)
    # Reached through a union too: an optional object is still an object.
    assert not strict_ast_schema_supported(
        [
            {
                "name": "t",
                "properties": {"x": {"anyOf": [{"type": "null"}, {"type": "object"}]}},
            }
        ]
    )
    # Reached through a type union too: ToolProperty permits JSON Schema's
    # array form, and a nullable object remains object-capable.
    assert not strict_ast_schema_supported(
        [
            {
                "name": "t",
                "properties": {"x": {"type": ["object", "null"]}},
            }
        ]
    )
