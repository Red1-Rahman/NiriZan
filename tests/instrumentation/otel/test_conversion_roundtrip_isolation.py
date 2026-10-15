# tests/instrumentation/otel/test_conversion_roundtrip_isolation.py
"""L6 isolation layer: NiriZan -> OTel -> NiriZan round-trip fidelity.

The two adapters must be inverses of each other on the data the pipeline
actually carries: a NiriZan ``Trace`` exported into OpenTelemetry and then
ingested back by ``NiriZanSpanProcessor`` must come out as the same trace
shape, with identity, span kinds, parent links, and payloads preserved.
If the two halves drift (an attribute one side writes and the other stops
reading), traces silently degrade as they cross the bridge.

Requires the optional ``otel`` extra; deselect with ``-m "not otel"``.
"""

import pytest

pytest.importorskip("opentelemetry")
pytest.importorskip("opentelemetry.sdk")

from datetime import UTC, datetime, timedelta  # noqa: E402
from uuid import uuid4  # noqa: E402

from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter as OTelInMemoryExporter,
)

from nirizan.instrumentation.otel.from_otel import NiriZanSpanProcessor  # noqa: E402
from nirizan.instrumentation.otel.to_otel import (  # noqa: E402
    OTelExporterConfig,
    export_trace_to_otel,
)
from nirizan.instrumentation.spans import Span, SpanKind, Trace  # noqa: E402

pytestmark = pytest.mark.otel

START = datetime(2026, 1, 1, tzinfo=UTC)


class RecordingSink:
    def __init__(self) -> None:
        self.traces: list[Trace] = []

    def enqueue_trace(self, trace: Trace) -> None:
        self.traces.append(trace)


def make_trace() -> Trace:
    """A parent/child trace with distinct start instants.

    The two spans start one second apart, which is what real nested spans
    look like: assembly orders spans by start time, so distinct starts make
    the resulting order independent of the random OTel span ids the SDK
    mints on every export.
    """
    trace_id = uuid4()
    root_id = uuid4()
    child_id = uuid4()
    return Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        session_id=uuid4(),
        spans=[
            Span(
                span_id=root_id,
                trace_id=trace_id,
                parent_span_id=None,
                kind=SpanKind.PLANNING,
                name="plan",
                started_at=START,
                ended_at=START + timedelta(milliseconds=500),
                input_payload="plan the thing",
            ),
            Span(
                span_id=child_id,
                trace_id=trace_id,
                parent_span_id=root_id,
                kind=SpanKind.RETRIEVAL,
                name="retrieve",
                started_at=START + timedelta(seconds=1),
                ended_at=START + timedelta(seconds=1, milliseconds=500),
                attributes={"retrieval.top_k": 3},
            ),
        ],
    )


def roundtrip(trace: Trace, sink: RecordingSink) -> None:
    """Export ``trace`` into a real OTel pipeline and ingest it back."""
    provider = TracerProvider()
    trusted = frozenset({trace.session_id}) if trace.session_id else frozenset()
    processor = NiriZanSpanProcessor(
        sink,
        trust_stashed_ids=True,
        trusted_session_ids=trusted,
        capture_content=True,
    )
    provider.add_span_processor(processor)
    provider.add_span_processor(SimpleSpanProcessor(OTelInMemoryExporter()))
    tracer = provider.get_tracer("l6-roundtrip")

    export_trace_to_otel(
        trace,
        tracer,
        config=OTelExporterConfig(capture_content=True),
    )
    assert processor.force_flush(timeout_millis=5_000) is True
    provider.shutdown()


def test_roundtrip_preserves_span_names_and_count() -> None:
    sink = RecordingSink()

    roundtrip(make_trace(), sink)

    assert len(sink.traces) == 1
    assert sorted(s.name for s in sink.traces[0].spans) == ["plan", "retrieve"]


def test_roundtrip_preserves_parent_links() -> None:
    sink = RecordingSink()

    roundtrip(make_trace(), sink)

    by_name = {s.name: s for s in sink.traces[0].spans}
    assert by_name["retrieve"].parent_span_id == by_name["plan"].span_id


def test_roundtrip_preserves_span_kinds() -> None:
    sink = RecordingSink()

    roundtrip(make_trace(), sink)

    by_name = {s.name: s for s in sink.traces[0].spans}
    assert by_name["plan"].kind == SpanKind.PLANNING
    assert by_name["retrieve"].kind == SpanKind.RETRIEVAL


def test_roundtrip_recovers_the_stashed_nirizan_trace_id() -> None:
    """The exported trace_id is derived; the stashed id must win when trusted."""
    trace = make_trace()
    sink = RecordingSink()

    roundtrip(trace, sink)

    assert sink.traces[0].trace_id == trace.trace_id


def test_roundtrip_recovers_the_stashed_session_id() -> None:
    trace = make_trace()
    sink = RecordingSink()

    roundtrip(trace, sink)

    assert sink.traces[0].session_id == trace.session_id


def test_roundtrip_preserves_payloads_when_capture_is_enabled() -> None:
    trace = make_trace()
    sink = RecordingSink()

    roundtrip(trace, sink)

    by_name = {s.name: s for s in sink.traces[0].spans}
    assert by_name["plan"].input_payload == "plan the thing"


def test_roundtrip_withholds_payloads_by_default() -> None:
    """The default config captures no content: payloads stay empty end to end."""
    trace = make_trace()
    sink = RecordingSink()
    provider = TracerProvider()
    processor = NiriZanSpanProcessor(sink)  # default config: capture_content=False
    provider.add_span_processor(processor)
    tracer = provider.get_tracer("l6-default")

    export_trace_to_otel(trace, tracer)
    assert processor.force_flush(timeout_millis=5_000) is True
    provider.shutdown()

    assert len(sink.traces) == 1
    by_name = {s.name: s for s in sink.traces[0].spans}
    assert by_name["plan"].input_payload is None


def test_roundtrip_preserves_scalar_attributes() -> None:
    trace = make_trace()
    sink = RecordingSink()

    roundtrip(trace, sink)

    by_name = {s.name: s for s in sink.traces[0].spans}
    assert by_name["retrieve"].attributes["retrieval.top_k"] == 3


def test_roundtrip_of_a_single_span_trace() -> None:
    trace_id = uuid4()
    trace = Trace(
        trace_id=trace_id,
        application_name="roundtrip-tests",
        created_at=START,
        spans=[
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                parent_span_id=None,
                kind=SpanKind.GENERATION,
                name="only",
                started_at=START,
                ended_at=START,
            )
        ],
    )
    sink = RecordingSink()

    roundtrip(trace, sink)

    assert len(sink.traces) == 1
    assert [s.name for s in sink.traces[0].spans] == ["only"]


def test_roundtrip_is_deterministic_across_repeats() -> None:
    """The same trace exported twice yields the same shape both times."""
    trace = make_trace()
    first, second = RecordingSink(), RecordingSink()

    roundtrip(trace, first)
    roundtrip(trace, second)

    assert [s.name for s in first.traces[0].spans] == [s.name for s in second.traces[0].spans]
    assert first.traces[0].trace_id == second.traces[0].trace_id
