import pytest

from treelang.ai.capabilities import (
    DefaultModelCapabilityNegotiator,
    ModelCapabilities,
    StructuredOutputSelection,
    capabilities_for,
)
from treelang.exceptions import StructuredOutputUnsupportedError

TOOLS = [
    {
        "name": "identity",
        "description": "Return a value",
        "properties": {"value": {"type": "integer"}},
    }
]


class CapableTransport:
    def capabilities(self, model):
        assert model == "model"
        return ModelCapabilities(strict_json_schema=True, temperature=True)


def test_capability_discovery_is_transport_owned_and_conservative():
    assert capabilities_for(CapableTransport(), "model") == ModelCapabilities(
        strict_json_schema=True,
        temperature=True,
    )
    assert capabilities_for(object(), "model") == ModelCapabilities()


@pytest.mark.parametrize("schema_version", ["1.0", "2.0"])
def test_negotiator_selects_strict_output_from_declared_capability(schema_version):
    selection = DefaultModelCapabilityNegotiator().structured_output(
        ModelCapabilities(strict_json_schema=True),
        model="model",
        configured_mode="auto",
        schema_version=schema_version,
        tools=TOOLS,
    )

    assert selection.mode == "strict"
    assert selection.fallback_reason is None
    assert selection.response_format["type"] == "json_schema"
    assert selection.response_format["json_schema"]["name"] == (
        f"treelang_ast_v{schema_version[0]}"
    )


def test_negotiator_selects_compatibility_or_rejects_required_mode():
    negotiator = DefaultModelCapabilityNegotiator()

    selection = negotiator.structured_output(
        ModelCapabilities(),
        model="model",
        configured_mode="auto",
        schema_version="1.0",
        tools=TOOLS,
    )
    assert selection == StructuredOutputSelection(
        response_format={"type": "json_object"},
        mode="compatibility",
        fallback_reason="capability_unavailable",
    )

    with pytest.raises(StructuredOutputUnsupportedError, match="does not declare"):
        negotiator.structured_output(
            ModelCapabilities(),
            model="model",
            configured_mode="required",
            schema_version="1.0",
            tools=TOOLS,
        )


def test_compatibility_mode_overrides_declared_strict_support():
    selection = DefaultModelCapabilityNegotiator().structured_output(
        ModelCapabilities(strict_json_schema=True),
        model="model",
        configured_mode="compatibility",
        schema_version="1.0",
        tools=TOOLS,
    )

    assert selection == StructuredOutputSelection(
        response_format={"type": "json_object"},
        mode="compatibility",
    )


def test_only_auto_strict_selection_can_fallback_after_rejection():
    negotiator = DefaultModelCapabilityNegotiator()
    strict = StructuredOutputSelection(
        response_format={"type": "json_schema"},
        mode="strict",
    )

    assert negotiator.fallback_after_rejection(
        strict, "auto"
    ) == StructuredOutputSelection(
        response_format={"type": "json_object"},
        mode="compatibility",
        fallback_reason="provider_rejected",
    )
    assert negotiator.fallback_after_rejection(strict, "required") is None
    assert (
        negotiator.fallback_after_rejection(
            StructuredOutputSelection(
                response_format={"type": "json_object"},
                mode="compatibility",
            ),
            "auto",
        )
        is None
    )


OBJECT_TOOLS = [
    {
        "name": "commit",
        "description": "Record a typed literal",
        "properties": {"object": {"type": "object", "properties": {}}},
    }
]


def test_a_provider_rejection_is_remembered_instead_of_paid_for_every_time():
    """The wasted round trip this fixes.

    The fallback is per-request and nothing wrote the answer down, so a
    provider that refuses the strict schema was asked again on every
    subsequent request -- one wasted call per plan, for the life of the
    process.
    """
    negotiator = DefaultModelCapabilityNegotiator()
    capable = ModelCapabilities(strict_json_schema=True)

    first = negotiator.structured_output(
        capable,
        model="model",
        configured_mode="auto",
        schema_version="1.0",
        tools=TOOLS,
    )
    assert first.mode == "strict"

    assert negotiator.fallback_after_rejection(first, "auto") is not None

    second = negotiator.structured_output(
        capable,
        model="model",
        configured_mode="auto",
        schema_version="1.0",
        tools=TOOLS,
    )
    assert second.mode == "compatibility"
    assert second.fallback_reason == "provider_rejected"

    # Remembered against what was rejected, not globally: another model, or
    # the same model on the other schema version, has said nothing yet.
    other = negotiator.structured_output(
        capable,
        model="other",
        configured_mode="auto",
        schema_version="1.0",
        tools=TOOLS,
    )
    assert other.mode == "strict"


def test_a_rejection_is_remembered_even_where_no_fallback_is_allowed():
    """`required` mode cannot fall back, but the provider has still answered,
    and asking it again cannot change the answer."""
    negotiator = DefaultModelCapabilityNegotiator()
    capable = ModelCapabilities(strict_json_schema=True)
    selection = negotiator.structured_output(
        capable,
        model="model",
        configured_mode="required",
        schema_version="1.0",
        tools=TOOLS,
    )

    assert negotiator.fallback_after_rejection(selection, "required") is None

    with pytest.raises(StructuredOutputUnsupportedError, match="rejected the strict"):
        negotiator.structured_output(
            capable,
            model="model",
            configured_mode="required",
            schema_version="1.0",
            tools=TOOLS,
        )


def test_strict_output_is_declined_for_tools_the_subset_cannot_express():
    """Better than a schema the model satisfies and the walk rejects."""
    negotiator = DefaultModelCapabilityNegotiator()
    capable = ModelCapabilities(strict_json_schema=True)

    selection = negotiator.structured_output(
        capable,
        model="model",
        configured_mode="auto",
        schema_version="1.0",
        tools=OBJECT_TOOLS,
    )

    assert selection.mode == "compatibility"
    assert selection.fallback_reason == "tool_schema_unsupported"

    with pytest.raises(StructuredOutputUnsupportedError, match="object-typed"):
        negotiator.structured_output(
            capable,
            model="model",
            configured_mode="required",
            schema_version="1.0",
            tools=OBJECT_TOOLS,
        )


def test_strict_output_is_declined_for_object_type_unions():
    negotiator = DefaultModelCapabilityNegotiator()

    selection = negotiator.structured_output(
        ModelCapabilities(strict_json_schema=True),
        model="model",
        configured_mode="auto",
        schema_version="1.0",
        tools=[
            {
                "name": "commit",
                "properties": {"payload": {"type": ["object", "null"]}},
            }
        ],
    )

    assert selection.mode == "compatibility"
    assert selection.fallback_reason == "tool_schema_unsupported"
