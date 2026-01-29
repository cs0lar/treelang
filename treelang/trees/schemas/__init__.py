import json
from typing import Dict

from treelang.trees.schemas.v1 import AST, ast_v1_examples

CURRENT_SCHEMA_VERSION = "1.0"


def ast_json_schema() -> dict:
    """Return the JSON schema for the Treelang AST model."""
    schema = AST.model_json_schema()
    return json.dumps(schema, indent=2, ensure_ascii=False)


def ast_examples() -> list[Dict[str, str]]:
    """Return examples for the Treelang AST model."""
    return ("\n\n").join(
        [f"Q:{example['q']}\nA:{example['a']}" for example in ast_v1_examples()]
    )
