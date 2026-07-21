from pathlib import Path

import treelang
from scripts.generate_api_docs import render_api_reference


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
