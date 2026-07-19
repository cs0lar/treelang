"""Validate release identity before building or publishing distributions."""

import argparse
import re
import subprocess
import tomllib
from pathlib import Path

TAG_PATTERN = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def validate_release(tag: str, root: Path) -> str:
    """Return the release version when tag, metadata, and changelog agree."""
    match = TAG_PATTERN.fullmatch(tag)
    if match is None:
        raise ValueError("release tag must use stable semantic version form vX.Y.Z")
    version = tag.removeprefix("v")
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = metadata["project"]["version"]
    if project_version != version:
        raise ValueError(
            f"tag version {version} does not match project version {project_version}"
        )
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{version}]" not in changelog:
        raise ValueError(f"CHANGELOG.md has no release section for {version}")
    return version


def require_main_ancestry(root: Path) -> None:
    """Reject tags whose commit has not been promoted to origin/main."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("release tag commit is not contained in origin/main")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--require-main", action="store_true")
    arguments = parser.parse_args()
    try:
        version = validate_release(arguments.tag, arguments.root)
        if arguments.require_main:
            require_main_ancestry(arguments.root)
    except (KeyError, OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Validated release {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
