# tests/orchestrator/test_otel_boundary_isolation.py
"""L3 isolation layer: the orchestrator boundary is OpenTelemetry-blind.

The collector path (``CollectorExporter`` -> ``TraceCollector`` -> repository,
and the thread-hop ``LoopTraceSink`` the OTel processor uses) must accept
traces from *either* instrumentation source without importing OpenTelemetry
and without caring where a trace came from. By the time a ``Trace`` reaches
the orchestrator, every OpenTelemetry concept has already been erased: the
boundary object is NiriZan's own ``Trace``.

This file is part of the core-only CI leg: it must never import
``opentelemetry`` (enforced by ``tests/test_otel_isolation.py``'s static scan
of the package and by the leg itself, which installs no otel extra).
"""

import asyncio
import threading
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from nirizan.instrumentation.spans import (
    SYNTHETIC_PARENT_ATTRIBUTE,
    Span,
    SpanKind,
    Trace,
)
from nirizan.orchestrator.collector import CollectorExporter, TraceCollector
from nirizan.orchestrator.loop_sink import LoopTraceSink

START = datetime(2026, 1, 1, tzinfo=UTC)


class RecordingRepository:
    """Minimal TraceSink double: records exactly what the collector saved."""

    def __init__(self) -> None:
        self.saved: list[Trace] = []
        self.saved_event = asyncio.Event()
        self._lock = threading.Lock()

    async def save(self, trace: Trace) -> None:
        with self._lock:
            self.saved.append(trace)
        self.saved_event.set()


def make_trace(*, application_name: str = "boundary-tests") -> Trace:
    return Trace(
        trace_id=uuid4(),
        application_name=application_name,
        created_at=START,
        spans=[],
    )


def make_span(
    trace_id: UUID,
    *,
    name: str,
    parent_span_id: UUID | None = None,
    attributes: dict[str, str | int | float | bool] | None = None,
) -> Span:
    return Span(
        span_id=uuid4(),
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        kind=SpanKind.GENERATION,
        name=name,
        started_at=START,
        ended_at=START,
        attributes=attributes or {},
    )


async def test_collector_persists_a_trace_with_synthetic_parent_metadata() -> None:
    """A trace carrying OTel-bridge synthetic-parent metadata needs no adapter.

    ``SYNTHETIC_PARENT_ATTRIBUTE`` is how the OTel ingestion path marks a
    dangling parent link. The orchestrator persists such traces untouched:
    the marker lives in core attributes, not in any OTel type.
    """
    repository = RecordingRepository()
    collector = TraceCollector(repository)
    await collector.start()
    trace = make_trace()
    trace = trace.model_copy(
        update={
            "spans": [
                make_span(
                    trace.trace_id,
                    name="orphan-child",
                    parent_span_id=uuid4(),
                    attributes={SYNTHETIC_PARENT_ATTRIBUTE: True},
                )
            ]
        }
    )
    exporter = CollectorExporter(collector)

    await exporter.export(trace)
    await collector.stop()

    assert len(repository.saved) == 1
    saved = repository.saved[0]
    assert saved.trace_id == trace.trace_id
    assert saved.spans[0].attributes[SYNTHETIC_PARENT_ATTRIBUTE] is True
    # Ingest-stamped fields are applied by the collector, not the exporter.
    assert saved.code_commit is not None or saved.data_snapshot_id is not None


async def test_collector_stop_flushes_every_enqueued_trace() -> None:
    """stop() drains the queue: nothing exported before stop() is lost."""
    repository = RecordingRepository()
    collector = TraceCollector(repository)
    await collector.start()
    exporter = CollectorExporter(collector)

    traces = [make_trace() for _ in range(5)]
    for trace in traces:
        await exporter.export(trace)
    await collector.stop()

    assert {t.trace_id for t in repository.saved} == {t.trace_id for t in traces}


async def test_loop_sink_delivers_from_a_foreign_thread_into_the_loop() -> None:
    """LoopTraceSink hops a synchronous (foreign-thread) enqueue into the loop.

    This is exactly how NiriZanSpanProcessor (which runs on its own consumer
    thread) hands traces to the async collector; the sink must not need or
    touch OpenTelemetry to do it.
    """
    repository = RecordingRepository()
    collector = TraceCollector(repository)
    loop = asyncio.get_running_loop()
    await collector.start()
    sink = LoopTraceSink(collector, loop)
    trace = make_trace()

    enqueued = threading.Event()

    def producer() -> None:
        sink.enqueue_trace(trace)
        enqueued.set()

    thread = threading.Thread(target=producer)
    thread.start()
    thread.join(timeout=5)
    assert enqueued.is_set()

    # The sink schedules the collector coroutine onto the loop without
    # blocking; wait for the delivery itself, not just the enqueue call.
    await asyncio.wait_for(repository.saved_event.wait(), timeout=5)
    await collector.stop()

    assert [t.trace_id for t in repository.saved] == [trace.trace_id]


async def test_the_boundary_object_is_a_core_trace_even_for_otel_shaped_data() -> None:
    """Whatever the provenance, the orchestrator only ever sees ``Trace``.

    A trace assembled from OTel spans can carry provenance attributes, long
    payloads and sequence-encoded values; all of it is plain core data by the
    time it crosses the boundary.
    """
    repository = RecordingRepository()
    collector = TraceCollector(repository)
    await collector.start()
    root_id = uuid4()
    trace = make_trace().model_copy(
        update={
            "spans": [
                make_span(root_id, name="root"),
                make_span(
                    root_id,
                    name="child",
                    parent_span_id=root_id,
                    attributes={"nirizan.provenance": "roundtrip", "seq": '["a", "b"]'},
                ),
            ]
        }
    )

    await CollectorExporter(collector).export(trace)
    await collector.stop()

    saved = repository.saved[0]
    assert isinstance(saved, Trace)
    assert [s.name for s in saved.spans] == ["root", "child"]
    assert saved.spans[1].attributes["nirizan.provenance"] == "roundtrip"


@pytest.mark.parametrize("count", [0, 1, 2, 10])
async def test_collector_round_trips_traces_of_any_span_count(count: int) -> None:
    """Empty traces (all spans dropped by policy) persist like any other."""
    repository = RecordingRepository()
    collector = TraceCollector(repository)
    await collector.start()
    trace = make_trace().model_copy(
        update={"spans": [make_span(uuid4(), name=f"s{i}") for i in range(count)]}
    )

    await CollectorExporter(collector).export(trace)
    await collector.stop()

    assert len(repository.saved[0].spans) == count
