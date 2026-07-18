import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from treelang.ai.arborist import (
    ArboristConfig,
    BaseArborist,
    EvalResponse,
    EvalType,
    OpenAIArborist,
)
from treelang.ai.memory import ChatMessage, Memory
from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.ai.responses import TreeDescription
from treelang.ai.transport import OpenAITransport
from treelang.exceptions import ProviderResponseError
from treelang.trees.schemas.v1 import TreeProgram, TreeValue


def program_json(body):
    return json.dumps({"type": "program", "mode": "single", "body": body})


class FakeTransport:
    def __init__(self, *responses, stream_parts=()):
        self.responses = list(responses)
        self.stream_parts = list(stream_parts)
        self.requests = []
        self.stream_requests = []

    async def complete(self, request):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def stream(self, request):
        self.stream_requests.append(request)

        async def parts():
            for part in self.stream_parts:
                yield part

        return parts()


class FakeProvider(ToolProvider):
    async def list_tools(self):
        tools = [
            {
                "name": "identity",
                "description": "Return a value",
                "properties": {"value": {"type": "integer"}},
            }
        ]
        self.tools = {tool["name"]: tool for tool in tools}
        return tools

    async def call_tool(self, name, arguments):
        return ToolOutput(content=arguments["value"])


class FakeMemory(Memory):
    async def add(self, messages):
        return None

    async def get(self):
        return [
            ChatMessage(role="user", content="first"),
            ChatMessage(role="assistant", content="second"),
        ]

    async def clear(self):
        return None


def test_config_reads_environment_once(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "configured-model")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("OPENAI_TIMEOUT", "2.5")

    config = ArboristConfig.from_env()

    assert config == ArboristConfig(
        model="configured-model", api_key="secret", timeout=2.5
    )
    assert ArboristConfig.from_env("explicit").model == "explicit"


@pytest.mark.asyncio
async def test_arborist_tree_mode_builds_typed_request_with_memory_and_tools():
    transport = FakeTransport(
        program_json([{"type": "value", "name": "answer", "value": 42}])
    )
    arborist = OpenAIArborist(
        model="gpt-4o-test",
        provider=FakeProvider(),
        memory=FakeMemory(),
        transport=transport,
    )

    response = await arborist.eval("question", EvalType.TREE)

    assert response.type == EvalType.TREE
    assert isinstance(response.content, TreeProgram)
    assert response.transport is transport
    request = transport.requests[0]
    assert request["temperature"] == 0.0
    assert [message["content"] for message in request["messages"][1:3]] == [
        "first",
        "second",
    ]
    assert request["tools"][0]["function"]["name"] == "identity"


@pytest.mark.asyncio
async def test_arborist_walk_mode_executes_generated_tree():
    transport = FakeTransport(
        program_json(
            [
                {
                    "type": "function",
                    "name": "identity",
                    "params": [{"type": "value", "name": "value", "value": 7}],
                }
            ]
        )
    )
    arborist = OpenAIArborist(
        model="reasoning-model",
        provider=FakeProvider(),
        transport=transport,
    )

    response = await arborist.eval("question")

    assert response.type == EvalType.WALK
    assert response.content == 7
    assert "temperature" not in transport.requests[0]


@pytest.mark.asyncio
async def test_arborist_rejects_non_object_model_response():
    arborist = OpenAIArborist(
        model="model", provider=FakeProvider(), transport=FakeTransport("[]")
    )

    with pytest.raises(ValueError, match="JSON object AST"):
        await arborist.eval("question")


@pytest.mark.asyncio
async def test_arborist_cancellation_propagates_from_transport():
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class BlockingTransport(FakeTransport):
        async def complete(self, request):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    arborist = OpenAIArborist(
        model="model", provider=FakeProvider(), transport=BlockingTransport()
    )
    task = asyncio.create_task(arborist.eval("question"))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_arborist_enforces_configured_timeout():
    cancelled = asyncio.Event()

    class BlockingTransport(FakeTransport):
        async def complete(self, request):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    arborist = OpenAIArborist(
        model="model",
        provider=FakeProvider(),
        config=ArboristConfig(model="model", timeout=0.01),
        transport=BlockingTransport(),
    )

    with pytest.raises(TimeoutError):
        await arborist.eval("question")
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_eval_response_explain_and_stream_use_injected_runtime():
    transport = FakeTransport("Explanation", stream_parts=["one", "two"])
    response = EvalResponse(
        query="question",
        type=EvalType.WALK,
        content=42,
        config=ArboristConfig(model="model"),
        transport=transport,
    )

    assert await response.explain() == "Explanation"
    assert [part async for part in response.explain_stream()] == [b"one", b"two"]
    assert transport.requests[0]["model"] == "model"


@pytest.mark.asyncio
async def test_eval_response_describe_updates_tree():
    tree = TreeProgram(body=[TreeValue(name="answer", value=42)], mode="single")
    transport = FakeTransport('{"name":"Answer","description":"Returns 42"}')
    response = EvalResponse(
        query="question",
        type=EvalType.TREE,
        content=tree,
        config=ArboristConfig(model="model"),
        transport=transport,
    )

    assert await response.describe() is tree
    assert (tree.name, tree.description) == ("Answer", "Returns 42")
    assert TreeDescription(name="name", description="description").properties == {}


@pytest.mark.asyncio
async def test_eval_response_mode_guards():
    tree_response = EvalResponse(query="q", type=EvalType.TREE, content=None)
    walk_response = EvalResponse(query="q", type=EvalType.WALK, content=1)

    with pytest.raises(ValueError, match="Cannot explain"):
        await tree_response.explain()
    with pytest.raises(ValueError, match="Only tree responses"):
        await walk_response.describe()
    with pytest.raises(ValueError, match="No JSON representation"):
        await tree_response.describe()


@pytest.mark.asyncio
async def test_base_arborist_defaults_and_abstract_operations():
    base = BaseArborist("model", "system", "user", FakeProvider())
    tree = TreeValue(name="value", value=3)

    assert base.prune(tree) is tree
    assert await base.walk(tree) == 3
    with pytest.raises(NotImplementedError):
        base.grow()
    with pytest.raises(NotImplementedError):
        await base.eval("question")


@pytest.mark.asyncio
async def test_openai_transport_complete_and_stream_without_network():
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="complete"))]
    )
    chunks = [
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="part"))]
        ),
        SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))]),
    ]

    async def stream_chunks():
        for chunk in chunks:
            yield chunk

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(side_effect=[completion, stream_chunks()])
            )
        )
    )
    transport = OpenAITransport(client=client)

    assert await transport.complete({"model": "model", "messages": []}) == "complete"
    assert [
        part async for part in transport.stream({"model": "model", "messages": []})
    ] == ["part"]


@pytest.mark.asyncio
async def test_openai_transport_rejects_missing_text():
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(
                    return_value=SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
                    )
                )
            )
        )
    )

    with pytest.raises(ProviderResponseError, match="no text content"):
        await OpenAITransport(client=client).complete({})
