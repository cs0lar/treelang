from types import SimpleNamespace

import pytest

from treelang.ai.anthropic import AnthropicTransport
from treelang.ai.capabilities import ModelCapabilities
from treelang.ai.transport import ModelUsage, OpenAITransport
from treelang.testing import (
    CompletionContract,
    FakeCompletion,
    FakeModelTransport,
    FakeStream,
    FakeToolProvider,
    ModelTransportContract,
    StreamContract,
    ToolCall,
    ToolCallContract,
    ToolProviderContract,
)
from treelang.testing import __all__ as testing_exports

COMPLETION_REQUEST = {
    "model": "model-test",
    "messages": [{"role": "user", "content": "complete"}],
}
STREAM_REQUEST = {
    "model": "model-test",
    "messages": [{"role": "user", "content": "stream"}],
}
MODEL_CONTRACT = ModelTransportContract(
    completion=CompletionContract(
        request=COMPLETION_REQUEST,
        response="complete-response",
        usage=ModelUsage(prompt_tokens=5, completion_tokens=2),
    ),
    stream=StreamContract(
        request=STREAM_REQUEST,
        chunks=("one", "two"),
        usage=ModelUsage(prompt_tokens=7, completion_tokens=3),
    ),
)
IDENTITY_TOOL = {
    "name": "identity",
    "description": "Return the input.",
    "input_schema": {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
        "additionalProperties": False,
    },
}


def test_testing_package_declares_every_supported_fixture_and_contract():
    assert set(testing_exports) == {
        "CompletionContract",
        "FakeCompletion",
        "FakeModelTransport",
        "FakeStream",
        "FakeToolProvider",
        "FakeToolResult",
        "ModelTransportContract",
        "StreamContract",
        "ToolCall",
        "ToolCallContract",
        "ToolProviderContract",
    }


@pytest.mark.asyncio
async def test_fake_model_transport_satisfies_reusable_contract_and_records_requests():
    transport = FakeModelTransport(
        completions=[
            FakeCompletion(
                "complete-response",
                ModelUsage(prompt_tokens=5, completion_tokens=2),
            )
        ],
        streams=[
            FakeStream(
                ("one", "two"),
                ModelUsage(prompt_tokens=7, completion_tokens=3),
            )
        ],
        capabilities=ModelCapabilities(strict_json_schema=True),
    )

    await MODEL_CONTRACT.verify(transport, transport)

    assert transport.completion_requests == [COMPLETION_REQUEST]
    assert transport.stream_requests == [STREAM_REQUEST]
    assert transport.capabilities("any").strict_json_schema is True
    transport.assert_consumed()


@pytest.mark.asyncio
async def test_fake_model_transport_queues_failures_and_rejects_exhaustion():
    transport = FakeModelTransport(
        completions=[FakeCompletion(RuntimeError("unavailable"))]
    )

    with pytest.raises(RuntimeError, match="unavailable"):
        await transport.complete(COMPLETION_REQUEST)
    with pytest.raises(Exception, match="No fake completion"):
        await transport.complete(COMPLETION_REQUEST)


@pytest.mark.asyncio
async def test_fake_tool_provider_supports_values_functions_and_recorded_calls():
    async def increment(arguments):
        return arguments["value"] + 1

    provider = FakeToolProvider(
        [IDENTITY_TOOL],
        results={"identity": increment},
    )
    contract = ToolProviderContract(
        tools=(IDENTITY_TOOL,),
        calls=(ToolCallContract("identity", {"value": 2}, 3),),
    )

    await contract.verify(provider)

    assert provider.calls == [ToolCall("identity", {"value": 2})]


class OpenAICompletions:
    async def create(self, **request):
        if request.get("stream"):

            async def chunks():
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="one"))],
                    usage=None,
                )
                yield SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content="two"))],
                    usage=SimpleNamespace(
                        prompt_tokens=7,
                        completion_tokens=3,
                    ),
                )

            return chunks()
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="complete-response"))
            ],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2),
        )


class AnthropicMessages:
    async def create(self, **request):
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="complete-response")],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=5, output_tokens=2),
        )

    def stream(self, **request):
        class Stream:
            async def __aenter__(self):
                async def text():
                    yield "one"
                    yield "two"

                self.text_stream = text()
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def get_final_message(self):
                return SimpleNamespace(
                    usage=SimpleNamespace(input_tokens=7, output_tokens=3)
                )

        return Stream()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "transport",
    [
        OpenAITransport(
            client=SimpleNamespace(
                chat=SimpleNamespace(completions=OpenAICompletions())
            )
        ),
        AnthropicTransport(client=SimpleNamespace(messages=AnthropicMessages())),
    ],
)
async def test_supported_adapters_pass_the_same_downstream_model_contract(transport):
    await MODEL_CONTRACT.verify(transport, transport)
