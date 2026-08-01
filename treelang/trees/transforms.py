"""Schema-neutral records for immutable tree transformations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

type TreePathSegment = str | int


@dataclass(frozen=True, slots=True)
class TreePath:
    """Identify a node by field names and zero-based sequence indexes.

    Paths are structural rather than object-identity based, so they remain stable
    across serialization and immutable model copies. The empty path identifies the
    transformation root.
    """

    segments: tuple[TreePathSegment, ...] = ()

    def __post_init__(self) -> None:
        for segment in self.segments:
            if isinstance(segment, bool) or not isinstance(segment, (str, int)):
                raise TypeError("Tree path segments must be strings or integers")
            if isinstance(segment, str) and not segment:
                raise ValueError("Tree path field names must not be empty")
            if isinstance(segment, int) and segment < 0:
                raise ValueError("Tree path indexes must not be negative")

    @property
    def is_root(self) -> bool:
        """Return whether this path identifies the transformation root."""

        return not self.segments

    @property
    def parent(self) -> TreePath | None:
        """Return the containing path, or ``None`` for the root path."""

        if self.is_root:
            return None
        return TreePath(self.segments[:-1])

    def child(self, segment: TreePathSegment) -> TreePath:
        """Return a new path extended by one field name or sequence index."""

        return TreePath((*self.segments, segment))

    def __str__(self) -> str:
        """Render the path as an escaped JSON Pointer."""

        return "".join(
            f"/{str(segment).replace('~', '~0').replace('/', '~1')}"
            for segment in self.segments
        )


class TreeChangeKind(StrEnum):
    """Structural operations that a transformation can report."""

    INSERT = "insert"
    MOVE = "move"
    REMOVE = "remove"
    RENAME = "rename"
    REPLACE = "replace"


@dataclass(frozen=True, slots=True)
class TreeChange:
    """One deterministic structural change made by a transformation."""

    kind: TreeChangeKind
    path: TreePath
    description: str
    source_path: TreePath | None = None

    def __post_init__(self) -> None:
        if not self.description:
            raise ValueError("Tree change descriptions must not be empty")
        if self.kind is TreeChangeKind.MOVE and self.source_path is None:
            raise ValueError("Move changes must identify their source path")
        if self.kind is not TreeChangeKind.MOVE and self.source_path is not None:
            raise ValueError("Only move changes can identify a source path")


@dataclass(frozen=True, slots=True)
class TransformationRecord:
    """Named transformation step and the changes it produced."""

    name: str
    changes: tuple[TreeChange, ...] = ()
    seed: int | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Transformation names must not be empty")


@dataclass(frozen=True, slots=True)
class TransformResult[TreeT]:
    """A transformed tree together with its complete reproducible lineage."""

    tree: TreeT
    lineage: tuple[TransformationRecord, ...] = ()

    @property
    def changes(self) -> tuple[TreeChange, ...]:
        """Return all reported changes in lineage order."""

        return tuple(change for record in self.lineage for change in record.changes)

    @property
    def changed(self) -> bool:
        """Return whether any lineage record reports a structural change."""

        return bool(self.changes)


__all__ = [
    "TransformResult",
    "TransformationRecord",
    "TreeChange",
    "TreeChangeKind",
    "TreePath",
    "TreePathSegment",
]
