"""Model transport protocol and OpenAI implementation."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol, cast, runtime_checkable

from openai import AsyncOpenAI

from treelang.exceptions import ProviderResponseError
from treelang.observability import Observability

ModelRequest = Mapping[str, Any]


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
    ) -> None:
        self.client = client or AsyncOpenAI(api_key=api_key, timeout=timeout)
        self._usage: ContextVar[ModelUsage] = ContextVar(
            "openai_completion_usage", default=ModelUsage()
        )

    async def complete(self, request: ModelRequest) -> str:
        create = cast(Any, self.client.chat.completions.create)
        completion = await create(**dict(request))
        usage = getattr(completion, "usage", None)
        self._usage.set(
            ModelUsage(
                prompt_tokens=(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0,
                completion_tokens=(
                    (getattr(usage, "completion_tokens", 0) or 0) if usage else 0
                ),
            )
        )
        content = completion.choices[0].message.content
        if not isinstance(content, str):
            raise ProviderResponseError("Model response contained no text content")
        return content

    def consume_usage(self) -> ModelUsage:
        """Return and clear usage for the latest completion in this async context."""
        usage = self._usage.get()
        self._usage.set(ModelUsage())
        return usage

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        create = cast(Any, self.client.chat.completions.create)
        response = await create(**{**request, "stream": True})
        async for chunk in response:
            for choice in chunk.choices:
                content = choice.delta.content
                if content:
                    yield content
