# ADR 0003: Separate provider and model transports

- Status: Accepted
- Date: 2026-07-21

## Context

Tool discovery/execution and model completion have different responsibilities,
failure modes, and security boundaries. Coupling both to one SDK made deterministic
testing difficult and spread provider-specific configuration through orchestration.

## Decision

`ToolProvider` owns typed tool discovery and invocation. Definitions contain a
name, optional description, and ordered input properties. AST function parameters
are positional and are paired with that property order. Calls return `ToolOutput`;
provider adapters translate SDK-specific responses and errors at this boundary.

`ModelTransport` owns text completion and streaming. `OpenAIArborist` receives its
transport and immutable `ArboristConfig`, builds requests, validates model output,
and optionally retries only invalid JSON or AST responses. Cancellation, timeouts,
and provider failures are not treated as validation retries.

Structured observability wraps both boundaries and redacts prompts, model output,
tool arguments, results, and credential-shaped values by default.

## Consequences

- Core orchestration and evaluation can use deterministic fake transports and
  providers without network credentials.
- New providers must implement the same typed behavior and error expectations.
- Provider capability negotiation remains future work and must not leak into AST
  execution semantics.
