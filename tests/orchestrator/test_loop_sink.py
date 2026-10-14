import asyncio
from collections.abc import Coroutine
from typing import Any
from uuid import uuid4

import pytest

from nirizan.instrumentation.spans import Trace
from nirizan.orchestrator.loop_sink import LoopTraceSink


def make_trace() -> Trace:
    from datetime import UTC, datetime

    return Trace(
        trace_id=uuid4(),
        application_name="loop-sink-tests",
        created_at=datetime.now(UTC),
    )


class RecordingCollector:
    def __init__(self) -> None:
        self.created_coroutine: Coroutine[Any, Any, None] | None = None

    def enqueue_trace(self, _trace: Trace) -> Coroutine[Any, Any, None]:
        async def record() -> None:
            return None

        self.created_coroutine = record()
        return self.created_coroutine


def test_enqueue_trace_closes_coroutine_when_loop_is_closed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    loop = asyncio.new_event_loop()
    loop.close()
    collector = RecordingCollector()

    with caplog.at_level("ERROR"):
        LoopTraceSink(collector, loop).enqueue_trace(make_trace())

    assert collector.created_coroutine is not None
    assert collector.created_coroutine.cr_frame is None
    assert "Failed to enqueue trace from OTel processor" in caplog.text
