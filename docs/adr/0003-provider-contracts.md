# ADR 0003: Separate provider and model transports

- Status: Accepted
- Date: 2026-07-21
- Amended: 2026-07-25

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

Transports may implement the separate `CapabilityAwareTransport` protocol to
declare model-specific features without coupling negotiation to orchestration.
Strict structured output has three policies: `auto` selects strict JSON Schema
when declared and otherwise uses compatibility JSON mode; `required` refuses an
incapable transport; and `compatibility` always uses JSON mode. An `auto` request
may downgrade after `StructuredOutputUnsupportedError`, but unrelated provider
errors never trigger fallback.

Strict output uses a closed projection of the runtime AST schema. Unsupported
schema annotations and free-form JSON objects are excluded, optional fields are
required but nullable, and version 2 external calls are specialized to the tools
selected for that request. Runtime Pydantic validation still runs on every model
response, including strict responses and repaired compatibility responses.

Structured observability wraps both boundaries and redacts prompts, model output,
tool arguments, results, and credential-shaped values by default.

## Consequences

- Core orchestration and evaluation can use deterministic fake transports and
  providers without network credentials.
- New providers must implement the same typed behavior and error expectations.
- Legacy transports remain compatible and conservatively advertise no optional
  capabilities.
- Capability negotiation does not change AST execution semantics.
