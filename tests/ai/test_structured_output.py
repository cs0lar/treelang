from collections.abc import Mapping
from typing import Any

import pytest

from treelang.ai.structured_output import strict_ast_schema, strict_response_format

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
