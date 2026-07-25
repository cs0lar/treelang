import json

from treelang.trees.schemas.v1 import AST, ast_v1_examples
from treelang.trees.schemas.v2 import AST as ASTV2
from treelang.trees.schemas.v2 import ast_v2_examples

CURRENT_SCHEMA_VERSION = "1.0"


def ast_json_schema() -> str:
    """Return the JSON schema for the Treelang AST model."""
    schema = AST.model_json_schema()
    return json.dumps(schema, indent=2, ensure_ascii=False)


def ast_examples() -> str:
    """Return examples for the Treelang AST model."""
    return ("\n\n").join(
        [f"Q:{example['q']}\nA:{example['a']}" for example in ast_v1_examples()]
    )


def ast_v2_json_schema() -> str:
    """Return the JSON schema for opt-in recursive Treelang programs."""
    return json.dumps(ASTV2.model_json_schema(), indent=2, ensure_ascii=False)


def recursive_ast_examples() -> str:
    """Return canonical recursive examples for schema version 2 prompts."""
    return ("\n\n").join(
        [f"Q:{example['q']}\nA:{example['a']}" for example in ast_v2_examples()]
    )
