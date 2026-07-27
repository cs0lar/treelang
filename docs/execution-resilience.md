# Execution resilience and deterministic replay

Treelang keeps its historical execution behavior by default: tool calls run once,
the first failure is raised, cancellation propagates, and successful programs
return their values directly. `ExecutionPolicy` enables retry and partial-result
behavior explicitly without changing serialized ASTs.

## Safe retries

Retries are disabled unless both conditions are met:

1. `max_attempts` is greater than one; and
2. the tool name is listed in `idempotent_tools`.

```python
from treelang import AST, ExecutionPolicy, RetryPolicy

policy = ExecutionPolicy(
    retry=RetryPolicy(
        max_attempts=3,
        delay_seconds=0.1,
        idempotent_tools=frozenset({"exchange_rate"}),
    )
)
result = await AST.eval(program, provider, policy=policy)
```

Treelang retries `ToolExecutionError` and `TimeoutError` by default. Applications
may replace `retryable_exceptions`, but should only include failures known to be
transient. Arguments are evaluated once and reused unchanged. Every physical
attempt consumes the tool-call budget. Cancellation is never retried and also
interrupts retry backoff.

A tool must not be declared idempotent unless repeating the same call has the same
externally observable effect. Mutating tools should normally remain single-shot.

## Parallel failures

The default `parallel_failures="raise"` is fail-fast. When one parallel branch
fails, Treelang cancels and awaits unfinished siblings before raising the original
error. This prevents background tool activity after execution has returned.

Set `parallel_failures="collect"` to return one ordered `BranchOutcome` per branch:

```python
from treelang import ExecutionPolicy

outcomes = await AST.eval(
    parallel_program,
    provider,
    policy=ExecutionPolicy(parallel_failures="collect"),
)
```

Each outcome contains either `success=True` and `value`, or `success=False` plus
the exception type and message. Collection is only valid for programs whose mode
is `parallel`; using it with `single` mode raises `ValueError`. External
cancellation always propagates rather than becoming an outcome.

## Offline replay

`ToolReplayProvider` and `ModelReplayTransport` consume ordered fixtures and
validate each tool argument or model request. Unexpected, reordered, changed, or
unconsumed entries raise `ReplayMismatchError`.

```python
from treelang import ToolReplayEntry, ToolReplayProvider

provider = ToolReplayProvider(
    tools=[tool_definition],
    entries=[
        ToolReplayEntry(
            name="exchange_rate",
            arguments={"base": "USD", "quote": "JPY"},
            output=150.0,
        )
    ],
)
result = await AST.eval(program, provider)
provider.assert_consumed()
```

Replay fixtures contain complete arguments, model requests, and outputs. Treat
them as potentially sensitive: redact secrets and personal data before committing
fixtures, just as for evaluation datasets.
