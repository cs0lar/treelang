# Treelang Documentation

- [Supported API reference](api.md) — generated from `treelang.__all__`.
- [Migration guide](migration-0.10.md) — compatibility guidance for the 0.10 series.
- [Experimental recursive programs](recursive-programs.md) — validate and execute
  opt-in schema version 2 programs with explicit safety budgets.
- [Structured model output](structured-output.md) — strict JSON Schema capability
  negotiation, fallback policy, and compatibility mode.
- [Tool input validation](tool-input-validation.md) — full pre-invocation JSON
  Schema enforcement for v1 and v2 execution.
- [Execution resilience and replay](execution-resilience.md) — configure safe
  retries, parallel partial failures, cancellation, and offline replay.
- [Model capability negotiation](provider-capabilities.md) — declare transport
  features and customize provider-neutral request policy.
- [Anthropic transport](anthropic.md) — install and use the optional Claude
  Messages API adapter.
- Architecture decisions:
  - [ADR 0001: Version the serialized AST schema](adr/0001-schema-versioning.md)
  - [ADR 0002: Execute ASTs with isolated async contexts](adr/0002-execution-semantics.md)
  - [ADR 0003: Separate provider and model transports](adr/0003-provider-contracts.md)
  - [ADR 0004: Add recursion through a version 2 schema and explicit-stack runtime](adr/0004-recursive-schema-and-execution.md)

Run `make docs` after changing the supported public API. `make check` and CI
verify that the committed reference is current.
