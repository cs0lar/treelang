import tomllib
from pathlib import Path

import pytest

from scripts.smoke_release import smoke_release
from scripts.validate_release import validate_release


def release_files(tmp_path: Path, *, version: str = "1.2.3") -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "treelang"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{version}] - 2026-07-19\n",
        encoding="utf-8",
    )
    return tmp_path


def test_release_identity_requires_matching_tag_metadata_and_changelog(tmp_path):
    assert validate_release("v1.2.3", release_files(tmp_path)) == "1.2.3"


@pytest.mark.parametrize("tag", ["1.2.3", "v1.2", "v01.2.3", "v1.2.3rc1"])
def test_release_identity_rejects_noncanonical_tags(tmp_path, tag):
    with pytest.raises(ValueError, match="stable semantic version"):
        validate_release(tag, release_files(tmp_path))


def test_release_identity_rejects_metadata_mismatch(tmp_path):
    with pytest.raises(ValueError, match="does not match project version"):
        validate_release("v1.2.4", release_files(tmp_path))


def test_release_identity_requires_changelog_section(tmp_path):
    root = release_files(tmp_path)
    (root / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no release section"):
        validate_release("v1.2.3", root)


def test_current_package_passes_public_api_smoke_test():
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    smoke_release(metadata["project"]["version"])


def test_github_release_command_has_explicit_repository_context():
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")

    assert 'gh release create "$GITHUB_REF_NAME"' in workflow
    assert '--repo "$GITHUB_REPOSITORY"' in workflow
