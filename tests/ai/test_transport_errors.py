import asyncio
from types import SimpleNamespace

import pytest

from treelang.ai.anthropic import AnthropicTransport
from treelang.ai.errors import translate_model_error
from treelang.ai.transport import OpenAIResponsesTransport, OpenAITransport
from treelang.exceptions import (
    ModelAuthenticationError,
    ModelConnectionError,
    ModelRateLimitError,
    ModelTimeoutError,
    ModelTransportError,
)


def sdk_error(
    provider,
    name,
    *,
    status_code=None,
    retry_after=None,
):
    error_type = type(name, (Exception,), {"__module__": provider})
    error = error_type("provider failed")
    error.status_code = status_code
    headers = {} if retry_after is None else {"retry-after": retry_after}
    error.response = SimpleNamespace(status_code=status_code, headers=headers)
    return error


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
@pytest.mark.parametrize(
    ("name", "status_code", "expected"),
    [
        ("AuthenticationError", 401, ModelAuthenticationError),
        ("PermissionDeniedError", 403, ModelAuthenticationError),
        ("RateLimitError", 429, ModelRateLimitError),
        ("APITimeoutError", None, ModelTimeoutError),
        ("APIConnectionError", None, ModelConnectionError),
        ("BadRequestError", 400, ModelTransportError),
    ],
)
def test_provider_sdks_share_one_error_contract(provider, name, status_code, expected):
    translated = translate_model_error(
        provider,
        sdk_error(provider, name, status_code=status_code),
    )

    assert isinstance(translated, expected)
    assert translated.provider == provider
    assert translated.status_code == status_code


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_rate_limit_retry_after_is_normalized(provider):
    translated = translate_model_error(
        provider,
        sdk_error(
            provider,
            "RateLimitError",
            status_code=429,
            retry_after="1.5",
        ),
    )

    assert isinstance(translated, ModelRateLimitError)
    assert translated.retry_after == 1.5


def test_unrelated_application_errors_are_preserved():
    error = ValueError("application")

    assert translate_model_error("openai", error) is error
    assert translate_model_error("anthropic", error) is error


def test_normalized_provider_timeout_remains_catchable_as_timeout_error():
    translated = translate_model_error(
        "openai",
        sdk_error("openai", "APITimeoutError"),
    )

    assert isinstance(translated, TimeoutError)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "openai_responses", "anthropic"])
async def test_adapter_cancellation_propagates_without_translation(provider):
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def block(**request):
        started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    messages = SimpleNamespace(create=block)
    if provider == "openai":
        transport = OpenAITransport(
            client=SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=block),
                )
            )
        )
        request = {"model": "model", "messages": []}
    elif provider == "openai_responses":
        transport = OpenAIResponsesTransport(
            client=SimpleNamespace(
                responses=SimpleNamespace(create=block),
            )
        )
        request = {"model": "model", "messages": []}
    else:
        transport = AnthropicTransport(
            client=SimpleNamespace(messages=messages),
        )
        request = {
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "question"}],
        }

    task = asyncio.create_task(transport.complete(request))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()
