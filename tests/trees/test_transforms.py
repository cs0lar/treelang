from dataclasses import FrozenInstanceError

import pytest

from treelang.trees.schemas.v1 import TreeProgram as TreeProgramV1
from treelang.trees.schemas.v1 import TreeValue
from treelang.trees.schemas.v2 import TreeLiteral
from treelang.trees.schemas.v2 import TreeProgram as TreeProgramV2
from treelang.trees.transforms import (
    TransformationRecord,
    TransformResult,
    TreeChange,
    TreeChangeKind,
    TreePath,
)


def test_tree_path_builds_immutable_schema_neutral_locations():
    root = TreePath()
    body = root.child("body")
    argument = body.child(0).child("arguments").child("value")

    assert root.is_root
    assert root.parent is None
    assert argument.segments == ("body", 0, "arguments", "value")
    assert argument.parent == TreePath(("body", 0, "arguments"))
    assert str(argument) == "/body/0/arguments/value"
    assert body == TreePath(("body",))

    with pytest.raises(FrozenInstanceError):
        argument.segments = ()


def test_tree_path_escapes_json_pointer_fields():
    assert str(TreePath(("a/b", "~name"))) == "/a~1b/~0name"


@pytest.mark.parametrize("segment", ["", -1, True, 1.5, None])
def test_tree_path_rejects_ambiguous_segments(segment):
    expected = ValueError if segment in ("", -1) else TypeError
    with pytest.raises(expected):
        TreePath((segment,))


def test_transformation_result_flattens_deterministic_lineage():
    removed = TreeChange(
        kind=TreeChangeKind.REMOVE,
        path=TreePath(("definitions", 1)),
        description="Remove unreachable function 'unused'.",
    )
    replaced = TreeChange(
        kind=TreeChangeKind.REPLACE,
        path=TreePath(("body", 0)),
        description="Select literal true branch.",
    )
    result = TransformResult(
        tree={"type": "program"},
        lineage=(
            TransformationRecord(name="dead-functions", changes=(removed,)),
            TransformationRecord(name="literal-conditionals", changes=(replaced,)),
        ),
    )

    assert result.changed
    assert result.changes == (removed, replaced)


def test_unchanged_result_and_seeded_record_are_explicit():
    record = TransformationRecord(name="seeded-mutation", seed=42)
    result = TransformResult(tree="unchanged", lineage=(record,))

    assert not result.changed
    assert result.changes == ()
    assert result.lineage[0].seed == 42


@pytest.mark.parametrize(
    "tree",
    [
        TreeProgramV1(body=[TreeValue(name="answer", value=42)], mode="single"),
        TreeProgramV2(body=[TreeLiteral(value=42)]),
    ],
)
def test_transform_result_is_compatible_with_both_schema_versions(tree):
    result = TransformResult(tree=tree)

    assert result.tree is tree
    assert not result.changed


def test_change_records_reject_invalid_move_metadata():
    with pytest.raises(ValueError, match="source path"):
        TreeChange(TreeChangeKind.MOVE, TreePath(), "Move a node.")

    with pytest.raises(ValueError, match="Only move"):
        TreeChange(
            TreeChangeKind.REMOVE,
            TreePath(),
            "Remove a node.",
            source_path=TreePath(("body", 0)),
        )

    with pytest.raises(ValueError, match="descriptions"):
        TreeChange(TreeChangeKind.REMOVE, TreePath(), "")


def test_transformation_records_require_a_name():
    with pytest.raises(ValueError, match="names"):
        TransformationRecord(name="")
