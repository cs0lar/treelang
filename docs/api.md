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
- `eval(cls, ast: treelang.trees.schemas.v1.TreeNode, provider: treelang.ai.provider.ToolProvider) -> Any` — Evaluates the given AST.
- `visit(cls, ast: treelang.trees.schemas.v1.TreeNode, op: collections.abc.Callable[[treelang.trees.schemas.v1.TreeNode], None]) -> None` — Performs a depth-first visit of the AST and applies the given operation to each node.
- `avisit(cls, ast: treelang.trees.schemas.v1.TreeNode, op: collections.abc.Callable[[treelang.trees.schemas.v1.TreeNode], None]) -> None` — Performs an asynchronous depth-first visit of the AST and applies the given operation to each node.
- `repr(cls, ast: treelang.trees.schemas.v1.TreeNode) -> str` — Returns a string representation of the AST.
- `tool(ast: treelang.trees.schemas.v1.TreeNode, provider: treelang.ai.provider.ToolProvider) -> collections.abc.Callable[..., typing.Any]` — Converts the given AST into a callable function that can be added as a tool.

## `ASTCompilationError`

**Class** · `treelang.exceptions`

Raised when an AST cannot be compiled into a callable tool.

## `ASTExecutionError`

**Class** · `treelang.exceptions`

Raised when a compiled AST fails during execution.

## `ASTValidationError`

**Class** · `treelang.exceptions`

Raised when an AST violates a runtime tool contract.

## `CURRENT_SCHEMA_VERSION`

**Constant** · `treelang`

Current value: `'1.0'`

## `MCPToolProvider`

**Class** · `treelang.ai.provider`

```python
MCPToolProvider(session: mcp.client.session.ClientSession) -> None
```

Tool provider backed by an initialized MCP client session.


Methods:

- `call_tool(self, name: str, arguments: dict[str, typing.Any]) -> treelang.ai.provider.ToolOutput` — Invoke a named tool with validated keyword arguments.
- `list_tools(self) -> list[treelang.ai.tool.ToolDefinition]` — Return normalized metadata for every available tool.

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

- `type: str`
- `description: str`
- `enum: list[Any]`
- `default: Any`

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

## `TraceSink`

**Class** · `treelang.observability`

```python
TraceSink(*args, **kwargs)
```

Vendor-neutral destination for already-redacted trace events.


Methods:

- `record(self, event: str, attributes: collections.abc.Mapping[str, typing.Any]) -> None`

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

## `__version__`

**Constant** · `treelang`

Current value: `'0.10.1'`

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
