import ast
import json
from pathlib import Path

import pytest

import treelang
from scripts.generate_api_docs import render_api_reference
from scripts.generate_provider_matrix import load_manifest, render_provider_matrix


def test_generated_api_reference_is_current():
    reference = Path("docs/api.md").read_text(encoding="utf-8")

    assert reference == render_api_reference()


def test_generated_api_reference_covers_every_supported_export():
    reference = Path("docs/api.md").read_text(encoding="utf-8")

    for name in treelang.__all__:
        assert f"## `{name}`" in reference


def test_documentation_index_links_required_architecture_decisions():
    index = Path("docs/README.md").read_text(encoding="utf-8")

    assert "0001-schema-versioning.md" in index
    assert "0002-execution-semantics.md" in index
    assert "0003-provider-contracts.md" in index
    assert "migration-0.10.md" in index
    assert "provider-matrix.md" in index


def test_documentation_site_includes_generated_reference_and_guides():
    configuration = Path("mkdocs.yml").read_text(encoding="utf-8")
    landing_page = Path("docs/index.md").read_text(encoding="utf-8")

    assert "site_url: https://csolar.github.io/treelang/" in configuration
    assert "provider: mike" in configuration
    assert "Supported API: api.md" in configuration
    assert "Command-line interface: cli.md" in configuration
    assert "Downstream testing kit: testing.md" in configuration
    assert "JSON Schema and editor validation: json-schema.md" in configuration
    assert "End-to-end cookbooks: cookbooks.md" in configuration
    assert "Extensions and provider contributions: extensions.md" in configuration
    assert "Migration guide: migration-0.10.md" in configuration
    assert "adr/0004-recursive-schema-and-execution.md" in configuration
    assert "Versioned documentation" in landing_page


def test_generated_provider_matrix_is_current_and_runtime_validated():
    manifest = load_manifest()
    reference = Path("docs/provider-matrix.md").read_text(encoding="utf-8")

    assert reference == render_provider_matrix(manifest)
    assert {provider["id"] for provider in manifest["providers"]} == {
        "openai",
        "anthropic",
    }


def test_provider_manifest_rejects_capability_drift(tmp_path):
    manifest = json.loads(Path("docs/providers.json").read_text(encoding="utf-8"))
    manifest["providers"][0]["model_profiles"][0]["strict_json_schema"] = False
    path = tmp_path / "providers.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="capability drift"):
        load_manifest(path)


def test_cookbook_and_extension_guides_cover_contribution_contracts():
    cookbooks = Path("docs/cookbooks.md").read_text(encoding="utf-8")
    extensions = Path("docs/extensions.md").read_text(encoding="utf-8")
    contributing = Path("CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "quickstart.ipynb" in cookbooks
    assert "custom-provider.ipynb" in cookbooks
    assert "ci_execute" in cookbooks
    assert "ToolProviderContract" in extensions
    assert "ModelTransportContract" in extensions
    assert "live-evaluation" in extensions
    assert "docs/extensions.md" in contributing
    assert "make cookbooks" in contributing


def test_readme_positions_the_niche_and_quick_start_compiles():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "gap between simple\ntool calling and a full workflow engine" in readme
    assert "Intermediate\ntool results stay in your process" in readme
    assert "not intended for open-ended agents" in readme
    assert "Private bulk operations" in readme
    assert "Generate, inspect, then execute" in readme

    quick_start = readme.split("### Generate, inspect, then execute", maxsplit=1)[1]
    python_source = quick_start.split("```python", maxsplit=1)[1].split(
        "```", maxsplit=1
    )[0]
    ast.parse(python_source)
