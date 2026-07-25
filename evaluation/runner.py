"""Deterministic offline benchmark runner."""

import json
import logging
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
from treelang.observability import Observability
from treelang.trees.budget import ExecutionLimits
from treelang.trees.execution_v2 import execute_v2
from treelang.trees.schemas.v1 import TreeNode
from treelang.trees.schemas.v2 import AST as ASTV2
from treelang.trees.schemas.v2 import TreeProgram as TreeProgramV2
from treelang.trees.tree import AST


class OfflineBenchmarkRunner:
    def __init__(
        self,
        provider: ToolProvider,
        *,
        clock: Callable[[], float] = perf_counter,
        model: str = "curated-ast-v1",
        provider_name: str = "offline-tools-v1",
        observability: Observability | None = None,
    ) -> None:
        self.provider = provider
        self.clock = clock
        self.model = model
        self.provider_name = provider_name
        self.observability = observability or Observability(
            logger=logging.getLogger("evaluation.benchmark")
        )

    async def run(self, dataset: EvaluationDataset) -> BenchmarkResult:
        started_at = datetime.now(UTC)
        started = self.clock()
        self.observability.emit(
            "benchmark.started",
            dataset_version=dataset.version,
            mode="offline",
            model=self.model,
            provider=self.provider_name,
            case_count=len(dataset.cases),
        )
        results = [await self.run_case(case) for case in dataset.cases]
        result = BenchmarkResult(
            dataset_version=dataset.version,
            started_at=started_at,
            duration_ms=max(0.0, (self.clock() - started) * 1000),
            model=self.model,
            provider=self.provider_name,
            results=results,
        )
        self.observability.emit(
            "benchmark.completed",
            dataset_version=dataset.version,
            duration_ms=result.duration_ms,
            passed=result.passed,
            total=result.total,
            pass_rate=result.pass_rate,
        )
        return result

    async def run_case(self, case: EvaluationCase) -> CaseResult:
        started = self.clock()
        self.observability.emit(
            "benchmark.case.started",
            case_id=case.id,
            question=case.question,
            expected=case.expected,
            ast=case.ast,
        )
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
            schema_version = parsed_json.get("schema_version", "1.0")
            tree: TreeNode | TreeProgramV2
            if schema_version == "2.0":
                tree = ASTV2.model_validate(parsed_json).root
            else:
                tree = AST.parse(parsed_json)
            values["schema_valid"] = True
        except (ValueError, TypeError) as error:
            return self._failure(values, started, FailureCategory.SCHEMA, error)

        try:
            if isinstance(tree, TreeProgramV2):
                actual = await execute_v2(
                    tree,
                    self.provider,
                    limits=ExecutionLimits(
                        max_nodes=10_000,
                        max_call_depth=1_000,
                        max_tool_calls=10_000,
                        timeout_seconds=10,
                    ),
                )
            else:
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
        result = CaseResult.model_validate(values)
        self._emit_case_completed(result)
        return result

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
        result = CaseResult.model_validate(values)
        self._emit_case_completed(result)
        return result

    def _latency(self, started: float) -> float:
        return max(0.0, (self.clock() - started) * 1000)

    def _emit_case_completed(self, result: CaseResult) -> None:
        self.observability.emit(
            "benchmark.case.completed",
            case_id=result.case_id,
            passed=result.passed,
            parse_success=result.parse_success,
            schema_valid=result.schema_valid,
            execution_success=result.execution_success,
            answer_correct=result.answer_correct,
            required_tools_used=result.required_tools_used,
            latency_ms=result.latency_ms,
            model=result.model,
            provider=result.provider,
            failure_category=result.failure_category,
            error=result.error,
            actual=result.actual,
            expected=result.expected,
        )
