import json
import os
from typing import Any, Dict
from enum import Enum
from pydantic import BaseModel, ConfigDict
from dotenv import load_dotenv
from mcp import ClientSession
from openai import OpenAI

from treelang.ai.prompt import (
    ARBORIST_SYSTEM_PROMPT,
    EXPLAIN_EVALUATION_SYSTEM_PROMPT,
    EXPLAIN_EVALUATION_USER_PROMPT,
    TREE_DESCRIPTOR_SYSTEM_PROMPT,
    TREE_DESCRIPTOR_USER_PROMPT,
)
from treelang.ai.selector import AllToolsSelector, BaseToolSelector
from treelang.trees.tree import AST, TreeNode, TreeProgram

load_dotenv()


class EvalType(Enum):
    """
    Enum representing the types of evaluation modes for tree processing.

    Attributes:
        TREE (str): Represents an evaluation mode where evaluation of the tree is deferred to a third party (i.e. only return the tree).
        WALK (str): Represents an evaluation mode where the tree is to be fully evaluated (i.e. evaluate the tree and return the result).
    """

    TREE = "tree"
    WALK = "walk"


class Model(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


class TreeDescription(Model):
    name: str
    description: str
    properties: dict[str, Any]


class EvalResponse(Model):
    """
    Data model representing the response of an evaluation process.

    Attributes:
        query (str): The original query that was evaluated.
        type (EvalType): The type of evaluation being performed.
        content (Any): The content of the evaluation response. This can be a TreeNode
        if type is TREE or Any if type is WALK depending on the evaluation.
        jsontree (dict[str, Any] | None): The JSON representation of the tree if available.
            This is used for tree responses to generate a description of the tree.

    Methods:
        explain() -> str:
            Generates an English explanation of the evaluation response.
    """

    query: str
    type: EvalType
    content: TreeNode | Any
    jsontree: dict[str, Any] | None = None

    def explain(self) -> str:
        """
        Generates an English explanation of the evaluation response.

        Returns:
            str: A string representation of the evaluation response.
        """
        openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        if self.type == EvalType.TREE:
            raise ValueError("Cannot explain a tree response.")

        query = EXPLAIN_EVALUATION_USER_PROMPT.format(
            question=self.query, data={"data": self.content}
        )

        messages = [
            {"role": "system", "content": EXPLAIN_EVALUATION_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]

        params = {
            "model": "gpt-4o-2024-11-20",
            "messages": messages,
        }

        completion = openai.chat.completions.create(**params)
        message = completion.choices[0].message.model_dump(mode="json")
        content = message["content"]

        return content

    def describe(self) -> TreeNode:
        """
        Generates a name and a description for the response tree.
        It uses an LLM to generate a description based on the tree's JSON representation.
        The name and description are set on the tree root node (a TreeProgram instance).

        Raises:
            ValueError: If the tree is not a TreeProgram instance or if the JSON representation is not available.

        Returns:
            TreeNode: The tree with the name and description set.
        """
        openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        if self.type == EvalType.WALK:
            raise ValueError("Only tree responses can be described.")

        if not self.jsontree:
            raise ValueError("No JSON representation of the tree available.")

        if not isinstance(self.content, TreeProgram):
            raise ValueError("Only TreeProgram instances can be described.")

        query = TREE_DESCRIPTOR_USER_PROMPT.format(tree=json.dumps(self.jsontree))
        messages = [
            {"role": "system", "content": TREE_DESCRIPTOR_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        params = {
            "model": "gpt-4o-2024-11-20",
            "messages": messages,
            "response_format": {"type": "json_object"},
        }

        completion = openai.chat.completions.create(**params)
        message = completion.choices[0].message.model_dump(mode="json")
        response = json.loads(message["content"])

        self.content.name = response["name"]
        self.content.description = response["description"]

        return self.content


class BaseArborist:
    """
    Base class for LLM agents that solve problems by assembling Abstract Syntax Trees out of
    the tools (function calls) they have at their disposal.

    This class provides a foundation for implementing tree manipulation and evaluation
    logic. It includes methods for pruning, growing, walking, and evaluating trees,
    which can be extended or overridden by subclasses.

    Attributes:
        model (str): The name or identifier of the model being used.
        system_prompt (str): The system-level prompt used for guiding the AI's behavior.
        user_prompt_template (str): A template for generating user prompts.
        session (ClientSession): An asynchronous MCP session for interacting with tools and resources.
        selector (BaseToolSelector): A tool selector instance for determining applicable tools.
            Defaults to an instance of `AllToolsSelector`.

    Methods:
        prune(tree: TreeNode) -> TreeNode:
            Prunes the given tree. By default, this method returns the tree unchanged.

        grow():
            Abstract method for growing the tree. Must be implemented by subclasses.

        async walk(tree: TreeNode) -> Any:
            Walks through the tree and evaluates it asynchronously using the provided session.

        async eval(query: str, type: EvalType = EvalType.WALK) -> EvalResponse:
            Abstract method for generating trees that solve a user query. Must be implemented
            by subclasses.
    """

    def __init__(
        self,
        model: str,
        system_prompt: str,
        user_prompt_template: str,
        session: ClientSession,
        selector: BaseToolSelector = AllToolsSelector(),
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template
        self.session = session
        self.selector = selector

    def prune(self, tree: TreeNode) -> TreeNode:
        return tree

    def grow(self):
        raise NotImplementedError()

    async def walk(self, tree: TreeNode) -> Any:
        return await AST.eval(tree, self.session)

    async def eval(self, query: str, type: EvalType = EvalType.WALK) -> EvalResponse:
        raise NotImplementedError()


class OpenAIArborist(BaseArborist):
    """
    A specialized implementation of the `BaseArborist` class that integrates with OpenAI's API
    to evaluate queries and generate abstract syntax trees (ASTs). This class is designed to
    facilitate interaction with OpenAI's chat models and supports tool selection for enhanced
    functionality.

    Attributes:
        model (str): The name of the OpenAI model to use for generating responses.
        session (ClientSession): An asynchronous MCP session for interacting with tools and resources.
        selector (BaseToolSelector): A tool selector instance to determine available tools
            for the evaluation process. Defaults to `AllToolsSelector`.
        openai (OpenAI): An instance of the OpenAI client initialized with the API key.

    Methods:
        grow():
            Placeholder method for extending functionality. Currently not implemented.

        eval(query: str, type: EvalType = EvalType.WALK) -> EvalResponse:
            Asynchronously evaluates a query using the OpenAI model and generates an AST.
    """

    def __init__(
        self,
        model: str,
        session: ClientSession,
        selector: BaseToolSelector = AllToolsSelector(),
    ):
        super().__init__(model, ARBORIST_SYSTEM_PROMPT, "", session, selector)
        self.openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def grow(self):
        pass

    async def eval(self, query: str, type: EvalType = EvalType.WALK) -> EvalResponse:
        """
        Asynchronously evaluates a query using the OpenAI model and generates an AST.
        Optionally prunes the tree and performs a walk operation based on the evaluation type.

        Args:
            query (str): The input query to evaluate.
            type (EvalType): The type of evaluation to perform. Defaults to `EvalType.WALK`.

        Returns:
            EvalResponse: The result of the evaluation, either as a walked response or
            the generated AST.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query},
        ]

        params = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }

        if self.model != "o1":
            params["temperature"] = 0.0

        available_tools = await self.selector.select(self.session)

        if available_tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": tool.inputSchema["properties"],
                        },
                    },
                }
                for tool in available_tools
            ]

        completion = self.openai.chat.completions.create(**params)
        message = completion.choices[0].message.model_dump(mode="json")
        content = message["content"]
        jsontree = json.loads(content)
        tree = AST.parse(jsontree)
        tree = self.prune(tree)

        if type == EvalType.WALK:
            return EvalResponse(
                query=query, type=EvalType.WALK, content=await self.walk(tree)
            )
        else:
            return EvalResponse(
                query=query, type=EvalType.TREE, content=tree, jsontree=jsontree
            )
