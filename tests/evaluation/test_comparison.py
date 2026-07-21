from pathlib import Path

from evaluation.comparison import (
    RegressionKind,
    RegressionTolerances,
    compare_results,
    summarize,
)
from evaluation.models import BenchmarkResult

BASELINE_PATH = (
    Path(__file__).parents[2] / "evaluation" / "baselines" / "v1" / "offline.json"
)


def load_baseline() -> BenchmarkResult:
    return BenchmarkResult.model_validate_json(
        BASELINE_PATH.read_text(encoding="utf-8")
    )


def test_compatible_result_passes_default_tolerances():
    baseline = load_baseline()
    comparison = compare_results(
        baseline, baseline.model_copy(deep=True), RegressionTolerances()
    )

    assert comparison.compatible
    assert comparison.passed
    assert comparison.issues == []
    assert comparison.baseline_metrics == comparison.current_metrics


def test_identity_mismatch_fails_closed_without_metric_comparison():
    baseline = load_baseline()
    current = baseline.model_copy(update={"model": "different-model"}, deep=True)

    comparison = compare_results(baseline, current, RegressionTolerances())

    assert not comparison.compatible
    assert not comparison.passed
    assert [(issue.kind, issue.metric) for issue in comparison.issues] == [
        (RegressionKind.IDENTITY, "model")
    ]


def test_case_sequence_is_part_of_baseline_identity():
    baseline = load_baseline()
    current = baseline.model_copy(update={"results": baseline.results[:-1]}, deep=True)

    comparison = compare_results(baseline, current, RegressionTolerances())

    assert not comparison.compatible
    assert [issue.metric for issue in comparison.issues] == ["case_ids"]


def test_quality_regression_is_categorized():
    baseline = load_baseline()
    current = baseline.model_copy(deep=True)
    current.results[0].answer_correct = False

    comparison = compare_results(baseline, current, RegressionTolerances())

    assert not comparison.passed
    assert {issue.metric for issue in comparison.issues} == {
        "pass_rate",
        "correctness_rate",
    }
    assert {issue.kind for issue in comparison.issues} == {RegressionKind.QUALITY}


def test_resource_regressions_use_explicit_limits():
    baseline = load_baseline()
    current = baseline.model_copy(deep=True)
    current.results[0].latency_ms = 200
    current.results[0].prompt_tokens = 1
    current.results[0].completion_tokens = 1
    current.results[0].estimated_cost_usd = 0.01

    comparison = compare_results(baseline, current, RegressionTolerances())

    assert {issue.kind for issue in comparison.issues} == {
        RegressionKind.LATENCY,
        RegressionKind.TOKENS,
        RegressionKind.COST,
    }
    assert {issue.metric for issue in comparison.issues} == {
        "mean_latency_ms",
        "max_latency_ms",
        "prompt_tokens",
        "completion_tokens",
        "estimated_cost_usd",
    }


def test_explicit_tolerances_allow_expected_noise():
    baseline = load_baseline()
    current = baseline.model_copy(deep=True)
    current.results[0].latency_ms = 10
    current.results[0].answer_correct = False
    tolerances = RegressionTolerances(
        max_pass_rate_drop=0.34,
        max_correctness_rate_drop=0.34,
    )

    comparison = compare_results(baseline, current, tolerances)

    assert comparison.passed


def test_empty_result_summary_is_well_defined():
    baseline = load_baseline()
    empty = baseline.model_copy(update={"results": []})

    metrics = summarize(empty)

    assert metrics.pass_rate == 0
    assert metrics.mean_latency_ms == 0
    assert metrics.prompt_tokens == 0
