# Provider capability and compatibility matrix

This file is generated from [`providers.json`](providers.json). Do not edit it directly.
Run `make docs` after changing provider support.

Status meanings: **supported** is contract-tested for the adapter; **model-dependent** is
selected through declared capabilities; **unsupported** is rejected or omitted.

| Capability | OpenAI | Anthropic |
|---|---|---|
| Completion | supported | supported |
| Streaming | supported | supported |
| Tool Definitions | supported | supported |
| Strict JSON Schema | model-dependent | model-dependent |
| Temperature | model-dependent | model-dependent |
| Completion Usage | supported | supported |
| Streaming Usage | supported | supported |
| Normalized Errors | supported | supported |
| Cancellation | supported | supported |
| Live Evaluation | supported | supported |

## Adapter details

### OpenAI

- Adapter: `treelang.ai.transport.OpenAITransport`
- Install: `treelang`
- Contract tests: [`tests/test_testing.py`](https://github.com/cs0lar/treelang/blob/dev/tests/test_testing.py)
- Guide: [`docs/provider-capabilities.md`](provider-capabilities.md)
- [Official documentation](https://platform.openai.com/docs/guides/structured-outputs)
- Checked model profiles:

  - `gpt-4o`: strict JSON Schema yes; temperature yes
  - `unknown-model`: strict JSON Schema no; temperature no

### Anthropic

- Adapter: `treelang.ai.anthropic.AnthropicTransport`
- Install: `treelang[anthropic]`
- Contract tests: [`tests/test_testing.py`](https://github.com/cs0lar/treelang/blob/dev/tests/test_testing.py)
- Guide: [`docs/anthropic.md`](anthropic.md)
- [Official documentation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- Checked model profiles:

  - `claude-sonnet-4-6`: strict JSON Schema yes; temperature yes
  - `claude-3-5-sonnet`: strict JSON Schema no; temperature yes

The matrix is validated in normal CI without credentials or network access. Live
provider quality is measured separately by the credentialed evaluation workflow.
