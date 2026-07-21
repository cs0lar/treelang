# Migrating to Treelang 0.10

Treelang 0.10 requires Python 3.12 or newer and uses uv/Hatchling for repository
development and packaging. Applications installing from PyPI can continue using
`pip install treelang`.

## Supported imports

Prefer imports from `treelang` for the supported AST, provider, observability,
schema helper, and exception APIs. Consult the [generated API reference](api.md)
for the compatibility surface. Imports from internal modules may change without a
major release unless separately documented.

The undocumented `LlamIndexToolProvider` was removed. Implement custom providers
with `ToolProvider`, or use `MCPToolProvider`.

## Async and provider behavior

- Memory methods and model/provider interaction are asynchronous.
- Tool calls return `ToolOutput`; MCP scalar text is decoded to its scalar value.
- Runtime configuration is captured in `ArboristConfig` rather than repeatedly
  reading environment variables during evaluation.
- Invalid generated JSON or ASTs receive bounded validation retries. Configure
  this with `ArboristConfig(validation_retries=...)`.

## AST compatibility

Serialized programs remain schema version `1.0`. Lambda placeholders must match
their declared parameter names. Map and filter lambdas take one parameter; reduce
lambdas take accumulator and item parameters.

In 0.10.1, a null reduce accumulator adopts standard fold behavior: the first
iterable item initializes the accumulator and iteration begins with the second.
Use a non-null accumulator value when every item must be processed against an
explicit initializer.

AST evaluation no longer mutates shared nodes when injecting arguments. Code that
relied on inspecting mutated placeholder values after execution must instead use
the evaluation result or explicit tracing hooks.

## Development commands

Replace Poetry commands and `poetry.lock` with the committed uv environment:

```sh
uv sync --frozen --all-groups
make check
uv run python evaluation/eval.py
```
