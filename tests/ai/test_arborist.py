import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import BadRequestError

from treelang.ai.arborist import (
    ArboristConfig,
    BaseArborist,
    EvalResponse,
    EvalType,
    OpenAIArborist,
)
from treelang.ai.capabilities import ModelCapabilities, StructuredOutputSelection
from treelang.ai.memory import ChatMessage, Memory
from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.ai.responses import TreeDescription
from treelang.ai.transport import OpenAITransport
from treelang.exceptions import (
    ExecutionLimitError,
    ProviderResponseError,
    StructuredOutputUnsupportedError,
)
from treelang.observability import Observability
from treelang.trees.budget import ExecutionLimits
from treelang.trees.schemas.v1 import TreeProgram, TreeValue
from treelang.trees.schemas.v2 import TreeProgram as TreeProgramV2


def program_json(body):
    return json.dumps({"type": "program", "mode": "single", "body": body})


class FakeTransport:
    def __init__(
        self,
        *responses,
        stream_parts=(),
        strict_json_schema=False,
        temperature=False,
    ):
        self.responses = list(responses)
        self.stream_parts = list(stream_parts)
        self.requests = []
        self.stream_requests = []
        self.strict_json_schema = strict_json_schema
        self.temperature = temperature

    def capabilities(self, model):
        return ModelCapabilities(
            strict_json_schema=self.strict_json_schema,
            temperature=self.temperature,
        )

    async def complete(self, request):
        self.requests.append(deepcopy(request))
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
            },
            {
                "name": "greater_than",
                "description": "Compare two values",
                "properties": {
                    "value": {"type": "integer"},
                    "threshold": {"type": "integer"},
                },
            },
            {
                "name": "add",
                "description": "Add two values",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
            },
        ]
        self.tools = {tool["name"]: tool for tool in tools}
        return tools

    async def call_tool(self, name, arguments):
        if name == "greater_than":
            return ToolOutput(content=arguments["value"] > arguments["threshold"])
        if name == "add":
            return ToolOutput(content=arguments["x"] + arguments["y"])
        return ToolOutput(content=arguments["value"])


def recursive_program_json() -> str:
    return json.dumps(
        {
            "type": "program",
            "schema_version": "2.0",
            "mode": "single",
            "definitions": [
                {
                    "type": "function_definition",
                    "name": "sum_to_three",
                    "params": ["n", "acc"],
                    "body": {
                        "type": "conditional",
                        "condition": {
                            "type": "tool_call",
                            "tool": "greater_than",
                            "arguments": {
                                "value": {"type": "variable", "name": "n"},
                                "threshold": {"type": "literal", "value": 3},
                            },
                        },
                        "true_branch": {"type": "variable", "name": "acc"},
                        "false_branch": {
                            "type": "call",
                            "function": "sum_to_three",
                            "arguments": [
                                {
                                    "type": "tool_call",
                                    "tool": "add",
                                    "arguments": {
                                        "x": {"type": "variable", "name": "n"},
                                        "y": {"type": "literal", "value": 1},
                                    },
                                },
                                {
                                    "type": "tool_call",
                                    "tool": "add",
                                    "arguments": {
                                        "x": {"type": "variable", "name": "acc"},
                                        "y": {"type": "variable", "name": "n"},
                                    },
                                },
                            ],
                        },
                    },
                }
            ],
            "body": [
                {
                    "type": "call",
                    "function": "sum_to_three",
                    "arguments": [
                        {"type": "literal", "value": 1},
                        {"type": "literal", "value": 0},
                    ],
                }
            ],
        }
    )


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
        program_json([{"type": "value", "name": "answer", "value": 42}]),
        temperature=True,
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
    assert (
        "exactly matches one of that lambda's params"
        in request["messages"][0]["content"]
    )
    assert request["temperature"] == 0.0
    assert [message["content"] for message in request["messages"][1:3]] == [
        "first",
        "second",
    ]
    assert request["tools"][0]["function"]["name"] == "identity"
    assert request["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
@pytest.mark.parametrize("schema_version", ["1.0", "2.0"])
async def test_arborist_uses_strict_schema_when_transport_supports_it(schema_version):
    response = (
        recursive_program_json()
        if schema_version == "2.0"
        else program_json([{"type": "value", "name": "answer", "value": 42}])
    )
    transport = FakeTransport(response, strict_json_schema=True)
    arborist = OpenAIArborist(
        model="strict-model",
        provider=FakeProvider(),
        config=ArboristConfig(model="strict-model", schema_version=schema_version),
        transport=transport,
    )

    await arborist.eval("question", EvalType.TREE)

    response_format = transport.requests[0]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["name"] == (
        f"treelang_ast_v{schema_version[0]}"
    )


@pytest.mark.asyncio
async def test_arborist_auto_falls_back_only_for_strict_output_rejection():
    transport = FakeTransport(
        StructuredOutputUnsupportedError("unsupported response_format"),
        program_json([{"type": "value", "name": "answer", "value": 42}]),
        strict_json_schema=True,
    )
    arborist = OpenAIArborist(
        model="strict-model",
        provider=FakeProvider(),
        transport=transport,
    )

    response = await arborist.eval("question", EvalType.TREE)

    assert isinstance(response.content, TreeProgram)
    assert transport.requests[0]["response_format"]["type"] == "json_schema"
    assert transport.requests[1]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_arborist_does_not_fallback_for_unrelated_provider_failure():
    transport = FakeTransport(
        PermissionError("authentication failed"),
        strict_json_schema=True,
    )
    arborist = OpenAIArborist(
        model="strict-model",
        provider=FakeProvider(),
        transport=transport,
    )

    with pytest.raises(PermissionError, match="authentication failed"):
        await arborist.eval("question", EvalType.TREE)

    assert len(transport.requests) == 1


@pytest.mark.asyncio
async def test_required_strict_mode_rejects_incapable_transport_before_request():
    transport = FakeTransport(
        program_json([{"type": "value", "name": "answer", "value": 42}])
    )
    arborist = OpenAIArborist(
        model="legacy-model",
        provider=FakeProvider(),
        config=ArboristConfig(model="legacy-model", structured_output_mode="required"),
        transport=transport,
    )

    with pytest.raises(StructuredOutputUnsupportedError, match="does not declare"):
        await arborist.eval("question", EvalType.TREE)

    assert transport.requests == []


@pytest.mark.asyncio
async def test_compatibility_mode_ignores_strict_capability():
    transport = FakeTransport(
        program_json([{"type": "value", "name": "answer", "value": 42}]),
        strict_json_schema=True,
    )
    arborist = OpenAIArborist(
        model="strict-model",
        provider=FakeProvider(),
        config=ArboristConfig(
            model="strict-model", structured_output_mode="compatibility"
        ),
        transport=transport,
    )

    await arborist.eval("question", EvalType.TREE)

    assert transport.requests[0]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_arborist_delegates_request_features_to_injected_negotiator():
    class Negotiator:
        def __init__(self):
            self.calls = []

        def capabilities(self, transport, model):
            self.calls.append(("capabilities", transport, model))
            return ModelCapabilities(temperature=True)

        def structured_output(
            self,
            capabilities,
            *,
            model,
            configured_mode,
            schema_version,
            tools,
        ):
            self.calls.append(
                (
                    "structured_output",
                    capabilities,
                    model,
                    configured_mode,
                    schema_version,
                    tools,
                )
            )
            return StructuredOutputSelection(
                response_format={"type": "json_object"},
                mode="compatibility",
            )

        def fallback_after_rejection(self, selection, configured_mode):
            self.calls.append(("fallback", selection, configured_mode))
            return None

    transport = FakeTransport(
        program_json([{"type": "value", "name": "answer", "value": 42}])
    )
    negotiator = Negotiator()
    arborist = OpenAIArborist(
        model="provider-specific-model",
        provider=FakeProvider(),
        transport=transport,
        capability_negotiator=negotiator,
    )

    await arborist.eval("question", EvalType.TREE)

    assert transport.requests[0]["temperature"] == 0.0
    assert transport.requests[0]["response_format"] == {"type": "json_object"}
    assert [call[0] for call in negotiator.calls] == [
        "capabilities",
        "structured_output",
    ]


@pytest.mark.asyncio
async def test_structured_output_selection_and_fallback_are_observable():
    class Tracer:
        def __init__(self):
            self.events = []

        def record(self, event, attributes):
            self.events.append((event, attributes))

    tracer = Tracer()
    transport = FakeTransport(
        program_json([{"type": "value", "name": "answer", "value": 42}])
    )
    arborist = OpenAIArborist(
        model="legacy-model",
        provider=FakeProvider(),
        transport=transport,
        observability=Observability(tracer=tracer),
    )

    await arborist.eval("question", EvalType.TREE)

    events = {event: attributes for event, attributes in tracer.events}
    assert events["model.structured_output.fallback"]["reason"] == (
        "capability_unavailable"
    )
    assert events["model.structured_output.selected"]["mode"] == "compatibility"


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
async def test_arborist_walk_mode_enforces_execution_limits():
    arborist = OpenAIArborist(
        model="model",
        provider=FakeProvider(),
        transport=FakeTransport(
            program_json([{"type": "value", "name": "answer", "value": 42}])
        ),
        execution_limits=ExecutionLimits(max_nodes=1),
    )

    with pytest.raises(ExecutionLimitError, match="nodes"):
        await arborist.eval("question")


@pytest.mark.asyncio
async def test_arborist_generates_and_walks_opt_in_recursive_schema():
    transport = FakeTransport(recursive_program_json())
    arborist = OpenAIArborist(
        model="model",
        provider=FakeProvider(),
        config=ArboristConfig(model="model", schema_version="2.0"),
        transport=transport,
        execution_limits=ExecutionLimits(
            max_nodes=100,
            max_call_depth=10,
            timeout_seconds=1,
        ),
    )

    response = await arborist.eval("sum one through three")

    assert response.content == 6
    assert response.jsontree["schema_version"] == "2.0"
    assert '"function_definition"' in transport.requests[0]["messages"][0]["content"]


@pytest.mark.asyncio
async def test_arborist_returns_typed_recursive_tree_without_walking():
    arborist = OpenAIArborist(
        model="model",
        provider=FakeProvider(),
        config=ArboristConfig(model="model", schema_version="2.0"),
        transport=FakeTransport(recursive_program_json()),
    )

    response = await arborist.eval("sum one through three", EvalType.TREE)

    assert isinstance(response.content, TreeProgramV2)


@pytest.mark.asyncio
async def test_arborist_requires_safety_limits_to_walk_generated_v2_program():
    arborist = OpenAIArborist(
        model="model",
        provider=FakeProvider(),
        config=ArboristConfig(model="model", schema_version="2.0"),
        transport=FakeTransport(recursive_program_json()),
        execution_limits=ExecutionLimits(max_call_depth=10),
    )

    with pytest.raises(ValueError, match="max_call_depth, max_nodes"):
        await arborist.eval("sum one through three")


@pytest.mark.asyncio
async def test_arborist_repairs_invalid_recursive_model_output():
    invalid = json.loads(recursive_program_json())
    invalid["definitions"][0]["body"]["true_branch"] = {
        "type": "variable",
        "name": "missing",
    }
    transport = FakeTransport(json.dumps(invalid), recursive_program_json())
    arborist = OpenAIArborist(
        model="model",
        provider=FakeProvider(),
        config=ArboristConfig(
            model="model", schema_version="2.0", validation_retries=1
        ),
        transport=transport,
    )

    response = await arborist.eval("sum one through three", EvalType.TREE)

    assert isinstance(response.content, TreeProgramV2)
    assert len(transport.requests) == 2
    assert "Unbound variable" in transport.requests[1]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_arborist_rejects_non_object_model_response():
    arborist = OpenAIArborist(
        model="model",
        provider=FakeProvider(),
        config=ArboristConfig(model="model", validation_retries=0),
        transport=FakeTransport("[]"),
    )

    with pytest.raises(ValueError, match="JSON object AST"):
        await arborist.eval("question")


@pytest.mark.asyncio
async def test_arborist_retries_an_invalid_conditional_ast_with_feedback():
    invalid = program_json(
        [
            {
                "type": "conditional",
                "condition": True,
                "true_branch": 100,
                "false_branch": 93,
            }
        ]
    )
    valid = program_json(
        [
            {
                "type": "conditional",
                "condition": {"type": "value", "name": "condition", "value": True},
                "true_branch": {"type": "value", "name": "result", "value": 100},
                "false_branch": {"type": "value", "name": "result", "value": 93},
            }
        ]
    )
    transport = FakeTransport(invalid, valid, strict_json_schema=True)
    arborist = OpenAIArborist(
        model="model", provider=FakeProvider(), transport=transport
    )

    response = await arborist.eval("cap the result at 100")

    assert response.content == 100
    assert len(transport.requests) == 2
    assert all(
        request["response_format"]["type"] == "json_schema"
        for request in transport.requests
    )
    correction = transport.requests[1]["messages"][-1]["content"]
    assert "failed validation" in correction
    assert "conditional.condition" in correction


@pytest.mark.asyncio
async def test_arborist_repairs_an_unbound_lambda_placeholder():
    invalid = program_json(
        [
            {
                "type": "map",
                "function": {
                    "type": "lambda",
                    "params": ["num"],
                    "body": {
                        "type": "function",
                        "name": "identity",
                        "params": [{"type": "value", "name": "value", "value": None}],
                    },
                },
                "iterable": {"type": "value", "name": "items", "value": [1, 2]},
            }
        ]
    )
    valid = program_json(
        [
            {
                "type": "map",
                "function": {
                    "type": "lambda",
                    "params": ["value"],
                    "body": {
                        "type": "function",
                        "name": "identity",
                        "params": [{"type": "value", "name": "value", "value": None}],
                    },
                },
                "iterable": {"type": "value", "name": "items", "value": [1, 2]},
            }
        ]
    )
    transport = FakeTransport(invalid, valid)
    arborist = OpenAIArborist(
        model="model", provider=FakeProvider(), transport=transport
    )

    response = await arborist.eval("return these values")

    assert response.content == [1, 2]
    assert len(transport.requests) == 2
    assert "Invalid lambda binding" in transport.requests[1]["messages"][-1]["content"]


def test_arborist_config_rejects_negative_validation_retries():
    with pytest.raises(ValueError, match="non-negative"):
        ArboristConfig(model="model", validation_retries=-1)


def test_arborist_config_rejects_unknown_schema_version():
    with pytest.raises(ValueError, match="schema_version"):
        ArboristConfig(model="model", schema_version="3.0")  # type: ignore[arg-type]


def test_arborist_config_rejects_unknown_structured_output_mode():
    with pytest.raises(ValueError, match="structured_output_mode"):
        ArboristConfig(
            model="model",
            structured_output_mode="sometimes",  # type: ignore[arg-type]
        )


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
        model="model",
        provider=FakeProvider(),
        transport=BlockingTransport(strict_json_schema=True),
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
        transport=BlockingTransport(strict_json_schema=True),
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
        choices=[SimpleNamespace(message=SimpleNamespace(content="complete"))],
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=3),
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
    assert transport.capabilities("gpt-4o").strict_json_schema is True
    assert transport.capabilities("gpt-4o").temperature is True
    assert transport.capabilities("unknown-model").strict_json_schema is False
    assert transport.capabilities("unknown-model").temperature is False
    assert transport.consume_usage().prompt_tokens == 12
    assert transport.consume_usage().prompt_tokens == 0
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


@pytest.mark.asyncio
async def test_openai_transport_translates_only_structured_output_rejections():
    response = httpx.Response(
        400,
        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
    )
    structured_error = BadRequestError(
        "response_format json_schema is unsupported",
        response=response,
        body={
            "code": "unsupported_value",
            "param": "response_format",
        },
    )
    other_error = BadRequestError(
        "invalid temperature",
        response=response,
        body={"code": "invalid_parameter", "param": "temperature"},
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(side_effect=[structured_error, other_error])
            )
        )
    )
    transport = OpenAITransport(client=client)
    strict_request = {
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "tree", "strict": True, "schema": {}},
        }
    }

    with pytest.raises(StructuredOutputUnsupportedError):
        await transport.complete(strict_request)
    with pytest.raises(BadRequestError, match="invalid temperature"):
        await transport.complete(strict_request)
