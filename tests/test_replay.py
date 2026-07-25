import pytest

from treelang.exceptions import ReplayMismatchError
from treelang.replay import (
    ModelReplayEntry,
    ModelReplayTransport,
    ToolReplayEntry,
    ToolReplayProvider,
)

TOOL = {
    "name": "add",
    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
}


@pytest.mark.asyncio
async def test_tool_replay_validates_order_and_arguments():
    replay = ToolReplayProvider(
        [TOOL],
        [ToolReplayEntry(name="add", arguments={"a": 2, "b": 3}, output=5)],
    )

    assert (await replay.call_tool("add", {"a": 2, "b": 3})).content == 5
    replay.assert_consumed()


@pytest.mark.asyncio
async def test_tool_replay_rejects_drift_and_unconsumed_entries():
    replay = ToolReplayProvider(
        [TOOL],
        [ToolReplayEntry(name="add", arguments={"a": 2, "b": 3}, output=5)],
    )

    with pytest.raises(ReplayMismatchError, match="did not match"):
        await replay.call_tool("add", {"a": 3, "b": 2})

    replay = ToolReplayProvider(
        [TOOL],
        [ToolReplayEntry(name="add", arguments={"a": 2, "b": 3}, output=5)],
    )
    with pytest.raises(ReplayMismatchError, match="unconsumed"):
        replay.assert_consumed()


@pytest.mark.asyncio
async def test_model_replay_supports_completions_and_streams():
    request = {"model": "test", "messages": []}
    replay = ModelReplayTransport(
        [
            ModelReplayEntry(request=request, response="complete"),
            ModelReplayEntry(
                request=request,
                response=("one", "two"),
                kind="stream",
            ),
        ]
    )

    assert await replay.complete(request) == "complete"
    assert [chunk async for chunk in replay.stream(request)] == ["one", "two"]
    replay.assert_consumed()


@pytest.mark.asyncio
async def test_model_replay_rejects_request_drift():
    replay = ModelReplayTransport(
        [ModelReplayEntry(request={"model": "expected"}, response="response")]
    )

    with pytest.raises(ReplayMismatchError, match="did not match"):
        await replay.complete({"model": "different"})
