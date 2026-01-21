import asyncio
import json
from hashlib import sha256
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from treelang.ai.provider import ToolProvider


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

    async def eval(self, provider: ToolProvider) -> Any:
        raise NotImplementedError()

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

    type: Literal["value"] = "value"
    name: str = Field(..., min_length=1)
    value: JsonValue

    async def eval(self, provider: ToolProvider) -> Any:
        return self.value


class TreeFunction(TreeNode):
    """
    Represents a function in the abstract syntax tree (AST).
    """

    type: Literal["function"] = "function"
    name: str = Field(..., min_length=1)
    params: List["Node"] = Field(default_factory=list)

    async def eval(self, provider: ToolProvider) -> Any:
        tool = await provider.get_tool_definition(self.name)

        if not tool:
            raise ValueError(f"Tool {self.name} is not available")

        tool_properties = tool["properties"].keys()

        # evaluate each parameter in order
        results = await asyncio.gather(*[param.eval(provider) for param in self.params])
        # create a dictionary of parameter names and values
        params = dict(zip(tool_properties, results))
        # invoke the underlying tool
        output = await provider.call_tool(self.name, params)

        return output.content


class TreeProgram(TreeNode):
    """
    Represents a program in the abstract syntax tree (AST).
    """

    type: Literal["program"] = "program"
    body: List["Node"] = Field(default_factory=list)
    name: Optional[str] = None
    description: Optional[str] = None

    async def eval(self, provider: ToolProvider) -> Any:
        result = await asyncio.gather(*[node.eval(provider) for node in self.body])
        return result[0] if len(result) == 1 else result


class TreeConditional(TreeNode):
    """
    Represents a conditional statement in the AST.
    """

    type: Literal["conditional"] = "conditional"
    condition: "Node"
    true_branch: "Node"
    false_branch: Optional["Node"] = None

    async def eval(self, provider: ToolProvider) -> Any:
        condition_result = await self.condition.eval(provider)

        if condition_result:
            return await self.true_branch.eval(provider)
        elif self.false_branch:
            return await self.false_branch.eval(provider)

        return None


class FunctionBodySpec(TreeNode):
    name: str = Field(..., min_length=1)
    params: List["Node"] = Field(default_factory=list)


LambdaBody = Union[TreeFunction, FunctionBodySpec]


class TreeLambda(TreeNode):
    """
    Represents an anonymous (lambda) function.
    """

    type: Literal["lambda"] = "lambda"
    params: List[str] = Field(default_factory=list)
    body: LambdaBody

    async def eval(self, provider: ToolProvider):
        # Returns a callable that can be invoked with arguments
        async def func(*args):
            # update this TreeFunction's argument values with
            # the provided arguments preserving the order. Note that
            # the number of arguments maybe less than or equal to
            # the number of parameters but not more.
            for i, param in enumerate(self.body.params):
                if i < len(args):
                    param.value = args[i]
                else:
                    # if there are not enough arguments, we leave the parameter value as is
                    break
            return await self.body.eval(provider)

        return func


class TreeMap(TreeNode):
    """
    Represents a map operation in the abstract syntax tree (AST).
    """

    type: Literal["map"] = "map"
    function: TreeLambda
    iterable: "Node"

    async def eval(self, provider: ToolProvider) -> Any:
        items = await self.iterable.eval(provider)

        if not isinstance(items, list):
            raise TypeError("Map expects an iterable (list) as input")

        func = await self.function.eval(provider)

        return [await func(item) for item in items]


class TreeFilter(TreeNode):
    """
    Represents a filter operation in the abstract syntax tree (AST).
    """

    type: Literal["filter"] = "filter"
    function: TreeLambda
    iterable: "Node"

    async def eval(self, provider: ToolProvider) -> Any:
        items = await self.iterable.eval(provider)

        if not isinstance(items, list):
            raise TypeError("Filter expects an iterable (list) as input")

        func = await self.function.eval(provider)

        return [item for item in items if await func(item)]


class TreeReduce(TreeNode):
    """
    Represents a reduce operation in the abstract syntax tree (AST).
    """

    type: Literal["reduce"] = "reduce"
    function: TreeLambda
    iterable: "Node"

    async def eval(self, provider: ToolProvider) -> Any:
        items = await self.iterable.eval(provider)

        if not isinstance(items, list):
            raise TypeError("Reduce expects an iterable (list) as input")

        func = await self.function.eval(provider)

        if not items:
            return None

        result = items[0]

        for item in items[1:]:
            result = await func(result, item)

        return result


type Node = Annotated[
    Union[
        TreeNode,  # base type for testing
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


class AST(RootModel[Node]):
    """
    Root wrapper for top level node validation.
    """

    @model_validator(mode="after")
    def enforce_function_param_count_and_order(self) -> "AST":
        """
        Optional enforcement using tool signatures.

        Provide context:
          AST.model_validate(obj, context={"tool_param_order": {"toolname": ["a","b"]}})

        This enforces:
          len(params) == len(expected)
        and can be extended to enforce types/constraints per arg.
        """
        ctx = getattr(self, "__pydantic_context__", None) or {}
        sig_map: dict[str, list[str]] = ctx.get("tool_param_order", {})

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


def ast_v1_examples() -> list[str]:
    """Provide example ASTs in canonical JSON format for use in few-shots prompts for LLMs."""
    examples: list[str] = []

    example_1 = {
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
                name="Calculate (12*6)+4",
                description="A simple arithmetic calculation using add and multiply functions.",
            )
        ).model_dump_json(by_alias=True, exclude_unset=False),
    }
    examples.append(example_1)
    example_2 = {
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
            )
        ).model_dump_json(by_alias=True, exclude_unset=False),
    }
    examples.append(example_2)

    example_3 = {
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
                                    TreeValue(name="material_resistivity", value=0),
                                ],
                            ),
                        ),
                        iterable=TreeValue(
                            name="resistivities",
                            value={
                                "copper": 1.68e-8,
                                "aluminum": 2.82e-8,
                            },
                        ),
                    )
                ],
                name="Calculate Wire Resistance for Different Materials",
                description="Calculates the resistance of a wire made of copper and aluminum given length, area, and resistivity.",
            )
        ).model_dump_json(by_alias=True, exclude_unset=False),
    }
    examples.append(example_3)

    example_4 = {
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
                name="Filter Odd Numbers",
                description="Filters out even numbers from a list of numbers from 1 to 10.",
            )
        ).model_dump_json(by_alias=True, exclude_unset=False),
    }

    examples.append(example_4)

    example_5 = {
        "q": "Sum all numbers in the list [1, 2, 3, 4, 5].",
        "a": AST(
            root=TreeProgram(
                body=[
                    TreeReduce(
                        function=TreeLambda(
                            params=["acc", "x"],
                            body=TreeFunction(
                                name="add",
                                params=[
                                    TreeValue(name="a", value=0),
                                    TreeValue(name="b", value=0),
                                ],
                            ),
                        ),
                        iterable=TreeValue(
                            name="numbers",
                            value=[1, 2, 3, 4, 5],
                        ),
                    )
                ],
                name="Sum List",
                description="Sums all numbers in the list [1, 2, 3, 4, 5] using reduce.",
            )
        ).model_dump_json(by_alias=True, exclude_unset=False),
    }
    examples.append(example_5)

    return examples