# API Reference

This file is generated from `treelang.__all__`. Do not edit it by hand;
run `make docs` after changing the supported public API.

## `AST`

**Class** · `treelang.trees.tree`

```python
AST()
```

Represents an Abstract Syntax Tree (AST) for a very simple programming language.


Methods:

- `parse(cls, ast: Union[Dict[str, Any], List[Dict[str, Any]]]) -> treelang.trees.schemas.v1.TreeNode | list[treelang.trees.schemas.v1.TreeNode]` — Parses the given dictionary or list into a TreeNode.
- `eval(cls, ast: treelang.trees.schemas.v1.TreeNode, provider: treelang.ai.provider.ToolProvider, *, limits: treelang.trees.budget.ExecutionLimits | None = None, policy: treelang.trees.policy.ExecutionPolicy | None = None) -> Any` — Evaluates the given AST.
- `visit(cls, ast: treelang.trees.schemas.v1.TreeNode, op: collections.abc.Callable[[treelang.trees.schemas.v1.TreeNode], None]) -> None` — Performs a depth-first visit of the AST and applies the given operation to each node.
- `avisit(cls, ast: treelang.trees.schemas.v1.TreeNode, op: collections.abc.Callable[[treelang.trees.schemas.v1.TreeNode], None]) -> None` — Performs an asynchronous depth-first visit of the AST and applies the given operation to each node.
- `repr(cls, ast: treelang.trees.schemas.v1.TreeNode) -> str` — Returns a string representation of the AST.
- `tool(ast: treelang.trees.schemas.v1.TreeNode, provider: treelang.ai.provider.ToolProvider, *, limits: treelang.trees.budget.ExecutionLimits | None = None, policy: treelang.trees.policy.ExecutionPolicy | None = None) -> collections.abc.Callable[..., typing.Any]` — Converts the given AST into a callable function that can be added as a tool.

## `ASTCompilationError`

**Class** · `treelang.exceptions`

Raised when an AST cannot be compiled into a callable tool.

## `ASTExecutionError`

**Class** · `treelang.exceptions`

Raised when an AST fails during execution.

## `ASTValidationError`

**Class** · `treelang.exceptions`

Raised when an AST violates a runtime tool contract.

## `AsyncTreeGrower`

**Class** · `treelang.trees.strategies`

```python
AsyncTreeGrower(*args, **kwargs)
```

Asynchronous boundary for model- or evaluation-guided growth.


Methods:

- `grow(self, programs: 'Sequence[TreeProgram]', *, options: 'GrowthOptions') -> 'TransformResult[TreeProgram]'`

## `AnthropicTransport`

**Class** · `treelang.ai.anthropic`

```python
AnthropicTransport(*, api_key: 'str | None' = None, timeout: 'float | None' = None, max_tokens: 'int' = 4096, client: 'Any | None' = None, strict_json_schema: 'bool | None' = None) -> 'None'
```

Translate provider-neutral model requests to Anthropic Messages.


Methods:

- `capabilities(self, model: 'str') -> 'ModelCapabilities'` — Report Claude features, allowing an explicit deployment override.
- `complete(self, request: 'ModelRequest') -> 'str'`
- `consume_usage(self) -> 'ModelUsage'` — Return and clear usage for the latest completion in this async context.
- `stream(self, request: 'ModelRequest') -> 'AsyncIterator[str]'`

## `BranchOutcome`

**Class** · `treelang.trees.policy`

```python
BranchOutcome(success: 'bool', value: 'Any' = None, error_type: 'str | None' = None, error_message: 'str | None' = None) -> None
```

Serializable outcome for one parallel branch in collection mode.


Methods:

- `succeeded(cls, value: 'Any') -> 'BranchOutcome'`
- `failed(cls, error: 'Exception') -> 'BranchOutcome'`

## `CapabilityAwareTransport`

**Class** · `treelang.ai.capabilities`

```python
CapabilityAwareTransport(*args, **kwargs)
```

Optional transport extension for model-specific capability discovery.


Methods:

- `capabilities(self, model: 'str') -> 'ModelCapabilities'`

## `compose_programs`

**Function** · `treelang.trees.composition`

```python
compose_programs(programs: 'Sequence[TreeProgram]', *, mode: "Literal['single', 'parallel']" = 'single', name: 'str | None' = None, description: 'str | None' = None, limits: 'TransformationLimits | None' = None) -> 'TransformResult[TreeProgram]'
```

Combine independent programs with hygienic user-function names.

## `deduplicate_pure_tool_calls`

**Function** · `treelang.trees.deduplication`

```python
deduplicate_pure_tool_calls(program: 'TreeProgram', tools: 'Sequence[ToolDefinition]', *, limits: 'TransformationLimits | None' = None) -> 'TransformResult[TreeProgram]'
```

Memoize repeated closed calls to declared pure deterministic tools.

## `ConservativeTreePruner`

**Class** · `treelang.trees.pruning`

```python
ConservativeTreePruner()
```

Apply only locally provable rewrites without evaluating external tools.


Methods:

- `prune(self, tree: 'TreeProgram | TreeNode') -> 'TransformResult[TreeProgram] | TransformResult[TreeNode]'` — Return a validated pruned copy, or the original version 1 tree.

## `CURRENT_SCHEMA_VERSION`

**Constant** · `treelang`

Current value: `'1.0'`

## `DefaultModelCapabilityNegotiator`

**Class** · `treelang.ai.capabilities`

```python
DefaultModelCapabilityNegotiator()
```

Conservative capability and structured-output policy.


Methods:

- `capabilities(self, transport: 'object', model: 'str') -> 'ModelCapabilities'`
- `structured_output(self, capabilities: 'ModelCapabilities', *, model: 'str', configured_mode: 'StructuredOutputMode', schema_version: 'SchemaVersion', tools: 'list[ToolDefinition]') -> 'StructuredOutputSelection'`
- `fallback_after_rejection(self, selection: 'StructuredOutputSelection', configured_mode: 'StructuredOutputMode') -> 'StructuredOutputSelection | None'`

## `ExecutionLimitError`

**Class** · `treelang.exceptions`

```python
ExecutionLimitError(resource: str, limit: int | float) -> None
```

Raised when an AST invocation exceeds a configured resource limit.

## `ExecutionLimits`

**Class** · `treelang.trees.budget`

```python
ExecutionLimits(max_nodes: 'int | None' = None, max_depth: 'int | None' = None, max_call_depth: 'int | None' = None, max_tool_calls: 'int | None' = None, max_concurrency: 'int | None' = None, timeout_seconds: 'float | None' = None) -> None
```

Optional resource limits for one AST invocation.

``None`` leaves a resource unlimited. Positive values enforce an inclusive
maximum, preserving historical behavior when no limits are supplied.

## `ExecutionPolicy`

**Class** · `treelang.trees.policy`

```python
ExecutionPolicy(retry: 'RetryPolicy' = <factory>, parallel_failures: "Literal['raise', 'collect']" = 'raise') -> None
```

Opt-in retry and parallel partial-failure behavior.

## `GrowthOptions`

**Class** · `treelang.trees.strategies`

```python
GrowthOptions(mode: "Literal['single', 'parallel']" = 'single', name: 'str | None' = None, description: 'str | None' = None, limits: 'TransformationLimits | None' = None) -> None
```

Deterministic options shared by synchronous and asynchronous growers.

## `MCPToolProvider`

**Class** · `treelang.ai.provider`

```python
MCPToolProvider(session: mcp.client.session.ClientSession) -> None
```

Tool provider backed by an initialized MCP client session.


Methods:

- `call_tool(self, name: str, arguments: dict[str, typing.Any]) -> treelang.ai.provider.ToolOutput` — Invoke a named tool with validated keyword arguments.
- `list_tools(self) -> list[treelang.ai.tool.ToolDefinition]` — Return normalized metadata for every available tool.

## `ModelAuthenticationError`

**Class** · `treelang.exceptions`

```python
ModelAuthenticationError(message: str, *, provider: str, status_code: int | None = None, retry_after: float | None = None) -> None
```

Raised when a model provider rejects authentication or authorization.

## `ModelCapabilities`

**Class** · `treelang.ai.capabilities`

```python
ModelCapabilities(strict_json_schema: 'bool' = False, temperature: 'bool' = False) -> None
```

Features supported by one model through a transport.

## `ModelCapabilityNegotiator`

**Class** · `treelang.ai.capabilities`

```python
ModelCapabilityNegotiator(*args, **kwargs)
```

Policy boundary between model features and request orchestration.


Methods:

- `capabilities(self, transport: 'object', model: 'str') -> 'ModelCapabilities'`
- `structured_output(self, capabilities: 'ModelCapabilities', *, model: 'str', configured_mode: 'StructuredOutputMode', schema_version: 'SchemaVersion', tools: 'list[ToolDefinition]') -> 'StructuredOutputSelection'`
- `fallback_after_rejection(self, selection: 'StructuredOutputSelection', configured_mode: 'StructuredOutputMode') -> 'StructuredOutputSelection | None'`

## `ModelConnectionError`

**Class** · `treelang.exceptions`

```python
ModelConnectionError(message: str, *, provider: str, status_code: int | None = None, retry_after: float | None = None) -> None
```

Raised when the provider SDK cannot reach its model service.

## `ModelRateLimitError`

**Class** · `treelang.exceptions`

```python
ModelRateLimitError(message: str, *, provider: str, status_code: int | None = None, retry_after: float | None = None) -> None
```

Raised when a model provider reports exhausted request capacity.

## `ModelReplayEntry`

**Class** · `treelang.replay`

```python
ModelReplayEntry(request: 'dict[str, Any]', response: 'str | tuple[str, ...]', kind: "Literal['complete', 'stream']" = 'complete') -> None
```

One expected model request and completion or stream response.

## `ModelReplayTransport`

**Class** · `treelang.replay`

```python
ModelReplayTransport(entries: 'Sequence[ModelReplayEntry]') -> 'None'
```

Replay ordered model requests without credentials or network access.


Methods:

- `complete(self, request: 'ModelRequest') -> 'str'`
- `stream(self, request: 'ModelRequest') -> 'AsyncIterator[str]'`
- `assert_consumed(self) -> 'None'` — Raise when expected requests remain unconsumed.

## `ModelTimeoutError`

**Class** · `treelang.exceptions`

```python
ModelTimeoutError(message: str, *, provider: str, status_code: int | None = None, retry_after: float | None = None) -> None
```

Raised when the provider SDK times out a model request.

## `ModelTransport`

**Class** · `treelang.ai.transport`

```python
ModelTransport(*args, **kwargs)
```

Minimal model interface required by Arborist orchestration.


Methods:

- `complete(self, request: collections.abc.Mapping[str, typing.Any]) -> str`
- `stream(self, request: collections.abc.Mapping[str, typing.Any]) -> collections.abc.AsyncIterator[str]`

## `ModelTransportError`

**Class** · `treelang.exceptions`

```python
ModelTransportError(message: str, *, provider: str, status_code: int | None = None, retry_after: float | None = None) -> None
```

Normalized failure returned by a model transport SDK.

## `ModelUsage`

**Class** · `treelang.ai.transport`

```python
ModelUsage(prompt_tokens: int = 0, completion_tokens: int = 0) -> None
```

Token usage reported for one model completion.

## `NoOpTraceSink`

**Class** · `treelang.observability`

```python
NoOpTraceSink()
```

Trace sink that intentionally discards every event.


Methods:

- `record(self, event: str, attributes: collections.abc.Mapping[str, typing.Any]) -> None`

## `Observability`

**Class** · `treelang.observability`

```python
Observability(logger: logging.Logger = <factory>, tracer: treelang.observability.TraceSink = <factory>, allow_content: bool = False) -> None
```

Send the same redacted event to JSON logs and an optional trace sink.


Methods:

- `emit(self, event: str, **attributes: Any) -> None`

## `ProviderResponseError`

**Class** · `treelang.exceptions`

Raised when a provider returns an invalid response.

## `ProgramCompositionGrower`

**Class** · `treelang.trees.strategies`

```python
ProgramCompositionGrower()
```

Default deterministic grower backed by validated program composition.


Methods:

- `grow(self, programs: 'Sequence[TreeProgram]', *, options: 'GrowthOptions') -> 'TransformResult[TreeProgram]'`

## `ReplayMismatchError`

**Class** · `treelang.exceptions`

Raised when runtime activity diverges from a deterministic replay.

## `RetryPolicy`

**Class** · `treelang.trees.policy`

```python
RetryPolicy(max_attempts: 'int' = 1, delay_seconds: 'float' = 0, idempotent_tools: 'frozenset[str]' = <factory>, retryable_exceptions: 'tuple[type[Exception], ...]' = (<class 'treelang.exceptions.ToolExecutionError'>, <class 'TimeoutError'>)) -> None
```

Retry transient failures only for tools declared safe to repeat.

## `StructuredOutputUnsupportedError`

**Class** · `treelang.exceptions`

Raised when a provider rejects strict structured-output configuration.

## `StructuredOutputSelection`

**Class** · `treelang.ai.capabilities`

```python
StructuredOutputSelection(response_format: 'dict[str, Any]', mode: 'SelectedOutputMode', fallback_reason: 'str | None' = None) -> None
```

Negotiated response format and the reason for compatibility fallback.

## `SUPPORTED_SCHEMA_VERSIONS`

**Constant** · `treelang`

Current value: `('1.0', '2.0')`

## `ToolExecutionError`

**Class** · `treelang.exceptions`

Raised when a provider reports that a tool invocation failed.

## `ToolDefinition`

**Typed dictionary** · `treelang.ai.tool`

Provider-neutral metadata for one callable tool.


Fields:

- `name: Required[str]`
- `properties: Required[dict[str, treelang.ai.tool.ToolProperty]]`
- `description: NotRequired[str | None]`
- `input_schema: NotRequired[dict[str, Any]]`
- `effects: NotRequired[ForwardRef('ToolEffects')]`

## `ToolEffects`

**Typed dictionary** · `treelang.ai.tool`

Optional behavioral guarantees used by safe transformations.


Fields:

- `pure: bool`
- `deterministic: bool`
- `idempotent: bool`

## `ToolNotFoundError`

**Class** · `treelang.exceptions`

Raised when a provider does not expose a requested tool.

## `ToolOutput`

**Class** · `treelang.ai.provider`

```python
ToolOutput(*, content: Any) -> None
```

Provider-neutral value returned by one successful tool invocation.


Fields:

- `content: Any`

## `ToolProperty`

**Typed dictionary** · `treelang.ai.tool`

JSON Schema metadata used for one tool argument.


Fields:

- `type: str | list[str]`
- `description: str`
- `enum: list[Any]`
- `default: Any`
- `const: Any`
- `minimum: int | float`
- `maximum: int | float`
- `exclusiveMinimum: int | float`
- `exclusiveMaximum: int | float`
- `multipleOf: int | float`
- `minLength: int`
- `maxLength: int`
- `pattern: str`
- `format: str`
- `minItems: int`
- `maxItems: int`
- `uniqueItems: bool`
- `items: Any`
- `minProperties: int`
- `maxProperties: int`
- `properties: dict[str, Any]`
- `required: list[str]`
- `additionalProperties: bool | dict[str, Any]`

## `ToolProvider`

**Class** · `treelang.ai.provider`

```python
ToolProvider() -> None
```

Provider-neutral interface for tool discovery and invocation.


Methods:

- `get_tool_definition(self, name: str) -> treelang.ai.tool.ToolDefinition` — Return normalized metadata for one named tool.
- `call_tool(self, name: str, arguments: dict[str, typing.Any]) -> treelang.ai.provider.ToolOutput` — Invoke a named tool with validated keyword arguments.
- `list_tools(self) -> list[treelang.ai.tool.ToolDefinition]` — Return normalized metadata for every available tool.

## `ToolReplayEntry`

**Class** · `treelang.replay`

```python
ToolReplayEntry(name: 'str', arguments: 'dict[str, Any]', output: 'Any') -> None
```

One expected provider invocation and its deterministic output.

## `ToolReplayProvider`

**Class** · `treelang.replay`

```python
ToolReplayProvider(tools: 'Sequence[ToolDefinition]', entries: 'Sequence[ToolReplayEntry]') -> 'None'
```

Replay an ordered sequence of tool calls and reject any drift.


Methods:

- `list_tools(self) -> 'list[ToolDefinition]'` — Return normalized metadata for every available tool.
- `call_tool(self, name: 'str', arguments: 'dict[str, Any]') -> 'ToolOutput'` — Invoke a named tool with validated keyword arguments.
- `assert_consumed(self) -> 'None'` — Raise when expected calls remain unconsumed.

## `TraceSink`

**Class** · `treelang.observability`

```python
TraceSink(*args, **kwargs)
```

Vendor-neutral destination for already-redacted trace events.


Methods:

- `record(self, event: str, attributes: collections.abc.Mapping[str, typing.Any]) -> None`

## `TransformationLimits`

**Class** · `treelang.trees.transforms`

```python
TransformationLimits(max_nodes: 'int | None' = None, max_depth: 'int | None' = None) -> None
```

Optional inclusive structural limits for a transformed program.

## `TransformResult`

**Class** · `treelang.trees.transforms`

```python
TransformResult(tree: 'TreeT', lineage: 'tuple[TransformationRecord, ...]' = ()) -> None
```

A transformed tree together with its complete reproducible lineage.

## `TransformationRecord`

**Class** · `treelang.trees.transforms`

```python
TransformationRecord(name: 'str', changes: 'tuple[TreeChange, ...]' = (), seed: 'int | None' = None) -> None
```

Named transformation step and the changes it produced.

## `TreeConditional`

**Class** · `treelang.trees.schemas.v1`

```python
TreeConditional(*, type: Literal['conditional'] = 'conditional', condition: Node, true_branch: Node, false_branch: Optional[Node] = None) -> None
```

Represents a conditional statement in the AST.


Fields:

- `type: Literal['conditional']`
- `condition: 'Node'`
- `true_branch: 'Node'`
- `false_branch: Optional[ForwardRef('Node')]`

Methods:

- `eval(self, provider: treelang.ai.provider.ToolProvider, context: 'ExecutionContext | None' = None) -> Any`

## `TreeChange`

**Class** · `treelang.trees.transforms`

```python
TreeChange(kind: 'TreeChangeKind', path: 'TreePath', description: 'str', source_path: 'TreePath | None' = None) -> None
```

One deterministic structural change made by a transformation.

## `TreeChangeKind`

**Class** · `treelang.trees.transforms`

```python
TreeChangeKind(*values)
```

Structural operations that a transformation can report.

## `TreeFilter`

**Class** · `treelang.trees.schemas.v1`

```python
TreeFilter(*, type: Literal['filter'] = 'filter', function: treelang.trees.schemas.v1.TreeLambda, iterable: Node) -> None
```

Represents a filter operation in the abstract syntax tree (AST).


Fields:

- `type: Literal['filter']`
- `function: treelang.trees.schemas.v1.TreeLambda`
- `iterable: 'Node'`

Methods:

- `eval(self, provider: treelang.ai.provider.ToolProvider, context: 'ExecutionContext | None' = None) -> Any`

## `TreeFunction`

**Class** · `treelang.trees.schemas.v1`

```python
TreeFunction(*, type: Literal['function'] = 'function', name: Annotated[str, MinLen(min_length=1)], params: List[Node]) -> None
```

Represents a function in the abstract syntax tree (AST).


Fields:

- `type: Literal['function']`
- `name: str`
- `params: List[ForwardRef('Node')]`

Methods:

- `eval(self, provider: treelang.ai.provider.ToolProvider, context: 'ExecutionContext | None' = None) -> Any`

## `TreeLambda`

**Class** · `treelang.trees.schemas.v1`

```python
TreeLambda(*, type: Literal['lambda'] = 'lambda', params: List[str], body: treelang.trees.schemas.v1.TreeFunction) -> None
```

Represents an anonymous (lambda) function.


Fields:

- `type: Literal['lambda']`
- `params: List[str]`
- `body: treelang.trees.schemas.v1.TreeFunction`

Methods:

- `eval(self, provider: treelang.ai.provider.ToolProvider, context: 'ExecutionContext | None' = None) -> Any`

## `TreeMap`

**Class** · `treelang.trees.schemas.v1`

```python
TreeMap(*, type: Literal['map'] = 'map', function: treelang.trees.schemas.v1.TreeLambda, iterable: Node) -> None
```

Represents a map operation in the abstract syntax tree (AST).


Fields:

- `type: Literal['map']`
- `function: treelang.trees.schemas.v1.TreeLambda`
- `iterable: 'Node'`

Methods:

- `eval(self, provider: treelang.ai.provider.ToolProvider, context: 'ExecutionContext | None' = None) -> Any`

## `TreeNode`

**Class** · `treelang.trees.schemas.v1`

```python
TreeNode(*, type: Literal['node'] = 'node') -> None
```

Represents a node in the abstract syntax tree (AST).


Fields:

- `type: Literal['node']`

Methods:

- `eval(self, provider: treelang.ai.provider.ToolProvider, context: 'ExecutionContext | None' = None) -> Any`
- `hash(self) -> str`

## `TreePath`

**Class** · `treelang.trees.transforms`

```python
TreePath(segments: 'tuple[TreePathSegment, ...]' = ()) -> None
```

Identify a node by field names and zero-based sequence indexes.

Paths are structural rather than object-identity based, so they remain stable
across serialization and immutable model copies. The empty path identifies the
transformation root.


Methods:

- `child(self, segment: 'TreePathSegment') -> 'TreePath'` — Return a new path extended by one field name or sequence index.

## `TreeGrower`

**Class** · `treelang.trees.strategies`

```python
TreeGrower(*args, **kwargs)
```

Synchronous deterministic program-growth strategy.


Methods:

- `grow(self, programs: 'Sequence[TreeProgram]', *, options: 'GrowthOptions') -> 'TransformResult[TreeProgram]'`

## `TreePruner`

**Class** · `treelang.trees.strategies`

```python
TreePruner(*args, **kwargs)
```

Strategy that returns a tree and reproducible pruning lineage.


Methods:

- `prune(self, tree: 'GeneratedTree') -> 'TransformResult[TreeNode] | TransformResult[TreeProgram]'`

## `TreeProgram`

**Class** · `treelang.trees.schemas.v1`

```python
TreeProgram(*, type: Literal['program'] = 'program', body: List[Node], mode: Literal['single', 'parallel'], name: Optional[str] = None, description: Optional[str] = None, schema_version: Literal['1.0'] = '1.0') -> None
```

Represents a program in the abstract syntax tree (AST).


Fields:

- `type: Literal['program']`
- `body: List[ForwardRef('Node')]`
- `mode: Literal['single', 'parallel']`
- `name: Optional[str]`
- `description: Optional[str]`
- `schema_version: Literal['1.0']`

Methods:

- `eval(self, provider: treelang.ai.provider.ToolProvider, context: 'ExecutionContext | None' = None) -> Any`

## `TreeReduce`

**Class** · `treelang.trees.schemas.v1`

```python
TreeReduce(*, type: Literal['reduce'] = 'reduce', function: treelang.trees.schemas.v1.TreeLambda, iterable: Node) -> None
```

Represents a reduce operation in the abstract syntax tree (AST).


Fields:

- `type: Literal['reduce']`
- `function: treelang.trees.schemas.v1.TreeLambda`
- `iterable: 'Node'`

Methods:

- `eval(self, provider: treelang.ai.provider.ToolProvider, context: 'ExecutionContext | None' = None) -> Any`

## `TreeValue`

**Class** · `treelang.trees.schemas.v1`

```python
TreeValue(*, type: Literal['value'] = 'value', name: Annotated[str, MinLen(min_length=1)], value: JsonValue) -> None
```

Represents a value in the abstract syntax tree (AST).


Fields:

- `type: Literal['value']`
- `name: str`
- `value: JsonValue`

Methods:

- `eval(self, provider: treelang.ai.provider.ToolProvider, context: 'ExecutionContext | None' = None) -> Any`

## `TreelangError`

**Class** · `treelang.exceptions`

Base class for errors raised by Treelang.

## `TreeTransformationError`

**Class** · `treelang.exceptions`

Raised when a requested tree transformation cannot produce a valid tree.

## `UsageAwareTransport`

**Class** · `treelang.ai.transport`

```python
UsageAwareTransport(*args, **kwargs)
```

Optional transport contract for normalized per-context token usage.


Methods:

- `consume_usage(self) -> treelang.ai.transport.ModelUsage`

## `__version__`

**Constant** · `treelang`

Current value: `'1.0.0'`

## `ast_examples`

**Function** · `treelang.trees.schemas`

```python
ast_examples() -> str
```

Return examples for the Treelang AST model.

## `ast_json_schema`

**Function** · `treelang.trees.schemas`

```python
ast_json_schema() -> str
```

Return the JSON schema for the Treelang AST model.

## `graft_expression`

**Function** · `treelang.trees.grafting`

```python
graft_expression(program: 'TreeProgram', graft: 'Expression', *, at: 'TreePath', limits: 'TransformationLimits | None' = None) -> 'TransformResult[TreeProgram]'
```

Replace the expression at ``at`` with ``graft`` and validate the result.

## `json_schema_text`

**Function** · `treelang.schema_artifacts`

```python
json_schema_text(version: 'SupportedSchemaVersion') -> 'str'
```

Read one canonical schema exactly as distributed in the package.

## `load_json_schema`

**Function** · `treelang.schema_artifacts`

```python
load_json_schema(version: 'SupportedSchemaVersion') -> 'dict[str, Any]'
```

Load one canonical schema as a JSON-compatible mapping.

## `prune_tree`

**Function** · `treelang.trees.pruning`

```python
prune_tree(tree: 'TreeProgram | TreeNode') -> 'TransformResult[TreeProgram] | TransformResult[TreeNode]'
```

Prune a version 2 program, preserving version 1 trees unchanged.

## `wrap_expression`

**Function** · `treelang.trees.grafting`

```python
wrap_expression(program: 'TreeProgram', wrapper: 'Expression', *, at: 'TreePath', placeholder: 'str' = 'graft', limits: 'TransformationLimits | None' = None) -> 'TransformResult[TreeProgram]'
```

Replace placeholder variables in ``wrapper`` with the expression at ``at``.
