"""Smoke-test the supported API from an installed release artifact."""

import argparse
from importlib.metadata import distribution
from pathlib import Path

import treelang
import treelang.testing


def smoke_release(expected_version: str, *, require_installed: bool = False) -> None:
    """Check package identity and every declared public export."""
    if treelang.__version__ != expected_version:
        raise RuntimeError(
            f"installed version {treelang.__version__} != {expected_version}"
        )
    missing = [name for name in treelang.__all__ if not hasattr(treelang, name)]
    if missing:
        raise RuntimeError(f"missing public exports: {', '.join(missing)}")
    if treelang.CURRENT_SCHEMA_VERSION != "1.0":
        raise RuntimeError("installed artifact has an unexpected schema version")
    for version in treelang.SUPPORTED_SCHEMA_VERSIONS:
        schema = treelang.load_json_schema(version)
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise RuntimeError(f"installed schema {version} has no stable dialect")
    console_scripts = {
        entry.name: entry.value
        for entry in distribution("treelang").entry_points
        if entry.group == "console_scripts"
    }
    if console_scripts.get("treelang") != "treelang.cli:main":
        raise RuntimeError("installed artifact has no supported treelang CLI")
    if not treelang.testing.__all__:
        raise RuntimeError("installed artifact has an empty downstream testing kit")
    if require_installed and "site-packages" not in str(Path(treelang.__file__)):
        raise RuntimeError(f"loaded package from source tree: {treelang.__file__}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--require-installed", action="store_true")
    arguments = parser.parse_args()
    smoke_release(
        arguments.expected_version, require_installed=arguments.require_installed
    )
    print(f"Installed treelang {arguments.expected_version} passed smoke tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
