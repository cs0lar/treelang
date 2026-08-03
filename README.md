# 🌲 `treelang`

![PyPI - Version](https://img.shields.io/pypi/v/treelang?label=pypi%20package&color=green)
[![PyPI Downloads](https://static.pepy.tech/badge/treelang)](https://pepy.tech/projects/treelang)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Treelang is a small, typed orchestration language for the gap between simple
tool calling and a full workflow engine.

Most tool-using agents alternate between a model call and a tool call, sending
each result back to the model so it can choose the next step. Treelang takes a
different path: the model generates a complete, validated program first, then
your application executes that program locally against its tools. Intermediate
tool results stay in your process and do not return to the model.

That trade is especially useful when the workflow shape can be planned before
the data arrives: bulk operations, private-data processing, repeatable
automations, and tool compositions that need branching, mapping, filtering,
reduction, concurrency, or bounded recursion. The generated AST is a real
artifact—you can inspect it, reject it, apply resource limits, cache it, replay
it, or expose it as another tool.

## Highlights

- **Plan once, execute locally** — generate the complete tool program before
  execution instead of paying for a model round-trip after every tool result.
- **Keep the data plane out of the prompt** — customer records, financial
  values, internal search results, and other intermediate outputs flow between
  local nodes and tools without being sent back to the model.
- **Use real control flow** — validated ASTs support nested tool calls,
  conditionals, `map`, `filter`, `reduce`, parallel branches, and opt-in
  recursive functions.
- **Review the program before it runs** — serialize, diff, sign, cache, approve,
  replay, or reject a plan independently from model generation.
- **Put hard limits around generated code** — enforce node, depth, call, tool,
  concurrency, and wall-clock budgets; validate complete tool input schemas
  before invocation.
- **Bring your own models and tools** — OpenAI and Anthropic share the same
  orchestration contract; MCP and custom `ToolProvider` implementations share
  the same execution runtime.
- **Test without a model bill** — deterministic transports, tool fakes, replay
  fixtures, provider contract suites, and an offline benchmark ship with the
  project.

## What you can build

- **Private bulk operations** — fetch IDs, fan out over records, apply
  deterministic eligibility tools, and aggregate results without placing the
  underlying records in model context.
- **Finance and operations workflows** — compose invoice, pricing, inventory, or
  reconciliation tools into reviewable plans with explicit branches and
  execution budgets.
- **Reusable generated automations** — create a workflow for a user's intent,
  approve it once, then persist and rerun the same AST as inputs change.
- **MCP tool composition** — turn several narrow MCP tools into one higher-level
  callable tool without implementing a new orchestration service for every
  composition.
- **Controlled recursive jobs** — use opt-in schema v2 for bounded retries,
  hierarchical traversal, divide-and-conquer operations, or recursive business
  rules with a separate call-depth limit.
- **Auditable AI features** — store the proposed program separately from its
  execution evidence, then reproduce model and tool behavior with deterministic
  replay.

Treelang is not intended for open-ended agents that must repeatedly inspect
unstructured tool output and improvise their next action. It fits best when
tools expose the operations and predicates needed to express the decision logic,
and when local execution, privacy, repeatability, or auditability matter more
than continuous model deliberation.

## Quick start

### Requirements

- Python 3.12+
- An OpenAI API key for the example below, or install `treelang[anthropic]` and
  use the Anthropic transport
- A source of tools for production: an MCP server or a custom `ToolProvider`

### Install

```bash
pip install treelang
```

Treelang also installs a command-line interface:

```sh
treelang validate program.json
treelang inspect program.json
treelang execute program.json --max-nodes 1000 --timeout 10
```

See the [CLI guide](docs/cli.md) for replay fixtures, provider-backed generation,
and stable exit statuses.

Provider and application authors can import deterministic fakes and reusable,
framework-neutral contract suites from `treelang.testing`; see the
[testing-kit guide](docs/testing.md).

Canonical v1 and v2 JSON Schema files ship in the package and documentation site.
See the [editor-validation guide](docs/json-schema.md), or run
`treelang schema --schema-version 2.0`.

### Generate, inspect, then execute

This runnable example models a realistic data-minimization boundary: the model
can see the invoice tool definitions, but invoice IDs and balances appear only
during local execution. `FakeToolProvider` keeps the quick start self-contained;
replace it with `MCPToolProvider` or your own provider in an application.

```python
import asyncio

from treelang import AST, ExecutionLimits
from treelang.ai.arborist import OpenAIArborist
from treelang.ai.responses import EvalType
from treelang.testing import FakeToolProvider


async def main() -> None:
    balances = {1001: 850.0, 1002: 1_900.0, 1003: 400.0}
    provider = FakeToolProvider(
        tools=[
            {
                "name": "list_open_invoice_ids",
                "description": "Return the IDs of all currently open invoices.",
                "properties": {},
            },
            {
                "name": "get_invoice_balance",
                "description": "Return the outstanding balance for one invoice ID.",
                "properties": {"invoice_id": {"type": "integer"}},
            },
            {
                "name": "sum_values",
                "description": "Return the sum of a list of numbers.",
                "properties": {
                    "values": {"type": "array", "items": {"type": "number"}}
                },
            },
        ],
        results={
            "list_open_invoice_ids": list(balances),
            "get_invoice_balance": lambda args: balances[args["invoice_id"]],
            "sum_values": lambda args: sum(args["values"]),
        },
    )

    arborist = OpenAIArborist(
        model="gpt-4o-2024-11-20",
        provider=provider,
    )
    response = await arborist.eval(
        "Get every open invoice balance, then return their total.",
        EvalType.TREE,
    )

    # The model call is finished. Review or persist the program before it runs.
    tree = response.content
    print(AST.repr(tree))

    # Invoice IDs and balances now move only between local tools and AST nodes.
    total = await AST.eval(
        tree,
        provider,
        limits=ExecutionLimits(
            max_nodes=100,
            max_tool_calls=20,
            max_concurrency=5,
            timeout_seconds=10,
        ),
    )
    print(total)  # 3150.0


asyncio.run(main())
```

The exact generated tree can vary by model, but it must validate before Treelang
returns it. Asking for `EvalType.TREE` creates an explicit approval boundary;
use `EvalType.WALK` when immediate execution is appropriate. The
[credential-free quickstart notebook](cookbook/quickstart.ipynb) demonstrates
the same validate/inspect/execute lifecycle with no model call.

### Bound execution resources

Evaluation remains unlimited by default for compatibility. Applications that
execute generated or untrusted trees can apply one shared budget per invocation:

```python
from treelang import AST, ExecutionLimits

result = await AST.eval(
    tree,
    provider,
    limits=ExecutionLimits(
        max_nodes=1_000,
        max_depth=50,
        max_tool_calls=100,
        max_concurrency=10,
        timeout_seconds=30,
    ),
)
```

Exceeding any configured maximum raises `ExecutionLimitError`. External task
cancellation still propagates normally. Pass the same `limits` argument to
`AST.tool()` to apply a fresh budget to every invocation of a compiled tool.
Pass `execution_limits=...` to `OpenAIArborist` to enforce the policy whenever
`EvalType.WALK` executes a generated tree; `EvalType.TREE` only returns the tree
for inspection.

Experimental schema v2 recursion and opt-in model generation additionally support
`max_call_depth`; see the [recursive-program guide](docs/recursive-programs.md).

Arborist automatically uses provider-native strict JSON Schema output when the
transport declares support, while retaining validated JSON-mode fallback. Use
`ArboristConfig(structured_output_mode="required")` to prohibit fallback or
`"compatibility"` to force the legacy path. See the
[structured-output guide](docs/structured-output.md).

Evaluated tool arguments are validated against each provider's complete JSON
Schema before invocation. MCP schemas retain required fields, nested constraints,
formats, and additional-property rules; see the
[tool-input validation guide](docs/tool-input-validation.md).

## Tree-first workflow

1. **Generate** – `OpenAIArborist` assembles an AST using your available tools.
2. **Inspect** – represent the tree as JSON, describe it with `EvalResponse.describe()`, or pretty-print it using `AST.repr()`.
3. **Evaluate** – `AST.eval(tree, provider)` asynchronously executes every node; the LLM never sees intermediate values.
4. **Package** – `await AST.tool(tree, provider)` turns a tree into a callable tool so you can add it back to your MCP server.

## Architecture at a glance

- **Arborist (`treelang/ai/arborist.py`)** – orchestrates LLM calls, maintains history via the optional `Memory` interface, and decides whether to return ASTs or walked results.
- **Tool providers (`treelang/ai/provider.py`)** – abstract how tools are discovered/invoked. We ship an MCP client implementation and a template for custom providers.
- **Selectors (`treelang/ai/selector.py`)** – plug in your own tool filtering logic; `AllToolsSelector` ships by default.
- **Trees (`treelang/trees/tree.py`)** – validated node models plus helpers for
  async traversal, execution, representation, and compilation into callable
  tools.

## Resources & examples

- **Documentation** ([published site](https://cs0lar.github.io/treelang/)) contains the [supported API reference](docs/api.md),
  [architecture decisions](docs/README.md), and the
  [1.0 migration guide](docs/migration-1.0.md).
- **Cookbook notebooks** (`cookbook/`) provide a
  [tested end-to-end learning path](docs/cookbooks.md), from credential-free
  execution and custom providers to live model/MCP workflows.
- **Reproducible benchmark** (`evaluation/eval.py`) runs versioned deterministic
  cases without credentials, records machine-readable quality and resource
  metrics, and checks them against committed regression baselines. A separate
  owner-only manual live workflow records comparable OpenAI and Anthropic model
  quality, latency, token, and cost evidence without exposing credentials to
  pull requests. See
  [`evaluation/README.md`](evaluation/README.md) for commands and baseline policy.
- **Unit tests** (`tests/`) cover the AST core and are a good reference for expected behavior when extending nodes.

Install the locked development environment and launch the cookbook notebooks from
the repository root:

```sh
uv sync --frozen --all-groups
uv run jupyter notebook cookbook/
```

The calculator and game-stat notebooks call the configured OpenAI model and
therefore require `OPENAI_API_KEY`. Normal CI does not make live model calls: it
executes the credential-free quickstart and custom-provider tutorials, validates
that every notebook is clean and compilable, then starts the cookbook MCP
servers and exercises their deterministic tools. Run the same checks locally
with `make cookbooks` and `uv run pytest tests/test_cookbooks.py`. See the
[extension guide](docs/extensions.md) when contributing providers or other
integrations.

## Contributing & local development

We actively welcome contributions—see [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

Maintainers publish signed, provenance-attested releases through PyPI Trusted
Publishing. See [RELEASING.md](RELEASING.md) for versioning, promotion, publishing,
and verification instructions.
