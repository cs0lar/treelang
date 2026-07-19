"""Arborist orchestration for generating and evaluating AST programs."""

import json
from typing import Any

from treelang.ai.config import ArboristConfig
from treelang.ai.memory import Memory
from treelang.ai.prompt import ARBORIST_SYSTEM_PROMPT
from treelang.ai.provider import ToolProvider
from treelang.ai.responses import EvalResponse, EvalType, TreeDescription
from treelang.ai.selector import AllToolsSelector, BaseToolSelector
from treelang.ai.transport import (
    ModelTransport,
    OpenAITransport,
    complete_with_timeout,
)
from treelang.observability import Observability
from treelang.trees.schemas import ast_examples, ast_json_schema
from treelang.trees.schemas.v1 import TreeNode
from treelang.trees.tree import AST


class BaseArborist:
    """Base orchestration interface for AST-generating agents."""

    def __init__(
        self,
        model: str,
        system_prompt: str,
        user_prompt_template: str,
        provider: ToolProvider,
        selector: BaseToolSelector | None = None,
    ) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template
        self.provider = provider
        self.selector = selector or AllToolsSelector()

    def prune(self, tree: TreeNode) -> TreeNode:
        return tree

    def grow(self) -> None:
        raise NotImplementedError()

    async def walk(self, tree: TreeNode) -> Any:
        return await AST.eval(tree, self.provider)

    async def eval(self, query: str, type: EvalType = EvalType.WALK) -> EvalResponse:
        raise NotImplementedError()


class OpenAIArborist(BaseArborist):
    """Generate AST programs with an injected model transport."""

    def __init__(
        self,
        model: str,
        provider: ToolProvider,
        selector: BaseToolSelector | None = None,
        memory: Memory | None = None,
        *,
        config: ArboristConfig | None = None,
        transport: ModelTransport | None = None,
        observability: Observability | None = None,
    ) -> None:
        runtime_config = config or ArboristConfig.from_env(model)
        super().__init__(
            runtime_config.model,
            ARBORIST_SYSTEM_PROMPT.format(
                schema=ast_json_schema(), examples=ast_examples()
            ),
            "",
            provider,
            selector,
        )
        self.config = runtime_config
        self.transport = transport or OpenAITransport(
            api_key=runtime_config.api_key, timeout=runtime_config.timeout
        )
        # Compatibility for callers that accessed the OpenAI client directly.
        self.openai = getattr(self.transport, "client", None)
        self.memory = memory
        self.observability = observability or Observability()

    def grow(self) -> None:
        return None

    @staticmethod
    def supports_temperature(model_name: str) -> bool:
        chat_models = (
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4.1",
            "gpt-4.1-mini",
            "o1",
            "o1-mini",
        )
        return model_name.startswith(chat_models)

    async def eval(self, query: str, type: EvalType = EvalType.WALK) -> EvalResponse:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query},
        ]
        if self.memory:
            history = await self.memory.get()
            for item in reversed(history):
                messages.insert(1, {"role": item.role, "content": item.content})

        request: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        if self.supports_temperature(self.config.model):
            request["temperature"] = self.config.temperature

        available_tools = await self.selector.select(self.provider, query)
        if available_tools:
            request["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description"),
                        "parameters": {
                            "type": "object",
                            "properties": tool["properties"],
                        },
                    },
                }
                for tool in available_tools
            ]

        content = await complete_with_timeout(
            self.transport,
            request,
            self.config.timeout,
            self.observability,
        )
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Model response must contain a JSON object AST")
        jsontree: dict[str, Any] = parsed
        tree = AST.parse(jsontree)
        tree = self.prune(tree)

        if type == EvalType.WALK:
            result: Any = await self.walk(tree)
        else:
            result = tree
        return EvalResponse(
            query=query,
            type=type,
            content=result,
            jsontree=jsontree,
            config=self.config,
            transport=self.transport,
            observability=self.observability,
        )


__all__ = [
    "ArboristConfig",
    "BaseArborist",
    "EvalResponse",
    "EvalType",
    "OpenAIArborist",
    "TreeDescription",
]
