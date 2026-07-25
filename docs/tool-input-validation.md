# Tool input validation

Treelang validates fully evaluated tool arguments against the provider's JSON
Schema immediately before invocation. The same Draft 2020-12 validator is used by
schema v1 and v2 execution.

Validated constraints include:

- required and optional fields;
- JSON scalar, array, object, and nullable union types;
- enums and constants;
- numeric ranges and multiples;
- string length, patterns, and recognized formats;
- array length, uniqueness, and item schemas;
- nested object properties and additional-property policy; and
- local `$ref` definitions.

External schema references are rejected during tool discovery so argument
validation never retrieves remote content. Invalid metadata raises
`ProviderResponseError`. Invalid evaluated arguments raise `ASTValidationError`
containing only the tool name, safe field path, and failed constraint—not the
argument value. Rejected calls do not reach the provider or consume tool-call
budget.

MCP providers preserve the complete `inputSchema`. Custom providers can return:

```python
{
    "name": "register",
    "properties": {
        "age": {"type": "integer", "minimum": 18},
        "nickname": {"type": "string"},
    },
    "input_schema": {
        "type": "object",
        "properties": {
            "age": {"type": "integer", "minimum": 18},
            "nickname": {"type": "string"},
        },
        "required": ["age"],
        "additionalProperties": False,
    },
}
```

For compatibility, providers that return only `properties` retain the historical
contract: every listed property is required and additional properties are
rejected. JSON Schema `default` remains an annotation; Treelang does not inject
default values. Schema v1 can omit trailing optional parameters but cannot skip a
positional property to provide a later one. Schema v2 uses named arguments and
can omit any field not listed in `required`.
