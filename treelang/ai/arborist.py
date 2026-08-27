"""Arborist orchestration for generating and evaluating AST programs."""

import json
import warnings
from collections.abc import Sequence
from typing import Any, Literal

from treelang.ai.capabilities import (
    DefaultModelCapabilityNegotiator,
    ModelCapabilities,
    ModelCapabilityNegotiator,
    StructuredOutputSelection,
)
from treelang.ai.config import ArboristConfig
from treelang.ai.memory import Memory
from treelang.ai.prompt import (
    ARBORIST_SYSTEM_PROMPT,
    RECURSIVE_ARBORIST_SYSTEM_PROMPT,
)
from treelang.ai.provider import ToolProvider
from treelang.ai.responses import EvalResponse, EvalType, TreeDescription
from treelang.ai.selector import AllToolsSelector, BaseToolSelector
from treelang.ai.tool import ToolDefinition, tool_input_schema
from treelang.ai.transport import (
    ModelTransport,
    OpenAIResponsesTransport,
    OpenAITransport,
    complete_with_timeout,
    openai_model_capabilities,
)
from treelang.exceptions import StructuredOutputUnsupportedError
from treelang.observability import Observability
from treelang.trees.budget import ExecutionLimits
from treelang.trees.execution_v2 import execute_v2
from treelang.trees.pruning import ConservativeTreePruner
from treelang.trees.schemas import (
    ast_examples,
    ast_json_schema,
    ast_v2_json_schema,
    recursive_ast_examples,
)
from treelang.trees.schemas.v1 import TreeNode
from treelang.trees.schemas.v2 import AST as ASTV2
from treelang.trees.schemas.v2 import TreeProgram as TreeProgramV2
from treelang.trees.strategies import (
    AsyncTreeGrower,
    GeneratedTree,
    GrowthOptions,
    ProgramCompositionGrower,
    TreeGrower,
    TreePruner,
)
from treelang.trees.transforms import TransformationLimits, TransformResult
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
        execution_limits: ExecutionLimits | None = None,
        *,
        pruning_strategy: TreePruner | None = None,
        growth_strategy: TreeGrower | None = None,
        async_growth_strategy: AsyncTreeGrower | None = None,
    ) -> None:
        self.model = model
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template
        self.provider = provider
        self.selector = selector or AllToolsSelector()
        self.execution_limits = execution_limits
        self.pruning_strategy = pruning_strategy or ConservativeTreePruner()
        self.growth_strategy = growth_strategy or ProgramCompositionGrower()
        self.async_growth_strategy = async_growth_strategy

    def prune(self, tree: GeneratedTree) -> GeneratedTree:
        """Prune and return only the tree for compatibility with existing callers."""

        return self.prune_result(tree).tree

    def prune_result(
        self, tree: GeneratedTree
    ) -> TransformResult[TreeNode] | TransformResult[TreeProgramV2]:
        """Prune a tree and retain its deterministic transformation lineage."""

        return self.pruning_strategy.prune(tree)

    def grow_result(
        self,
        programs: Sequence[TreeProgramV2],
        *,
        mode: Literal["single", "parallel"] = "single",
        name: str | None = None,
        description: str | None = None,
        limits: TransformationLimits | None = None,
    ) -> TransformResult[TreeProgramV2]:
        """Compose programs through the configured synchronous growth strategy."""

        return self.growth_strategy.grow(
            programs,
            options=GrowthOptions(mode, name, description, limits),
        )

    def grow(
        self,
        *programs: TreeProgramV2,
        mode: Literal["single", "parallel"] = "single",
        name: str | None = None,
        description: str | None = None,
        limits: TransformationLimits | None = None,
    ) -> TreeProgramV2 | None:
        """Grow programs synchronously; subclasses define legacy zero-arg behavior."""

        if not programs:
            raise NotImplementedError("grow() requires at least two schema v2 programs")
        return self.grow_result(
            list(programs),
            mode=mode,
            name=name,
            description=description,
            limits=limits,
        ).tree

    async def agrow_result(
        self,
        programs: Sequence[TreeProgramV2],
        *,
        mode: Literal["single", "parallel"] = "single",
        name: str | None = None,
        description: str | None = None,
        limits: TransformationLimits | None = None,
    ) -> TransformResult[TreeProgramV2]:
        """Grow through an explicitly configured asynchronous strategy."""

        if self.async_growth_strategy is None:
            raise NotImplementedError("No asynchronous growth strategy is configured")
        return await self.async_growth_strategy.grow(
            programs,
            options=GrowthOptions(mode, name, description, limits),
        )

    async def agrow(
        self,
        *programs: TreeProgramV2,
        mode: Literal["single", "parallel"] = "single",
        name: str | None = None,
        description: str | None = None,
        limits: TransformationLimits | None = None,
    ) -> TreeProgramV2:
        """Return only the asynchronously grown tree."""

        return (
            await self.agrow_result(
                list(programs),
                mode=mode,
                name=name,
                description=description,
                limits=limits,
            )
        ).tree

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
        capability_negotiator: ModelCapabilityNegotiator | None = None,
        pruning_strategy: TreePruner | None = None,
        growth_strategy: TreeGrower | None = None,
        async_growth_strategy: AsyncTreeGrower | None = None,
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
            pruning_strategy=pruning_strategy,
            growth_strategy=growth_strategy,
            async_growth_strategy=async_growth_strategy,
        )
        self.config = runtime_config
        if transport is not None:
            self.transport = transport
        elif runtime_config.openai_api == "responses":
            self.transport = OpenAIResponsesTransport(
                api_key=runtime_config.api_key, timeout=runtime_config.timeout
            )
        else:
            self.transport = OpenAITransport(
                api_key=runtime_config.api_key, timeout=runtime_config.timeout
            )
        # Compatibility for callers that accessed the OpenAI client directly.
        self.openai = getattr(self.transport, "client", None)
        self.memory = memory
        self.observability = observability or Observability()
        self.capability_negotiator = (
            capability_negotiator or DefaultModelCapabilityNegotiator()
        )

    def grow(
        self,
        *programs: TreeProgramV2,
        mode: Literal["single", "parallel"] = "single",
        name: str | None = None,
        description: str | None = None,
        limits: TransformationLimits | None = None,
    ) -> TreeProgramV2 | None:
        """Grow programs while preserving the legacy no-argument no-op."""

        if not programs:
            warnings.warn(
                "Zero-argument OpenAIArborist.grow() is deprecated; pass at least "
                "two schema v2 programs.",
                DeprecationWarning,
                stacklevel=2,
            )
            return None
        return super().grow(
            *programs,
            mode=mode,
            name=name,
            description=description,
            limits=limits,
        )

    @staticmethod
    def supports_temperature(model_name: str) -> bool:
        """Compatibility helper delegated to the OpenAI transport adapter."""
        return openai_model_capabilities(model_name).temperature

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
        capabilities = self.capability_negotiator.capabilities(
            self.transport, self.config.model
        )
        if capabilities.temperature:
            request["temperature"] = self.config.temperature

        available_tools = await self.selector.select(self.provider, query)
        if self.config.openai_api == "responses":
            request["treelang_tools"] = available_tools
            if self.config.reasoning_effort is not None:
                request["reasoning_effort"] = self.config.reasoning_effort
        elif available_tools:
            request["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description"),
                        "parameters": tool_input_schema(tool),
                    },
                }
                for tool in available_tools
            ]
            # Tools describe the vocabulary available to the generated AST. The
            # model must not invoke them while it is compiling that AST.
            request["tool_choice"] = "none"
        output_selection = self._configure_structured_output(
            request, available_tools, capabilities
        )

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
                fallback = self.capability_negotiator.fallback_after_rejection(
                    output_selection,
                    self.config.structured_output_mode,
                )
                if fallback is None:
                    raise
                output_selection = fallback
                request["response_format"] = fallback.response_format
                self.observability.emit(
                    "model.structured_output.fallback",
                    model=self.config.model,
                    reason=fallback.fallback_reason,
                    error_type=error.__class__.__name__,
                )
                self._observe_structured_output(fallback)
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
        capabilities: ModelCapabilities,
    ) -> StructuredOutputSelection:
        mode = self.config.structured_output_mode
        selection = self.capability_negotiator.structured_output(
            capabilities,
            model=self.config.model,
            configured_mode=mode,
            schema_version=self.config.schema_version,
            tools=tools,
        )
        request["response_format"] = selection.response_format
        if selection.fallback_reason is not None:
            self.observability.emit(
                "model.structured_output.fallback",
                model=self.config.model,
                reason=selection.fallback_reason,
            )
        self._observe_structured_output(selection)
        return selection

    def _observe_structured_output(self, selection: StructuredOutputSelection) -> None:
        self.observability.emit(
            "model.structured_output.selected",
            model=self.config.model,
            mode=selection.mode,
            configured_mode=self.config.structured_output_mode,
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
