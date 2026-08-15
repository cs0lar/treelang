# ADR 0004: Add recursion through a version 2 schema and explicit-stack runtime

- Status: Accepted
- Date: 2026-07-24

## Context

Version 1 models every named function as an external provider tool call. Lambda
parameters are placeholders used only by map, filter, and reduce. It has no user
function declarations, variable-reference expression, or call frame, so it
cannot express recursion without changing the meaning of existing serialized
programs.

Using Python calls or coroutine recursion directly would also expose evaluation
to the host recursion limit before Treelang can reliably enforce its own resource
policy. Structural AST depth is not recursive call depth: a small tree can call
itself indefinitely.

## Decision

Recursive programs use an opt-in schema version `2.0`. Version 1 remains the
current executable and model-generated schema until version 2 execution is
implemented and deliberately promoted.

Version 2 separates:

- `function_definition`, a globally declared function with positional parameters;
- `call`, a positional call to a user-defined function;
- `tool_call`, a named-argument call to an external provider tool;
- `variable`, a lexical parameter reference;
- `literal` and lazy `conditional` expressions.

Declarations are visible throughout the program, including to definitions that
appear earlier, so direct and mutual recursion are valid. Function names and
parameter names are identifiers. Function names are unique, parameters within a
function are unique, user calls must resolve with exact arity, and variables must
resolve in the current function's parameter scope. There are no implicit globals,
closures, assignment, or higher-order functions. User and tool namespaces are
structurally distinct, so the same spelling is unambiguous.

Arguments are evaluated in the caller's scope before a callee frame is created.
Conditionals evaluate only the selected branch. User functions may call tools,
but tool calls cannot implicitly invoke user functions.

Execution will use an explicit stack of interpreter frames rather than Python
recursion. Each frame records its expression continuation, lexical bindings, and
pending child results. A future `max_call_depth` execution limit will bound active
user call frames independently of `max_depth`, which continues to mean structural
evaluation depth. Node, tool-call, concurrency, cancellation, and wall-clock
budgets remain shared across the complete invocation. Recursive execution must
not ship until call depth is enforceable.

Version 2 execution is available through the opt-in
`treelang.trees.execution_v2.execute_v2` API and through `treelang.AST` when a
program explicitly declares `schema_version: "2.0"`. Parsing, representation,
evaluation, traversal, and callable compilation dispatch by the typed program
version; model generation remains an explicit Arborist configuration choice.

## Consequences

- Version 1 data and execution retain their existing meaning.
- Static errors such as unknown calls, incorrect arity, and unbound variables fail
  before runtime.
- Direct and mutual recursion share one language contract.
- Provider tools cannot be confused with user functions.
- The interpreter can enforce Treelang limits without depending on Python's call
  stack.
- Promoting version 2 requires an explicit compatibility and migration decision.
