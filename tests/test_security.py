from pathlib import Path


def workflow(name: str) -> str:
    return (Path(".github/workflows") / name).read_text(encoding="utf-8")


def test_codeql_scans_python_and_can_upload_security_events():
    content = workflow("codeql.yml")

    assert "security-events: write" in content
    assert "github/codeql-action/init@v4" in content
    assert "github/codeql-action/analyze@v4" in content
    assert "languages: python" in content
    assert "queries: security-extended" in content


def test_dependency_audit_uses_the_frozen_hashed_environment():
    content = workflow("dependency-audit.yml")

    assert "uv export" in content
    assert "--frozen" in content
    assert "--all-groups" in content
    assert "--no-emit-project" in content
    assert "uv run pip-audit" in content
    assert "--disable-pip" in content
    assert "--require-hashes" in content
    assert "continue-on-error" not in content


def test_dependabot_tracks_uv_and_actions_on_dev():
    content = Path(".github/dependabot.yml").read_text(encoding="utf-8")

    assert "package-ecosystem: uv" in content
    assert "package-ecosystem: github-actions" in content
    assert content.count("target-branch: dev") == 2


def test_security_policy_does_not_require_unavailable_validity_checks():
    policy = Path("SECURITY.md").read_text(encoding="utf-8")

    assert "validity checks are not required" in policy
    assert "personal GitHub account" in policy


def test_main_promotion_policy_only_accepts_the_repository_dev_branch():
    content = workflow("promotion-policy.yml")

    assert "branches: [main]" in content
    assert "HEAD_REF" in content
    assert "HEAD_REPOSITORY" in content
    assert '"$HEAD_REPOSITORY" != "$REPOSITORY"' in content
    assert '"$HEAD_REF" != "dev"' in content
    assert "pull_request_target" not in content
