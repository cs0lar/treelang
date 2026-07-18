"""Per-invocation state used while evaluating an AST."""

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Immutable bindings for one AST invocation.

    Named bindings are used by lambdas. Node bindings are used by compiled tools,
    where duplicate leaf names must remain independently addressable.
    """

    names: Mapping[str, Any] = field(default_factory=dict)
    nodes: Mapping[int, Any] = field(default_factory=dict)

    def bind_names(self, values: Mapping[str, Any]) -> "ExecutionContext":
        return ExecutionContext(names={**self.names, **values}, nodes=self.nodes)

    def bind_nodes(self, values: Mapping[int, Any]) -> "ExecutionContext":
        return ExecutionContext(names=self.names, nodes={**self.nodes, **values})

    def value_for(self, node: object, name: str, default: Any) -> Any:
        if id(node) in self.nodes:
            return self.nodes[id(node)]
        return self.names.get(name, default)
