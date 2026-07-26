# Normalized model transport contracts

Treelang's OpenAI and Anthropic adapters implement the same completion,
streaming, capability, usage, cancellation, and error contracts.

## Usage

`UsageAwareTransport.consume_usage()` returns `ModelUsage` with normalized
`prompt_tokens` and `completion_tokens`. Completion and streaming calls both
publish usage in the current async context. Consuming it resets that context to
zero, and beginning a new call clears earlier usage even if the new call fails,
so concurrent evaluations do not overwrite each other.

Provider-specific fields retain their provider meanings. Treelang does not fold
cache-read, cache-write, reasoning, or server-tool counters into these two values.
Cost calculations must therefore use provider-specific prices and policies.

## Errors

Known SDK failures are translated at the adapter boundary:

| Condition | Treelang exception |
|---|---|
| Authentication or authorization | `ModelAuthenticationError` |
| Rate limit / HTTP 429 | `ModelRateLimitError` |
| Provider SDK timeout | `ModelTimeoutError` |
| Connection failure | `ModelConnectionError` |
| Other provider SDK or HTTP failure | `ModelTransportError` |
| Invalid or incomplete successful response | `ProviderResponseError` |
| Explicit rejection of strict output | `StructuredOutputUnsupportedError` |

Every normalized transport error includes `provider`, optional `status_code`, and
an optional numeric `retry_after`. The original SDK exception is retained as the
exception cause. Messages may contain provider request identifiers but Treelang
does not add request content, credentials, or tool arguments to them.

`ModelTimeoutError` is also a `TimeoutError`, preserving the standard timeout
catch boundary. It differs from the plain `TimeoutError` raised when Treelang's
configured orchestration deadline expires.

## Cancellation and fallback

`asyncio.CancelledError` is never translated, retried, or converted to a response.
Both completion and streaming release control through their SDK cancellation
paths.

Structured-output fallback remains narrower than general error translation. In
`auto` mode only `StructuredOutputUnsupportedError` permits one compatibility
request. Authentication, rate limits, timeouts, cancellation, connection errors,
and unrelated bad requests never downgrade structured output.
