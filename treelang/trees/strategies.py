"""Injectable contracts for deterministic and asynchronous tree transforms."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from treelang.trees.composition import compose_programs
from treelang.trees.schemas.v1 import TreeNode
from treelang.trees.schemas.v2 import TreeProgram
from treelang.trees.transforms import TransformationLimits, TransformResult

type GeneratedTree = TreeNode | TreeProgram


@dataclass(frozen=True, slots=True)
class GrowthOptions:
    """Deterministic options shared by synchronous and asynchronous growers."""

    mode: Literal["single", "parallel"] = "single"
    name: str | None = None
    description: str | None = None
    limits: TransformationLimits | None = None

    def __post_init__(self) -> None:
        if self.mode not in ("single", "parallel"):
            raise ValueError("mode must be 'single' or 'parallel'")


class TreePruner(Protocol):
    """Strategy that returns a tree and reproducible pruning lineage."""

    def prune(
        self, tree: GeneratedTree
    ) -> TransformResult[TreeNode] | TransformResult[TreeProgram]: ...


class TreeGrower(Protocol):
    """Synchronous deterministic program-growth strategy."""

    def grow(
        self, programs: Sequence[TreeProgram], *, options: GrowthOptions
    ) -> TransformResult[TreeProgram]: ...


class AsyncTreeGrower(Protocol):
    """Asynchronous boundary for model- or evaluation-guided growth."""

    async def grow(
        self, programs: Sequence[TreeProgram], *, options: GrowthOptions
    ) -> TransformResult[TreeProgram]: ...


class ProgramCompositionGrower:
    """Default deterministic grower backed by validated program composition."""

    def grow(
        self, programs: Sequence[TreeProgram], *, options: GrowthOptions
    ) -> TransformResult[TreeProgram]:
        return compose_programs(
            programs,
            mode=options.mode,
            name=options.name,
            description=options.description,
            limits=options.limits,
        )


__all__ = [
    "AsyncTreeGrower",
    "GeneratedTree",
    "GrowthOptions",
    "ProgramCompositionGrower",
    "TreeGrower",
    "TreePruner",
]
