"""Typed models for versioned evaluation datasets and benchmark results."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field


class FailureCategory(str, Enum):
    DATASET = "dataset"
    PARSE = "parse"
    SCHEMA = "schema"
    EXECUTION = "execution"
    CORRECTNESS = "correctness"
    INTERNAL = "internal"


class EvaluationCase(BaseModel):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    expected: Any
    ast: dict[str, Any] | str
    must_use: list[str] = Field(default_factory=list)


class EvaluationDataset(BaseModel):
    version: str = Field(pattern=r"^\d+\.\d+$")
    cases: list[EvaluationCase]


class CaseResult(BaseModel):
    case_id: str
    question: str
    expected: Any
    actual: Any = None
    parse_success: bool = False
    schema_valid: bool = False
    execution_success: bool = False
    answer_correct: bool = False
    required_tools_used: bool = False
    latency_ms: float = Field(ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0, ge=0)
    model: str
    provider: str
    failure_category: FailureCategory | None = None
    error: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed(self) -> bool:
        return (
            self.parse_success
            and self.schema_valid
            and self.execution_success
            and self.answer_correct
            and self.required_tools_used
        )


class BenchmarkResult(BaseModel):
    dataset_version: str
    mode: Literal["offline"] = "offline"
    started_at: datetime
    duration_ms: float = Field(ge=0)
    model: str
    provider: str
    results: list[CaseResult]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed(self) -> int:
        return sum(result.passed for result in self.results)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> int:
        return len(self.results)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0
