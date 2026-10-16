# tests/instrumentation/otel/test_tracer_exporter_isolation.py
"""L7 isolation layer: both bridge directions wired to one provider.

The exporter (NiriZan -> OTel) and the span processor (OTel -> NiriZan) can be
attached to the same ``TracerProvider``, which is the configuration that turns
a wiring mistake into an export/ingest loop: every trace NiriZan exports would
come straight back as an ingested trace, forever. This file pins the loop
guard (``ignore_own_scope``, keyed on the instrumentation scope of the span,
not on object identity) and the shutdown lifecycle of that shared provider.

The core ``Tracer`` drives every scenario end to end, so the tests cover the
path an application actually takes: spans assembled by NiriZan, exported into
OpenTelemetry, and offered back to the NiriZan processor.

Deterministic: flushes go through ``force_flush`` (bounded wait on the
consumer's done event), never through sleeps.

Requires the optional ``otel`` extra; deselect with ``-m "not otel"``.
"""

import pytest

pytest.importorskip("opentelemetry")
pytest.importorskip("opentelemetry.sdk")

import asyncio  # noqa: E402
import threading  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from pathlib import Path  # noqa: E402
from uuid import UUID, uuid4  # noqa: E402

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)
from opentelemetry.trace import (  # noqa: E402
    NonRecordingSpan,
    SpanContext,
    TraceFlags,
    set_span_in_context,
)

from nirizan.instrumentation.exporters import BaseExporter, InMemoryExporter  # noqa: E402
from nirizan.instrumentation.otel.from_otel import NiriZanSpanProcessor  # noqa: E402
from nirizan.instrumentation.otel.semconv import (  # noqa: E402
    NIRIZAN_INSTRUMENTATION_SCOPE,
    NIRIZAN_SESSION_ID,
    NIRIZAN_SPAN_KIND,
)
from nirizan.instrumentation.otel.to_otel import NiriZanToOTelExporter  # noqa: E402
from nirizan.instrumentation.spans import Span, SpanKind, Trace  # noqa: E402
from nirizan.instrumentation.tracer import Tracer as NiriZanTracer  # noqa: E402
from nirizan.orchestrator.collector import TraceCollector  # noqa: E402
from nirizan.orchestrator.loop_sink import LoopTraceSink  # noqa: E402
from nirizan.storage.trace_repository import SQLiteTraceRepository  # noqa: E402

pytestmark = pytest.mark.otel


class RecordingSink:
    """Thread-safe sink that records traces in arrival order."""

    def __init__(self) -> None:
        self.traces: list[Trace] = []
        self._lock = threading.Lock()

    def enqueue_trace(self, trace: Trace) -> None:
        with self._lock:
            self.traces.append(trace)

    def snapshot(self) -> list[Trace]:
        with self._lock:
            return list(self.traces)


@dataclass
class Bridge:
    """One provider carrying both bridge directions, plus the core Tracer."""

    provider: TracerProvider
    memory: InMemorySpanExporter
    sink: RecordingSink
    processor: NiriZanSpanProcessor
    exporter: NiriZanToOTelExporter
    core: NiriZanTracer

    def finished(self) -> list[ReadableSpan]:
        return list(self.memory.get_finished_spans())

    def flush(self) -> bool:
        return self.processor.force_flush(timeout_millis=5_000)


def make_bridge(
    *,
    ignore_own_scope: bool = True,
    exporter_scope: str = NIRIZAN_INSTRUMENTATION_SCOPE,
    application_name: str = "l7-app",
) -> Bridge:
    """Wire core Tracer -> exporter -> provider -> processor on one provider."""
    sink = RecordingSink()
    provider = TracerProvider(shutdown_on_exit=False)
    processor = NiriZanSpanProcessor(sink, ignore_own_scope=ignore_own_scope)
    provider.add_span_processor(processor)
    memory = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    exporter = NiriZanToOTelExporter(tracer=provider.get_tracer(exporter_scope, "test"))
    core = NiriZanTracer(application_name, exporter=exporter)
    return Bridge(provider, memory, sink, processor, exporter, core)


@pytest.fixture
def bridge() -> Bridge:
    shared = make_bridge()
    yield shared
    shared.provider.shutdown()


async def run_trace(tracer: NiriZanTracer) -> None:
    """One root with two children: three spans in a single NiriZan trace."""
    async with tracer.start_span("plan", SpanKind.PLANNING):
        async with tracer.start_span("retrieve", SpanKind.RETRIEVAL):
            pass
        async with tracer.start_span("generate", SpanKind.GENERATION):
            pass


# ---------------------------------------------------------------------------
# The loop guard: exported spans are never ingested back
# ---------------------------------------------------------------------------


async def test_exporter_and_processor_on_one_provider_do_not_feed_each_other(
    bridge: Bridge,
) -> None:
    """The self-export loop guard holds on the full application path.

    The core Tracer exports three spans through the shared provider. The
    processor must skip them (they carry NiriZan's own instrumentation scope),
    so the sink stays empty while the OpenTelemetry side receives all three.
    """
    await run_trace(bridge.core)

    assert bridge.exporter.export_failures == 0
    assert bridge.flush() is True
    assert bridge.sink.snapshot() == []
    assert bridge.processor.get_stats() == {"own_scope_skipped": 3}
    assert len(bridge.finished()) == 3


async def test_the_skipped_spans_are_identified_by_their_instrumentation_scope(
    bridge: Bridge,
) -> None:
    """The guard reads the span's scope name: every exported span carries it.

    This is the mechanism ``ignore_own_scope`` keys on, so the spans the
    processor skips really do announce NiriZan's own scope.
    """
    await run_trace(bridge.core)

    spans = bridge.finished()
    assert len(spans) == 3
    for span in spans:
        scope = span.instrumentation_scope
        assert scope is not None
        assert scope.name == NIRIZAN_INSTRUMENTATION_SCOPE


async def test_own_scope_guard_can_be_disabled_so_one_provider_round_trips() -> None:
    """With ``ignore_own_scope=False`` the same wiring loops back exactly once.

    The exported spans are ingested and assembled into one trace; a second
    flush proves nothing keeps arriving, i.e. there is no runaway feedback.
    """
    shared = make_bridge(ignore_own_scope=False)
    try:
        await run_trace(shared.core)

        assert shared.flush() is True
        delivered = shared.sink.snapshot()
        assert len(delivered) == 1
        assert sorted(s.name for s in delivered[0].spans) == [
            "generate",
            "plan",
            "retrieve",
        ]
        assert len(shared.finished()) == 3

        assert shared.flush() is True
        assert len(shared.sink.snapshot()) == 1
    finally:
        shared.provider.shutdown()


async def test_the_guard_is_scope_based_not_identity_based() -> None:
    """A differently scoped tracer on the same provider is ingested back.

    Counterpart to the loop guard: skipping is decided by the span's
    instrumentation scope, not by whether the span came from this process.
    The very same core Tracer path, with an exporter bound to a foreign
    scope, flows into the NiriZan sink.
    """
    shared = make_bridge(exporter_scope="l7-foreign-app")
    try:
        await run_trace(shared.core)

        assert shared.flush() is True
        delivered = shared.sink.snapshot()
        assert len(delivered) == 1
        assert sorted(s.name for s in delivered[0].spans) == [
            "generate",
            "plan",
            "retrieve",
        ]
        assert shared.processor.get_stats() == {}
    finally:
        shared.provider.shutdown()


async def test_foreign_scope_spans_are_still_ingested_on_a_shared_provider(
    bridge: Bridge,
) -> None:
    """While the guard skips NiriZan's own spans, application spans arrive."""
    await run_trace(bridge.core)  # three own-scope spans, all skipped
    foreign = bridge.provider.get_tracer("l7-foreign-app")
    with foreign.start_span("foreign-op", attributes={NIRIZAN_SPAN_KIND: "planning"}):
        pass

    assert bridge.flush() is True
    delivered = bridge.sink.snapshot()
    assert len(delivered) == 1
    assert [s.name for s in delivered[0].spans] == ["foreign-op"]
    assert bridge.processor.get_stats() == {"own_scope_skipped": 3}


# ---------------------------------------------------------------------------
# Shutdown lifecycle of the shared provider
# ---------------------------------------------------------------------------


async def test_export_after_provider_shutdown_is_silent_and_drops_the_trace(
    bridge: Bridge,
) -> None:
    """Exporting into a shut down provider neither raises nor counts a failure."""
    bridge.provider.shutdown()

    await run_trace(bridge.core)

    assert bridge.exporter.export_failures == 0
    assert bridge.finished() == []
    assert bridge.sink.snapshot() == []


async def test_shutting_the_processor_down_first_leaves_the_export_side_working(
    bridge: Bridge,
) -> None:
    """A stopped ingest side does not break the application's export path."""
    bridge.processor.shutdown()

    assert bridge.processor.force_flush() is False

    await run_trace(bridge.core)

    assert bridge.exporter.export_failures == 0
    assert len(bridge.finished()) == 3
    assert bridge.sink.snapshot() == []


# ---------------------------------------------------------------------------
# Payload propagation across the whole bridge
# ---------------------------------------------------------------------------


async def test_session_id_travels_from_the_core_tracer_into_otel_attributes(
    bridge: Bridge,
) -> None:
    """The session opened around the core Tracer reaches every OTel span."""
    async with bridge.core.session() as session_id:
        await run_trace(bridge.core)

    spans = bridge.finished()
    assert len(spans) == 3
    for span in spans:
        assert (span.attributes or {}).get(NIRIZAN_SESSION_ID) == str(session_id)


async def test_parenting_survives_the_shared_provider_round_trip(bridge: Bridge) -> None:
    """Children exported through the shared provider keep their parent link."""
    await run_trace(bridge.core)

    by_name = {s.name: s for s in bridge.finished()}
    plan_id = by_name["plan"].get_span_context().span_id
    assert by_name["retrieve"].parent is not None
    assert by_name["retrieve"].parent.span_id == plan_id
    assert by_name["generate"].parent is not None
    assert by_name["generate"].parent.span_id == plan_id


# ---------------------------------------------------------------------------
# Core parity: attaching the bridge changes nothing about core tracing
# ---------------------------------------------------------------------------


def normalized_shape(trace: Trace) -> dict[str, object]:
    """A trace reduced to the facts the bridge must not affect.

    Identifiers and timestamps differ between two runs of the same program, so
    parity is checked on the structure the core tracer produced: application
    name, span names and kinds, the parent *name* of each span, and the
    attribute keys. Nothing here is time- or id-dependent, so the comparison is
    deterministic.
    """
    names = {span.span_id: span.name for span in trace.spans}
    return {
        "application_name": trace.application_name,
        "has_session": trace.session_id is not None,
        "spans": sorted(
            (
                span.name,
                span.kind.value,
                names.get(span.parent_span_id, "<root>"),
                tuple(sorted(span.attributes)),
                span.input_payload is not None,
                span.output_payload is not None,
            )
            for span in trace.spans
        ),
    }


class FanOutExporter(BaseExporter):
    """Delivers each trace to several exporters, in order, like an app would."""

    def __init__(self, *exporters: BaseExporter) -> None:
        self._exporters = exporters

    async def export(self, trace: Trace) -> None:
        for exporter in self._exporters:
            await exporter.export(trace)


async def test_the_same_run_produces_the_same_shape_with_and_without_the_bridge() -> None:
    """Core parity: an active bridge does not change what the core tracer emits.

    The same three-span run is executed twice: once with the bridge wired to a
    real provider next to an in-memory core exporter, and once with only the
    core exporter. The trace handed to the core exporter must have the same
    normalized shape both times, so an application that switches the bridge on
    does not silently get different data out of the core tracer.
    """
    bridged = make_bridge(application_name="l7-parity")
    recorder = InMemoryExporter()
    parity_tracer = NiriZanTracer(
        "l7-parity",
        exporter=FanOutExporter(
            recorder,
            NiriZanToOTelExporter(
                tracer=bridged.provider.get_tracer(NIRIZAN_INSTRUMENTATION_SCOPE, "parity")
            ),
        ),
    )
    try:
        await run_trace(parity_tracer)
    finally:
        bridged.provider.shutdown()

    plain_exporter = InMemoryExporter()
    plain = NiriZanTracer("l7-parity", exporter=plain_exporter)
    await run_trace(plain)

    with_bridge = recorder.get_traces()
    without_bridge = plain_exporter.get_traces()
    assert len(with_bridge) == 1
    assert len(without_bridge) == 1

    assert normalized_shape(with_bridge[0]) == normalized_shape(without_bridge[0])
    # The bridge really was active in the first run, so the equality above is
    # a comparison of two different paths rather than of one path with itself.
    assert bridged.processor.get_stats() == {"own_scope_skipped": 3}
    assert len(bridged.finished()) == 3


async def test_exporting_a_trace_does_not_mutate_the_input_trace(bridge: Bridge) -> None:
    """The exporter treats the caller's ``Trace`` as read-only.

    ``Trace`` is a shared value object that the caller may keep and reuse;
    export writing into it (an ingest stamp, a normalized name) would corrupt
    the caller's copy, so the model dump is compared before and after.
    """
    trace = _single_span_trace()
    before = trace.model_dump(mode="json")

    await bridge.exporter.export(trace)
    assert bridge.flush() is True

    assert trace.model_dump(mode="json") == before


def _single_span_trace() -> Trace:
    """A minimal trace built directly, without the core tracer's timing."""
    trace_id = uuid4()
    return Trace(
        trace_id=trace_id,
        application_name="l7-mutation",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.GENERATION,
                name="single",
                started_at=datetime(2026, 1, 1, tzinfo=UTC),
                ended_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
                attributes={"key": "value"},
                input_payload="in",
                output_payload="out",
            )
        ],
    )


# ---------------------------------------------------------------------------
# Untrusted ingest cannot take a stored native trace's id
# ---------------------------------------------------------------------------


def _native_stored_trace() -> Trace:
    """A native trace with metadata and two spans, as the core tracer builds it."""
    trace_id = uuid4()
    root_id = uuid4()
    child_id = uuid4()
    started = datetime(2026, 1, 1, tzinfo=UTC)
    return Trace(
        trace_id=trace_id,
        application_name="native-app",
        created_at=started,
        code_commit="native0000",
        data_snapshot_id="native-snapshot",
        session_id=uuid4(),
        spans=[
            Span(
                span_id=root_id,
                trace_id=trace_id,
                kind=SpanKind.PLANNING,
                name="native-root",
                started_at=started,
                ended_at=started,
                attributes={"native": "yes"},
            ),
            Span(
                span_id=child_id,
                trace_id=trace_id,
                parent_span_id=root_id,
                kind=SpanKind.GENERATION,
                name="native-child",
                started_at=started,
                ended_at=started,
            ),
        ],
    )


class _SignallingRepository(SQLiteTraceRepository):
    """The real repository, plus an event set once a save has completed."""

    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)
        self.saved = asyncio.Event()

    async def save(self, trace: Trace) -> None:
        await super().save(trace)
        self.saved.set()


async def _ingest_otel_trace_id_into(
    repository: _SignallingRepository,
    otel_trace_id: int,
    *,
    trust_stashed_ids: bool,
    attributes: dict[str, str] | None = None,
) -> None:
    """Run one OTel span through the real ingest path into ``repository``.

    The span is created by a real SDK tracer under an explicit context, so the
    processor sees exactly what it would see in production, and delivery goes
    through ``LoopTraceSink`` and ``TraceCollector`` into the repository that
    already holds the native trace. The save is awaited through the
    repository's event, because ``LoopTraceSink`` only schedules the collector
    coroutine and ``collector.stop()`` would otherwise race it.
    """
    loop = asyncio.get_running_loop()
    collector = TraceCollector(repository)
    await collector.start()
    provider = TracerProvider(shutdown_on_exit=False)
    processor = NiriZanSpanProcessor(
        LoopTraceSink(collector, loop),
        trust_stashed_ids=trust_stashed_ids,
    )
    provider.add_span_processor(processor)
    context = set_span_in_context(
        NonRecordingSpan(
            SpanContext(
                trace_id=otel_trace_id,
                span_id=0x1234,
                is_remote=True,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
            )
        )
    )

    with provider.get_tracer("l7-collision").start_span(
        "foreign-op",
        context=context,
        attributes={"nirizan.span.kind": "generation", **(attributes or {})},
    ):
        pass

    assert processor.force_flush(timeout_millis=30_000) is True
    provider.shutdown()
    await asyncio.wait_for(repository.saved.wait(), timeout=15)
    await collector.stop()


def _stored_rows(repository: SQLiteTraceRepository, trace_id: object) -> tuple[dict, list[dict]]:
    """The raw stored rows for a trace, for a byte-for-byte comparison."""
    trace_row = repository._conn.execute(
        "SELECT * FROM traces WHERE trace_id = ?", (str(trace_id),)
    ).fetchone()
    span_rows = repository._conn.execute(
        "SELECT * FROM spans WHERE trace_id = ? ORDER BY span_id", (str(trace_id),)
    ).fetchall()
    return dict(trace_row), [dict(row) for row in span_rows]


def _other_trace_ids(repository: SQLiteTraceRepository, keep: object) -> list[str]:
    return [
        row["trace_id"]
        for row in repository._conn.execute("SELECT trace_id FROM traces").fetchall()
        if row["trace_id"] != str(keep)
    ]


async def test_untrusted_ingest_cannot_overwrite_a_stored_native_trace(tmp_path: Path) -> None:
    """An OTel trace id must not let an ingested trace take a native trace's id.

    The OTel trace id arrives over the wire (a W3C ``traceparent`` header), so
    it is producer-influenced: any producer can send the exact id of an
    existing stored native trace. If ingest mapped that id straight back to a
    NiriZan UUID, ``save`` would treat the incoming trace as the stored one and
    replace its metadata and its whole span set, so this asserts the stored rows
    are byte-for-byte unchanged and the ingested trace lands under a different
    id.
    """
    repository = _SignallingRepository(str(tmp_path / "traces.db"))
    try:
        native = _native_stored_trace()
        await repository.save(native)
        before_trace_row, before_span_rows = _stored_rows(repository, native.trace_id)
        repository.saved.clear()

        await _ingest_otel_trace_id_into(
            repository,
            native.trace_id.int,
            trust_stashed_ids=False,
        )

        after_trace_row, after_span_rows = _stored_rows(repository, native.trace_id)
        assert after_trace_row == before_trace_row
        assert after_span_rows == before_span_rows
        assert after_span_rows, "the native trace lost its spans"

        ingested_ids = _other_trace_ids(repository, native.trace_id)
        assert len(ingested_ids) == 1
        assert ingested_ids[0] != str(native.trace_id)
        ingested = await repository.get(UUID(ingested_ids[0]))
        assert ingested is not None
        assert [span.name for span in ingested.spans] == ["foreign-op"]
    finally:
        repository.close()


async def test_untrusted_stash_with_no_stashed_id_cannot_take_a_native_trace_id(
    tmp_path: Path,
) -> None:
    """The trusted-but-unstashed fallback derives too, so it cannot collide.

    With ``trust_stashed_ids=True`` a stashed id still wins, which is the
    round-trip path. When no span stashes one, the fallback must not fall back
    to the exact inverse mapping either, because that is the same collision with
    a different reason for arriving.
    """
    repository = _SignallingRepository(str(tmp_path / "traces.db"))
    try:
        native = _native_stored_trace()
        await repository.save(native)
        before_trace_row, before_span_rows = _stored_rows(repository, native.trace_id)
        repository.saved.clear()

        await _ingest_otel_trace_id_into(
            repository,
            native.trace_id.int,
            trust_stashed_ids=True,
        )

        after_trace_row, after_span_rows = _stored_rows(repository, native.trace_id)
        assert after_trace_row == before_trace_row
        assert after_span_rows == before_span_rows

        ingested_ids = _other_trace_ids(repository, native.trace_id)
        assert len(ingested_ids) == 1
        assert ingested_ids[0] != str(native.trace_id)
    finally:
        repository.close()


async def test_a_stashed_trace_id_is_still_used_and_marked_roundtrip(tmp_path: Path) -> None:
    """A trusted stash keeps the round trip intact, provenance included.

    This is the counterpart to the two collision tests: deriving is the default
    for untrusted and unstashed input, not a blanket removal of identity
    recovery. A producer that is trusted and stashes the id still gets the
    NiriZan id it exported, and `save` still recognizes the trace as its own.
    """
    repository = _SignallingRepository(str(tmp_path / "traces.db"))
    try:
        native = _native_stored_trace()
        await repository.save(native)
        before_trace_row, before_span_rows = _stored_rows(repository, native.trace_id)
        repository.saved.clear()

        await _ingest_otel_trace_id_into(
            repository,
            native.trace_id.int,
            trust_stashed_ids=True,
            attributes={"nirizan.trace_id": str(native.trace_id)},
        )

        after_trace_row, after_span_rows = _stored_rows(repository, native.trace_id)
        # The stashed id wins, so this save is a replacement of that trace.
        assert len(after_span_rows) == 1
        assert after_span_rows[0]["name"] == "foreign-op"
        assert after_trace_row["trace_id"] == before_trace_row["trace_id"]
        # And the round trip is recorded as such, not as a derived id.
        stored = await repository.get(native.trace_id)
        assert stored is not None
        assert stored.spans[0].attributes["nirizan.trace_id.source"] == "roundtrip"
    finally:
        repository.close()
