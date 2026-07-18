"""Structured, redacted logging and optional tracing hooks."""

import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

REDACTED = "[REDACTED]"

_CREDENTIAL_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
}
_CONTENT_KEYS = {
    "actual",
    "arguments",
    "ast",
    "completion",
    "content",
    "error",
    "expected",
    "input",
    "messages",
    "output",
    "prompt",
    "query",
    "question",
    "request",
    "response",
    "result",
}
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"),
)


@runtime_checkable
class TraceSink(Protocol):
    """Vendor-neutral destination for already-redacted trace events."""

    def record(self, event: str, attributes: Mapping[str, Any]) -> None: ...


class NoOpTraceSink:
    def record(self, event: str, attributes: Mapping[str, Any]) -> None:
        return None


def redact(value: Any, *, allow_content: bool = False) -> Any:
    """Recursively remove credentials and, by default, user/model content."""
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            normalized = name.lower().replace("-", "_")
            if _matches_key(normalized, _CREDENTIAL_KEYS):
                redacted[name] = REDACTED
            elif not allow_content and _matches_key(normalized, _CONTENT_KEYS):
                redacted[name] = None if item is None else REDACTED
            else:
                redacted[name] = redact(item, allow_content=allow_content)
        return redacted
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item, allow_content=allow_content) for item in value]
    if isinstance(value, str):
        result = value
        for pattern in _SECRET_PATTERNS:
            result = pattern.sub(REDACTED, result)
        return result
    return value


def _matches_key(value: str, candidates: set[str]) -> bool:
    return value in candidates or any(
        value.endswith(f"_{candidate}") for candidate in candidates
    )


@dataclass(slots=True)
class Observability:
    """Send the same redacted event to JSON logs and an optional trace sink."""

    logger: logging.Logger = field(
        default_factory=lambda: logging.getLogger("treelang.observability")
    )
    tracer: TraceSink = field(default_factory=NoOpTraceSink)
    allow_content: bool = False

    def emit(self, event: str, **attributes: Any) -> None:
        safe_attributes = redact(attributes, allow_content=self.allow_content)
        payload = {"event": event, **safe_attributes}
        self.logger.info(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        )
        self.tracer.record(event, safe_attributes)
