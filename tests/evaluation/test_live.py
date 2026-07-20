import json
from itertools import count

import pytest

from evaluation.dataset import load_live_dataset
from evaluation.live import LiveBenchmarkRunner
from evaluation.live_eval import run as run_live_cli
from evaluation.models import FailureCategory, LiveEvaluationCase, LiveEvaluationDataset
from evaluation.offline import OfflineToolProvider
from treelang.ai.arborist import ArboristConfig, OpenAIArborist
from treelang.ai.transport import ModelUsage


def ticking_clock():
    ticks = count()
    return lambda: next(ticks) / 1000


class UsageTransport:
    def __init__(self, responses, usage=ModelUsage(100, 20)):
        self.responses = list(responses)
        self.usage = usage

    async def complete(self, request):
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def stream(self, request):
        async def empty():
            if False:
                yield ""

        return empty()

    def consume_usage(self):
        usage = self.usage
        self.usage = ModelUsage()
        return usage


def value_program(value):
    return json.dumps(
        {
            "type": "program",
            "mode": "single",
            "body": [{"type": "value", "name": "answer", "value": value}],
        }
    )


def live_case(**updates):
    values = {"id": "case", "q": "question", "a": 42, "must_use": []}
    values.update(updates)
    return LiveEvaluationCase.model_validate(values)


def runner(responses, **kwargs):
    transport = UsageTransport(responses)
    provider = OfflineToolProvider()
    arborist = OpenAIArborist(
        model="gpt-test",
        provider=provider,
        config=ArboristConfig(model="gpt-test", validation_retries=0),
        transport=transport,
    )
    return LiveBenchmarkRunner(
        arborist,
        transport,
        clock=ticking_clock(),
        input_cost_per_million=kwargs.pop("input_cost_per_million", 2.0),
        output_cost_per_million=kwargs.pop("output_cost_per_million", 8.0),
        **kwargs,
    )


def test_live_dataset_has_stable_case_identifiers():
    dataset = load_live_dataset()

    assert dataset.version == "1.0"
    assert len(dataset.cases) == 10
    assert len({case.id for case in dataset.cases}) == 10


@pytest.mark.asyncio
async def test_live_runner_records_quality_usage_cost_and_identity():
    benchmark = runner([value_program(42)])
    dataset = LiveEvaluationDataset(version="1.0", cases=[live_case()])

    result = await benchmark.run(dataset)

    assert result.mode == "live"
    assert result.model == "gpt-test"
    assert result.provider == "openai"
    assert result.passed == result.total == 1
    case = result.results[0]
    assert case.prompt_tokens == 100
    assert case.completion_tokens == 20
    assert case.estimated_cost_usd == pytest.approx(0.00036)


def test_live_runner_rejects_negative_pricing():
    with pytest.raises(ValueError, match="cannot be negative"):
        runner([], input_cost_per_million=-1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "case", "category"),
    [
        ("{", live_case(), FailureCategory.PARSE),
        ("[]", live_case(), FailureCategory.SCHEMA),
        (RuntimeError("unavailable"), live_case(), FailureCategory.PROVIDER),
        (value_program(41), live_case(), FailureCategory.CORRECTNESS),
        (
            value_program(42),
            live_case(must_use=["map"]),
            FailureCategory.CORRECTNESS,
        ),
    ],
)
async def test_live_runner_categorizes_model_failures(response, case, category):
    result = await runner([response]).run_case(case)

    assert result.failure_category == category
    assert not result.passed
    assert result.prompt_tokens == 100


@pytest.mark.asyncio
async def test_live_cli_writes_machine_readable_result(tmp_path, monkeypatch):
    dataset_path = tmp_path / "live.jsonl"
    dataset_path.write_text(
        '{"id":"answer","q":"question","a":42,"must_use":[]}\n',
        encoding="utf-8",
    )
    output_path = tmp_path / "results" / "live.json"
    transport = UsageTransport([value_program(42)])
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "evaluation.live_eval.OpenAITransport", lambda **kwargs: transport
    )

    exit_code = await run_live_cli(
        dataset_path=dataset_path,
        dataset_version="1.0",
        output_path=output_path,
        model="gpt-test",
        input_cost_per_million=2.0,
        output_cost_per_million=8.0,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["mode"] == "live"
    assert payload["passed"] == payload["total"] == 1
