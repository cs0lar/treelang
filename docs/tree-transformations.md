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

## Expression grafting

Schema version 2 expressions can be replaced immutably using a `TreePath`:

```python
from treelang import TreePath, graft_expression
from treelang.trees.schemas.v2 import TreeLiteral, TreeProgram

program = TreeProgram(body=[TreeLiteral(value=1)])
result = graft_expression(
    program,
    TreeLiteral(value=42),
    at=TreePath(("body", 0)),
)
```

Paths must identify expressions rather than program fields or argument
containers. Grafts into function bodies may refer to parameters in that lexical
scope. Grafts elsewhere containing unbound variables, calls with invalid arity,
or references to unknown user functions are rejected by complete-program
validation.

Use `wrap_expression()` when the existing expression should be nested inside a
larger expression. Every variable matching the chosen placeholder is replaced:

```python
from treelang import wrap_expression
from treelang.trees.schemas.v2 import TreeToolCall, TreeVariable

wrapper = TreeToolCall(
    tool="square",
    arguments={"value": TreeVariable(name="input")},
)
wrapped = wrap_expression(
    program,
    wrapper,
    at=TreePath(("body", 0)),
    placeholder="input",
)
```

The placeholder must occur at least once and is removed before lexical-scope
validation. Wrapping does not call the referenced tool or assume anything about
its effects.

### Structural limits

`TransformationLimits` can reject a result whose static program structure is too
large or deep:

```python
from treelang import TransformationLimits

limits = TransformationLimits(max_nodes=100, max_depth=12)
```

The node count includes the program, function definitions, and expressions.
Depth starts at one for the program; root body expressions are at depth two and
function bodies are at depth three. Limits are inclusive and are separate from
dynamic execution budgets such as recursive call depth and tool-call count.

## Program composition

`compose_programs()` combines two or more independently valid schema version 2
programs. Definitions and root expressions retain source-program order, while
the caller explicitly selects sequential or parallel execution:

```python
from treelang import compose_programs

combined = compose_programs(
    [first_program, second_program],
    mode="parallel",
    name="Combined report",
    description="Run two independent reports concurrently.",
)
```

Each input must validate on its own. Composition does not resolve an unknown call
in one input using a definition supplied by another; connect programs explicitly
with expression grafting when data or control flow should cross that boundary.

Function definitions share a global namespace in the combined program. Name
collisions are resolved deterministically with suffixes such as `_2`, and every
corresponding user call—including recursive calls—is rewritten. Names belonging
to untouched incoming definitions are reserved before suffix selection, avoiding
unnecessary cascading renames. Lexical parameters and variable references remain
inside their original function scope, and external tool names are never renamed.

The returned transformation record identifies inserted definitions and body
expressions at their output paths, plus every hygienic rename. The input programs
remain unchanged. `TransformationLimits` apply to the complete combined result.

## Arborist strategies

`BaseArborist` delegates transformations to injected, provider-independent
strategies. Its default pruner is `ConservativeTreePruner`, and its default
synchronous grower is `ProgramCompositionGrower`.

The compatibility methods return trees directly:

```python
pruned_tree = arborist.prune(program)
combined_tree = arborist.grow(first_program, second_program, mode="parallel")
```

Use the result-oriented methods when change records are required:

```python
pruning = arborist.prune_result(program)
growth = arborist.grow_result(
    [first_program, second_program],
    name="Combined program",
)
```

Custom synchronous strategies implement `TreePruner` or `TreeGrower` and are
injected as `pruning_strategy=` or `growth_strategy=`. Model-specific Arborists
therefore do not need to own deterministic rewriting logic.

Model-guided or evaluation-guided growth has a separate `AsyncTreeGrower`
contract and the `agrow()`/`agrow_result()` methods. Calling those methods without
an injected `async_growth_strategy` raises `NotImplementedError`; Treelang does
not silently introduce model calls into deterministic composition.

Historically, `OpenAIArborist.grow()` accepted no arguments and returned `None`.
That call remains a no-op with a `DeprecationWarning`; pass at least two schema v2
programs to use deterministic growth. The base-class zero-argument call continues
to raise `NotImplementedError`.

## Effects and duplicate computation

Tool definitions may declare `effects` containing `pure`, `deterministic`, and
`idempotent` boolean guarantees. These declarations are optional and conservative:
missing guarantees are treated as false.

`deduplicate_pure_tool_calls()` finds structurally identical, closed tool-call
expressions and wraps them in schema-v2 `memo` expressions only when every tool
in the expression declares both `pure=True` and `deterministic=True`. Calls using
lexical variables, user functions, undeclared tools, or incomplete guarantees are
left unchanged.

Memo values are isolated to one program invocation. Concurrent occurrences share
an async lock, so a successful expression executes once even in parallel mode;
failures and cancellation release the lock normally. Memo expressions must be
closed, and one key cannot identify different expressions. Arborist prompts do
not generate memo nodes directly: validated deterministic transformations add
them from trusted effect metadata.
