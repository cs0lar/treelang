import asyncio
from hashlib import sha256
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from treelang.ai.provider import ToolProvider
from treelang.trees.schemas import CURRENT_SCHEMA_VERSION


class TreeNode(BaseModel):
    """
    Represents a node in the abstract syntax tree (AST).

    Attributes:
        type (str): The type of the AST node.

    Methods:
        eval(ToolProvider): Evaluates the node using the provided ToolProvider.
    """

    type: Literal["node"] = "node"

    model_config = ConfigDict(
        extra="forbid",  # Forbid extra fields not defined in the model
        frozen=True,  # Make the model immutable
        validate_assignment=True,  # Validate fields on assignment
        populate_by_name=True,  # For alias support
    )

    async def eval(self, provider: ToolProvider) -> Any:
        raise NotImplementedError()

    def hash(self) -> str:
        canonical_json = self.model_dump_json(
            by_alias=True, exclude_unset=True)
        return sha256(canonical_json.encode("utf-8")).hexdigest()


# Define JSON value types for `TreeValue.value`
JsonPrimitive = Union[str, int, float, bool, None]
type JsonValue = Union[JsonPrimitive, List["JsonValue"], Dict[str, "JsonValue"]]


class TreeValue(TreeNode):
    """
    Represents a value in the abstract syntax tree (AST).

    Attributes:
        value (Any): The value of the node.

    Methods:
        eval(ToolProvider): Returns the value of the node.
    """

    type: Literal["value"] = "value"
    name: str = Field(..., min_length=1)
    value: JsonValue

    async def eval(self, provider: ToolProvider) -> Any:
        return self.value


class TreeFunction(TreeNode):
    """
    Represents a function in the abstract syntax tree (AST).

    Attributes:
        name (str): The name of the function.
        params (List[str]): The list of parameters of the function.

    Methods:
        eval(ToolProvider): Evaluates the function by calling the underlying tool with the provided parameters.
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

    Attributes:
        body (List[TreeNode]): The list of statements in the program.
        name str: optional name for this program.
        description str: optional description for this program.

    Methods:
        eval(ToolProvider): Evaluates the program by evaluating each statement in the body.
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

    Attributes:
        condition (TreeNode): The condition to evaluate.
        true_branch (TreeNode): The branch to execute if the condition is true.
        false_branch (TreeNode): The branch to execute if the condition is false.

    Methods:
        eval(ToolProvider): Evaluates the condition and executes the appropriate branch.
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
    """
    This is the minimal shape your parser expects inside lambda.body
    and map/filter/reduce.function.body:
      {"name": "...", "params": [...]}
    It may optionally include "type":"function" too (we'll allow via union).
    :contentReference[oaicite:6]{index=6}
    """

    name: str = Field(..., min_length=1)
    params: List["Node"] = Field(default_factory=list)


LambdaBody = Union[TreeFunction, FunctionBodySpec]


class TreeLambda(TreeNode):
    """
    Represents an anonymous (lambda) function.
    Attributes:
        params (List[str]): Parameter names.
        body (TreeFunction): The function body.
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

    Attributes:
        function (TreeLambda): The function to apply to each item in the iterable.
        iterable (TreeNode): The iterable to map over. The iterable TreeNode should evaluate to a list.

    Methods:
        eval(ToolProvider): Applies the map function to each item in the iterable.
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

    Attributes:
        function (TreeLambda): The function to apply to each item in the iterable. The function should return a boolean value.
        iterable (TreeNode): The iterable to filter. The iterable TreeNode should evaluate to a list.

    Methods:
        eval(ToolProvider): Applies the filter function to each item in the iterable.
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

    Attributes:
        function (TreeLambda): The function to apply to each item in the iterable. The function should take two arguments,
                               the accumulated value and the current item, and return a new accumulated value.
        iterable (TreeNode): The iterable to reduce. The iterable TreeNode should evaluate to a list.

    Methods:
        eval(ToolProvider): Applies the reduce function to each item in the iterable.
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


# -----------------------
# Discriminated union for Node
# -----------------------
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


class SchemaV1(BaseModel):
    """
    Canonical top-level object returned by Arborists.

    {
      "schema_version": "1.0",
      "ast": { ...Node... }
    }
    """

    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["1.0"] = Field(default=CURRENT_SCHEMA_VERSION)
    ast: Node


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
