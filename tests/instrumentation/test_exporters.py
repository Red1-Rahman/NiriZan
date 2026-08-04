from datetime import datetime, timezone
from uuid import uuid4

import pytest

from nirizan.instrumentation.exporters import ConsoleExporter, InMemoryExporter
from nirizan.instrumentation.spans import Span, SpanKind, Trace


@pytest.fixture
def sample_trace() -> Trace:
    trace_id = uuid4()
    now = datetime.now(timezone.utc)
    span = Span(
        span_id=uuid4(),
        trace_id=trace_id,
        kind=SpanKind.RETRIEVAL,
        name="vector_db_search",
        started_at=now,
        ended_at=now,
    )
    return Trace(
        trace_id=trace_id,
        application_name="test_app",
        spans=[span],
        created_at=now,
    )


@pytest.mark.asyncio
async def test_in_memory_exporter(sample_trace: Trace) -> None:
    exporter = InMemoryExporter()
    assert len(exporter.get_traces()) == 0

    await exporter.export(sample_trace)
    traces = exporter.get_traces()
    assert len(traces) == 1
    assert traces[0].trace_id == sample_trace.trace_id

    exporter.clear()
    assert len(exporter.get_traces()) == 0


@pytest.mark.asyncio
async def test_console_exporter(sample_trace: Trace, caplog: pytest.LogCaptureFixture) -> None:
    exporter = ConsoleExporter()
    with caplog.at_level("INFO"):
        await exporter.export(sample_trace)

    assert "Trace Exported" in caplog.text
    assert str(sample_trace.trace_id) in caplog.text
