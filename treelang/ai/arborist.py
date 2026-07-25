"""Arborist orchestration for generating and evaluating AST programs."""

import json
from typing import Any

from treelang.ai.capabilities import capabilities_for
from treelang.ai.config import ArboristConfig
from treelang.ai.memory import Memory
from treelang.ai.prompt import (
    ARBORIST_SYSTEM_PROMPT,
    RECURSIVE_ARBORIST_SYSTEM_PROMPT,
)
from treelang.ai.provider import ToolProvider
from treelang.ai.responses import EvalResponse, EvalType, TreeDescription
from treelang.ai.selector import AllToolsSelector, BaseToolSelector
from treelang.ai.structured_output import strict_response_format
from treelang.ai.tool import ToolDefinition
from treelang.ai.transport import (
    ModelTransport,
    OpenAITransport,
    complete_with_timeout,
)
from treelang.exceptions import StructuredOutputUnsupportedError
from treelang.observability import Observability
from treelang.trees.budget import ExecutionLimits
from treelang.trees.execution_v2 import execute_v2
from treelang.trees.schemas import (
    ast_examples,
    ast_json_schema,
    ast_v2_json_schema,
    recursive_ast_examples,
)
from treelang.trees.schemas.v1 import TreeNode
from treelang.trees.schemas.v2 import AST as ASTV2
from treelang.trees.schemas.v2 import TreeProgram as TreeProgramV2
from treelang.trees.tree import AST

type GeneratedTree = TreeNode | TreeProgramV2


class BaseArborist:
    """Base orchestration interface for AST-generating agents."""

    def __init__(
        self,
        model: str,
        system_prompt: str,
        user_prompt_template: str,
        provider: ToolProvider,
        selector: BaseToolSelector | None = None,
        execution_limits: ExecutionLimits | None = None,
    ) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template
        self.provider = provider
        self.selector = selector or AllToolsSelector()
        self.execution_limits = execution_limits

    def prune(self, tree: GeneratedTree) -> GeneratedTree:
        return tree

    def grow(self) -> None:
        raise NotImplementedError()

    async def walk(self, tree: GeneratedTree) -> Any:
        if isinstance(tree, TreeProgramV2):
            limits = self.execution_limits
            if (
                limits is None
                or limits.max_call_depth is None
                or limits.max_nodes is None
                or limits.timeout_seconds is None
            ):
                raise ValueError(
                    "Schema v2 WALK requires execution limits for max_call_depth, "
                    "max_nodes, and timeout_seconds"
                )
            return await execute_v2(tree, self.provider, limits=limits)
        return await AST.eval(tree, self.provider, limits=self.execution_limits)

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
        execution_limits: ExecutionLimits | None = None,
    ) -> None:
        runtime_config = config or ArboristConfig.from_env(model)
        if runtime_config.schema_version == "2.0":
            prompt = RECURSIVE_ARBORIST_SYSTEM_PROMPT.format(
                schema=ast_v2_json_schema(), examples=recursive_ast_examples()
            )
        else:
            prompt = ARBORIST_SYSTEM_PROMPT.format(
                schema=ast_json_schema(), examples=ast_examples()
            )
        super().__init__(
            runtime_config.model,
            prompt,
            "",
            provider,
            selector,
            execution_limits,
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
        self._configure_structured_output(request, available_tools)

        content = ""
        jsontree: dict[str, Any]
        tree: GeneratedTree
        for attempt in range(self.config.validation_retries + 1):
            try:
                content = await complete_with_timeout(
                    self.transport,
                    request,
                    self.config.timeout,
                    self.observability,
                )
            except StructuredOutputUnsupportedError as error:
                if (
                    self.config.structured_output_mode != "auto"
                    or request["response_format"]["type"] != "json_schema"
                ):
                    raise
                request["response_format"] = {"type": "json_object"}
                self.observability.emit(
                    "model.structured_output.fallback",
                    model=self.config.model,
                    reason="provider_rejected",
                    error_type=error.__class__.__name__,
                )
                content = await complete_with_timeout(
                    self.transport,
                    request,
                    self.config.timeout,
                    self.observability,
                )
            try:
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise ValueError("Model response must contain a JSON object AST")
                jsontree = parsed
                if self.config.schema_version == "2.0":
                    tree = ASTV2.model_validate(jsontree).root
                else:
                    tree = AST.parse(jsontree)
                break
            except (json.JSONDecodeError, ValueError) as error:
                if attempt == self.config.validation_retries:
                    raise
                self.observability.emit(
                    "model.response.validation_retry",
                    attempt=attempt + 1,
                    error=f"{error.__class__.__name__}: {error}",
                )
                messages.extend(
                    [
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": (
                                "The JSON AST failed validation. Return a corrected, "
                                "complete program JSON object only. Validation error: "
                                f"{error}"
                            ),
                        },
                    ]
                )
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

    def _configure_structured_output(
        self,
        request: dict[str, Any],
        tools: list[ToolDefinition],
    ) -> None:
        mode = self.config.structured_output_mode
        capabilities = capabilities_for(self.transport, self.config.model)
        if mode == "compatibility":
            request["response_format"] = {"type": "json_object"}
            selected = "compatibility"
        elif capabilities.strict_json_schema:
            request["response_format"] = strict_response_format(
                self.config.schema_version, tools
            )
            selected = "strict"
        elif mode == "required":
            raise StructuredOutputUnsupportedError(
                f"Model '{self.config.model}' does not declare strict JSON Schema "
                "support"
            )
        else:
            request["response_format"] = {"type": "json_object"}
            selected = "compatibility"
            self.observability.emit(
                "model.structured_output.fallback",
                model=self.config.model,
                reason="capability_unavailable",
            )
        self.observability.emit(
            "model.structured_output.selected",
            model=self.config.model,
            mode=selected,
            configured_mode=mode,
            schema_version=self.config.schema_version,
        )


__all__ = [
    "ArboristConfig",
    "BaseArborist",
    "EvalResponse",
    "EvalType",
    "OpenAIArborist",
    "TreeDescription",
]
