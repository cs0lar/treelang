"""Access canonical JSON Schema files shipped with Treelang."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, Literal, cast

type SupportedSchemaVersion = Literal["1.0", "2.0"]
SUPPORTED_SCHEMA_VERSIONS: tuple[SupportedSchemaVersion, ...] = ("1.0", "2.0")


def schema_filename(version: SupportedSchemaVersion) -> str:
    """Return the stable filename for a supported schema version."""
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(f"Unsupported schema version '{version}'")
    return f"treelang-{version}.schema.json"


def json_schema_text(version: SupportedSchemaVersion) -> str:
    """Read one canonical schema exactly as distributed in the package."""
    return (
        files("treelang.schema_files")
        .joinpath(schema_filename(version))
        .read_text(encoding="utf-8")
    )


def load_json_schema(version: SupportedSchemaVersion) -> dict[str, Any]:
    """Load one canonical schema as a JSON-compatible mapping."""
    value = json.loads(json_schema_text(version))
    if not isinstance(value, dict):  # pragma: no cover - generated invariant
        raise RuntimeError("Distributed JSON Schema must be an object")
    return cast(dict[str, Any], value)


__all__ = [
    "SUPPORTED_SCHEMA_VERSIONS",
    "SupportedSchemaVersion",
    "json_schema_text",
    "load_json_schema",
    "schema_filename",
]
