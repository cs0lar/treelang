"""Configuration for Arborist model transports."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class ArboristConfig:
    """Immutable runtime configuration shared by orchestration and responses."""

    model: str
    api_key: str | None = None
    temperature: float = 0.0
    timeout: float | None = None

    @classmethod
    def from_env(cls, model: str | None = None) -> "ArboristConfig":
        """Read compatibility defaults once at the composition boundary."""
        load_dotenv()
        timeout_value = os.getenv("OPENAI_TIMEOUT")
        configured_model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-2024-11-20"
        return cls(
            model=configured_model,
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=float(timeout_value) if timeout_value else None,
        )
