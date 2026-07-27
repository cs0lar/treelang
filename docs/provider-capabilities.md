# Model capability negotiation

Treelang keeps model feature discovery separate from Arborist request
orchestration. A model transport may implement `CapabilityAwareTransport` and
return `ModelCapabilities` for each model or deployment:

```python
from treelang import ModelCapabilities


class CustomTransport:
    def capabilities(self, model: str) -> ModelCapabilities:
        return ModelCapabilities(
            strict_json_schema=model == "strict-deployment",
            temperature=True,
        )
```

Transports that do not implement capability discovery receive conservative
defaults: strict JSON Schema and temperature are both disabled. Capability claims
must reflect the model as exposed through that transport, not just a similarly
named model offered elsewhere.

`DefaultModelCapabilityNegotiator` converts declared capabilities and
`ArboristConfig.structured_output_mode` into a `StructuredOutputSelection`. It
owns strict/compatibility selection, required-mode rejection, and the one allowed
automatic downgrade after a provider explicitly rejects strict output.
`OpenAIArborist` only applies that decision and records redacted observability
events.

Applications and future provider adapters can inject a custom
`ModelCapabilityNegotiator` into `OpenAIArborist` when deployments need different
policy. A negotiator must:

- discover capabilities without making model requests;
- return a complete response-format selection;
- refuse unsupported required capabilities before a request is sent;
- allow fallback only when its policy explicitly permits it; and
- avoid using authentication, rate-limit, timeout, cancellation, or unrelated
  provider errors as evidence that a capability is unavailable.

OpenAI model-name heuristics are confined to `OpenAITransport`. They are not part
of provider-neutral Arborist orchestration.

The generated [provider compatibility matrix](provider-matrix.md) publishes these
claims from a machine-readable manifest. Normal CI checks every representative
model profile against the adapter capability functions and rejects stale output.
