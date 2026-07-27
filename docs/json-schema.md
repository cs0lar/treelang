# JSON Schema and editor validation

Treelang publishes canonical JSON Schema Draft 2020-12 documents for language
versions 1.0 and 2.0. Each artifact is generated from the same Pydantic model
used at runtime and checked for drift in normal CI.

| Language | Published schema | Packaged filename |
|---|---|---|
| 1.0 | [treelang-1.0.schema.json](schemas/treelang-1.0.schema.json) | `treelang/schema_files/treelang-1.0.schema.json` |
| 2.0 | [treelang-2.0.schema.json](schemas/treelang-2.0.schema.json) | `treelang/schema_files/treelang-2.0.schema.json` |

Published schemas use stable `latest` URLs for editor integration. Select the
matching documentation version when validating programs for an older release.

## Command line

Write either canonical artifact without locating the installed package:

```sh
treelang schema --schema-version 1.0 --output treelang-v1.schema.json
treelang schema --schema-version 2.0 --output treelang-v2.schema.json
```

`treelang validate` remains the authoritative runtime validation command.

## Python

```python
from treelang import json_schema_text, load_json_schema

schema_document = load_json_schema("2.0")
schema_source = json_schema_text("2.0")
```

`json_schema_text()` returns the exact packaged artifact. `load_json_schema()`
returns a new JSON-compatible mapping. JSON Schema covers the serialized
structural contract; `treelang validate` additionally applies semantic model
validators such as lexical-scope and function-call checks.

## Visual Studio Code

Copy the [example settings](examples/vscode-settings.json) into the
`json.schemas` section of `.vscode/settings.json`, then adapt `fileMatch` to your
program layout. The example maps `program-v1.json` and `program-v2.json`, as well
as files under `programs/v1/` and `programs/v2/`.

The repository includes matching [version 1](examples/program-v1.json) and
[version 2](examples/program-v2.json) example programs. Opening either file
provides completion, field documentation, and inline validation diagnostics.

## JetBrains IDEs

Open **Settings → Languages & Frameworks → Schemas and DTDs → JSON Schema
Mappings**, add the published schema URL for the language version, and map it to
the relevant file or directory pattern.

## Other editors

Any editor with JSON Schema Draft 2020-12 support can use the published URL or a
file emitted by `treelang schema`. Keep v1 and v2 file patterns separate because
their node vocabularies and recursion contracts intentionally differ.
