# End-to-end cookbooks

The repository's notebooks progress from credential-free execution to live model
generation. Launch them from the repository root:

```sh
uv sync --frozen --all-groups
uv run jupyter notebook cookbook/
```

## Learning path

1. [Credential-free quickstart](https://github.com/cs0lar/treelang/blob/dev/cookbook/quickstart.ipynb)
   validates, inspects, and executes a complete program with
   `FakeToolProvider`.
2. [Custom provider](https://github.com/cs0lar/treelang/blob/dev/cookbook/custom-provider.ipynb)
   implements `ToolProvider`, runs the reusable provider contract, and executes
   a program through the extension.
3. [Calculator](https://github.com/cs0lar/treelang/blob/dev/cookbook/calculator.ipynb)
   connects to a local MCP server and asks a configured OpenAI model to generate
   arithmetic, higher-order, and conditional programs.
4. [Memory](https://github.com/cs0lar/treelang/blob/dev/cookbook/memory.ipynb)
   adds conversational memory to model-backed generation.
5. [Game statistics](https://github.com/cs0lar/treelang/blob/dev/cookbook/gamestats.ipynb)
   composes local MCP tools into a data-processing workflow.

The first two tutorials need no credentials or network access and execute fully
in normal CI. The remaining notebooks require `OPENAI_API_KEY`; CI validates
their notebook structure, cleanliness, Python syntax, server paths, and
deterministic MCP tools without making model calls.

## CI execution contract

A notebook opts into credential-free execution with:

```json
{
  "metadata": {
    "treelang": {
      "ci_execute": true
    }
  }
}
```

`make cookbooks` rejects committed cell outputs or execution counts, compiles
every code cell, and executes each opted-in notebook in memory from the
repository root. The executed notebook is never written back to the working
tree.

When adding a tutorial:

1. State its learning goal and prerequisites in the first Markdown cell.
2. Keep every code cell independently readable and use assertions for important
   outcomes.
3. Prefer `treelang.testing` fakes for deterministic examples.
4. Mark it `ci_execute` only when it needs no credentials, network, or external
   service.
5. Clear all outputs and execution counts before committing.
6. Add it to this learning path and run `make cookbooks`.
