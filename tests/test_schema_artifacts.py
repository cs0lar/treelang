import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from scripts.generate_json_schemas import (
    DOCUMENTATION_DIRECTORY,
    PACKAGE_DIRECTORY,
    generate,
    render_schema,
    schema_filename,
)
from treelang import (
    SUPPORTED_SCHEMA_VERSIONS,
    json_schema_text,
    load_json_schema,
)
from treelang.cli import main


@pytest.mark.parametrize("version", SUPPORTED_SCHEMA_VERSIONS)
def test_generated_package_and_site_schemas_are_current_and_identical(version):
    filename = schema_filename(version)
    expected = render_schema(version)

    assert (PACKAGE_DIRECTORY / filename).read_text(encoding="utf-8") == expected
    assert (DOCUMENTATION_DIRECTORY / filename).read_text(encoding="utf-8") == expected
    assert json_schema_text(version) == expected
    assert load_json_schema(version) == json.loads(expected)


def test_schema_drift_check_passes_for_committed_artifacts():
    generate(check=True)


def test_schema_generator_rejects_unknown_language_version():
    with pytest.raises(ValueError, match="Unsupported schema version"):
        render_schema("3.0")


@pytest.mark.parametrize(
    ("version", "example"),
    [
        ("1.0", "program-v1.json"),
        ("2.0", "program-v2.json"),
    ],
)
def test_editor_examples_validate_against_published_draft_2020_12_schema(
    version, example
):
    schema = load_json_schema(version)
    program = json.loads((Path("docs/examples") / example).read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(program)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith(f"/schemas/treelang-{version}.schema.json")


def test_vscode_example_maps_both_published_schema_urls():
    settings = json.loads(
        Path("docs/examples/vscode-settings.json").read_text(encoding="utf-8")
    )

    mappings = settings["json.schemas"]
    assert len(mappings) == 2
    assert {mapping["url"] for mapping in mappings} == {
        "https://cs0lar.github.io/treelang/latest/schemas/treelang-1.0.schema.json",
        "https://cs0lar.github.io/treelang/latest/schemas/treelang-2.0.schema.json",
    }


@pytest.mark.parametrize("version", SUPPORTED_SCHEMA_VERSIONS)
def test_cli_writes_exact_canonical_schema(tmp_path, version):
    output = tmp_path / f"schema-{version}.json"

    assert main(["schema", "--schema-version", version, "--output", str(output)]) == 0

    assert output.read_text(encoding="utf-8") == json_schema_text(version)
