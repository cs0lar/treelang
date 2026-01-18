from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from treelang.trees.schemas.v1 import Node


CURRENT_SCHEMA_VERSION = "1.0"


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