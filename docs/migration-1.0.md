# Migrating to Treelang 1.0

Treelang 1.0 makes the version 1 language contract, supported root exports,
execution semantics, provider interfaces, CLI behavior, and distributed JSON
Schema stable compatibility surfaces. There are no intentional breaking changes
from 0.10.2 for applications using supported APIs and schema version 1.0.

## Upgrade

```sh
python -m pip install --upgrade "treelang==1.0.0"
```

Anthropic remains optional:

```sh
python -m pip install --upgrade "treelang[anthropic]==1.0.0"
```

Python 3.12 or newer is required.

## Keep schema version 1 explicit

Existing serialized programs continue to use:

```json
{
  "type": "program",
  "body": [
    {
      "type": "value",
      "name": "answer",
      "value": 42
    }
  ],
  "mode": "single",
  "schema_version": "1.0"
}
```

Version 1 behavior remains the default for parsing and model generation. The
recursive version 2 language is opt-in:

```python
from treelang.ai.config import ArboristConfig

config = ArboristConfig(
    model="gpt-4o-2024-11-20",
    schema_version="2.0",
)
```

Do not relabel a version 1 program as version 2; its node vocabulary and call
semantics are intentionally different. Use the
[recursive-program guide](recursive-programs.md) when adopting v2.

## Adopt execution limits

Historical unlimited execution remains the compatibility default. Apply limits
when executing generated, persisted, or otherwise untrusted programs:

```python
from treelang import AST, ExecutionLimits

result = await AST.eval(
    program,
    provider,
    limits=ExecutionLimits(
        max_nodes=1_000,
        max_depth=50,
        max_call_depth=25,
        max_tool_calls=100,
        max_concurrency=10,
        timeout_seconds=30,
    ),
)
```

`max_call_depth` applies to schema v2 user functions. Limit violations raise
`ExecutionLimitError`.

## Check custom tool providers

Treelang now validates complete tool input schemas before invocation. Custom
providers should return `input_schema` with required fields, nested constraints,
formats, and additional-property rules, then return values through `ToolOutput`.

Run the reusable downstream contract:

```python
from treelang.testing import ToolProviderContract

await ToolProviderContract(tools=(definition,)).verify(provider)
```

See the [extension guide](extensions.md) for the full provider checklist.

## Check model transports

Custom model transports should expose provider-neutral completion and streaming,
consume-once `ModelUsage`, conservative `ModelCapabilities`, cancellation, and
normalized transport errors. Validate them with `ModelTransportContract`.

OpenAI remains the default transport. Install the optional Anthropic dependency
and inject `AnthropicTransport` to use Claude without changing application-level
Arborist orchestration.

## Use stable artifacts

The `treelang` command can validate and inspect existing programs:

```sh
treelang validate program.json
treelang inspect program.json
treelang execute program.json --max-nodes 1000 --timeout 30
```

Canonical schemas are available through `treelang schema`,
`load_json_schema()`, packaged JSON files, and the versioned documentation site.
Use the [JSON Schema guide](json-schema.md) for editor integration.

## Error handling

Catch public domain errors from the package root. In particular:

- `ExecutionLimitError` indicates a configured budget was exceeded;
- `ASTValidationError` indicates a program or evaluated tool contract failed;
- `ModelAuthenticationError`, `ModelRateLimitError`, `ModelTimeoutError`, and
  `ModelConnectionError` identify normalized provider failures;
- `ReplayMismatchError` indicates deterministic replay drift.

Cancellation remains cooperative and propagates rather than being wrapped as an
ordinary provider failure.

## Verify the migration

Run the normal project gate and deterministic evaluation:

```sh
make check
uv run python evaluation/eval.py
```

Applications with live-model coverage should run the owner-only live evaluation
against their selected provider and model before production deployment.
