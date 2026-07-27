# Treelang

Treelang turns natural-language requests into validated abstract syntax tree
programs that execute against your tools. It keeps model generation separate
from deterministic program execution and supports OpenAI and Anthropic model
transports.

## Install

```sh
pip install treelang
```

Install the optional Anthropic adapter with:

```sh
pip install "treelang[anthropic]"
```

Python 3.12 or newer is required.

## Start here

- Use the [supported API reference](api.md) to see the stable root exports.
- Use the [command-line interface](cli.md) to validate, inspect, execute, replay,
  and generate programs.
- Test integrations with [deterministic fakes and provider contracts](testing.md).
- Configure editors with the [canonical JSON Schema artifacts](json-schema.md).
- Learn the [execution and replay semantics](execution-resilience.md).
- Compare model integrations in the [provider compatibility matrix](provider-matrix.md).
- Follow the [0.10 migration guide](migration-0.10.md) when upgrading.
- Read the [architecture decisions](adr/0001-schema-versioning.md) for the
  rationale behind schema and runtime contracts.

## Versioned documentation

Each tagged release publishes an immutable documentation version. The `latest`
alias points to the most recently published release; use the version selector in
the header when working with an older package version.

For source development, install the locked environment and preview the site:

```sh
uv sync --frozen --all-groups
uv run mkdocs serve
```
