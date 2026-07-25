# Experimental recursive programs

Treelang schema version 2 is an opt-in preview. It supports declared user
functions, lexical parameters, user calls, external tool calls, literals, and
lazy conditionals. Version 1 remains the current root API and the default format
produced by `OpenAIArborist`.

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
wall-clock limits. Compilation into tools, traversal helpers, tree descriptions,
and the stable root API do not support version 2 yet.
