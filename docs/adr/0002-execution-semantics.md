# ADR 0002: Execute ASTs with isolated async contexts

- Status: Accepted
- Date: 2026-07-21

## Context

AST instances may be cached and evaluated concurrently. Mutating value nodes to
inject callable or lambda arguments caused shared-state races and made repeated
execution order-dependent.

## Decision

Evaluation is asynchronous and uses an immutable per-invocation
`ExecutionContext`. Named bindings resolve lambda parameters; identity bindings
resolve compiled-tool parameters without relying on globally unique leaf names.
Evaluation never mutates the AST to pass runtime values.

A single-mode program contains one composed root operation. Parallel mode
evaluates independent body nodes concurrently. Function parameters are evaluated
before one provider call. Conditionals evaluate only the selected branch. Map and
filter lambdas have one parameter; reduce lambdas have accumulator and item
parameters. A null reduce accumulator starts from the first item, while a non-null
value is an explicit initializer. Empty reductions return `None`.

Cancellation propagates. Configured model deadlines raise `TimeoutError`.
Provider, tool, validation, compilation, and execution failures use the public
exception hierarchy where a domain-specific boundary exists.

## Consequences

- The same tree can be invoked concurrently without corrupting later calls.
- Lambda placeholder names are semantic and validated before execution.
- Conditional branches are lazy, while function parameters and parallel program
  bodies may execute concurrently.
- Future execution optimizations must preserve these observable semantics.
