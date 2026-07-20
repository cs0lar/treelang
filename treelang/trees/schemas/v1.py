from hashlib import sha256
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
    Union,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationInfo,
    model_validator,
)

from treelang.ai.provider import ToolProvider

if TYPE_CHECKING:
    from treelang.trees.execution import ExecutionContext


class TreeNode(BaseModel):
    """
    Represents a node in the abstract syntax tree (AST).
    """

    type: Literal["node"] = "node"

    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields not defined in the model
        frozen=False,  # Allow mutation of model instances
        validate_assignment=True,  # Validate fields on assignment
        populate_by_name=True,  # For alias support
    )

    async def eval(
        self, provider: ToolProvider, context: "ExecutionContext | None" = None
    ) -> Any:
        from treelang.trees.execution import evaluate

        return await evaluate(self, provider, context)

    def hash(self) -> str:
        canonical_json = self.model_dump_json(by_alias=True, exclude_unset=False)
        return sha256(canonical_json.encode("utf-8")).hexdigest()


# Define JSON value types for `TreeValue.value`
JsonPrimitive = Union[str, int, float, bool, None]
type JsonValue = Union[JsonPrimitive, List["JsonValue"], Dict[str, "JsonValue"]]


class TreeValue(TreeNode):
    """
    Represents a value in the abstract syntax tree (AST).
    """

    type: Literal["value"] = "value"  # type: ignore[assignment]
    name: str = Field(..., min_length=1)
    value: JsonValue

    async def eval(
        self, provider: ToolProvider, context: "ExecutionContext | None" = None
    ) -> Any:
        from treelang.trees.execution import evaluate

        return await evaluate(self, provider, context)


class TreeFunction(TreeNode):
    """
    Represents a function in the abstract syntax tree (AST).
    """

    type: Literal["function"] = "function"  # type: ignore[assignment]
    name: str = Field(..., min_length=1)
    params: List["Node"]

    async def eval(
        self, provider: ToolProvider, context: "ExecutionContext | None" = None
    ) -> Any:
        from treelang.trees.execution import evaluate

        return await evaluate(self, provider, context)


class TreeProgram(TreeNode):
    """
    Represents a program in the abstract syntax tree (AST).
    """

    type: Literal["program"] = "program"  # type: ignore[assignment]
    body: List["Node"]
    mode: Literal["single", "parallel"]
    name: Optional[str] = None
    description: Optional[str] = None
    schema_version: Literal["1.0"] = "1.0"

    async def eval(
        self, provider: ToolProvider, context: "ExecutionContext | None" = None
    ) -> Any:
        from treelang.trees.execution import evaluate

        return await evaluate(self, provider, context)


class TreeConditional(TreeNode):
    """
    Represents a conditional statement in the AST.
    """

    type: Literal["conditional"] = "conditional"  # type: ignore[assignment]
    condition: "Node"
    true_branch: "Node"
    false_branch: Optional["Node"] = None

    async def eval(
        self, provider: ToolProvider, context: "ExecutionContext | None" = None
    ) -> Any:
        from treelang.trees.execution import evaluate

        return await evaluate(self, provider, context)


class TreeLambda(TreeNode):
    """
    Represents an anonymous (lambda) function.
    """

    type: Literal["lambda"] = "lambda"  # type: ignore[assignment]
    params: List[str]
    body: TreeFunction

    async def eval(
        self, provider: ToolProvider, context: "ExecutionContext | None" = None
    ) -> Any:
        from treelang.trees.execution import evaluate

        return await evaluate(self, provider, context)


class TreeMap(TreeNode):
    """
    Represents a map operation in the abstract syntax tree (AST).
    """

    type: Literal["map"] = "map"  # type: ignore[assignment]
    function: TreeLambda
    iterable: "Node"

    async def eval(
        self, provider: ToolProvider, context: "ExecutionContext | None" = None
    ) -> Any:
        from treelang.trees.execution import evaluate

        return await evaluate(self, provider, context)


class TreeFilter(TreeNode):
    """
    Represents a filter operation in the abstract syntax tree (AST).
    """

    type: Literal["filter"] = "filter"  # type: ignore[assignment]
    function: TreeLambda
    iterable: "Node"

    async def eval(
        self, provider: ToolProvider, context: "ExecutionContext | None" = None
    ) -> Any:
        from treelang.trees.execution import evaluate

        return await evaluate(self, provider, context)


class TreeReduce(TreeNode):
    """
    Represents a reduce operation in the abstract syntax tree (AST).
    """

    type: Literal["reduce"] = "reduce"  # type: ignore[assignment]
    function: TreeLambda
    iterable: "Node"

    async def eval(
        self, provider: ToolProvider, context: "ExecutionContext | None" = None
    ) -> Any:
        from treelang.trees.execution import evaluate

        return await evaluate(self, provider, context)


type Node = Annotated[
    Union[
        TreeProgram,
        TreeFunction,
        TreeValue,
        TreeConditional,
        TreeLambda,
        TreeMap,
        TreeFilter,
        TreeReduce,
    ],
    Field(discriminator="type"),
]

TreeProgram.model_rebuild()
TreeFunction.model_rebuild()
TreeValue.model_rebuild()
TreeConditional.model_rebuild()
TreeLambda.model_rebuild()
TreeMap.model_rebuild()
TreeFilter.model_rebuild()
TreeReduce.model_rebuild()


class AST(RootModel[TreeProgram]):
    """
    Root wrapper for top level node validation.
    """

    @model_validator(mode="after")
    def enforce_function_param_count_and_order(self, info: ValidationInfo) -> "AST":
        """
        Optional enforcement using tool signatures.

        Provide context:
          AST.model_validate(obj, context={"tool_param_order": {"toolname": ["a","b"]}})

        This enforces:
          len(params) == len(expected)
        and can be extended to enforce types/constraints per arg.
        """
        ctx = info.context or {}
        sig_map: dict[str, list[str]] = ctx.get("tool_param_order", {})

        def lambda_values(n: Node) -> list[TreeValue]:
            if isinstance(n, TreeValue):
                return [n]
            if isinstance(n, TreeFunction):
                return [value for child in n.params for value in lambda_values(child)]
            if isinstance(n, TreeConditional):
                branches = [n.condition, n.true_branch]
                if n.false_branch is not None:
                    branches.append(n.false_branch)
                return [value for child in branches for value in lambda_values(child)]
            if isinstance(n, (TreeMap, TreeFilter, TreeReduce)):
                return lambda_values(n.iterable)
            if isinstance(n, (TreeLambda, TreeProgram)):
                return []
            return []

        def walk(n: Node) -> None:
            if isinstance(n, TreeFunction) and n.name in sig_map:
                expected = sig_map[n.name]
                got_n = len(n.params)
                exp_n = len(expected)
                if got_n != exp_n:
                    raise ValueError(
                        f"Function '{n.name}' expects {exp_n} positional params "
                        f"({expected}), got {got_n}."
                    )

            if isinstance(n, TreeLambda):
                if len(n.params) != len(set(n.params)):
                    raise ValueError("Lambda parameter names must be unique.")
                values = lambda_values(n.body)
                referenced_names = {value.name for value in values}
                missing = [name for name in n.params if name not in referenced_names]
                invalid_nulls = sorted(
                    {
                        value.name
                        for value in values
                        if value.value is None and value.name not in n.params
                    }
                )
                if missing or invalid_nulls:
                    details: list[str] = []
                    if missing:
                        details.append(
                            f"params {missing} are not referenced by name in the body"
                        )
                    if invalid_nulls:
                        details.append(
                            f"null placeholders {invalid_nulls} do not match a lambda param"
                        )
                    raise ValueError(f"Invalid lambda binding: {'; '.join(details)}.")

            if isinstance(n, TreeProgram):
                for c in n.body:
                    walk(c)
            elif isinstance(n, TreeConditional):
                walk(n.condition)
                walk(n.true_branch)
                if n.false_branch is not None:
                    walk(n.false_branch)
            elif isinstance(n, TreeLambda):
                # body may be TreeFunction or FunctionBodySpec
                body = n.body
                if isinstance(body, TreeFunction):
                    walk(body)
                else:
                    for p in body.params:
                        walk(p)
            elif isinstance(n, (TreeMap, TreeFilter, TreeReduce)):
                walk(n.function)
                walk(n.iterable)
            elif isinstance(n, TreeFunction):
                for p in n.params:
                    walk(p)

        walk(self.root)
        return self


class ASTExample(TypedDict):
    """One question and canonical serialized AST example."""

    q: str
    a: str


def ast_v1_examples() -> list[ASTExample]:
    """Provide example ASTs in canonical JSON format for use in few-shots prompts for LLMs."""
    examples: list[ASTExample] = []

    example_1: ASTExample = {
        "q": "Can you calculate (12*6)+4?",
        "a": AST(
            root=TreeProgram(
                body=[
                    TreeFunction(
                        name="add",
                        params=[
                            TreeFunction(
                                name="multiply",
                                params=[
                                    TreeValue(name="a", value=12),
                                    TreeValue(name="b", value=6),
                                ],
                            ),
                            TreeValue(name="c", value=4),
                        ],
                    )
                ],
                mode="single",
                name="Calculate (12*6)+4",
                description="A simple arithmetic calculation using add and multiply functions.",
            )
        ).model_dump_json(by_alias=True, exclude_unset=False),
    }
    examples.append(example_1)
    example_2: ASTExample = {
        "q": "Chart the distribution of a list of 100 random numbers between 1 and 10.",
        "a": AST(
            root=TreeProgram(
                body=[
                    TreeFunction(
                        name="chart_distribution",
                        params=[
                            TreeFunction(
                                name="generate_random_numbers",
                                params=[
                                    TreeValue(name="count", value=100),
                                    TreeValue(name="min", value=1),
                                    TreeValue(name="max", value=10),
                                ],
                            ),
                            TreeValue(name="bins", value=10),
                            TreeValue(name="title", value="Random Number Distribution"),
                            TreeValue(name="xlabel", value="Number"),
                            TreeValue(name="ylabel", value="Frequency"),
                        ],
                    )
                ],
                name="Chart Random Number Distribution",
                description="Generates 100 random numbers between 1 and 10 and charts their distribution.",
                mode="single",
            )
        ).model_dump_json(by_alias=True, exclude_unset=False),
    }
    examples.append(example_2)

    example_conditional: ASTExample = {
        "q": "Calculate 12*6, but if the result is greater than 50, return 50.",
        "a": AST(
            root=TreeProgram(
                body=[
                    TreeConditional(
                        condition=TreeFunction(
                            name="greater_than",
                            params=[
                                TreeFunction(
                                    name="multiply",
                                    params=[
                                        TreeValue(name="a", value=12),
                                        TreeValue(name="b", value=6),
                                    ],
                                ),
                                TreeValue(name="b", value=50),
                            ],
                        ),
                        true_branch=TreeValue(name="result", value=50),
                        false_branch=TreeFunction(
                            name="multiply",
                            params=[
                                TreeValue(name="a", value=12),
                                TreeValue(name="b", value=6),
                            ],
                        ),
                    )
                ],
                mode="single",
                name="Cap Multiplication Result",
                description="Multiplies two values and caps the result at 50.",
            )
        ).model_dump_json(by_alias=True, exclude_unset=False),
    }
    examples.append(example_conditional)

    example_3: ASTExample = {
        "q": "Calculate the resistance of a wire with a length of 5m and cross sectional area 0.01m\u00b2 with resistivity of copper and aluminum.",
        "a": AST(
            root=TreeProgram(
                body=[
                    TreeMap(
                        function=TreeLambda(
                            params=["material_resistivity"],
                            body=TreeFunction(
                                name="calculate_resistance",
                                params=[
                                    TreeValue(name="length", value=5),
                                    TreeValue(name="area", value=0.01),
                                    TreeValue(name="material_resistivity", value=None),
                                ],
                            ),
                        ),
                        iterable=TreeValue(
                            name="material_resistivities",
                            value={
                                "copper": 1.68e-8,
                                "aluminum": 2.82e-8,
                            },
                        ),
                    )
                ],
                mode="single",
                name="Calculate Wire Resistance for Different Materials",
                description="Calculates the resistance of a wire made of copper and aluminum given length, area, and resistivity.",
            )
        ).model_dump_json(by_alias=True, exclude_unset=False),
    }
    examples.append(example_3)

    example_4: ASTExample = {
        "q": "Filter out even numbers from a list of numbers from 1 to 10.",
        "a": AST(
            root=TreeProgram(
                body=[
                    TreeFilter(
                        function=TreeLambda(
                            params=["num"],
                            body=TreeFunction(
                                name="is_odd",
                                params=[
                                    TreeValue(name="num", value=0),
                                ],
                            ),
                        ),
                        iterable=TreeValue(
                            name="numbers",
                            value=list(range(1, 11)),
                        ),
                    )
                ],
                mode="single",
                name="Filter Odd Numbers",
                description="Filters out even numbers from a list of numbers from 1 to 10.",
            )
        ).model_dump_json(by_alias=True, exclude_unset=False),
    }

    examples.append(example_4)

    example_5: ASTExample = {
        "q": "Sum all numbers in a randomly generated list of integers.",
        "a": AST(
            root=TreeProgram(
                body=[
                    TreeReduce(
                        function=TreeLambda(
                            params=["acc", "x"],
                            body=TreeFunction(
                                name="add",
                                params=[
                                    TreeValue(name="acc", value=0),
                                    TreeValue(name="x", value=0),
                                ],
                            ),
                        ),
                        iterable=TreeFunction(
                            name="generate_random_integers",
                            params=[
                                TreeValue(name="count", value=20),
                                TreeValue(name="min", value=1),
                                TreeValue(name="max", value=100),
                            ],
                        ),
                    )
                ],
                mode="single",
                name="Sum List",
                description="Sums all numbers in a randomly generated list of integers using reduce.",
            )
        ).model_dump_json(by_alias=True, exclude_unset=False),
    }
    examples.append(example_5)

    return examples
