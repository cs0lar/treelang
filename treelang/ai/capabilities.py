"""Provider-neutral model capability negotiation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from treelang.ai.config import SchemaVersion, StructuredOutputMode
from treelang.ai.structured_output import (
    strict_ast_schema_supported,
    strict_response_format,
)
from treelang.ai.tool import ToolDefinition
from treelang.exceptions import StructuredOutputUnsupportedError

type SelectedOutputMode = Literal["strict", "compatibility"]

_REFUSALS = {
    "capability_unavailable": "does not declare strict JSON Schema support",
    "provider_rejected": "rejected the strict JSON Schema for this request",
    "tool_schema_unsupported": (
        "was given a tool taking an object-typed parameter, which strict JSON "
        "Schema cannot express"
    ),
}
"""Why strict output was declined, in words, for the mode that refuses to
proceed without it. The keys are what `fallback_reason` carries."""


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
    negotiated_for: tuple[str, SchemaVersion] | None = field(
        default=None, compare=False
    )
    """The (model, schema version) this selection was made for.

    Bookkeeping for the negotiator, so a provider rejection can be remembered
    against the thing that was rejected. Excluded from equality: it is not part
    of what the selection *is*, and two selections that differ only in it would
    otherwise stop comparing equal.
    """


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
    """Conservative capability and structured-output policy.

    Stateful in one respect: a provider that rejects the strict schema is not
    asked again for the same model and schema version. Without that, a
    rejection costs a wasted round trip on *every* subsequent request for the
    life of the negotiator -- the fallback is per-request and nothing has ever
    written the answer down.
    """

    def __init__(self) -> None:
        self._rejected: set[tuple[str, SchemaVersion]] = set()

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
        negotiated_for = (model, schema_version)
        declined = self._declined(capabilities, negotiated_for, tools)
        if declined is None:
            return StructuredOutputSelection(
                response_format=strict_response_format(schema_version, tools),
                mode="strict",
                negotiated_for=negotiated_for,
            )
        if configured_mode == "required":
            raise StructuredOutputUnsupportedError(
                f"Model '{model}' {_REFUSALS[declined]}"
            )
        return StructuredOutputSelection(
            response_format={"type": "json_object"},
            mode="compatibility",
            fallback_reason=declined,
            negotiated_for=negotiated_for,
        )

    def fallback_after_rejection(
        self,
        selection: StructuredOutputSelection,
        configured_mode: StructuredOutputMode,
    ) -> StructuredOutputSelection | None:
        if selection.mode != "strict":
            return None
        # Remembered even where the configured mode forbids falling back: the
        # provider has answered, and asking it again cannot change the answer.
        if selection.negotiated_for is not None:
            self._rejected.add(selection.negotiated_for)
        if configured_mode != "auto":
            return None
        return StructuredOutputSelection(
            response_format={"type": "json_object"},
            mode="compatibility",
            fallback_reason="provider_rejected",
            negotiated_for=selection.negotiated_for,
        )

    def _declined(
        self,
        capabilities: ModelCapabilities,
        negotiated_for: tuple[str, SchemaVersion],
        tools: list[ToolDefinition],
    ) -> str | None:
        """Why strict output is not on the table, or nothing if it is."""
        if not capabilities.strict_json_schema:
            return "capability_unavailable"
        if negotiated_for in self._rejected:
            return "provider_rejected"
        if not strict_ast_schema_supported(tools):
            return "tool_schema_unsupported"
        return None


__all__ = [
    "CapabilityAwareTransport",
    "DefaultModelCapabilityNegotiator",
    "ModelCapabilities",
    "ModelCapabilityNegotiator",
    "StructuredOutputSelection",
    "capabilities_for",
]
