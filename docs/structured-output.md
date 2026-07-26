# Structured model output

Treelang validates every generated AST with its Pydantic runtime model. When a
transport and model declare strict JSON Schema support, Arborist can additionally
constrain generation at the provider boundary.

Configure the policy through `ArboristConfig`:

```python
from treelang.ai.arborist import ArboristConfig, OpenAIArborist

arborist = OpenAIArborist(
    model="gpt-4o",
    provider=provider,
    config=ArboristConfig(
        model="gpt-4o",
        schema_version="2.0",
        structured_output_mode="auto",
    ),
)
```

The modes are:

- `auto` (default): use strict JSON Schema when the transport declares support;
  otherwise use compatibility JSON mode. If the provider specifically rejects
  strict structured output, retry once in compatibility mode.
- `required`: require declared strict support and propagate any provider
  rejection without downgrading.
- `compatibility`: always use JSON-object mode.

Authentication, authorization, rate-limit, timeout, cancellation, and unrelated
provider failures never cause a downgrade. Invalid JSON or AST content uses the
existing bounded validated-repair loop in either output mode.

The strict generation schema is intentionally narrower than the serialized
runtime schema. It removes free-form JSON object literals and provider-unsupported
annotations, closes every object shape, and specializes schema v2 tool calls to
the tools selected for that request. Applications that need arbitrary JSON object
literals can select compatibility mode.

Custom transports can implement `CapabilityAwareTransport.capabilities(model)`.
Transports without that optional protocol are treated as compatibility-only.
`ModelCapabilityNegotiator` owns selection and fallback policy and can be
injected for provider-specific deployments. Selection and fallback events are
emitted through the normal redacted observability hooks. See
[Model capability negotiation](provider-capabilities.md).
