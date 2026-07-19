"""Credentialed live-model benchmark runner with deterministic tool execution."""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Protocol

from evaluation.models import (
    BenchmarkResult,
    CaseResult,
    FailureCategory,
    LiveEvaluationCase,
    LiveEvaluationDataset,
)
from treelang.ai.arborist import OpenAIArborist
from treelang.ai.responses import EvalType
from treelang.ai.transport import ModelUsage
from treelang.observability import Observability
from treelang.trees.schemas.v1 import TreeProgram
from treelang.trees.tree import AST


class UsageReporter(Protocol):
    def consume_usage(self) -> ModelUsage: ...


class LiveBenchmarkRunner:
    """Generate ASTs with a live model and execute them against curated tools."""

    def __init__(
        self,
        arborist: OpenAIArborist,
        usage_reporter: UsageReporter,
        *,
        provider_name: str = "openai",
        input_cost_per_million: float = 0.0,
        output_cost_per_million: float = 0.0,
        clock: Callable[[], float] = perf_counter,
        observability: Observability | None = None,
    ) -> None:
        if input_cost_per_million < 0 or output_cost_per_million < 0:
            raise ValueError("Token prices cannot be negative")
        self.arborist = arborist
        self.usage_reporter = usage_reporter
        self.provider_name = provider_name
        self.input_cost_per_million = input_cost_per_million
        self.output_cost_per_million = output_cost_per_million
        self.clock = clock
        self.observability = observability or Observability(
            logger=logging.getLogger("evaluation.benchmark")
        )

    async def run(self, dataset: LiveEvaluationDataset) -> BenchmarkResult:
        started_at = datetime.now(UTC)
        started = self.clock()
        self.observability.emit(
            "benchmark.started",
            dataset_version=dataset.version,
            mode="live",
            model=self.arborist.model,
            provider=self.provider_name,
            case_count=len(dataset.cases),
        )
        results = [await self.run_case(case) for case in dataset.cases]
        result = BenchmarkResult(
            dataset_version=dataset.version,
            mode="live",
            started_at=started_at,
            duration_ms=max(0.0, (self.clock() - started) * 1000),
            model=self.arborist.model,
            provider=self.provider_name,
            results=results,
        )
        self.observability.emit(
            "benchmark.completed",
            dataset_version=dataset.version,
            mode="live",
            duration_ms=result.duration_ms,
            passed=result.passed,
            total=result.total,
            pass_rate=result.pass_rate,
        )
        return result

    async def run_case(self, case: LiveEvaluationCase) -> CaseResult:
        started = self.clock()
        values: dict[str, Any] = {
            "case_id": case.id,
            "question": case.question,
            "expected": case.expected,
            "latency_ms": 0.0,
            "model": self.arborist.model,
            "provider": self.provider_name,
        }
        self.observability.emit(
            "benchmark.case.started",
            case_id=case.id,
            question=case.question,
            expected=case.expected,
        )
        try:
            response = await self.arborist.eval(case.question, EvalType.TREE)
            values["parse_success"] = True
            values["schema_valid"] = True
        except json.JSONDecodeError as error:
            return self._failure(values, started, FailureCategory.PARSE, error)
        except ValueError as error:
            return self._failure(values, started, FailureCategory.SCHEMA, error)
        except Exception as error:
            return self._failure(values, started, FailureCategory.PROVIDER, error)

        tree = response.content
        if not isinstance(tree, TreeProgram):
            return self._failure(
                values,
                started,
                FailureCategory.SCHEMA,
                TypeError("Model did not return a tree program"),
            )
        try:
            actual = await AST.eval(tree, self.arborist.provider)
            values["actual"] = actual
            values["execution_success"] = True
        except Exception as error:
            return self._failure(values, started, FailureCategory.EXECUTION, error)

        values["answer_correct"] = actual == case.expected
        serialized_ast = json.dumps(response.jsontree).lower()
        values["required_tools_used"] = all(
            required.lower() in serialized_ast for required in case.must_use
        )
        if not values["answer_correct"] or not values["required_tools_used"]:
            values["failure_category"] = FailureCategory.CORRECTNESS
        return self._complete(values, started)

    def _failure(
        self,
        values: dict[str, Any],
        started: float,
        category: FailureCategory,
        error: Exception,
    ) -> CaseResult:
        values.update(
            failure_category=category,
            error=f"{type(error).__name__}: {error}",
        )
        return self._complete(values, started)

    def _complete(self, values: dict[str, Any], started: float) -> CaseResult:
        usage = self.usage_reporter.consume_usage()
        values.update(
            latency_ms=max(0.0, (self.clock() - started) * 1000),
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            estimated_cost_usd=(
                usage.prompt_tokens * self.input_cost_per_million
                + usage.completion_tokens * self.output_cost_per_million
            )
            / 1_000_000,
        )
        result = CaseResult.model_validate(values)
        self.observability.emit(
            "benchmark.case.completed",
            case_id=result.case_id,
            passed=result.passed,
            latency_ms=result.latency_ms,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            failure_category=result.failure_category,
            error=result.error,
            actual=result.actual,
            expected=result.expected,
        )
        return result
