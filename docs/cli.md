# Command-line interface

Treelang installs a `treelang` command for validating, inspecting, executing,
replaying, and generating AST programs. Commands read program JSON from a file
or from standard input when the input is `-`.

## Export JSON Schema

```sh
treelang schema --schema-version 1.0
treelang schema --schema-version 2.0 --output treelang-v2.schema.json
```

The output is the exact canonical artifact shipped in the package and published
on the documentation site. See the [editor-validation guide](json-schema.md).

## Validate and inspect

```sh
treelang validate program.json
cat program.json | treelang validate - --output normalized.json
treelang inspect program.json
treelang inspect program.json --format json
```

Validation automatically selects schema version 1 or 2 from `schema_version`.
The default inspection format displays node relationships and important values.

## Execute safely

Tool-free programs can execute directly:

```sh
treelang execute program.json \
  --max-nodes 1000 \
  --max-depth 50 \
  --max-call-depth 25 \
  --max-tool-calls 20 \
  --max-concurrency 4 \
  --timeout 10
```

All limits are optional and use the Python API's execution-budget semantics.
Programs containing external tool calls require deterministic replay data; the
CLI does not import or execute arbitrary application code.

## Replay tool calls

```sh
treelang replay program.json --fixture replay.json
```

A replay fixture declares normalized tool definitions and exact ordered calls:

```json
{
  "tools": [
    {
      "name": "double",
      "description": "Double a number.",
      "input_schema": {
        "type": "object",
        "properties": {"value": {"type": "number"}},
        "required": ["value"],
        "additionalProperties": false
      }
    }
  ],
  "calls": [
    {"name": "double", "arguments": {"value": 2}, "output": 4}
  ]
}
```

`replay` fails if a call differs or any fixture entry remains unused. `execute`
also accepts `--replay` when full-consumption checking is not required.

## Generate

Generate and validate a program without executing it:

```sh
OPENAI_API_KEY=... treelang generate \
  "Square each number in this list" \
  --provider openai \
  --model gpt-4o-2024-11-20 \
  --schema-version 1.0 \
  --tools tools.json \
  --output program.json

ANTHROPIC_API_KEY=... treelang generate \
  "Define a recursive factorial function" \
  --provider anthropic \
  --model claude-sonnet-4-6 \
  --schema-version 2.0
```

`tools.json` is a JSON array using Treelang's provider-neutral tool-definition
format. Generation exposes definitions to the model but never invokes them. Use
`-` as the prompt to read it from standard input.

## Exit statuses

| Status | Meaning |
|---:|---|
| 0 | Command succeeded |
| 2 | Input, JSON, schema, fixture, or argument error |
| 3 | Execution, budget, tool, or replay failure |
| 4 | Model-provider, authentication, transport, or dependency failure |

Failures are machine-readable JSON on standard error:

```json
{
  "error": {
    "category": "input",
    "message": "Program input must be a JSON object"
  }
}
```
