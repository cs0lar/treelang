# ADR 0002: Execute ASTs with isolated async contexts

- Status: Accepted
- Date: 2026-07-21
- Amended: 2026-07-25

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

Execution can receive immutable `ExecutionLimits`. Omitted fields are unlimited
to preserve compatibility. A fresh shared budget is created for every direct or
compiled invocation and counts:

- every dynamic node evaluation, including repeated lambda bodies;
- one-based structural evaluation depth;
- provider tool invocations, excluding metadata lookup;
- concurrently evaluated sibling operations; and
- elapsed wall-clock duration.

Configured maxima are inclusive. Crossing a maximum raises
`ExecutionLimitError`, including `wall_clock_seconds` when Treelang's deadline
expires. A provider-raised `TimeoutError` remains a provider error, and external
cancellation is never translated. Separate invocations never share counters.
When concurrency is bounded, nested sibling operations inside an active budget
slot execute sequentially to prevent permit deadlock.

Version 2 additionally limits active user-function frames with
`max_call_depth`. This is independent of structural `max_depth`: repeated
evaluation of the same declared body retains its static program-relative depth,
while each recursive call increases call depth.

## Consequences

- The same tree can be invoked concurrently without corrupting later calls.
- Lambda placeholder names are semantic and validated before execution.
- Conditional branches are lazy, while function parameters and parallel program
  bodies may execute concurrently.
- Generated or untrusted trees can be constrained without changing their schema.
- Resource limits are runtime policy and are not serialized into version 1 ASTs.
- Future execution optimizations must preserve these observable semantics.

Retries are opt-in and only apply to tools explicitly declared idempotent by the
caller. Arguments are evaluated once, every physical attempt consumes the
tool-call budget, retry backoff is cancellable, and cancellation itself is never
retried. The default parallel failure mode cancels and awaits unfinished siblings
before raising. An opt-in collection mode returns ordered success/failure outcomes
and is rejected for single-mode programs.

Deterministic replay fixtures are ordered and validate complete model requests or
tool arguments. Drift and unconsumed entries are errors. Fixture persistence is an
application concern because request and response content may be sensitive.
