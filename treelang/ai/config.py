"""Configuration for Arborist model transports."""

import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv

type SchemaVersion = Literal["1.0", "2.0"]
type StructuredOutputMode = Literal["auto", "required", "compatibility"]
type OpenAIAPI = Literal["chat_completions", "responses"]
type ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh"]


@dataclass(frozen=True, slots=True)
class ArboristConfig:
    """Immutable runtime configuration shared by orchestration and responses."""

    model: str
    api_key: str | None = None
    temperature: float = 0.0
    timeout: float | None = None
    validation_retries: int = 2
    schema_version: SchemaVersion = "1.0"
    structured_output_mode: StructuredOutputMode = "auto"
    openai_api: OpenAIAPI = "chat_completions"
    reasoning_effort: ReasoningEffort | None = None

    def __post_init__(self) -> None:
        if self.validation_retries < 0:
            raise ValueError("validation_retries must be non-negative")
        if self.schema_version not in ("1.0", "2.0"):
            raise ValueError("schema_version must be '1.0' or '2.0'")
        if self.structured_output_mode not in (
            "auto",
            "required",
            "compatibility",
        ):
            raise ValueError(
                "structured_output_mode must be 'auto', 'required', or 'compatibility'"
            )
        if self.openai_api not in ("chat_completions", "responses"):
            raise ValueError("openai_api must be 'chat_completions' or 'responses'")
        if self.reasoning_effort not in (
            None,
            "none",
            "low",
            "medium",
            "high",
            "xhigh",
        ):
            raise ValueError("reasoning_effort has an unsupported value")
        if self.reasoning_effort is not None and self.openai_api != "responses":
            raise ValueError("reasoning_effort requires openai_api='responses'")

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
