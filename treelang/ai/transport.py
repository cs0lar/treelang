"""Model transport protocol and OpenAI implementation."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol, cast, runtime_checkable

from openai import AsyncOpenAI, BadRequestError

from treelang.ai.capabilities import ModelCapabilities
from treelang.ai.errors import translate_model_error
from treelang.ai.tool import ToolDefinition, render_tool_catalog
from treelang.exceptions import (
    ProviderResponseError,
    StructuredOutputUnsupportedError,
)
from treelang.observability import Observability

ModelRequest = Mapping[str, Any]


def openai_model_capabilities(
    model: str, *, strict_json_schema: bool | None = None
) -> ModelCapabilities:
    """Return OpenAI adapter capabilities for one model or deployment."""
    strict = strict_json_schema
    if strict is None:
        strict = model.startswith(("gpt-4o", "gpt-4.1", "gpt-5", "o1", "o3", "o4"))
    return ModelCapabilities(
        strict_json_schema=strict,
        temperature=model.startswith(("gpt-4o", "gpt-4.1", "o1")),
    )


@dataclass(frozen=True)
class ModelUsage:
    """Token usage reported for one model completion."""

    prompt_tokens: int = 0
    completion_tokens: int = 0


@runtime_checkable
class ModelTransport(Protocol):
    """Minimal model interface required by Arborist orchestration."""

    async def complete(self, request: ModelRequest) -> str: ...

    def stream(self, request: ModelRequest) -> AsyncIterator[str]: ...


@runtime_checkable
class UsageAwareTransport(Protocol):
    """Optional transport contract for normalized per-context token usage."""

    def consume_usage(self) -> ModelUsage: ...


async def complete_with_timeout(
    transport: ModelTransport,
    request: ModelRequest,
    timeout: float | None,
    observability: Observability | None = None,
) -> str:
    """Complete a request, propagating cancellation and enforcing its deadline."""
    observer = observability or Observability()
    started = perf_counter()
    observer.emit("model.request.started", request=request, timeout=timeout)
    try:
        if timeout is None:
            response = await transport.complete(request)
        else:
            async with asyncio.timeout(timeout):
                response = await transport.complete(request)
    except asyncio.CancelledError:
        observer.emit(
            "model.request.cancelled",
            latency_ms=(perf_counter() - started) * 1000,
        )
        raise
    except Exception as error:
        observer.emit(
            "model.request.failed",
            latency_ms=(perf_counter() - started) * 1000,
            error=f"{type(error).__name__}: {error}",
        )
        raise
    observer.emit(
        "model.request.completed",
        latency_ms=(perf_counter() - started) * 1000,
        response=response,
    )
    return response


async def stream_with_observability(
    transport: ModelTransport,
    request: ModelRequest,
    observability: Observability | None = None,
) -> AsyncIterator[str]:
    """Stream a request with redacted lifecycle events."""
    observer = observability or Observability()
    started = perf_counter()
    chunks = 0
    observer.emit("model.stream.started", request=request)
    try:
        async for content in transport.stream(request):
            chunks += 1
            yield content
    except asyncio.CancelledError:
        observer.emit(
            "model.stream.cancelled",
            latency_ms=(perf_counter() - started) * 1000,
            chunks=chunks,
        )
        raise
    except Exception as error:
        observer.emit(
            "model.stream.failed",
            latency_ms=(perf_counter() - started) * 1000,
            chunks=chunks,
            error=f"{type(error).__name__}: {error}",
        )
        raise
    observer.emit(
        "model.stream.completed",
        latency_ms=(perf_counter() - started) * 1000,
        chunks=chunks,
    )


class OpenAITransport:
    """OpenAI chat-completions adapter."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float | None = None,
        client: AsyncOpenAI | None = None,
        strict_json_schema: bool | None = None,
    ) -> None:
        self.client = client or AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._usage: ContextVar[ModelUsage] = ContextVar(
            "openai_completion_usage", default=ModelUsage()
        )
        self.strict_json_schema = strict_json_schema

    def capabilities(self, model: str) -> ModelCapabilities:
        """Report strict output support, allowing an explicit deployment override."""
        return openai_model_capabilities(
            model,
            strict_json_schema=self.strict_json_schema,
        )

    async def complete(self, request: ModelRequest) -> str:
        self._usage.set(ModelUsage())
        create = cast(Any, self.client.chat.completions.create)
        try:
            completion = await create(**dict(request))
        except Exception as error:
            response_format = request.get("response_format", {})
            if (
                isinstance(error, BadRequestError)
                and isinstance(response_format, Mapping)
                and response_format.get("type") == "json_schema"
                and _is_structured_output_rejection(error)
            ):
                raise StructuredOutputUnsupportedError(str(error)) from error
            translated = translate_model_error("openai", error)
            if translated is error:
                raise
            raise translated from error
        usage = getattr(completion, "usage", None)
        self._usage.set(
            ModelUsage(
                prompt_tokens=(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0,
                completion_tokens=(
                    (getattr(usage, "completion_tokens", 0) or 0) if usage else 0
                ),
            )
        )
        choices = getattr(completion, "choices", None)
        if not isinstance(choices, list) or not choices:
            raise ProviderResponseError("Model response contained no choices")
        choice = choices[0]
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if not isinstance(content, str):
            if getattr(message, "tool_calls", None):
                raise ProviderResponseError(
                    "Model returned tool calls instead of text content"
                )
            if getattr(message, "refusal", None):
                raise ProviderResponseError("Model refused to produce text content")
            finish_reason = getattr(choice, "finish_reason", None)
            if isinstance(finish_reason, str) and finish_reason:
                raise ProviderResponseError(
                    f"Model response contained no text content "
                    f"(finish reason: {finish_reason})"
                )
            raise ProviderResponseError("Model response contained no text content")
        return content

    def consume_usage(self) -> ModelUsage:
        """Return and clear usage for the latest completion in this async context."""
        usage = self._usage.get()
        self._usage.set(ModelUsage())
        return usage

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        self._usage.set(ModelUsage())
        create = cast(Any, self.client.chat.completions.create)
        try:
            response = await create(
                **{
                    **request,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                }
            )
            async for chunk in response:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    self._usage.set(
                        ModelUsage(
                            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                            completion_tokens=(
                                getattr(usage, "completion_tokens", 0) or 0
                            ),
                        )
                    )
                for choice in getattr(chunk, "choices", ()):
                    content = getattr(getattr(choice, "delta", None), "content", None)
                    if content:
                        yield content
        except Exception as error:
            translated = translate_model_error("openai", error)
            if translated is error:
                raise
            raise translated from error


class OpenAIResponsesTransport(OpenAITransport):
    """OpenAI Responses API adapter for complete AST generation."""

    async def complete(self, request: ModelRequest) -> str:
        self._usage.set(ModelUsage())
        arguments = _responses_arguments(request)
        create = cast(Any, self.client.responses.create)
        try:
            response = await create(**arguments)
        except Exception as error:
            if (
                isinstance(error, BadRequestError)
                and _has_strict_response_format(arguments)
                and _is_structured_output_rejection(error)
            ):
                raise StructuredOutputUnsupportedError(str(error)) from error
            translated = translate_model_error("openai", error)
            if translated is error:
                raise
            raise translated from error
        usage = getattr(response, "usage", None)
        self._usage.set(
            ModelUsage(
                prompt_tokens=(getattr(usage, "input_tokens", 0) or 0) if usage else 0,
                completion_tokens=(
                    (getattr(usage, "output_tokens", 0) or 0) if usage else 0
                ),
            )
        )
        content = getattr(response, "output_text", None)
        if not isinstance(content, str) or not content:
            raise ProviderResponseError("Model response contained no text content")
        return content

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        self._usage.set(ModelUsage())
        create = cast(Any, self.client.responses.create)
        try:
            response = await create(**_responses_arguments(request), stream=True)
            async for event in response:
                event_type = getattr(event, "type", None)
                if event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", None)
                    if isinstance(delta, str) and delta:
                        yield delta
                elif event_type == "response.completed":
                    usage = getattr(getattr(event, "response", None), "usage", None)
                    if usage is not None:
                        self._usage.set(
                            ModelUsage(
                                prompt_tokens=getattr(usage, "input_tokens", 0) or 0,
                                completion_tokens=(
                                    getattr(usage, "output_tokens", 0) or 0
                                ),
                            )
                        )
        except Exception as error:
            translated = translate_model_error("openai", error)
            if translated is error:
                raise
            raise translated from error


def _responses_arguments(request: ModelRequest) -> dict[str, Any]:
    messages = request.get("messages", [])
    if not isinstance(messages, list):
        raise ValueError("Responses requests require a message list")
    instructions: list[str] = []
    input_messages: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, Mapping):
            raise ValueError("Responses request messages must be mappings")
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            raise ValueError(
                "Responses request messages require text roles and content"
            )
        if role == "system":
            instructions.append(content)
        else:
            input_messages.append({"role": role, "content": content})

    tools = request.get("treelang_tools", [])
    if not isinstance(tools, list):
        raise ValueError("treelang_tools must be a list")
    if tools:
        instructions.append(render_tool_catalog(cast(list[ToolDefinition], tools)))

    arguments: dict[str, Any] = {
        "model": request["model"],
        "instructions": "\n\n".join(instructions),
        "input": input_messages,
    }
    response_format = request.get("response_format")
    if isinstance(response_format, Mapping):
        if response_format.get("type") == "json_schema":
            arguments["text"] = {
                "format": {
                    "type": "json_schema",
                    **response_format["json_schema"],
                }
            }
        elif response_format.get("type") == "json_object":
            arguments["text"] = {"format": {"type": "json_object"}}
    reasoning_effort = request.get("reasoning_effort")
    if reasoning_effort is not None:
        arguments["reasoning"] = {"effort": reasoning_effort}
    if "temperature" in request:
        arguments["temperature"] = request["temperature"]
    return arguments


def _has_strict_response_format(arguments: Mapping[str, Any]) -> bool:
    text = arguments.get("text")
    if not isinstance(text, Mapping):
        return False
    output_format = text.get("format")
    return (
        isinstance(output_format, Mapping)
        and output_format.get("type") == "json_schema"
    )


def _is_structured_output_rejection(error: BadRequestError) -> bool:
    body = getattr(error, "body", None)
    code = body.get("code") if isinstance(body, Mapping) else None
    parameter = body.get("param") if isinstance(body, Mapping) else None
    message = str(error).lower()
    return parameter in {"response_format", "text.format"} or (
        code in {"invalid_parameter", "unsupported_value"}
        and (
            "json_schema" in message
            or "response_format" in message
            or "text.format" in message
        )
    )
