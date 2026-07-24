import pytest
from pydantic import ValidationError

from treelang.trees.schemas.v2 import (
    AST,
    TreeCall,
    TreeConditional,
    TreeFunctionDefinition,
    TreeLiteral,
    TreeProgram,
    TreeToolCall,
    TreeVariable,
)


def factorial_program() -> TreeProgram:
    return TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name="factorial",
                params=["n"],
                body=TreeConditional(
                    condition=TreeToolCall(
                        tool="less_than_or_equal",
                        arguments={
                            "a": TreeVariable(name="n"),
                            "b": TreeLiteral(value=1),
                        },
                    ),
                    true_branch=TreeLiteral(value=1),
                    false_branch=TreeToolCall(
                        tool="multiply",
                        arguments={
                            "a": TreeVariable(name="n"),
                            "b": TreeCall(
                                function="factorial",
                                arguments=[
                                    TreeToolCall(
                                        tool="subtract",
                                        arguments={
                                            "a": TreeVariable(name="n"),
                                            "b": TreeLiteral(value=1),
                                        },
                                    )
                                ],
                            ),
                        },
                    ),
                ),
            )
        ],
        body=[TreeCall(function="factorial", arguments=[TreeLiteral(value=5)])],
        mode="single",
    )


def test_validates_direct_recursion_and_serialized_version():
    ast = AST(root=factorial_program())

    assert ast.root.schema_version == "2.0"
    assert '"schema_version":"2.0"' in ast.model_dump_json()


def test_validates_forward_references_and_mutual_recursion():
    program = TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name="even",
                params=["n"],
                body=TreeCall(function="odd", arguments=[TreeVariable(name="n")]),
            ),
            TreeFunctionDefinition(
                name="odd",
                params=["n"],
                body=TreeCall(function="even", arguments=[TreeVariable(name="n")]),
            ),
        ],
        body=[TreeCall(function="even", arguments=[TreeLiteral(value=2)])],
    )

    assert AST(root=program).root == program


@pytest.mark.parametrize(
    ("program", "message"),
    [
        (
            TreeProgram(
                definitions=[
                    TreeFunctionDefinition(
                        name="duplicate", params=[], body=TreeLiteral(value=1)
                    ),
                    TreeFunctionDefinition(
                        name="duplicate", params=[], body=TreeLiteral(value=2)
                    ),
                ],
                body=[TreeLiteral(value=None)],
            ),
            "must be unique",
        ),
        (
            TreeProgram(
                definitions=[],
                body=[TreeCall(function="missing", arguments=[])],
            ),
            "Unknown user function",
        ),
        (
            TreeProgram(
                definitions=[
                    TreeFunctionDefinition(
                        name="identity",
                        params=["value"],
                        body=TreeVariable(name="value"),
                    )
                ],
                body=[TreeCall(function="identity", arguments=[])],
            ),
            "expects 1 arguments",
        ),
        (
            TreeProgram(
                definitions=[
                    TreeFunctionDefinition(
                        name="broken",
                        params=["bound"],
                        body=TreeVariable(name="unbound"),
                    )
                ],
                body=[TreeLiteral(value=None)],
            ),
            "Unbound variable",
        ),
        (
            TreeProgram(definitions=[], body=[TreeVariable(name="not_global")]),
            "Unbound variable",
        ),
    ],
)
def test_rejects_invalid_program_contracts(program: TreeProgram, message: str):
    with pytest.raises(ValidationError, match=message):
        AST(root=program)


def test_rejects_duplicate_parameters():
    with pytest.raises(ValidationError, match="parameter names must be unique"):
        TreeFunctionDefinition(
            name="bad",
            params=["value", "value"],
            body=TreeVariable(name="value"),
        )


def test_rejects_invalid_identifiers_and_extra_fields():
    with pytest.raises(ValidationError):
        TreeVariable(name="not valid")
    with pytest.raises(ValidationError):
        TreeLiteral.model_validate({"type": "literal", "value": 1, "extra": True})


def test_user_and_tool_calls_are_structurally_distinct():
    program = TreeProgram(
        definitions=[
            TreeFunctionDefinition(
                name="calculate", params=[], body=TreeLiteral(value=1)
            )
        ],
        body=[
            TreeCall(function="calculate"),
            TreeToolCall(tool="calculate"),
        ],
        mode="parallel",
    )

    assert AST(root=program).root.body[0].type == "call"
    assert AST(root=program).root.body[1].type == "tool_call"


def test_v2_schema_does_not_accept_a_v1_program():
    with pytest.raises(ValidationError):
        AST.model_validate(
            {
                "type": "program",
                "schema_version": "1.0",
                "body": [{"type": "value", "name": "answer", "value": 42}],
                "mode": "single",
            }
        )
