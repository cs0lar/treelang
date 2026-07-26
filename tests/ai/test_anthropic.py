from types import SimpleNamespace

import pytest

from treelang.ai.anthropic import AnthropicTransport, anthropic_model_capabilities
from treelang.ai.arborist import OpenAIArborist
from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.ai.responses import EvalType
from treelang.exceptions import (
    ProviderResponseError,
    StructuredOutputUnsupportedError,
)
from treelang.trees.schemas.v1 import TreeProgram


class FakeMessages:
    def __init__(self, response=None, error=None, stream_parts=()):
        self.response = response
        self.error = error
        self.stream_parts = stream_parts
        self.requests = []
        self.stream_requests = []

    async def create(self, **request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response

    def stream(self, **request):
        self.stream_requests.append(request)
        parts = self.stream_parts

        class Stream:
            async def __aenter__(self):
                async def text_stream():
                    for part in parts:
                        yield part

                self.text_stream = text_stream()
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

        return Stream()


class EmptyProvider(ToolProvider):
    async def list_tools(self):
        self.tools = {}
        return []

    async def call_tool(self, name, arguments):
        return ToolOutput(content=None)


def message(
    text="response", *, stop_reason="end_turn", input_tokens=12, output_tokens=7
):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
    )


def request(response_format=None):
    value = {
        "model": "claude-sonnet-4-6",
        "messages": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "question"},
        ],
        "temperature": 0.0,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "identity",
                    "description": "Return a value",
                    "parameters": {
                        "type": "object",
                        "properties": {"value": {"type": "integer"}},
                        "required": ["value"],
                        "additionalProperties": False,
                    },
                },
            }
        ],
        "response_format": response_format or {"type": "json_object"},
    }
    return value


def test_anthropic_capabilities_are_conservative_and_overridable():
    assert anthropic_model_capabilities("claude-sonnet-4-6").strict_json_schema is True
    assert anthropic_model_capabilities("claude-3-5-sonnet").strict_json_schema is False
    assert (
        anthropic_model_capabilities(
            "private-deployment", strict_json_schema=True
        ).strict_json_schema
        is True
    )
    assert anthropic_model_capabilities("private-deployment").temperature is False


@pytest.mark.asyncio
async def test_completion_translates_messages_tools_and_usage():
    messages = FakeMessages(response=message())
    transport = AnthropicTransport(
        client=SimpleNamespace(messages=messages),
        max_tokens=2048,
    )

    assert await transport.complete(request()) == "response"

    assert messages.requests == [
        {
            "model": "claude-sonnet-4-6",
            "max_tokens": 2048,
            "system": "system",
            "messages": [{"role": "user", "content": "question"}],
            "temperature": 0.0,
            "tools": [
                {
                    "name": "identity",
                    "description": "Return a value",
                    "input_schema": {
                        "type": "object",
                        "properties": {"value": {"type": "integer"}},
                        "required": ["value"],
                        "additionalProperties": False,
                    },
                }
            ],
        }
    ]
    usage = transport.consume_usage()
    assert usage.prompt_tokens == 12
    assert usage.completion_tokens == 7
    assert transport.consume_usage().completion_tokens == 0


@pytest.mark.asyncio
async def test_anthropic_adapter_runs_through_unchanged_arborist_orchestration():
    response = (
        '{"type":"program","body":[{"type":"value","name":"answer","value":42}],'
        '"mode":"single","schema_version":"1.0"}'
    )
    messages = FakeMessages(response=message(response))
    transport = AnthropicTransport(client=SimpleNamespace(messages=messages))
    arborist = OpenAIArborist(
        model="claude-sonnet-4-6",
        provider=EmptyProvider(),
        transport=transport,
    )

    result = await arborist.eval("Return 42.", EvalType.TREE)

    assert isinstance(result.content, TreeProgram)
    assert result.content.body[0].value == 42
    assert messages.requests[0]["model"] == "claude-sonnet-4-6"
    assert messages.requests[0]["output_config"]["format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_strict_output_uses_anthropic_output_config_format():
    messages = FakeMessages(response=message('{"answer": 42}'))
    transport = AnthropicTransport(client=SimpleNamespace(messages=messages))
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "integer"}},
        "required": ["answer"],
        "additionalProperties": False,
    }

    await transport.complete(
        request(
            {
                "type": "json_schema",
                "json_schema": {
                    "name": "answer",
                    "strict": True,
                    "schema": schema,
                },
            }
        )
    )

    assert messages.requests[0]["output_config"] == {
        "format": {"type": "json_schema", "schema": schema}
    }


@pytest.mark.asyncio
async def test_stream_translates_request_and_yields_text():
    messages = FakeMessages(stream_parts=("one", "", "two"))
    transport = AnthropicTransport(client=SimpleNamespace(messages=messages))

    assert [part async for part in transport.stream(request())] == ["one", "two"]
    assert messages.stream_requests[0]["system"] == "system"
    assert "response_format" not in messages.stream_requests[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal"])
async def test_incomplete_and_refused_responses_fail_validation(stop_reason):
    transport = AnthropicTransport(
        client=SimpleNamespace(
            messages=FakeMessages(response=message(stop_reason=stop_reason))
        )
    )

    with pytest.raises(ProviderResponseError, match=stop_reason):
        await transport.complete(request())


@pytest.mark.asyncio
async def test_missing_text_fails_at_transport_boundary():
    response = SimpleNamespace(content=[], stop_reason="end_turn", usage=None)
    transport = AnthropicTransport(
        client=SimpleNamespace(messages=FakeMessages(response=response))
    )

    with pytest.raises(ProviderResponseError, match="no text"):
        await transport.complete(request())


@pytest.mark.asyncio
async def test_only_strict_output_rejections_are_translated():
    class BadRequest(Exception):
        status_code = 400

    strict = {
        "type": "json_schema",
        "json_schema": {
            "name": "answer",
            "schema": {"type": "object", "properties": {}},
        },
    }
    transport = AnthropicTransport(
        client=SimpleNamespace(
            messages=FakeMessages(error=BadRequest("output_config unsupported"))
        )
    )

    with pytest.raises(StructuredOutputUnsupportedError):
        await transport.complete(request(strict))

    transport = AnthropicTransport(
        client=SimpleNamespace(
            messages=FakeMessages(error=BadRequest("authentication failed"))
        )
    )
    with pytest.raises(BadRequest, match="authentication"):
        await transport.complete(request(strict))


@pytest.mark.parametrize("max_tokens", [0, -1, True, 1.5])
def test_max_tokens_must_be_a_positive_integer(max_tokens):
    with pytest.raises(ValueError, match="positive integer"):
        AnthropicTransport(client=object(), max_tokens=max_tokens)
