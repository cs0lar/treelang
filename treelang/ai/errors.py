"""Provider SDK error translation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from treelang.exceptions import (
    ModelAuthenticationError,
    ModelConnectionError,
    ModelRateLimitError,
    ModelTimeoutError,
    ModelTransportError,
)


def translate_model_error(provider: str, error: Exception) -> Exception:
    """Translate known SDK failures while preserving unrelated exceptions."""
    name = type(error).__name__
    status_code = _status_code(error)
    retry_after = _retry_after(error)
    if name in {"AuthenticationError", "PermissionDeniedError"} or status_code in {
        401,
        403,
    }:
        return ModelAuthenticationError(
            str(error),
            provider=provider,
            status_code=status_code,
            retry_after=retry_after,
        )
    if name == "RateLimitError" or status_code == 429:
        return ModelRateLimitError(
            str(error),
            provider=provider,
            status_code=status_code,
            retry_after=retry_after,
        )
    if name == "APITimeoutError" or isinstance(error, TimeoutError):
        return ModelTimeoutError(
            str(error),
            provider=provider,
            status_code=status_code,
            retry_after=retry_after,
        )
    if name == "APIConnectionError":
        return ModelConnectionError(
            str(error),
            provider=provider,
            status_code=status_code,
            retry_after=retry_after,
        )
    if _is_provider_sdk_error(provider, error) or status_code is not None:
        return ModelTransportError(
            str(error),
            provider=provider,
            status_code=status_code,
            retry_after=retry_after,
        )
    return error


def _status_code(error: Exception) -> int | None:
    value = getattr(error, "status_code", None)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _retry_after(error: Exception) -> float | None:
    response = getattr(error, "response", None)
    headers: Any = getattr(response, "headers", None)
    if not isinstance(headers, Mapping):
        return None
    value = headers.get("retry-after")
    if value is None:
        return None
    try:
        retry_after = float(value)
    except (TypeError, ValueError):
        return None
    return retry_after if retry_after >= 0 else None


def _is_provider_sdk_error(provider: str, error: Exception) -> bool:
    root_module = type(error).__module__.partition(".")[0]
    expected = "openai" if provider == "openai" else "anthropic"
    return root_module == expected


__all__ = ["translate_model_error"]
