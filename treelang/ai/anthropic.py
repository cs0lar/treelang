"""Anthropic Messages API transport adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextvars import ContextVar
from typing import Any, cast

from treelang.ai.capabilities import ModelCapabilities
from treelang.ai.errors import translate_model_error
from treelang.ai.transport import ModelRequest, ModelUsage
from treelang.exceptions import (
    ProviderResponseError,
    StructuredOutputUnsupportedError,
)

_STRICT_MODEL_PREFIXES = (
    "claude-haiku-4-5",
    "claude-mythos",
    "claude-opus-4-5",
    "claude-opus-4-6",
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-sonnet-4-5",
    "claude-sonnet-4-6",
)


def anthropic_model_capabilities(
    model: str, *, strict_json_schema: bool | None = None
) -> ModelCapabilities:
    """Return conservative Claude API capabilities for one model."""
    strict = strict_json_schema
    if strict is None:
        strict = model.startswith(_STRICT_MODEL_PREFIXES)
    return ModelCapabilities(
        strict_json_schema=strict,
        temperature=model.startswith("claude-"),
    )


class AnthropicTransport:
    """Translate provider-neutral model requests to Anthropic Messages."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float | None = None,
        max_tokens: int = 4096,
        client: Any | None = None,
        strict_json_schema: bool | None = None,
    ) -> None:
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
            raise ValueError("max_tokens must be a positive integer")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        if client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError as error:  # pragma: no cover - exercised in wheel smoke
                raise ImportError(
                    "AnthropicTransport requires 'treelang[anthropic]'"
                ) from error
            client = AsyncAnthropic(api_key=api_key, timeout=timeout)
        self.client = client
        self.max_tokens = max_tokens
        self.strict_json_schema = strict_json_schema
        self._usage: ContextVar[ModelUsage] = ContextVar(
            "anthropic_completion_usage", default=ModelUsage()
        )

    def capabilities(self, model: str) -> ModelCapabilities:
        """Report Claude features, allowing an explicit deployment override."""
        return anthropic_model_capabilities(
            model,
            strict_json_schema=self.strict_json_schema,
        )

    async def complete(self, request: ModelRequest) -> str:
        self._usage.set(ModelUsage())
        arguments = self._translate_request(request)
        create = cast(Any, self.client.messages.create)
        try:
            message = await create(**arguments)
        except Exception as error:
            if "output_config" in arguments and _is_structured_output_rejection(error):
                raise StructuredOutputUnsupportedError(str(error)) from error
            translated = translate_model_error("anthropic", error)
            if translated is error:
                raise
            raise translated from error

        stop_reason = getattr(message, "stop_reason", None)
        if stop_reason in {"max_tokens", "refusal"}:
            raise ProviderResponseError(
                f"Anthropic response stopped with reason '{stop_reason}'"
            )
        usage = getattr(message, "usage", None)
        self._set_usage(usage)
        text = _message_text(message)
        if not text:
            raise ProviderResponseError("Anthropic response contained no text content")
        return text

    def consume_usage(self) -> ModelUsage:
        """Return and clear usage for the latest completion in this async context."""
        usage = self._usage.get()
        self._usage.set(ModelUsage())
        return usage

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        self._usage.set(ModelUsage())
        arguments = self._translate_request(request)
        stream_factory = cast(Any, self.client.messages.stream)
        try:
            async with stream_factory(**arguments) as stream:
                async for text in stream.text_stream:
                    if text:
                        yield text
                message = await stream.get_final_message()
                self._set_usage(getattr(message, "usage", None))
        except Exception as error:
            if "output_config" in arguments and _is_structured_output_rejection(error):
                raise StructuredOutputUnsupportedError(str(error)) from error
            translated = translate_model_error("anthropic", error)
            if translated is error:
                raise
            raise translated from error

    def _set_usage(self, usage: Any) -> None:
        self._usage.set(
            ModelUsage(
                prompt_tokens=(getattr(usage, "input_tokens", 0) or 0) if usage else 0,
                completion_tokens=(getattr(usage, "output_tokens", 0) or 0)
                if usage
                else 0,
            )
        )

    def _translate_request(self, request: ModelRequest) -> dict[str, Any]:
        model = request.get("model")
        messages = request.get("messages")
        if not isinstance(model, str) or not model:
            raise ProviderResponseError("Model request has no valid model")
        if not isinstance(messages, list):
            raise ProviderResponseError("Model request has no valid messages")

        system_parts: list[str] = []
        conversation: list[dict[str, Any]] = []
        for item in messages:
            if not isinstance(item, Mapping):
                raise ProviderResponseError("Model request contains an invalid message")
            role = item.get("role")
            content = item.get("content")
            if role == "system":
                if not isinstance(content, str):
                    raise ProviderResponseError(
                        "Model request contains an invalid system message"
                    )
                system_parts.append(content)
            elif role in {"user", "assistant"} and isinstance(content, str):
                conversation.append({"role": role, "content": content})
            else:
                raise ProviderResponseError("Model request contains an invalid message")

        translated: dict[str, Any] = {
            "model": model,
            "max_tokens": self.max_tokens,
            "messages": conversation,
        }
        if system_parts:
            translated["system"] = "\n\n".join(system_parts)
        temperature = request.get("temperature")
        if temperature is not None:
            translated["temperature"] = temperature
        tools = request.get("tools")
        if tools is not None:
            translated["tools"] = _translate_tools(tools)

        response_format = request.get("response_format")
        if (
            isinstance(response_format, Mapping)
            and response_format.get("type") == "json_schema"
        ):
            json_schema = response_format.get("json_schema")
            if not isinstance(json_schema, Mapping) or not isinstance(
                json_schema.get("schema"), Mapping
            ):
                raise ProviderResponseError(
                    "Strict model request has no valid JSON schema"
                )
            translated["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": dict(cast(Mapping[str, Any], json_schema["schema"])),
                }
            }
        return translated


def _translate_tools(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ProviderResponseError("Model request has no valid tools")
    translated: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping) or not isinstance(
            item.get("function"), Mapping
        ):
            raise ProviderResponseError("Model request contains an invalid tool")
        function = cast(Mapping[str, Any], item["function"])
        name = function.get("name")
        schema = function.get("parameters")
        if not isinstance(name, str) or not isinstance(schema, Mapping):
            raise ProviderResponseError("Model request contains an invalid tool")
        tool: dict[str, Any] = {"name": name, "input_schema": dict(schema)}
        description = function.get("description")
        if isinstance(description, str):
            tool["description"] = description
        translated.append(tool)
    return translated


def _message_text(message: Any) -> str:
    parts = [
        block.text
        for block in getattr(message, "content", ())
        if getattr(block, "type", None) == "text"
        and isinstance(getattr(block, "text", None), str)
    ]
    return "".join(parts)


def _is_structured_output_rejection(error: Exception) -> bool:
    status_code = getattr(error, "status_code", None)
    message = str(error).lower()
    return status_code == 400 and (
        "output_config" in message
        or "json_schema" in message
        or "structured output" in message
    )


__all__ = ["AnthropicTransport", "anthropic_model_capabilities"]
