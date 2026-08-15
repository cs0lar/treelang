# Experimental recursive programs

Treelang schema version 2 is an opt-in preview. It supports declared user
functions, lexical parameters, user calls, external tool calls, literals, and
lazy conditionals. Version 1 remains the default format produced by
`OpenAIArborist`; root `AST` helpers dispatch explicit version 2 programs to the
v2 implementation.

To opt into model generation, select schema version 2 and provide mandatory
runtime limits before using `WALK`:

```python
from treelang import ExecutionLimits
from treelang.ai.arborist import ArboristConfig, OpenAIArborist

arborist = OpenAIArborist(
    model="gpt-4o",
    provider=provider,
    config=ArboristConfig(model="gpt-4o", schema_version="2.0"),
    execution_limits=ExecutionLimits(
        max_call_depth=100,
        max_nodes=10_000,
        max_tool_calls=1_000,
        timeout_seconds=30,
    ),
)
response = await arborist.eval("Calculate 10 factorial recursively.")
```

`TREE` mode can return a validated v2 program without execution limits, allowing
an application to inspect it before deciding whether and how to run it. V2
generation uses its own schema, rules, and recursive examples. Invalid model
responses enter the configured validated-repair loop.

The deterministic direct- and mutual-recursion benchmark can be reproduced with:

```sh
uv run python evaluation/eval.py \
  --dataset evaluation/data/v2/offline-recursion.json \
  --baseline evaluation/baselines/v2/offline-recursion.json \
  --tolerances evaluation/baselines/v2/tolerances.json
```

Validate a version 2 program before executing it:

```python
from treelang import ExecutionLimits
from treelang.trees.execution_v2 import execute_v2
from treelang.trees.schemas.v2 import AST

program = AST.model_validate(
    {
        "type": "program",
        "schema_version": "2.0",
        "definitions": [
            {
                "type": "function_definition",
                "name": "countdown",
                "params": ["n"],
                "body": {
                    "type": "conditional",
                    "condition": {
                        "type": "tool_call",
                        "tool": "less_than_or_equal",
                        "arguments": {
                            "a": {"type": "variable", "name": "n"},
                            "b": {"type": "literal", "value": 0},
                        },
                    },
                    "true_branch": {"type": "literal", "value": 0},
                    "false_branch": {
                        "type": "call",
                        "function": "countdown",
                        "arguments": [
                            {
                                "type": "tool_call",
                                "tool": "subtract",
                                "arguments": {
                                    "a": {"type": "variable", "name": "n"},
                                    "b": {"type": "literal", "value": 1},
                                },
                            }
                        ],
                    },
                },
            }
        ],
        "body": [
            {
                "type": "call",
                "function": "countdown",
                "arguments": [{"type": "literal", "value": 100}],
            }
        ],
        "mode": "single",
    }
)

result = await execute_v2(
    program,
    provider,
    limits=ExecutionLimits(
        max_call_depth=101,
        max_nodes=1_000,
        max_tool_calls=200,
        timeout_seconds=10,
    ),
)
```

`max_call_depth` is inclusive and counts active user-function calls. It is
separate from `max_depth`, which constrains the declared expression structure.
All limits and counters are shared across the program invocation.

The version 2 interpreter uses explicit frames rather than Python recursion, but
recursive programs should always configure call-depth, node, tool-call, and
wall-clock limits.

## Parse, traverse, compile, and describe

`AST.parse()` detects an explicit `schema_version: "2.0"`; `AST.repr()`,
`AST.eval()`, `AST.visit()`, `AST.avisit()`, and `AST.tool()` then accept the
validated v2 program. `EvalResponse.describe()` returns a new described program
because v2 models are immutable, and also replaces `response.content` with that
new value. The original program is never mutated.

V2 compilation preserves closed lexical scope: literals are constants, not free
variables. A literal occupying a named external-tool argument becomes an
overridable keyword-only default using that argument name. A literal passed
directly to a user function uses the corresponding declared parameter name.
Nested computations expose their own named argument slots, while literals in
unnamed positions remain constants. Duplicate names receive stable `_2`, `_3`,
and subsequent suffixes. Mutable defaults are deep-copied for every invocation.

```python
program = AST.parse(program_json)
compiled = await AST.tool(program, provider, limits=limits)

# Uses the literal embedded in the saved program.
default_result = await compiled()

# Overrides a named root user-function argument without changing the program.
custom_result = await compiled(n=25)
```
