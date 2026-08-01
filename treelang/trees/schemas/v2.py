"""Opt-in schema models for recursive Treelang programs.

Importing and validating these models does not change the version 1 root API.
Version 2 execution and model generation remain explicitly selected features.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from treelang.trees.schemas.v1 import JsonValue

Identifier = Annotated[str, Field(min_length=1, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]


class TreeExpression(BaseModel):
    """Base model for a version 2 expression."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TreeLiteral(TreeExpression):
    """A JSON-compatible literal value."""

    type: Literal["literal"] = "literal"
    value: JsonValue


class TreeVariable(TreeExpression):
    """A lexical variable reference."""

    type: Literal["variable"] = "variable"
    name: Identifier


class TreeCall(TreeExpression):
    """A call to a user-defined function."""

    type: Literal["call"] = "call"
    function: Identifier
    arguments: list["Expression"] = Field(default_factory=list)


class TreeToolCall(TreeExpression):
    """A call to an external provider tool."""

    type: Literal["tool_call"] = "tool_call"
    tool: Identifier
    arguments: dict[Identifier, "Expression"] = Field(default_factory=dict)


class TreeMemo(TreeExpression):
    """Memoize one closed expression within a program invocation."""

    type: Literal["memo"] = "memo"
    key: Identifier
    expression: "Expression"


class TreeConditional(TreeExpression):
    """A lazily evaluated conditional expression."""

    type: Literal["conditional"] = "conditional"
    condition: "Expression"
    true_branch: "Expression"
    false_branch: "Expression"


type Expression = Annotated[
    TreeLiteral | TreeVariable | TreeCall | TreeToolCall | TreeConditional | TreeMemo,
    Field(discriminator="type"),
]


class TreeFunctionDefinition(BaseModel):
    """A globally declared user function with a lexical parameter scope."""

    type: Literal["function_definition"] = "function_definition"
    name: Identifier
    params: list[Identifier] = Field(default_factory=list)
    body: Expression

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_unique_params(self) -> TreeFunctionDefinition:
        if len(self.params) != len(set(self.params)):
            raise ValueError(f"Function '{self.name}' parameter names must be unique.")
        return self


class TreeProgram(BaseModel):
    """A version 2 program containing declarations and root expressions."""

    type: Literal["program"] = "program"
    definitions: list[TreeFunctionDefinition] = Field(default_factory=list)
    body: list[Expression] = Field(min_length=1)
    mode: Literal["single", "parallel"] = "single"
    name: str | None = None
    description: str | None = None
    schema_version: Literal["2.0"] = "2.0"

    model_config = ConfigDict(extra="forbid", frozen=True)


TreeCall.model_rebuild()
TreeToolCall.model_rebuild()
TreeConditional.model_rebuild()
TreeMemo.model_rebuild()
TreeFunctionDefinition.model_rebuild()
TreeProgram.model_rebuild()


class AST(RootModel[TreeProgram]):
    """Validate the complete static contract of a version 2 program."""

    @model_validator(mode="after")
    def validate_program(self) -> AST:
        definitions: dict[str, TreeFunctionDefinition] = {}
        for definition in self.root.definitions:
            if definition.name in definitions:
                raise ValueError(
                    f"Function definition '{definition.name}' must be unique."
                )
            definitions[definition.name] = definition

        memo_expressions: dict[str, str] = {}

        def contains_variable(expression: Expression) -> bool:
            if isinstance(expression, TreeVariable):
                return True
            if isinstance(expression, TreeCall):
                return any(contains_variable(item) for item in expression.arguments)
            if isinstance(expression, TreeToolCall):
                return any(
                    contains_variable(item) for item in expression.arguments.values()
                )
            if isinstance(expression, TreeConditional):
                return any(
                    contains_variable(item)
                    for item in (
                        expression.condition,
                        expression.true_branch,
                        expression.false_branch,
                    )
                )
            if isinstance(expression, TreeMemo):
                return contains_variable(expression.expression)
            return False

        def walk(expression: Expression, scope: frozenset[str]) -> None:
            if isinstance(expression, TreeVariable):
                if expression.name not in scope:
                    raise ValueError(f"Unbound variable '{expression.name}'.")
                return
            if isinstance(expression, TreeCall):
                definition = definitions.get(expression.function)
                if definition is None:
                    raise ValueError(f"Unknown user function '{expression.function}'.")
                expected = len(definition.params)
                actual = len(expression.arguments)
                if actual != expected:
                    raise ValueError(
                        f"Function '{expression.function}' expects {expected} "
                        f"arguments, got {actual}."
                    )
                for argument in expression.arguments:
                    walk(argument, scope)
                return
            if isinstance(expression, TreeToolCall):
                for argument in expression.arguments.values():
                    walk(argument, scope)
                return
            if isinstance(expression, TreeConditional):
                walk(expression.condition, scope)
                walk(expression.true_branch, scope)
                walk(expression.false_branch, scope)
                return
            if isinstance(expression, TreeMemo):
                if contains_variable(expression.expression):
                    raise ValueError("Memoized expressions must be closed.")
                canonical = expression.expression.model_dump_json()
                previous = memo_expressions.setdefault(expression.key, canonical)
                if previous != canonical:
                    raise ValueError(
                        f"Memo key '{expression.key}' identifies different expressions."
                    )
                walk(expression.expression, scope)

        for definition in definitions.values():
            walk(definition.body, frozenset(definition.params))
        for expression in self.root.body:
            walk(expression, frozenset())
        return self


class ASTExample(TypedDict):
    """One question and canonical serialized version 2 AST example."""

    q: str
    a: str


def ast_v2_examples() -> list[ASTExample]:
    """Return canonical examples for model prompts."""
    factorial = AST(
        root=TreeProgram(
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
            name="Factorial",
            description="Calculate factorial recursively.",
        )
    )
    return [
        {
            "q": "Calculate 5 factorial recursively.",
            "a": factorial.model_dump_json(exclude_unset=False),
        }
    ]


__all__ = [
    "AST",
    "Expression",
    "TreeCall",
    "TreeConditional",
    "TreeFunctionDefinition",
    "TreeLiteral",
    "TreeMemo",
    "TreeProgram",
    "TreeToolCall",
    "TreeVariable",
    "ast_v2_examples",
]
