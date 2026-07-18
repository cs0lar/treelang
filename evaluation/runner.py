"""Deterministic offline benchmark runner."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from evaluation.models import (
    BenchmarkResult,
    CaseResult,
    EvaluationCase,
    EvaluationDataset,
    FailureCategory,
)
from treelang.ai.provider import ToolProvider
from treelang.trees.tree import AST


class OfflineBenchmarkRunner:
    def __init__(
        self,
        provider: ToolProvider,
        *,
        clock: Callable[[], float] = perf_counter,
        model: str = "curated-ast-v1",
        provider_name: str = "offline-tools-v1",
    ) -> None:
        self.provider = provider
        self.clock = clock
        self.model = model
        self.provider_name = provider_name

    async def run(self, dataset: EvaluationDataset) -> BenchmarkResult:
        started_at = datetime.now(UTC)
        started = self.clock()
        results = [await self.run_case(case) for case in dataset.cases]
        return BenchmarkResult(
            dataset_version=dataset.version,
            started_at=started_at,
            duration_ms=max(0.0, (self.clock() - started) * 1000),
            model=self.model,
            provider=self.provider_name,
            results=results,
        )

    async def run_case(self, case: EvaluationCase) -> CaseResult:
        started = self.clock()
        values: dict[str, Any] = {
            "case_id": case.id,
            "question": case.question,
            "expected": case.expected,
            "latency_ms": 0.0,
            "model": self.model,
            "provider": self.provider_name,
        }
        try:
            raw_ast = case.ast if isinstance(case.ast, str) else json.dumps(case.ast)
            parsed_json = json.loads(raw_ast)
            values["parse_success"] = True
        except (TypeError, json.JSONDecodeError) as error:
            return self._failure(values, started, FailureCategory.PARSE, error)

        if not isinstance(parsed_json, dict):
            return self._failure(
                values,
                started,
                FailureCategory.SCHEMA,
                ValueError("AST root must be a JSON object"),
            )

        try:
            tree = AST.parse(parsed_json)
            values["schema_valid"] = True
        except ValueError as error:
            return self._failure(values, started, FailureCategory.SCHEMA, error)

        try:
            actual = await AST.eval(tree, self.provider)
            values["actual"] = actual
            values["execution_success"] = True
        except Exception as error:
            return self._failure(values, started, FailureCategory.EXECUTION, error)

        values["answer_correct"] = actual == case.expected
        serialized_ast = raw_ast.lower()
        values["required_tools_used"] = all(
            required.lower() in serialized_ast for required in case.must_use
        )
        if not values["answer_correct"] or not values["required_tools_used"]:
            values["failure_category"] = FailureCategory.CORRECTNESS
        values["latency_ms"] = self._latency(started)
        return CaseResult.model_validate(values)

    def _failure(
        self,
        values: dict[str, Any],
        started: float,
        category: FailureCategory,
        error: Exception,
    ) -> CaseResult:
        values.update(
            latency_ms=self._latency(started),
            failure_category=category,
            error=f"{type(error).__name__}: {error}",
        )
        return CaseResult.model_validate(values)

    def _latency(self, started: float) -> float:
        return max(0.0, (self.clock() - started) * 1000)
