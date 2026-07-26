# Anthropic transport

Install the optional adapter dependency:

```sh
uv add "treelang[anthropic]"
```

Then inject `AnthropicTransport` into the same Arborist orchestration used by the
OpenAI adapter:

```python
import os

from treelang import AnthropicTransport
from treelang.ai.arborist import ArboristConfig, OpenAIArborist

transport = AnthropicTransport(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_tokens=4096,
)
arborist = OpenAIArborist(
    model="claude-sonnet-4-6",
    provider=provider,
    config=ArboristConfig(model="claude-sonnet-4-6"),
    transport=transport,
)
result = await arborist.eval("Build a program that answers the question.")
```

`OpenAIArborist` retains its historical name for compatibility, but its
orchestration is transport-neutral. The Anthropic adapter translates Treelang's
model request contract into the Messages API:

- system-role messages become the top-level `system` prompt;
- user and assistant messages remain conversational `messages`;
- function tools become Anthropic tools with `input_schema`;
- strict JSON Schema becomes `output_config.format`; and
- compatibility JSON mode relies on Treelang's JSON-only system prompt and
  validated repair, because it does not send an OpenAI `response_format`.

The adapter captures input/output token usage through `consume_usage()`, streams
text through the common `ModelTransport` protocol, rejects truncated or refused
responses, and preserves cancellation and unrelated SDK errors.

Structured-output support is declared conservatively for currently documented
Claude 4.5+ models. Private deployments or newly released models can override
discovery with `strict_json_schema=True` or `False` on `AnthropicTransport`.

The SDK is optional so existing installations do not acquire a second provider
dependency. Constructing the adapter without the extra installed raises an
installation error; importing `treelang` remains supported.

See Anthropic's official documentation for the current
[Messages API](https://platform.claude.com/docs/en/api/messages/create),
[structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
and [Python SDK](https://github.com/anthropics/anthropic-sdk-python).
