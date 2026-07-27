"""Generate distributable JSON Schema artifacts from Treelang models."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from treelang.trees.schemas.v1 import AST as ASTV1
from treelang.trees.schemas.v2 import AST as ASTV2

ROOT = Path(__file__).parents[1]
PACKAGE_DIRECTORY = ROOT / "treelang" / "schema_files"
DOCUMENTATION_DIRECTORY = ROOT / "docs" / "schemas"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_BASE_URL = "https://csolar.github.io/treelang/latest/schemas"
GENERATORS: dict[str, Callable[[], dict[str, Any]]] = {
    "1.0": ASTV1.model_json_schema,
    "2.0": ASTV2.model_json_schema,
}


def render_schema(version: str) -> str:
    """Render one stable schema document with public identity metadata."""
    try:
        schema = GENERATORS[version]()
    except KeyError as error:
        raise ValueError(f"Unsupported schema version '{version}'") from error
    filename = schema_filename(version)
    document = {
        **schema,
        "$schema": SCHEMA_DIALECT,
        "$id": f"{SCHEMA_BASE_URL}/{filename}",
        "title": f"Treelang AST Program {version}",
    }
    return f"{json.dumps(document, indent=2, ensure_ascii=False)}\n"


def schema_filename(version: str) -> str:
    """Return the stable artifact name for one schema version."""
    return f"treelang-{version}.schema.json"


def outputs() -> dict[Path, str]:
    """Return every generated package and documentation artifact."""
    rendered = {version: render_schema(version) for version in GENERATORS}
    return {
        directory / schema_filename(version): content
        for directory in (PACKAGE_DIRECTORY, DOCUMENTATION_DIRECTORY)
        for version, content in rendered.items()
    }


def generate(*, check: bool = False) -> None:
    """Write artifacts or fail if committed files differ from model output."""
    stale: list[Path] = []
    for path, content in outputs().items():
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                stale.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if stale:
        names = ", ".join(str(path.relative_to(ROOT)) for path in stale)
        raise RuntimeError(
            f"JSON Schema artifacts are stale: {names}; run make docs and commit them"
        )
    action = "current" if check else "generated"
    print(f"JSON Schema artifacts are {action}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    generate(check=arguments.check)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
