"""Provider-neutral model capability negotiation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

from treelang.ai.config import SchemaVersion, StructuredOutputMode
from treelang.ai.structured_output import strict_response_format
from treelang.ai.tool import ToolDefinition
from treelang.exceptions import StructuredOutputUnsupportedError

type SelectedOutputMode = Literal["strict", "compatibility"]


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    """Features supported by one model through a transport."""

    strict_json_schema: bool = False
    temperature: bool = False


@dataclass(frozen=True, slots=True)
class StructuredOutputSelection:
    """Negotiated response format and the reason for compatibility fallback."""

    response_format: dict[str, Any]
    mode: SelectedOutputMode
    fallback_reason: str | None = None


@runtime_checkable
class CapabilityAwareTransport(Protocol):
    """Optional transport extension for model-specific capability discovery."""

    def capabilities(self, model: str) -> ModelCapabilities: ...


def capabilities_for(transport: object, model: str) -> ModelCapabilities:
    """Return declared capabilities, defaulting safely for legacy transports."""
    if isinstance(transport, CapabilityAwareTransport):
        return transport.capabilities(model)
    return ModelCapabilities()


@runtime_checkable
class ModelCapabilityNegotiator(Protocol):
    """Policy boundary between model features and request orchestration."""

    def capabilities(self, transport: object, model: str) -> ModelCapabilities: ...

    def structured_output(
        self,
        capabilities: ModelCapabilities,
        *,
        model: str,
        configured_mode: StructuredOutputMode,
        schema_version: SchemaVersion,
        tools: list[ToolDefinition],
    ) -> StructuredOutputSelection: ...

    def fallback_after_rejection(
        self,
        selection: StructuredOutputSelection,
        configured_mode: StructuredOutputMode,
    ) -> StructuredOutputSelection | None: ...


class DefaultModelCapabilityNegotiator:
    """Conservative capability and structured-output policy."""

    def capabilities(self, transport: object, model: str) -> ModelCapabilities:
        return capabilities_for(transport, model)

    def structured_output(
        self,
        capabilities: ModelCapabilities,
        *,
        model: str,
        configured_mode: StructuredOutputMode,
        schema_version: SchemaVersion,
        tools: list[ToolDefinition],
    ) -> StructuredOutputSelection:
        if configured_mode == "compatibility":
            return StructuredOutputSelection(
                response_format={"type": "json_object"},
                mode="compatibility",
            )
        if capabilities.strict_json_schema:
            return StructuredOutputSelection(
                response_format=strict_response_format(schema_version, tools),
                mode="strict",
            )
        if configured_mode == "required":
            raise StructuredOutputUnsupportedError(
                f"Model '{model}' does not declare strict JSON Schema support"
            )
        return StructuredOutputSelection(
            response_format={"type": "json_object"},
            mode="compatibility",
            fallback_reason="capability_unavailable",
        )

    def fallback_after_rejection(
        self,
        selection: StructuredOutputSelection,
        configured_mode: StructuredOutputMode,
    ) -> StructuredOutputSelection | None:
        if configured_mode != "auto" or selection.mode != "strict":
            return None
        return StructuredOutputSelection(
            response_format={"type": "json_object"},
            mode="compatibility",
            fallback_reason="provider_rejected",
        )


__all__ = [
    "CapabilityAwareTransport",
    "DefaultModelCapabilityNegotiator",
    "ModelCapabilities",
    "ModelCapabilityNegotiator",
    "StructuredOutputSelection",
    "capabilities_for",
]
