# Extension and provider contribution guide

Treelang separates application tools, model transports, selection, memory, and
language execution. Extend the narrowest relevant interface and preserve
provider-neutral behavior above that boundary.

## Tool providers

Implement `ToolProvider` when tools come from a registry other than MCP:

```python
from treelang import ToolOutput, ToolProvider


class MyProvider(ToolProvider):
    async def list_tools(self):
        self.tools = {
            "lookup": {
                "name": "lookup",
                "description": "Look up one key.",
                "input_schema": {
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                    "required": ["key"],
                    "additionalProperties": False,
                },
            }
        }
        return list(self.tools.values())

    async def call_tool(self, name, arguments):
        value = await my_registry.call(name, arguments)
        return ToolOutput(content=value)
```

Requirements:

- return complete JSON Schema input metadata so Treelang can validate evaluated
  arguments before invocation;
- populate `self.tools` during discovery so direct lookup remains consistent;
- return `ToolOutput`, preserving structured JSON-compatible values;
- translate registry failures into `ToolNotFoundError`,
  `ToolExecutionError`, or `ProviderResponseError`;
- preserve cancellation rather than swallowing `CancelledError`.

Run `ToolProviderContract` from [`treelang.testing`](testing.md) against the
adapter and add focused failure and cancellation tests.

## Model transports

A model adapter implements the provider-neutral `ModelTransport` protocol:

```python
class MyModelTransport:
    async def complete(self, request):
        ...

    async def stream(self, request):
        yield ...
```

Supported adapters should also implement:

- `consume_usage()` with consume-once `ModelUsage`;
- `capabilities(model)` returning conservative `ModelCapabilities`;
- provider SDK timeout, authentication, connection, rate-limit, and response
  translation using Treelang's public exception hierarchy;
- non-empty text chunks for streaming and plain text for completion;
- cancellation propagation and configured timeout behavior;
- strict structured-output translation with
  `StructuredOutputUnsupportedError` only for a genuine capability rejection.

Use `ModelTransportContract` for completion, streaming, and usage conformance.
Provider-specific tests must additionally cover request translation, error
translation, strict-output rejection, timeout, and cancellation.

## Provider contribution checklist

A pull request adding a supported model provider must:

1. keep SDK dependencies optional unless they are required by the default
   installation;
2. add capability negotiation without provider-name branches in Arborist;
3. pass the shared downstream model contract;
4. add the provider to `docs/providers.json` and regenerate the matrix;
5. document installation, credentials, supported models, and limitations;
6. make the versioned live-evaluation runner selectable for the provider;
7. run the same live dataset and attach the workflow evidence when credentials
   are available;
8. note compatibility, cost, and security implications in the PR.

## Selectors and memory

Implement `BaseToolSelector.select()` to choose from provider tool definitions
without invoking tools. Implement the asynchronous `Memory` interface for
conversation history. Both extensions should remain deterministic under fake
providers/transports and must not log prompt or tool content by default.

## Language and schema extensions

Changing node fields or execution semantics is not a provider extension.
Preserve schema version 1 compatibility and add new language behavior through an
explicit schema version. Update models, traversal, execution, generated JSON
Schema artifacts, CLI validation, property tests, documentation, migration
guidance, and evaluation cases together.

## Development workflow

Create work from `dev`, add characterization and regression tests, and run:

```sh
uv sync --frozen --all-groups
make format
make check
```

Provider work should also run the relevant focused contract tests and, where
possible, the owner-only live evaluation. Pull requests target `dev` and follow
the repository's [contribution workflow](https://github.com/cs0lar/treelang/blob/dev/CONTRIBUTING.md).
