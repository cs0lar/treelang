# OpenAI Responses API

Treelang can use OpenAI's Responses API to compile a user request into a
complete, validated AST before any external tool executes. This path is useful
for reasoning-capable models and is explicit so existing Chat Completions users
do not change transport unexpectedly.

```python
from treelang.ai.arborist import ArboristConfig, EvalType, OpenAIArborist

config = ArboristConfig(
    model="gpt-5.6-terra",
    openai_api="responses",
    reasoning_effort="medium",
    schema_version="2.0",
    structured_output_mode="required",
)
arborist = OpenAIArborist(
    model=config.model,
    provider=provider,
    config=config,
    execution_limits=limits,
)

tree = (await arborist.eval("Build the requested workflow", EvalType.TREE)).content
```

`schema_version="2.0"` is recommended when the requested program needs named
arguments, user functions, lexical variables, or recursion. It is not required
by the Responses transport: schema version 1 remains supported for compatibility.

## Compiler vocabulary, not function calls

The configured tool selector still chooses the relevant provider-neutral tool
definitions. In both Responses and Chat Completions modes, Treelang serializes
their names, descriptions, and complete input JSON Schemas into the model
instructions. It does not register them as OpenAI function tools because the
model must not execute anything during generation. The sole requested output is
a Treelang AST. Schema property order is preserved because schema version 1 uses
that order when compiling positional function arguments.

After generation, Treelang performs the same AST validation, pruning, execution,
and complete tool-input validation used by the existing path. Intermediate tool
results remain local and are never sent back to the model.

## Compatibility and evaluation

Chat Completions remains the default. `reasoning_effort` is rejected unless
`openai_api="responses"`, preventing a configuration from being silently ignored.
Supported values are `none`, `low`, `medium`, `high`, and `xhigh`; actual model
support remains model-dependent.

Compare paths with the credentialed live harness:

```sh
uv run python evaluation/live_eval.py \
  --provider openai \
  --model gpt-5.6-terra \
  --openai-api responses \
  --reasoning-effort medium \
  --output evaluation-results/responses-medium.json
```

Benchmark output records `model_api` and `reasoning_effort` alongside semantic
correctness, latency, token use, and estimated cost. Treat reasoning quality as
an empirical result rather than an assumed improvement.

The Responses request follows OpenAI's documented `instructions`, `input`,
`reasoning`, and `text.format` fields and reads the SDK's aggregate `output_text`.
See the [official OpenAI Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create).
