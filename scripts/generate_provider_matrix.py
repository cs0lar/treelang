"""Validate and render the supported model-provider compatibility matrix."""

from __future__ import annotations

import argparse
import importlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

from treelang.ai.capabilities import ModelCapabilities

ROOT = Path(__file__).parents[1]
DEFAULT_MANIFEST = ROOT / "docs" / "providers.json"
DEFAULT_OUTPUT = ROOT / "docs" / "provider-matrix.md"
FEATURE_STATUSES = {"supported", "model-dependent", "unsupported"}
REQUIRED_PROVIDER_KEYS = {
    "id",
    "name",
    "adapter",
    "capability_function",
    "installation",
    "documentation",
    "contract_test",
    "features",
    "model_profiles",
    "official_documentation",
}


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    """Load and validate the provider manifest and runtime capability claims."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "1.0":
        raise ValueError("Provider manifest must use schema version 1.0")
    features = value.get("features")
    providers = value.get("providers")
    if (
        not isinstance(features, list)
        or not features
        or not all(isinstance(feature, str) and feature for feature in features)
    ):
        raise ValueError("Provider manifest must declare named features")
    if len(features) != len(set(features)):
        raise ValueError("Provider manifest feature names must be unique")
    if not isinstance(providers, list) or len(providers) < 2:
        raise ValueError("Provider manifest must declare at least two providers")

    provider_ids: set[str] = set()
    for provider in providers:
        _validate_provider(provider, features, provider_ids)
    return value


def _validate_provider(
    provider: Any, features: list[str], provider_ids: set[str]
) -> None:
    if not isinstance(provider, dict) or set(provider) != REQUIRED_PROVIDER_KEYS:
        raise ValueError("Provider manifest entry has invalid fields")
    provider_id = provider["id"]
    if not isinstance(provider_id, str) or not provider_id:
        raise ValueError("Provider id must be a non-empty string")
    if provider_id in provider_ids:
        raise ValueError(f"Provider id '{provider_id}' must be unique")
    provider_ids.add(provider_id)

    for field in (
        "name",
        "adapter",
        "capability_function",
        "installation",
        "documentation",
        "contract_test",
        "official_documentation",
    ):
        if not isinstance(provider[field], str) or not provider[field]:
            raise ValueError(f"Provider '{provider_id}' has invalid {field}")
    for field in ("documentation", "contract_test"):
        if not (ROOT / provider[field]).is_file():
            raise ValueError(
                f"Provider '{provider_id}' references missing {field} path"
            )

    statuses = provider["features"]
    if not isinstance(statuses, dict) or set(statuses) != set(features):
        raise ValueError(
            f"Provider '{provider_id}' feature set does not match manifest"
        )
    if not all(status in FEATURE_STATUSES for status in statuses.values()):
        raise ValueError(f"Provider '{provider_id}' has an invalid feature status")

    adapter = _import_symbol(provider["adapter"])
    for method in ("capabilities", "complete", "consume_usage", "stream"):
        if not callable(getattr(adapter, method, None)):
            raise ValueError(
                f"Provider '{provider_id}' adapter does not implement {method}"
            )
    capability_function = _import_capability_function(provider["capability_function"])
    profiles = provider["model_profiles"]
    if not isinstance(profiles, list) or not profiles:
        raise ValueError(f"Provider '{provider_id}' must declare model profiles")
    for profile in profiles:
        if not isinstance(profile, dict) or set(profile) != {
            "model",
            "strict_json_schema",
            "temperature",
        }:
            raise ValueError(f"Provider '{provider_id}' has an invalid model profile")
        if (
            not isinstance(profile["model"], str)
            or not profile["model"]
            or not isinstance(profile["strict_json_schema"], bool)
            or not isinstance(profile["temperature"], bool)
        ):
            raise ValueError(f"Provider '{provider_id}' has invalid profile values")
        capabilities = capability_function(profile["model"])
        expected = ModelCapabilities(
            strict_json_schema=profile["strict_json_schema"],
            temperature=profile["temperature"],
        )
        if capabilities != expected:
            raise ValueError(
                f"Provider '{provider_id}' capability drift for "
                f"model '{profile['model']}'"
            )


def _import_capability_function(
    path: str,
) -> Callable[[str], ModelCapabilities]:
    value = _import_symbol(path)
    return cast(Callable[[str], ModelCapabilities], value)


def _import_symbol(path: str) -> Any:
    module_name, _, attribute = path.rpartition(".")
    if not module_name:
        raise ValueError(f"Invalid import path '{path}'")
    value = getattr(importlib.import_module(module_name), attribute, None)
    if not callable(value):
        raise ValueError(f"Imported value '{path}' is not callable")
    return value


def render_provider_matrix(manifest: Mapping[str, Any]) -> str:
    """Render deterministic Markdown from a validated provider manifest."""
    features = cast(list[str], manifest["features"])
    providers = cast(list[dict[str, Any]], manifest["providers"])
    lines = [
        "# Provider capability and compatibility matrix",
        "",
        "This file is generated from [`providers.json`](providers.json). "
        "Do not edit it directly.",
        "Run `make docs` after changing provider support.",
        "",
        "Status meanings: **supported** is contract-tested for the adapter; "
        "**model-dependent** is",
        "selected through declared capabilities; **unsupported** is rejected or "
        "omitted.",
        "",
        "| Capability | "
        + " | ".join(provider["name"] for provider in providers)
        + " |",
        "|---|" + "|".join("---" for _ in providers) + "|",
    ]
    for feature in features:
        label = (
            "Strict JSON Schema"
            if feature == "strict_json_schema"
            else feature.replace("_", " ").title()
        )
        lines.append(
            "| "
            + label
            + " | "
            + " | ".join(provider["features"][feature] for provider in providers)
            + " |"
        )

    lines.extend(["", "## Adapter details", ""])
    for provider in providers:
        lines.extend(
            [
                f"### {provider['name']}",
                "",
                f"- Adapter: `{provider['adapter']}`",
                f"- Install: `{provider['installation']}`",
                f"- Contract tests: [`{provider['contract_test']}`]"
                "(https://github.com/cs0lar/treelang/blob/dev/"
                f"{provider['contract_test']})",
                f"- Guide: [`{provider['documentation']}`]"
                f"({Path(provider['documentation']).name})",
                f"- [Official documentation]({provider['official_documentation']})",
                "- Checked model profiles:",
                "",
            ]
        )
        for profile in provider["model_profiles"]:
            lines.append(
                f"  - `{profile['model']}`: strict JSON Schema "
                f"{_yes_no(profile['strict_json_schema'])}; temperature "
                f"{_yes_no(profile['temperature'])}"
            )
        lines.append("")
    lines.extend(
        [
            "The matrix is validated in normal CI without credentials or network "
            "access. Live",
            "provider quality is measured separately by the credentialed evaluation "
            "workflow.",
            "",
        ]
    )
    return "\n".join(lines)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    generated = render_provider_matrix(load_manifest(arguments.manifest))
    if arguments.check:
        if (
            not arguments.output.exists()
            or arguments.output.read_text(encoding="utf-8") != generated
        ):
            parser.error(
                f"{arguments.output} is stale; run `make docs` and commit the result"
            )
        print(f"Provider matrix is current: {arguments.output}")
        return 0
    arguments.output.write_text(generated, encoding="utf-8")
    print(f"Generated provider matrix: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
