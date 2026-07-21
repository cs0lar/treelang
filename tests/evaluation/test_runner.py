import json
from itertools import count

import pytest

from evaluation.dataset import DEFAULT_DATASET_PATH, load_dataset
from evaluation.eval import main
from evaluation.models import EvaluationCase, EvaluationDataset, FailureCategory
from evaluation.offline import OfflineModelTransport, OfflineToolProvider
from evaluation.runner import OfflineBenchmarkRunner


def ticking_clock():
    ticks = count()
    return lambda: next(ticks) / 1000


@pytest.mark.asyncio
async def test_versioned_offline_dataset_passes_deterministically():
    dataset = load_dataset()
    result = await OfflineBenchmarkRunner(
        OfflineToolProvider(), clock=ticking_clock()
    ).run(dataset)

    assert dataset.version == "1.0"
    assert result.passed == result.total == 4
    assert result.pass_rate == 1.0
    assert result.duration_ms >= 0
    assert all(case.prompt_tokens == 0 for case in result.results)
    assert all(case.completion_tokens == 0 for case in result.results)
    assert all(case.estimated_cost_usd == 0 for case in result.results)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "category"),
    [
        (
            EvaluationCase(id="parse", question="parse", expected=None, ast="{"),
            FailureCategory.PARSE,
        ),
        (
            EvaluationCase(id="schema", question="schema", expected=None, ast="[]"),
            FailureCategory.SCHEMA,
        ),
        (
            EvaluationCase(
                id="execution",
                question="execution",
                expected=None,
                ast={
                    "type": "program",
                    "mode": "single",
                    "body": [{"type": "function", "name": "missing", "params": []}],
                },
            ),
            FailureCategory.EXECUTION,
        ),
        (
            EvaluationCase(
                id="correctness",
                question="correctness",
                expected=2,
                must_use=["required-node"],
                ast={
                    "type": "program",
                    "mode": "single",
                    "body": [{"type": "value", "name": "value", "value": 1}],
                },
            ),
            FailureCategory.CORRECTNESS,
        ),
    ],
)
async def test_runner_categorizes_failures(case, category):
    result = await OfflineBenchmarkRunner(
        OfflineToolProvider(), clock=ticking_clock()
    ).run_case(case)

    assert result.failure_category == category
    assert not result.passed
    assert result.latency_ms >= 0
    if category != FailureCategory.CORRECTNESS:
        assert result.error


@pytest.mark.asyncio
async def test_offline_model_transport_returns_curated_ast():
    case = EvaluationCase(
        id="transport",
        question="question",
        expected=1,
        ast={
            "type": "program",
            "mode": "single",
            "body": [{"type": "value", "name": "value", "value": 1}],
        },
    )
    transport = OfflineModelTransport([case])

    response = await transport.complete(
        {"messages": [{"role": "user", "content": "question"}]}
    )

    assert json.loads(response) == case.ast
    assert [part async for part in transport.stream({})] == []


@pytest.mark.asyncio
async def test_cli_writes_machine_readable_result(tmp_path):
    output = tmp_path / "results" / "offline.json"
    comparison_output = tmp_path / "results" / "comparison.json"

    assert (
        await main(
            DEFAULT_DATASET_PATH,
            output,
            comparison_output_path=comparison_output,
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["dataset_version"] == "1.0"
    assert payload["passed"] == payload["total"] == 4
    assert payload["pass_rate"] == 1.0
    assert len(payload["results"]) == 4
    comparison = json.loads(comparison_output.read_text(encoding="utf-8"))
    assert comparison["passed"] is True
    assert comparison["issues"] == []


@pytest.mark.asyncio
async def test_empty_benchmark_has_zero_pass_rate():
    dataset = EvaluationDataset(version="1.0", cases=[])
    result = await OfflineBenchmarkRunner(
        OfflineToolProvider(), clock=ticking_clock()
    ).run(dataset)
    assert result.total == result.passed == 0
    assert result.pass_rate == 0.0
