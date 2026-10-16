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
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
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
from nirizan.storage.trace_repository import SQLiteTraceRepository

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
    thread.join(timeout=15)
    assert enqueued.is_set()

    # The sink schedules the collector coroutine onto the loop without
    # blocking; wait for the delivery itself, not just the enqueue call.
    await asyncio.wait_for(repository.saved_event.wait(), timeout=15)
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


# ---------------------------------------------------------------------------
# The real event loop: collector, thread-hop sink, and SQLite storage together
# ---------------------------------------------------------------------------


class RaisingRepository:
    """A repository whose ``save`` always fails, like a full disk would."""

    def __init__(self) -> None:
        self.calls = 0

    async def save(self, trace: Trace) -> None:
        self.calls += 1
        raise RuntimeError("storage is unavailable")


@pytest.fixture
def sqlite_repository(tmp_path: Path) -> Iterator[SQLiteTraceRepository]:
    repository = SQLiteTraceRepository(str(tmp_path / "traces.db"))
    yield repository
    repository.close()


class SignallingRepository(SQLiteTraceRepository):
    """The real repository, plus an event set once a save has completed."""

    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)
        self.saved_event = asyncio.Event()

    async def save(self, trace: Trace) -> None:
        await super().save(trace)
        self.saved_event.set()


async def test_the_full_loop_persists_an_otel_shaped_trace_as_canonical_utc(
    tmp_path: Path,
) -> None:
    """Sink, collector, and SQLite on one real loop: the trace lands in storage.

    This is the production path the bridge uses: a foreign thread calls
    ``enqueue_trace``, the sink hops onto this loop, and the collector persists
    through the real repository. A synthetic-parent marker and a non-UTC input
    both have to survive, with the stored text canonical UTC.
    """
    sqlite_repository = SignallingRepository(str(tmp_path / "traces.db"))
    collector = TraceCollector(sqlite_repository)
    await collector.start()
    loop = asyncio.get_running_loop()
    sink = LoopTraceSink(collector, loop)
    trace_id = uuid4()
    local = START.astimezone(timezone(timedelta(hours=5, minutes=30)))
    orphan_id = uuid4()
    orphan_parent_id = uuid4()
    trace = Trace(
        trace_id=trace_id,
        application_name="l3-loop",
        created_at=local,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.PLANNING,
                name="root",
                started_at=local,
                ended_at=local + timedelta(seconds=1),
            ),
            Span(
                span_id=orphan_id,
                trace_id=trace_id,
                parent_span_id=orphan_parent_id,
                kind=SpanKind.GENERATION,
                name="orphan-child",
                started_at=local,
                ended_at=local + timedelta(seconds=1),
                attributes={SYNTHETIC_PARENT_ATTRIBUTE: True},
            ),
        ],
    )

    delivered = asyncio.Event()

    def producer() -> None:
        sink.enqueue_trace(trace)
        delivered.set()

    worker = threading.Thread(target=producer)
    worker.start()
    worker.join(timeout=15)
    assert delivered.is_set()
    # Wait for the persistence itself, not just for the enqueue call: the sink
    # schedules the coroutine and returns without blocking.
    await asyncio.wait_for(sqlite_repository.saved_event.wait(), timeout=15)
    await collector.stop()

    stored = await sqlite_repository.get(trace_id)
    assert stored is not None
    assert stored.created_at == START
    assert stored.created_at.utcoffset() == timedelta(0)
    assert stored.created_at.tzinfo is not None
    names = {span.name: span for span in stored.spans}
    assert names["orphan-child"].parent_span_id == orphan_parent_id
    assert names["orphan-child"].attributes[SYNTHETIC_PARENT_ATTRIBUTE] is True
    row = sqlite_repository._conn.execute(
        "SELECT created_at FROM traces WHERE trace_id = ?", (str(trace_id),)
    ).fetchone()
    assert row["created_at"] == "2026-01-01T00:00:00+00:00"
    sqlite_repository.close()


async def test_the_loop_sink_is_silent_when_the_loop_is_closed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A closed loop loses the trace and logs; it never raises at the caller.

    ``enqueue_trace`` is called from the processor's consumer thread, where an
    exception would kill ingestion entirely, so the failure has to stay inside
    the adapter.
    """
    collector = TraceCollector(RecordingRepository())
    closed_loop = asyncio.new_event_loop()
    sink = LoopTraceSink(collector, closed_loop)
    closed_loop.close()

    with caplog.at_level("ERROR"):
        sink.enqueue_trace(make_trace())

    assert "Failed to enqueue trace from OTel processor" in caplog.text


async def test_the_loop_sink_is_silent_when_the_collector_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A collector that raises on enqueue is logged on the loop, not propagated."""

    class FailingCollector:
        def __init__(self) -> None:
            self.attempted = asyncio.Event()

        async def enqueue_trace(self, trace: Trace) -> None:
            self.attempted.set()
            raise RuntimeError("collector refused the trace")

    collector = FailingCollector()
    sink = LoopTraceSink(collector, asyncio.get_running_loop())

    def producer() -> None:
        sink.enqueue_trace(make_trace())

    worker = threading.Thread(target=producer)
    worker.start()
    worker.join(timeout=15)
    assert not worker.is_alive()
    # The call itself returned without raising into the calling thread.
    await asyncio.wait_for(collector.attempted.wait(), timeout=15)
    # The scheduled coroutine then failed on the loop; its done callback logs.
    await wait_for_log(caplog, "collector refused the trace")


async def wait_for_log(caplog: pytest.LogCaptureFixture, needle: str) -> None:
    """Wait (bounded) until ``needle`` appears in the captured log records."""
    # A generous but bounded budget: the sink hops the coroutine onto the loop
    # from another thread, and the done callback that logs runs afterwards, so
    # the wait has to cover thread scheduling as well as the loop's own.
    for _ in range(100):
        if needle in caplog.text:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"{needle!r} was never logged; log was:\n{caplog.text}")


async def test_the_collector_isolates_a_failing_repository(
    caplog: pytest.LogCaptureFixture,
    sqlite_repository: SQLiteTraceRepository,
) -> None:
    """A repository failure is logged per trace; the collector keeps running."""
    failing = RaisingRepository()
    collector = TraceCollector(failing)
    await collector.start()

    for _ in range(3):
        await collector.enqueue_trace(make_trace())

    await collector.stop()

    assert failing.calls == 3
    assert "Error persisting trace in collector worker" in caplog.text


async def test_a_failing_repository_does_not_block_the_next_trace(
    sqlite_repository: SQLiteTraceRepository,
) -> None:
    """One failing save must not stop the traces queued behind it."""

    class FailFirstRepository:
        def __init__(self) -> None:
            self.inner = sqlite_repository
            self.calls = 0

        async def save(self, trace: Trace) -> None:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient failure")
            await self.inner.save(trace)

    repository = FailFirstRepository()
    collector = TraceCollector(repository)
    await collector.start()
    first, second = (
        make_trace(application_name="l3-after-failure"),
        make_trace(application_name="l3-after-failure"),
    )

    await collector.enqueue_trace(first)
    await collector.enqueue_trace(second)
    await collector.stop()

    assert await sqlite_repository.get(first.trace_id) is None
    stored = await sqlite_repository.get(second.trace_id)
    assert stored is not None
    assert stored.trace_id == second.trace_id
