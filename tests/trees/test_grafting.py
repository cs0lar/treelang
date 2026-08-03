import pytest

from treelang.exceptions import TreeTransformationError
from treelang.trees.grafting import graft_expression, wrap_expression
from treelang.trees.schemas.v2 import (
    TreeCall,
    TreeConditional,
    TreeFunctionDefinition,
    TreeLiteral,
    TreeProgram,
    TreeToolCall,
    TreeVariable,
)
from treelang.trees.transforms import TransformationLimits, TreePath


def test_graft_replaces_nested_expression_without_mutating_input():
    original = TreeProgram(
        body=[TreeToolCall(tool="identity", arguments={"value": TreeLiteral(value=1)})]
    )
    original_json = original.model_dump_json()
    path = TreePath(("body", 0, "arguments", "value"))

    result = graft_expression(original, TreeLiteral(value=42), at=path)

    assert original.model_dump_json() == original_json
    assert result.tree.body == [
        TreeToolCall(tool="identity", arguments={"value": TreeLiteral(value=42)})
    ]
    assert result.changes[0].path == path
    assert result.lineage[0].name == "graft-expression"


def test_graft_into_function_body_can_use_lexical_scope():
    program = TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name="identity", params=["value"], body=TreeLiteral(value=None)
            )
        ],
        body=[TreeCall(function="identity", arguments=[TreeLiteral(value=1)])],
    )

    result = graft_expression(
        program,
        TreeVariable(name="value"),
        at=TreePath(("definitions", 0, "body")),
    )

    assert result.tree.definitions[0].body == TreeVariable(name="value")


@pytest.mark.parametrize(
    "path",
    [
        TreePath(),
        TreePath(("body",)),
        TreePath(("body", 5)),
        TreePath(("definitions", 0)),
        TreePath(("body", 0, "arguments")),
    ],
)
def test_graft_rejects_paths_that_do_not_identify_expressions(path):
    program = TreeProgram(body=[TreeLiteral(value=1)])

    with pytest.raises(TreeTransformationError, match="does not identify"):
        graft_expression(program, TreeLiteral(value=2), at=path)


def test_graft_rejects_unbound_variables_and_invalid_user_call_arity():
    program = TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name="identity", params=["value"], body=TreeVariable(name="value")
            )
        ],
        body=[TreeLiteral(value=1)],
    )

    with pytest.raises(TreeTransformationError, match="Unbound variable"):
        graft_expression(
            program,
            TreeVariable(name="missing"),
            at=TreePath(("body", 0)),
        )
    with pytest.raises(TreeTransformationError, match="expects 1 arguments"):
        graft_expression(
            program,
            TreeCall(function="identity"),
            at=TreePath(("body", 0)),
        )


def test_invalid_graft_error_does_not_expose_literal_values():
    program = TreeProgram(body=[TreeLiteral(value=1)])

    with pytest.raises(TreeTransformationError) as captured:
        graft_expression(
            program,
            TreeCall(
                function="missing",
                arguments=[TreeLiteral(value="private-graft-value")],
            ),
            at=TreePath(("body", 0)),
        )

    assert "private-graft-value" not in str(captured.value)


def test_wrap_substitutes_placeholder_with_selected_expression():
    program = TreeProgram(body=[TreeLiteral(value=3)])
    wrapper = TreeToolCall(
        tool="power",
        arguments={
            "a": TreeVariable(name="input"),
            "b": TreeLiteral(value=2),
        },
    )

    result = wrap_expression(
        program,
        wrapper,
        at=TreePath(("body", 0)),
        placeholder="input",
    )

    assert result.tree.body == [
        TreeToolCall(
            tool="power",
            arguments={
                "a": TreeLiteral(value=3),
                "b": TreeLiteral(value=2),
            },
        )
    ]
    assert result.lineage[0].name == "wrap-expression"


def test_wrap_rejects_missing_or_invalid_placeholder():
    program = TreeProgram(body=[TreeLiteral(value=3)])

    with pytest.raises(TreeTransformationError, match="does not reference"):
        wrap_expression(
            program,
            TreeLiteral(value=4),
            at=TreePath(("body", 0)),
        )
    with pytest.raises(TreeTransformationError, match="Invalid wrapper"):
        wrap_expression(
            program,
            TreeVariable(name="graft"),
            at=TreePath(("body", 0)),
            placeholder="not-valid!",
        )


def test_graft_enforces_inclusive_static_node_and_depth_limits():
    program = TreeProgram(body=[TreeLiteral(value=1)])
    graft = TreeConditional(
        condition=TreeLiteral(value=True),
        true_branch=TreeLiteral(value=1),
        false_branch=TreeLiteral(value=0),
    )

    accepted = graft_expression(
        program,
        graft,
        at=TreePath(("body", 0)),
        limits=TransformationLimits(max_nodes=5, max_depth=3),
    )
    assert accepted.tree.body == [graft]

    with pytest.raises(TreeTransformationError, match="max_nodes"):
        graft_expression(
            program,
            graft,
            at=TreePath(("body", 0)),
            limits=TransformationLimits(max_nodes=4),
        )
    with pytest.raises(TreeTransformationError, match="max_depth"):
        graft_expression(
            program,
            graft,
            at=TreePath(("body", 0)),
            limits=TransformationLimits(max_depth=2),
        )


@pytest.mark.parametrize("field", ["max_nodes", "max_depth"])
def test_transformation_limits_require_positive_integers(field):
    with pytest.raises(ValueError, match=field):
        TransformationLimits(**{field: 0})

    with pytest.raises(ValueError, match=field):
        TransformationLimits(**{field: True})
