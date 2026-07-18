import json
import logging

import pytest

from evaluation.models import EvaluationCase, EvaluationDataset
from evaluation.offline import OfflineToolProvider
from evaluation.runner import OfflineBenchmarkRunner
from treelang.ai.transport import complete_with_timeout, stream_with_observability
from treelang.observability import REDACTED, Observability, redact


class RecordingTracer:
    def __init__(self):
        self.events = []

    def record(self, event, attributes):
        self.events.append((event, attributes))


class FakeTransport:
    async def complete(self, request):
        return "model output with sk-outputsecret"

    def stream(self, request):
        async def chunks():
            yield "private chunk"

        return chunks()


def test_redact_removes_nested_credentials_and_content_by_default():
    value = {
        "api_key": "sk-abcdefghijk",
        "headers": {"Authorization": "Bearer abc.def.ghi"},
        "tool_secret": "hidden",
        "messages": [{"role": "user", "content": "private prompt"}],
        "error": "request failed for sk-errorsecret",
        "metadata": {"case_id": "case-1"},
    }

    safe = redact(value)

    assert safe["api_key"] == REDACTED
    assert safe["headers"]["Authorization"] == REDACTED
    assert safe["tool_secret"] == REDACTED
    assert safe["messages"] == REDACTED
    assert safe["error"] == REDACTED
    assert safe["metadata"] == {"case_id": "case-1"}


def test_content_requires_explicit_opt_in_but_credentials_never_do():
    safe = redact(
        {
            "question": "visible question",
            "error": "failed with sk-errorsecret",
            "api_key": "sk-abcdefghijk",
        },
        allow_content=True,
    )

    assert safe == {
        "question": "visible question",
        "error": f"failed with {REDACTED}",
        "api_key": REDACTED,
    }


def test_logs_and_traces_receive_identical_redacted_attributes(caplog):
    tracer = RecordingTracer()
    logger = logging.getLogger("test.observability")
    caplog.set_level(logging.INFO, logger=logger.name)
    observer = Observability(logger=logger, tracer=tracer)

    observer.emit(
        "case.completed",
        question="private question",
        actual="private output",
        authorization="Bearer top.secret.token",
        case_id="case-1",
    )

    logged = json.loads(caplog.records[-1].message)
    traced_event, traced = tracer.events[-1]
    assert logged == {"event": traced_event, **traced}
    assert logged["question"] == logged["actual"] == REDACTED
    assert logged["authorization"] == REDACTED
    assert logged["case_id"] == "case-1"
    serialized = json.dumps(logged)
    assert "private" not in serialized
    assert "top.secret.token" not in serialized


@pytest.mark.asyncio
async def test_transport_events_redact_requests_and_responses(caplog):
    tracer = RecordingTracer()
    logger = logging.getLogger("test.transport-observability")
    caplog.set_level(logging.INFO, logger=logger.name)
    observer = Observability(logger=logger, tracer=tracer)
    request = {
        "model": "model",
        "messages": [{"role": "user", "content": "private prompt"}],
        "api_key": "sk-requestsecret",
    }

    response = await complete_with_timeout(FakeTransport(), request, None, observer)
    streamed = [
        part
        async for part in stream_with_observability(FakeTransport(), request, observer)
    ]

    assert response.startswith("model output")
    assert streamed == ["private chunk"]
    serialized_logs = "\n".join(record.message for record in caplog.records)
    serialized_trace = json.dumps(tracer.events)
    for secret in (
        "private prompt",
        "sk-requestsecret",
        "model output",
        "sk-outputsecret",
        "private chunk",
    ):
        assert secret not in serialized_logs
        assert secret not in serialized_trace
    assert {event for event, _ in tracer.events} >= {
        "model.request.started",
        "model.request.completed",
        "model.stream.started",
        "model.stream.completed",
    }


@pytest.mark.asyncio
async def test_transport_failure_details_do_not_reach_sinks(caplog):
    tracer = RecordingTracer()
    logger = logging.getLogger("test.failed-transport-observability")
    caplog.set_level(logging.INFO, logger=logger.name)
    observer = Observability(logger=logger, tracer=tracer)

    class FailingTransport(FakeTransport):
        async def complete(self, request):
            raise RuntimeError("private prompt sk-failuresecret")

        def stream(self, request):
            async def failure():
                raise RuntimeError("private output sk-streamsecret")
                yield ""  # pragma: no cover

            return failure()

    with pytest.raises(RuntimeError):
        await complete_with_timeout(FailingTransport(), {}, None, observer)
    with pytest.raises(RuntimeError):
        _ = [
            part
            async for part in stream_with_observability(
                FailingTransport(), {}, observer
            )
        ]

    serialized = "\n".join(record.message for record in caplog.records)
    traced = json.dumps(tracer.events)
    for secret in (
        "private prompt",
        "sk-failuresecret",
        "private output",
        "sk-streamsecret",
    ):
        assert secret not in serialized
        assert secret not in traced
    failed_events = {
        event: attributes
        for event, attributes in tracer.events
        if event.endswith("failed")
    }
    assert failed_events["model.request.failed"]["error"] == REDACTED
    assert failed_events["model.stream.failed"]["error"] == REDACTED


@pytest.mark.asyncio
async def test_benchmark_events_are_metadata_only(caplog):
    tracer = RecordingTracer()
    logger = logging.getLogger("test.benchmark-observability")
    caplog.set_level(logging.INFO, logger=logger.name)
    observer = Observability(logger=logger, tracer=tracer)
    dataset = EvaluationDataset(
        version="1.0",
        cases=[
            EvaluationCase(
                id="secret-case",
                question="private benchmark question",
                expected="private expected output",
                ast={
                    "type": "program",
                    "mode": "single",
                    "body": [
                        {"type": "value", "name": "secret", "value": "secret-value"}
                    ],
                },
            )
        ],
    )

    result = await OfflineBenchmarkRunner(
        OfflineToolProvider(), observability=observer
    ).run(dataset)

    assert result.passed == 0
    serialized = "\n".join(record.message for record in caplog.records)
    traced = json.dumps(tracer.events)
    for secret in (
        "private benchmark question",
        "private expected output",
        "secret-value",
    ):
        assert secret not in serialized
        assert secret not in traced
    assert {event for event, _ in tracer.events} == {
        "benchmark.started",
        "benchmark.case.started",
        "benchmark.case.completed",
        "benchmark.completed",
    }
