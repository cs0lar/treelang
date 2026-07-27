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
