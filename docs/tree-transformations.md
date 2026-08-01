# Tree transformations

Treelang provides immutable transformation records and a conservative default
pruner. Transformations operate locally and do not require a model transport or
tool-provider credentials.

## Conservative pruning

`prune_tree()` currently performs two schema version 2 rewrites:

1. It replaces a conditional whose condition is a literal boolean with the
   selected branch.
2. It removes user-function definitions that are not transitively reachable from
   the program body after conditional simplification.

```python
from treelang import prune_tree
from treelang.trees.schemas.v2 import (
    TreeConditional,
    TreeFunctionDefinition,
    TreeLiteral,
    TreeProgram,
)

program = TreeProgram(
    definitions=[
        TreeFunctionDefinition(
            name="unused",
            body=TreeLiteral(value="never called"),
        )
    ],
    body=[
        TreeConditional(
            condition=TreeLiteral(value=True),
            true_branch=TreeLiteral(value=42),
            false_branch=TreeLiteral(value=0),
        )
    ],
)

result = prune_tree(program)
assert result.tree.body == [TreeLiteral(value=42)]
assert result.tree.definitions == []
assert result.changed
```

The input remains unchanged. Every returned version 2 program is validated as a
complete program, and `result.lineage` records the ordered passes and structural
paths of their changes. Paths refer to the input of the pass that reported them.
Running the pruner again produces the same tree with no reported changes.

Version 1 trees are returned unchanged because their mutable, tool-oriented
language does not currently provide equally unambiguous structural rewrites.

## Safety boundary

The conservative pruner never calls tools, folds tool results, combines repeated
tool calls, or assumes that a tool is pure. Simplifying a literal conditional can
discard its unreachable branch, just as normal execution would skip that branch.

Pruning can reduce node and depth consumption. Applications that treat an exact
execution-budget failure as part of their observable behavior should evaluate
the original program instead.
