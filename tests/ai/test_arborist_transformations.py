from typing import Any

import pytest

from treelang.ai.arborist import BaseArborist, OpenAIArborist
from treelang.ai.config import ArboristConfig
from treelang.ai.provider import ToolOutput, ToolProvider
from treelang.trees.schemas.v1 import TreeValue
from treelang.trees.schemas.v2 import (
    TreeFunctionDefinition,
    TreeLiteral,
    TreeProgram,
)
from treelang.trees.strategies import GrowthOptions
from treelang.trees.transforms import (
    TransformationRecord,
    TransformResult,
    TreeChange,
    TreeChangeKind,
    TreePath,
)


class EmptyProvider(ToolProvider):
    async def list_tools(self):
        self.tools = {}
        return []

    async def call_tool(self, name, arguments):
        return ToolOutput(content=None)


class ReplacementPruner:
    def __init__(self) -> None:
        self.seen: Any = None

    def prune(self, tree):
        self.seen = tree
        replacement = TreeValue(name="pruned", value=2)
        return TransformResult(
            tree=replacement,
            lineage=(
                TransformationRecord(
                    name="replacement",
                    changes=(
                        TreeChange(
                            TreeChangeKind.REPLACE,
                            TreePath(),
                            "Replace test tree.",
                        ),
                    ),
                ),
            ),
        )


class RecordingGrower:
    def __init__(self) -> None:
        self.programs = []
        self.options: GrowthOptions | None = None

    def grow(self, programs, *, options):
        self.programs = list(programs)
        self.options = options
        return TransformResult(
            tree=TreeProgram(body=[TreeLiteral(value="sync")]),
            lineage=(TransformationRecord(name="sync-grow"),),
        )


class RecordingAsyncGrower:
    def __init__(self) -> None:
        self.options: GrowthOptions | None = None

    async def grow(self, programs, *, options):
        self.options = options
        return TransformResult(
            tree=TreeProgram(body=[TreeLiteral(value="async")]),
            lineage=(TransformationRecord(name="async-grow"),),
        )


def test_prune_compatibility_method_unwraps_injected_strategy_result():
    strategy = ReplacementPruner()
    arborist = BaseArborist(
        "model",
        "system",
        "user",
        EmptyProvider(),
        pruning_strategy=strategy,
    )
    source = TreeValue(name="source", value=1)

    result = arborist.prune_result(source)

    assert strategy.seen is source
    assert result.changed
    assert arborist.prune(source) == TreeValue(name="pruned", value=2)


def test_default_pruner_and_grower_delegate_to_core_transformations():
    arborist = BaseArborist("model", "system", "user", EmptyProvider())
    with_dead_definition = TreeProgram(
        definitions=[TreeFunctionDefinition(name="unused", body=TreeLiteral(value=0))],
        body=[TreeLiteral(value=1)],
    )

    pruned = arborist.prune_result(with_dead_definition)
    grown = arborist.grow(
        TreeProgram(body=[TreeLiteral(value=1)]),
        TreeProgram(body=[TreeLiteral(value=2)]),
        mode="parallel",
    )

    assert pruned.tree.definitions == []
    assert pruned.changed
    assert grown is not None
    assert grown.mode == "parallel"
    assert grown.body == [TreeLiteral(value=1), TreeLiteral(value=2)]


def test_injected_synchronous_grower_receives_immutable_options():
    strategy = RecordingGrower()
    arborist = BaseArborist(
        "model",
        "system",
        "user",
        EmptyProvider(),
        growth_strategy=strategy,
    )
    programs = [
        TreeProgram(body=[TreeLiteral(value=1)]),
        TreeProgram(body=[TreeLiteral(value=2)]),
    ]

    result = arborist.grow_result(
        programs,
        mode="parallel",
        name="name",
        description="description",
    )

    assert result.lineage[0].name == "sync-grow"
    assert strategy.programs == programs
    assert strategy.options == GrowthOptions(
        mode="parallel", name="name", description="description"
    )

    with pytest.raises(ValueError, match="mode"):
        GrowthOptions(mode="invalid")


@pytest.mark.asyncio
async def test_asynchronous_growth_has_a_separate_injected_boundary():
    programs = [
        TreeProgram(body=[TreeLiteral(value=1)]),
        TreeProgram(body=[TreeLiteral(value=2)]),
    ]
    without_strategy = BaseArborist("model", "system", "user", EmptyProvider())
    with pytest.raises(NotImplementedError, match="asynchronous"):
        await without_strategy.agrow(*programs)

    strategy = RecordingAsyncGrower()
    arborist = BaseArborist(
        "model",
        "system",
        "user",
        EmptyProvider(),
        async_growth_strategy=strategy,
    )

    grown = await arborist.agrow(*programs, name="async name")

    assert grown.body == [TreeLiteral(value="async")]
    assert strategy.options == GrowthOptions(name="async name")


def test_legacy_zero_argument_grow_behavior_is_preserved():
    base = BaseArborist("model", "system", "user", EmptyProvider())
    with pytest.raises(NotImplementedError):
        base.grow()

    openai = OpenAIArborist(
        "model",
        EmptyProvider(),
        config=ArboristConfig(model="model"),
        transport=object(),
    )
    with pytest.warns(DeprecationWarning, match="Zero-argument"):
        assert openai.grow() is None
