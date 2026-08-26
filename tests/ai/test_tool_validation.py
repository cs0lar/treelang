import json

import pytest

from treelang.ai.tool import (
    normalize_tool_definition,
    render_tool_catalog,
    tool_input_schema,
    validate_tool_arguments,
)
from treelang.exceptions import ASTValidationError, ProviderResponseError


def constrained_tool():
    return normalize_tool_definition(
        {
            "name": "submit",
            "input_schema": {
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 3,
                    },
                    "kind": {"type": "string", "enum": ["a", "b"]},
                    "code": {
                        "type": "string",
                        "minLength": 3,
                        "maxLength": 5,
                        "pattern": "^[A-Z]+$",
                    },
                    "tags": {
                        "type": "array",
                        "minItems": 1,
                        "uniqueItems": True,
                        "items": {"type": "string"},
                    },
                    "profile": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string", "format": "email"},
                            "score": {"type": "number", "exclusiveMinimum": 0},
                        },
                        "required": ["email", "score"],
                        "additionalProperties": False,
                    },
                    "note": {
                        "type": "string",
                        "default": "not injected",
                    },
                },
                "required": ["count", "kind", "code", "tags", "profile"],
                "additionalProperties": False,
            },
        }
    )


def valid_arguments():
    return {
        "count": 2,
        "kind": "a",
        "code": "ABC",
        "tags": ["one"],
        "profile": {"email": "person@example.com", "score": 1.5},
    }


def test_tool_catalog_is_deterministic_and_preserves_complete_schema():
    tool = constrained_tool()

    rendered = render_tool_catalog([tool])
    payload = json.loads(rendered[rendered.index("[") :])

    assert rendered.startswith("AVAILABLE TREELANG OPERATIONS")
    assert payload == [
        {
            "name": "submit",
            "description": None,
            "input_schema": tool_input_schema(tool),
        }
    ]
    assert payload[0]["input_schema"]["additionalProperties"] is False
    assert payload[0]["input_schema"]["required"] == [
        "count",
        "kind",
        "code",
        "tags",
        "profile",
    ]


def test_complete_schema_accepts_valid_nested_arguments_and_optional_omission():
    tool = constrained_tool()

    validate_tool_arguments(tool, valid_arguments())

    assert "note" not in valid_arguments()
    assert tool_input_schema(tool)["required"] == [
        "count",
        "kind",
        "code",
        "tags",
        "profile",
    ]


def test_nullable_union_type_metadata_is_preserved_and_validated():
    tool = normalize_tool_definition(
        {
            "name": "nullable",
            "input_schema": {
                "type": "object",
                "properties": {"value": {"type": ["string", "null"]}},
                "required": ["value"],
                "additionalProperties": False,
            },
        }
    )

    validate_tool_arguments(tool, {"value": None})
    validate_tool_arguments(tool, {"value": "text"})
    with pytest.raises(ASTValidationError, match="'type'"):
        validate_tool_arguments(tool, {"value": 1})


def test_local_schema_references_are_supported_without_remote_resolution():
    tool = normalize_tool_definition(
        {
            "name": "local_ref",
            "input_schema": {
                "type": "object",
                "$defs": {
                    "positive": {"type": "integer", "minimum": 1},
                },
                "properties": {"value": {"$ref": "#/$defs/positive"}},
                "required": ["value"],
                "additionalProperties": False,
            },
        }
    )

    validate_tool_arguments(tool, {"value": 1})
    with pytest.raises(ASTValidationError, match="'minimum'"):
        validate_tool_arguments(tool, {"value": 0})


@pytest.mark.parametrize(
    ("mutate", "path", "constraint"),
    [
        (lambda value: value.pop("count"), "<root>", "required"),
        (lambda value: value.update(count=True), "count", "type"),
        (lambda value: value.update(count=0), "count", "minimum"),
        (lambda value: value.update(count=4), "count", "maximum"),
        (lambda value: value.update(kind="c"), "kind", "enum"),
        (lambda value: value.update(code="A"), "code", "minLength"),
        (lambda value: value.update(code="ABCDEF"), "code", "maxLength"),
        (lambda value: value.update(code="abc"), "code", "pattern"),
        (lambda value: value.update(tags=[]), "tags", "minItems"),
        (lambda value: value.update(tags=["x", "x"]), "tags", "uniqueItems"),
        (lambda value: value.update(tags=[1]), "tags.0", "type"),
        (
            lambda value: value["profile"].update(email="not-an-email"),
            "profile.email",
            "format",
        ),
        (
            lambda value: value["profile"].update(score=0),
            "profile.score",
            "exclusiveMinimum",
        ),
        (
            lambda value: value["profile"].update(unexpected=True),
            "profile",
            "additionalProperties",
        ),
        (
            lambda value: value.update(unexpected=True),
            "<root>",
            "additionalProperties",
        ),
    ],
)
def test_complete_schema_rejects_types_and_constraints(mutate, path, constraint):
    tool = constrained_tool()
    arguments = valid_arguments()
    mutate(arguments)

    with pytest.raises(ASTValidationError) as captured:
        validate_tool_arguments(tool, arguments)

    message = str(captured.value)
    assert "submit" in message
    assert f"'{path}'" in message
    assert f"'{constraint}'" in message


def test_validation_error_never_contains_argument_value():
    tool = constrained_tool()
    arguments = valid_arguments()
    arguments["code"] = "private-value"

    with pytest.raises(ASTValidationError) as captured:
        validate_tool_arguments(tool, arguments)

    assert "private-value" not in str(captured.value)


def test_legacy_metadata_requires_every_property_and_rejects_unknown_fields():
    tool = normalize_tool_definition(
        {"name": "legacy", "properties": {"value": {"type": "integer"}}}
    )

    assert tool_input_schema(tool) == {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
        "additionalProperties": False,
    }
    with pytest.raises(ASTValidationError, match="required"):
        validate_tool_arguments(tool, {})


@pytest.mark.parametrize(
    ("schema", "message"),
    [
        ({"type": "array"}, "must describe an object"),
        (
            {
                "type": "object",
                "properties": {},
                "required": "value",
            },
            "invalid input schema",
        ),
        (
            {
                "type": "object",
                "properties": {"value": {"$ref": "https://example.com/schema"}},
            },
            "external reference",
        ),
    ],
)
def test_normalization_rejects_malformed_or_external_schemas(schema, message):
    with pytest.raises(ProviderResponseError, match=message):
        normalize_tool_definition({"name": "bad", "input_schema": schema})
