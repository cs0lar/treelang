import json
from typing import Dict, Literal

from pydantic import BaseModel, ConfigDict, Field

from treelang.ai.prompt import ARBORIST_SYSTEM_PROMPT
from treelang.trees.schemas.v1 import AST, Node, ast_v1_examples

CURRENT_SCHEMA_VERSION = "1.0"


class SchemaV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["1.0"] = Field(default=CURRENT_SCHEMA_VERSION)
    ast: Node


def ast_json_schema() -> dict:
    schema = AST.model_json_schema()
    return json.dumps(schema, indent=2, ensure_ascii=False)


def ast_examples() -> list[Dict[str, str]]:
    return ("\n\n").join([f"Q:{example["q"]}\nA:{example["a"]}" for example in ast_v1_examples()])
