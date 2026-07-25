"""Provider-neutral model capability negotiation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    """Features supported by one model through a transport."""

    strict_json_schema: bool = False


@runtime_checkable
class CapabilityAwareTransport(Protocol):
    """Optional transport extension for model-specific capability discovery."""

    def capabilities(self, model: str) -> ModelCapabilities: ...


def capabilities_for(transport: object, model: str) -> ModelCapabilities:
    """Return declared capabilities, defaulting safely for legacy transports."""
    if isinstance(transport, CapabilityAwareTransport):
        return transport.capabilities(model)
    return ModelCapabilities()


__all__ = [
    "CapabilityAwareTransport",
    "ModelCapabilities",
    "capabilities_for",
]
