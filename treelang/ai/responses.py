"""Typed response models returned by Arborist orchestration."""

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from treelang.ai.config import ArboristConfig
from treelang.ai.prompt import (
    EXPLAIN_EVALUATION_SYSTEM_PROMPT,
    EXPLAIN_EVALUATION_USER_PROMPT,
    TREE_DESCRIPTOR_SYSTEM_PROMPT,
    TREE_DESCRIPTOR_USER_PROMPT,
)
from treelang.ai.transport import (
    ModelRequest,
    ModelTransport,
    OpenAITransport,
    complete_with_timeout,
    stream_with_observability,
)
from treelang.observability import Observability
from treelang.trees.schemas.v1 import TreeNode, TreeProgram
from treelang.trees.tree import AST


class EvalType(str, Enum):
    """Whether evaluation returns a tree or walks it immediately."""

    TREE = "tree"
    WALK = "walk"


class TreeDescription(BaseModel):
    name: str
    description: str
    properties: dict[str, Any] = Field(default_factory=dict)


class EvalResponse(BaseModel):
    """Tree generation or execution result with optional model runtime."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    query: str
    type: EvalType
    content: Any
    jsontree: dict[str, Any] | None = None
    config: ArboristConfig | None = Field(default=None, exclude=True, repr=False)
    transport: ModelTransport | None = Field(default=None, exclude=True, repr=False)
    observability: Observability | None = Field(default=None, exclude=True, repr=False)

    def _runtime(self) -> tuple[ArboristConfig, ModelTransport]:
        config = self.config or ArboristConfig.from_env()
        transport = self.transport or OpenAITransport(
            api_key=config.api_key, timeout=config.timeout
        )
        return config, transport

    async def explain(self) -> str:
        if self.type == EvalType.TREE:
            raise ValueError("Cannot explain a tree response.")
        config, transport = self._runtime()
        request: ModelRequest = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": EXPLAIN_EVALUATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": EXPLAIN_EVALUATION_USER_PROMPT.format(
                        question=self.query, data={"data": self.content}
                    ),
                },
            ],
        }
        return await complete_with_timeout(
            transport, request, config.timeout, self.observability
        )

    async def explain_stream(self):
        if self.type == EvalType.TREE:
            raise ValueError("Cannot explain a tree response.")
        config, transport = self._runtime()
        request: ModelRequest = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": EXPLAIN_EVALUATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": EXPLAIN_EVALUATION_USER_PROMPT.format(
                        question=self.query, data={"data": self.content}
                    ),
                },
            ],
        }
        async for content in stream_with_observability(
            transport, request, self.observability
        ):
            yield content.encode()

    async def describe(self) -> TreeNode:
        if self.type == EvalType.WALK:
            raise ValueError("Only tree responses can be described.")
        if not self.content:
            raise ValueError("No JSON representation of the tree available.")
        if not isinstance(self.content, TreeProgram):
            raise ValueError("Only TreeProgram instances can be described.")

        config, transport = self._runtime()
        request: ModelRequest = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": TREE_DESCRIPTOR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": TREE_DESCRIPTOR_USER_PROMPT.format(
                        tree=json.dumps(AST.repr(self.content))
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        content = await complete_with_timeout(
            transport, request, config.timeout, self.observability
        )
        description = TreeDescription.model_validate_json(content)
        self.content.name = description.name
        self.content.description = description.description
        return self.content
