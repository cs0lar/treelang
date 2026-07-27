import json
import tomllib
from pathlib import Path

import pytest

from treelang.cli import main


def write_json(path: Path, value) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def v1_value_program(value=42):
    return {
        "type": "program",
        "body": [{"type": "value", "name": "answer", "value": value}],
        "mode": "single",
        "schema_version": "1.0",
    }


def v2_literal_program(value=42):
    return {
        "type": "program",
        "definitions": [],
        "body": [{"type": "literal", "value": value}],
        "mode": "single",
        "schema_version": "2.0",
    }


def test_package_installs_treelang_console_script():
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["scripts"]["treelang"] == "treelang.cli:main"


@pytest.mark.parametrize("program", [v1_value_program(), v2_literal_program()])
def test_validate_normalizes_both_schema_versions(tmp_path, capsys, program):
    source = write_json(tmp_path / "program.json", program)

    assert main(["validate", str(source)]) == 0

    assert json.loads(capsys.readouterr().out) == program


def test_validate_reads_stdin_and_writes_a_file(tmp_path, monkeypatch, capsys):
    output = tmp_path / "nested" / "normalized.json"
    monkeypatch.setattr("sys.stdin.read", lambda: json.dumps(v1_value_program()))

    assert main(["validate", "-", "--output", str(output)]) == 0

    assert json.loads(output.read_text(encoding="utf-8")) == v1_value_program()
    assert capsys.readouterr().out == ""


def test_inspect_renders_a_readable_tree(tmp_path, capsys):
    source = write_json(tmp_path / "program.json", v1_value_program())

    assert main(["inspect", str(source)]) == 0

    output = capsys.readouterr().out
    assert "program" in output
    assert "body:" in output
    assert "value answer = 42" in output


@pytest.mark.parametrize("program", [v1_value_program(), v2_literal_program()])
def test_execute_runs_tool_free_programs(tmp_path, capsys, program):
    source = write_json(tmp_path / "program.json", program)

    assert main(["execute", str(source)]) == 0

    assert json.loads(capsys.readouterr().out) == {"result": 42}


def test_replay_executes_and_consumes_tool_calls(tmp_path, capsys):
    source = write_json(
        tmp_path / "program.json",
        {
            "type": "program",
            "body": [
                {
                    "type": "function",
                    "name": "double",
                    "params": [{"type": "value", "name": "value", "value": 2}],
                }
            ],
            "mode": "single",
            "schema_version": "1.0",
        },
    )
    fixture = write_json(
        tmp_path / "replay.json",
        {
            "tools": [
                {
                    "name": "double",
                    "description": "Double a number.",
                    "input_schema": {
                        "type": "object",
                        "properties": {"value": {"type": "number"}},
                        "required": ["value"],
                        "additionalProperties": False,
                    },
                }
            ],
            "calls": [{"name": "double", "arguments": {"value": 2}, "output": 4}],
        },
    )

    assert main(["replay", str(source), "--fixture", str(fixture)]) == 0

    assert json.loads(capsys.readouterr().out) == {"result": 4}


def test_replay_rejects_unconsumed_entries(tmp_path, capsys):
    source = write_json(tmp_path / "program.json", v1_value_program())
    fixture = write_json(
        tmp_path / "replay.json",
        {
            "tools": [{"name": "unused", "properties": {}}],
            "calls": [{"name": "unused", "arguments": {}, "output": 1}],
        },
    )

    with pytest.raises(SystemExit) as raised:
        main(["replay", str(source), "--fixture", str(fixture)])

    error = json.loads(capsys.readouterr().err)
    assert raised.value.code == 3
    assert error["error"]["category"] == "execution"
    assert "unconsumed" in error["error"]["message"]


def test_execute_reports_budget_failures_as_machine_readable_errors(tmp_path, capsys):
    source = write_json(tmp_path / "program.json", v1_value_program())

    with pytest.raises(SystemExit) as raised:
        main(["execute", str(source), "--max-nodes", "1"])

    error = json.loads(capsys.readouterr().err)
    assert raised.value.code == 3
    assert error["error"]["category"] == "execution"
    assert "nodes limit exceeded" in error["error"]["message"]


def test_invalid_input_has_stable_status_and_machine_readable_error(tmp_path, capsys):
    source = tmp_path / "invalid.json"
    source.write_text("{", encoding="utf-8")

    with pytest.raises(SystemExit) as raised:
        main(["validate", str(source)])

    error = json.loads(capsys.readouterr().err)
    assert raised.value.code == 2
    assert error["error"]["category"] == "input"


class GeneratedProgramTransport:
    async def complete(self, request):
        return json.dumps(v1_value_program(7))

    def stream(self, request):
        async def empty():
            if False:
                yield ""

        return empty()


@pytest.mark.parametrize(
    ("provider", "credential", "transport"),
    [
        ("openai", "OPENAI_API_KEY", "OpenAITransport"),
        ("anthropic", "ANTHROPIC_API_KEY", "AnthropicTransport"),
    ],
)
def test_generate_returns_a_validated_program(
    monkeypatch, capsys, provider, credential, transport
):
    monkeypatch.setenv(credential, "test-key")
    monkeypatch.setattr(
        f"treelang.cli.{transport}", lambda **kwargs: GeneratedProgramTransport()
    )

    assert (
        main(
            [
                "generate",
                "Return seven",
                "--provider",
                provider,
                "--model",
                f"{provider}-test",
            ]
        )
        == 0
    )

    assert json.loads(capsys.readouterr().out) == v1_value_program(7)


def test_generate_reports_missing_credentials_as_provider_error(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "")

    with pytest.raises(SystemExit) as raised:
        main(["generate", "Return seven", "--provider", "openai"])

    error = json.loads(capsys.readouterr().err)
    assert raised.value.code == 4
    assert error["error"]["category"] == "provider"
    assert "OPENAI_API_KEY" in error["error"]["message"]
