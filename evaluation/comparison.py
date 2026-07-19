"""Compare benchmark results against compatible versioned baselines."""

from enum import Enum

from pydantic import BaseModel, Field, computed_field

from evaluation.models import BenchmarkResult


class RegressionKind(str, Enum):
    IDENTITY = "identity"
    QUALITY = "quality"
    LATENCY = "latency"
    TOKENS = "tokens"
    COST = "cost"


class RegressionTolerances(BaseModel):
    max_pass_rate_drop: float = Field(default=0, ge=0, le=1)
    max_parse_rate_drop: float = Field(default=0, ge=0, le=1)
    max_schema_rate_drop: float = Field(default=0, ge=0, le=1)
    max_execution_rate_drop: float = Field(default=0, ge=0, le=1)
    max_correctness_rate_drop: float = Field(default=0, ge=0, le=1)
    max_required_tools_rate_drop: float = Field(default=0, ge=0, le=1)
    latency_ratio: float = Field(default=0.5, ge=0)
    mean_latency_absolute_ms: float = Field(default=25, ge=0)
    max_latency_absolute_ms: float = Field(default=50, ge=0)
    token_ratio: float = Field(default=0, ge=0)
    token_absolute: int = Field(default=0, ge=0)
    cost_ratio: float = Field(default=0, ge=0)
    cost_absolute_usd: float = Field(default=0, ge=0)


class BenchmarkMetrics(BaseModel):
    pass_rate: float
    parse_rate: float
    schema_rate: float
    execution_rate: float
    correctness_rate: float
    required_tools_rate: float
    mean_latency_ms: float
    max_latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float


class RegressionIssue(BaseModel):
    kind: RegressionKind
    metric: str
    baseline: str | float | int
    current: str | float | int
    limit: str | float | int | None = None


class BenchmarkComparison(BaseModel):
    dataset_version: str
    mode: str
    model: str
    provider: str
    compatible: bool
    baseline_metrics: BenchmarkMetrics
    current_metrics: BenchmarkMetrics
    issues: list[RegressionIssue]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed(self) -> bool:
        return self.compatible and not self.issues


def summarize(result: BenchmarkResult) -> BenchmarkMetrics:
    total = result.total
    if total == 0:
        return BenchmarkMetrics(
            pass_rate=0,
            parse_rate=0,
            schema_rate=0,
            execution_rate=0,
            correctness_rate=0,
            required_tools_rate=0,
            mean_latency_ms=0,
            max_latency_ms=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0,
        )

    latencies = [case.latency_ms for case in result.results]
    return BenchmarkMetrics(
        pass_rate=result.pass_rate,
        parse_rate=sum(case.parse_success for case in result.results) / total,
        schema_rate=sum(case.schema_valid for case in result.results) / total,
        execution_rate=sum(case.execution_success for case in result.results) / total,
        correctness_rate=sum(case.answer_correct for case in result.results) / total,
        required_tools_rate=sum(case.required_tools_used for case in result.results)
        / total,
        mean_latency_ms=sum(latencies) / total,
        max_latency_ms=max(latencies),
        prompt_tokens=sum(case.prompt_tokens for case in result.results),
        completion_tokens=sum(case.completion_tokens for case in result.results),
        estimated_cost_usd=sum(case.estimated_cost_usd for case in result.results),
    )


def compare_results(
    baseline: BenchmarkResult,
    current: BenchmarkResult,
    tolerances: RegressionTolerances,
) -> BenchmarkComparison:
    baseline_metrics = summarize(baseline)
    current_metrics = summarize(current)
    issues = _identity_issues(baseline, current)
    compatible = not issues
    if compatible:
        issues.extend(_metric_issues(baseline_metrics, current_metrics, tolerances))
    return BenchmarkComparison(
        dataset_version=current.dataset_version,
        mode=current.mode,
        model=current.model,
        provider=current.provider,
        compatible=compatible,
        baseline_metrics=baseline_metrics,
        current_metrics=current_metrics,
        issues=issues,
    )


def _identity_issues(
    baseline: BenchmarkResult, current: BenchmarkResult
) -> list[RegressionIssue]:
    issues: list[RegressionIssue] = []
    for metric in ("dataset_version", "mode", "model", "provider"):
        baseline_value = getattr(baseline, metric)
        current_value = getattr(current, metric)
        if baseline_value != current_value:
            issues.append(
                RegressionIssue(
                    kind=RegressionKind.IDENTITY,
                    metric=metric,
                    baseline=baseline_value,
                    current=current_value,
                    limit=baseline_value,
                )
            )
    baseline_case_ids = [case.case_id for case in baseline.results]
    current_case_ids = [case.case_id for case in current.results]
    if baseline_case_ids != current_case_ids:
        issues.append(
            RegressionIssue(
                kind=RegressionKind.IDENTITY,
                metric="case_ids",
                baseline=",".join(baseline_case_ids),
                current=",".join(current_case_ids),
                limit=",".join(baseline_case_ids),
            )
        )
    return issues


def _metric_issues(
    baseline: BenchmarkMetrics,
    current: BenchmarkMetrics,
    tolerances: RegressionTolerances,
) -> list[RegressionIssue]:
    issues: list[RegressionIssue] = []
    quality = {
        "pass_rate": tolerances.max_pass_rate_drop,
        "parse_rate": tolerances.max_parse_rate_drop,
        "schema_rate": tolerances.max_schema_rate_drop,
        "execution_rate": tolerances.max_execution_rate_drop,
        "correctness_rate": tolerances.max_correctness_rate_drop,
        "required_tools_rate": tolerances.max_required_tools_rate_drop,
    }
    for metric, allowed_drop in quality.items():
        baseline_value = getattr(baseline, metric)
        current_value = getattr(current, metric)
        limit = baseline_value - allowed_drop
        if current_value < limit:
            issues.append(
                RegressionIssue(
                    kind=RegressionKind.QUALITY,
                    metric=metric,
                    baseline=baseline_value,
                    current=current_value,
                    limit=limit,
                )
            )

    resources = (
        (
            RegressionKind.LATENCY,
            "mean_latency_ms",
            tolerances.latency_ratio,
            tolerances.mean_latency_absolute_ms,
        ),
        (
            RegressionKind.LATENCY,
            "max_latency_ms",
            tolerances.latency_ratio,
            tolerances.max_latency_absolute_ms,
        ),
        (
            RegressionKind.TOKENS,
            "prompt_tokens",
            tolerances.token_ratio,
            tolerances.token_absolute,
        ),
        (
            RegressionKind.TOKENS,
            "completion_tokens",
            tolerances.token_ratio,
            tolerances.token_absolute,
        ),
        (
            RegressionKind.COST,
            "estimated_cost_usd",
            tolerances.cost_ratio,
            tolerances.cost_absolute_usd,
        ),
    )
    for kind, metric, ratio, absolute in resources:
        baseline_value = getattr(baseline, metric)
        current_value = getattr(current, metric)
        limit = baseline_value * (1 + ratio) + absolute
        if current_value > limit:
            issues.append(
                RegressionIssue(
                    kind=kind,
                    metric=metric,
                    baseline=baseline_value,
                    current=current_value,
                    limit=limit,
                )
            )
    return issues
