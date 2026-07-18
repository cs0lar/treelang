"""Model transport protocol and OpenAI implementation."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from typing import Any, Protocol, cast, runtime_checkable

from openai import AsyncOpenAI

from treelang.exceptions import ProviderResponseError

ModelRequest = Mapping[str, Any]


@runtime_checkable
class ModelTransport(Protocol):
    """Minimal model interface required by Arborist orchestration."""

    async def complete(self, request: ModelRequest) -> str: ...

    def stream(self, request: ModelRequest) -> AsyncIterator[str]: ...


async def complete_with_timeout(
    transport: ModelTransport,
    request: ModelRequest,
    timeout: float | None,
) -> str:
    """Complete a request, propagating cancellation and enforcing its deadline."""
    if timeout is None:
        return await transport.complete(request)
    async with asyncio.timeout(timeout):
        return await transport.complete(request)


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

    async def complete(self, request: ModelRequest) -> str:
        create = cast(Any, self.client.chat.completions.create)
        completion = await create(**dict(request))
        content = completion.choices[0].message.content
        if not isinstance(content, str):
            raise ProviderResponseError("Model response contained no text content")
        return content

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        create = cast(Any, self.client.chat.completions.create)
        response = await create(**{**request, "stream": True})
        async for chunk in response:
            for choice in chunk.choices:
                content = choice.delta.content
                if content:
                    yield content
