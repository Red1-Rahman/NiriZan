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

import threading  # noqa: E402
from dataclasses import dataclass  # noqa: E402

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)

from nirizan.instrumentation.otel.from_otel import NiriZanSpanProcessor  # noqa: E402
from nirizan.instrumentation.otel.semconv import (  # noqa: E402
    NIRIZAN_INSTRUMENTATION_SCOPE,
    NIRIZAN_SESSION_ID,
    NIRIZAN_SPAN_KIND,
)
from nirizan.instrumentation.otel.to_otel import NiriZanToOTelExporter  # noqa: E402
from nirizan.instrumentation.spans import SpanKind, Trace  # noqa: E402
from nirizan.instrumentation.tracer import Tracer as NiriZanTracer  # noqa: E402

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
