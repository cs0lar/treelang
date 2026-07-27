# Downstream testing kit

`treelang.testing` provides deterministic fakes and framework-neutral contract
suites for applications and third-party provider adapters. It is included in the
normal package and does not require credentials, network access, or pytest.

## Fake model transport

Queue completion and streaming responses with normalized usage:

```python
from treelang import ModelUsage
from treelang.testing import FakeCompletion, FakeModelTransport, FakeStream

transport = FakeModelTransport(
    completions=[
        FakeCompletion(
            '{"type":"program","body":[]}',
            ModelUsage(prompt_tokens=10, completion_tokens=4),
        )
    ],
    streams=[FakeStream(("first", "second"))],
)
```

The fake records deep-copied `completion_requests` and `stream_requests`.
`consume_usage()` clears usage just like supported live adapters, and
`assert_consumed()` detects unused responses.

## Fake tool provider

```python
from treelang.testing import FakeToolProvider

provider = FakeToolProvider(
    [
        {
            "name": "double",
            "properties": {"value": {"type": "number"}},
        }
    ],
    results={"double": lambda arguments: arguments["value"] * 2},
)
```

Results may be values, exceptions, synchronous callables, or asynchronous
callables. Every invocation is available in `provider.calls`.

## Model transport contract

Contract objects are asynchronous and test-framework neutral:

```python
from treelang import ModelUsage
from treelang.testing import (
    CompletionContract,
    ModelTransportContract,
    StreamContract,
)

contract = ModelTransportContract(
    completion=CompletionContract(
        request={"model": "test", "messages": []},
        response="complete",
        usage=ModelUsage(2, 1),
    ),
    stream=StreamContract(
        request={"model": "test", "messages": []},
        chunks=("one", "two"),
        usage=ModelUsage(3, 2),
    ),
)

await contract.verify(transport, transport)
```

The suite verifies completion and stream types, exact content, normalized usage,
and consume-once usage behavior. Treelang runs this same suite continuously
against its OpenAI and Anthropic adapters.

## Tool provider contract

`ToolProviderContract` verifies normalized discovery, direct definition lookup,
and provider-neutral `ToolOutput` values:

```python
from treelang.testing import ToolCallContract, ToolProviderContract

contract = ToolProviderContract(
    tools=(tool_definition,),
    calls=(ToolCallContract("double", {"value": 2}, 4),),
)
await contract.verify(provider)
```

Contract failures raise `AssertionError`, so they work naturally with pytest,
unittest, or a custom asynchronous test harness.
