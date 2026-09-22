# tests/instrumentation/otel/test_from_otel.py
"""Unit tests for OpenTelemetry span processor and trace assembly."""

import pytest

# ``opentelemetry`` is an optional dependency installed via the ``otel`` extra.
# Skip this entire module if it is absent, so a contributor working on other
# parts of NiriZan is never forced to install OpenTelemetry to get a green
# build. CI installs ``nirizan[otel]`` in the job that actually exercises
# the bridge.
pytest.importorskip("opentelemetry")
pytest.importorskip("opentelemetry.sdk")

from datetime import UTC, datetime  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402
from uuid import UUID  # noqa: E402

from opentelemetry.trace import TraceFlags  # noqa: E402

from nirizan.instrumentation.otel._id_mapping import otel_span_id_to_uuid  # noqa: E402
from nirizan.instrumentation.otel.from_otel import (  # noqa: E402
    _MAX_SPAN_NAME_LENGTH,
    NiriZanSpanProcessor,
    _convert_attributes,
    _extract_nirizan_span_id,
    _extract_payloads,
    _infer_span_kind,
    _ns_to_datetime,
)
from nirizan.instrumentation.otel.semconv import (  # noqa: E402
    GEN_AI_COMPLETION,
    GEN_AI_PROMPT,
    NIRIZAN_PLANNING_CONTEXT,
    NIRIZAN_RETRIEVAL_QUERY,
    NIRIZAN_SESSION_ID,
    NIRIZAN_SPAN_ID,
    NIRIZAN_SPAN_ID_SOURCE,
    NIRIZAN_SPAN_KIND,
    NIRIZAN_TOOL_ARGUMENTS,
    OTEL_SAMPLED,
    OTEL_STATUS_CODE,
    OTEL_STATUS_DESCRIPTION,
    OTEL_TRACE_STATE,
    SPAN_ID_SOURCE_DERIVED,
    SPAN_ID_SOURCE_ROUNDTRIP,
)
from nirizan.instrumentation.spans import SpanKind, Trace  # noqa: E402


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------


class MockSink:
    """Synchronous sink mock recording enqueued traces.

    Note: List appends are atomic under CPython's GIL and thread-safe for
    testing when read after consumer synchronization.
    """

    def __init__(self, raise_on_enqueue: bool = False) -> None:
        self.traces: list[Trace] = []
        self.raise_on_enqueue = raise_on_enqueue

    def enqueue_trace(self, trace: Trace) -> None:
        if self.raise_on_enqueue:
            raise RuntimeError("Sink processing error")
        self.traces.append(trace)


def create_mock_span(
    *,
    span_id: int = 0x1122334455667788,
    trace_id: int = 0x1234567890ABCDEF1234567890ABCDEF,
    parent_span_id: int | None = None,
    name: str = "test-span",
    start_time_ns: int = 1_600_000_000_000_000_000,
    end_time_ns: int = 1_600_000_005_000_000_000,
    attributes: dict[str, object] | None = None,
    service_name: str | None = "my-service",
    sampled: bool = True,
    trace_state: object | None = None,
    status_code_name: str | None = "OK",
    status_description: str | None = None,
    invalid_context: bool = False,
) -> MagicMock:
    """Utility factory for producing OTel ReadableSpan mocks."""
    span = MagicMock()
    span.name = name
    span.start_time = start_time_ns
    span.end_time = end_time_ns

    if invalid_context:
        span.get_span_context.return_value = None
    else:
        ctx = MagicMock()
        ctx.span_id = span_id
        ctx.trace_id = trace_id
        ctx.trace_flags = TraceFlags.SAMPLED if sampled else TraceFlags.DEFAULT
        ctx.trace_state = trace_state
        span.get_span_context.return_value = ctx

    if parent_span_id is not None:
        parent_ctx = MagicMock()
        parent_ctx.span_id = parent_span_id
        parent_ctx.trace_id = trace_id
        span.parent = parent_ctx
    else:
        span.parent = None

    span.attributes = attributes or {}

    if service_name:
        resource = MagicMock()
        resource.attributes = {"service.name": service_name}
        span.resource = resource
    else:
        span.resource = None

    if status_code_name:
        status = MagicMock()
        status_code = MagicMock()
        status_code.name = status_code_name
        status.status_code = status_code
        status.description = status_description
        span.status = status
    else:
        span.status = None

    return span


# ---------------------------------------------------------------------------
# Helper Unit Tests (Conversion & Parsing)
# ---------------------------------------------------------------------------


def test_ns_to_datetime_conversion() -> None:
    ns = 1_600_000_000_123_456_789
    dt = _ns_to_datetime(ns)
    expected = datetime(2020, 9, 13, 12, 26, 40, tzinfo=UTC)

    assert dt.tzinfo == UTC
    assert dt.year == expected.year
    assert dt.month == expected.month
    assert dt.day == expected.day
    assert dt.microsecond == 123_456

    now_dt = _ns_to_datetime(None)
    assert now_dt.tzinfo == UTC


def test_extract_nirizan_span_id_roundtrip_and_derived() -> None:
    ctx = MagicMock()
    ctx.span_id = 0x1234567890ABCDEF

    # Roundtrip stashed ID
    stashed_uuid_str = "12345678-1234-5678-1234-567812345678"
    span_stashed = MagicMock()
    span_stashed.attributes = {NIRIZAN_SPAN_ID: stashed_uuid_str}

    uid, source = _extract_nirizan_span_id(span_stashed, ctx)
    assert uid == UUID(stashed_uuid_str)
    assert source == SPAN_ID_SOURCE_ROUNDTRIP

    # Derived fallback
    span_plain = MagicMock()
    span_plain.attributes = {}
    uid_derived, source_derived = _extract_nirizan_span_id(span_plain, ctx)
    assert uid_derived == otel_span_id_to_uuid(ctx.span_id)
    assert source_derived == SPAN_ID_SOURCE_DERIVED


def test_infer_span_kind() -> None:
    assert _infer_span_kind({NIRIZAN_SPAN_KIND: "nirizan.span.TOOL_USE"}) == SpanKind.TOOL_USE
    assert _infer_span_kind({GEN_AI_PROMPT: "hello"}) == SpanKind.GENERATION
    assert _infer_span_kind({NIRIZAN_RETRIEVAL_QUERY: "q"}) == SpanKind.RETRIEVAL
    assert _infer_span_kind({NIRIZAN_TOOL_ARGUMENTS: "{}"}) == SpanKind.TOOL_USE
    assert _infer_span_kind({NIRIZAN_PLANNING_CONTEXT: "c"}) == SpanKind.PLANNING
    assert _infer_span_kind({}) == SpanKind.GENERATION


def test_extract_payloads() -> None:
    attrs = {
        GEN_AI_PROMPT: "prompt input",
        GEN_AI_COMPLETION: "completion output",
    }
    inp, out = _extract_payloads(SpanKind.GENERATION, attrs)
    assert inp == "prompt input"
    assert out == "completion output"


def test_convert_attributes_full_coverage() -> None:
    otel_attrs = {
        "str_key": "val",
        "int_key": 42,
        "list_key": ["a", "b"],
        "none_key": None,
    }
    res = _convert_attributes(
        otel_attrs,
        service_name="app",
        span_id_hex="1234567890abcdef",
        span_id_source=SPAN_ID_SOURCE_ROUNDTRIP,
        sampled=False,
        trace_state="congo=4",
        status_code="error",
        status_description="Internal Failure",
    )
    assert res["str_key"] == "val"
    assert res["int_key"] == 42
    assert "nirizan.seq.list_key" in res
    assert res["otel.service.name"] == "app"
    assert res["otel.span_id"] == "1234567890abcdef"
    assert res[NIRIZAN_SPAN_ID_SOURCE] == SPAN_ID_SOURCE_ROUNDTRIP
    assert res[OTEL_SAMPLED] is False
    assert res[OTEL_TRACE_STATE] == "congo=4"
    assert res[OTEL_STATUS_CODE] == "error"
    assert res[OTEL_STATUS_DESCRIPTION] == "Internal Failure"


# ---------------------------------------------------------------------------
# Processor Lifecycle & Functional Tests
# ---------------------------------------------------------------------------


def test_processor_invalid_init_parameters() -> None:
    sink = MockSink()
    with pytest.raises(ValueError, match="idle_timeout_seconds must be positive"):
        NiriZanSpanProcessor(sink, idle_timeout_seconds=0)

    with pytest.raises(ValueError, match="max_trace_age_seconds must be greater"):
        NiriZanSpanProcessor(sink, idle_timeout_seconds=5.0, max_trace_age_seconds=4.0)

    with pytest.raises(ValueError, match="max_buffered_traces must be at least 1"):
        NiriZanSpanProcessor(sink, max_buffered_traces=0)

    with pytest.raises(ValueError, match="orphan_policy must be 'emit' or 'drop'"):
        NiriZanSpanProcessor(sink, orphan_policy="invalid")  # type: ignore[arg-type]


def test_processor_trace_assembly_and_phase1_contract() -> None:
    sink = MockSink()
    processor = NiriZanSpanProcessor(sink, idle_timeout_seconds=2.0)

    try:
        session_id_val = "12345678-1234-5678-1234-567812345678"
        stashed_span_id = "87654321-4321-8765-4321-876543218765"

        parent_span = create_mock_span(
            span_id=0x1111,
            trace_id=0x9999,
            name="parent-span",
            attributes={
                NIRIZAN_SESSION_ID: session_id_val,
                NIRIZAN_SPAN_ID: stashed_span_id,
                GEN_AI_PROMPT: "User prompt",
            },
        )
        child_span = create_mock_span(
            span_id=0x2222,
            trace_id=0x9999,
            parent_span_id=0x1111,
            name="child-span",
            attributes={GEN_AI_COMPLETION: "AI completion"},
        )

        processor.on_end(parent_span)
        processor.on_end(child_span)

        flushed = processor.force_flush(timeout_millis=1000)
        assert flushed is True
        assert len(sink.traces) == 1

        trace = sink.traces[0]
        assert trace.application_name == "my-service"
        assert trace.session_id == UUID(session_id_val)
        assert len(trace.spans) == 2

        # Invariant Phase 1 contract check: All spans share trace_id
        assert all(s.trace_id == trace.trace_id for s in trace.spans)

        spans_by_name = {s.name: s for s in trace.spans}

        # Provenance & Roundtrip ID preservation checks
        parent = spans_by_name["parent-span"]
        child = spans_by_name["child-span"]

        assert parent.span_id == UUID(stashed_span_id)
        assert parent.attributes[NIRIZAN_SPAN_ID_SOURCE] == SPAN_ID_SOURCE_ROUNDTRIP

        assert child.span_id == otel_span_id_to_uuid(0x2222)
        assert child.attributes[NIRIZAN_SPAN_ID_SOURCE] == SPAN_ID_SOURCE_DERIVED
        assert child.parent_span_id == parent.span_id
    finally:
        processor.shutdown()


def test_span_name_truncation() -> None:
    sink = MockSink()
    processor = NiriZanSpanProcessor(sink)

    try:
        long_name = "a" * 300
        span = create_mock_span(name=long_name)

        processor.on_end(span)
        processor.force_flush()

        assert len(sink.traces) == 1
        assembled_span = sink.traces[0].spans[0]
        assert len(assembled_span.name) == _MAX_SPAN_NAME_LENGTH
        assert assembled_span.name == "a" * _MAX_SPAN_NAME_LENGTH
    finally:
        processor.shutdown()


def test_processor_orphan_policy_drop() -> None:
    sink = MockSink()
    processor = NiriZanSpanProcessor(sink, orphan_policy="drop")

    try:
        orphan_span = create_mock_span(
            span_id=0x3333,
            trace_id=0x8888,
            parent_span_id=0x9999,  # Parent span context missing
            name="orphan-child",
        )

        processor.on_end(orphan_span)
        processor.force_flush()

        assert len(sink.traces) == 0
    finally:
        processor.shutdown()


def test_processor_orphan_policy_emit() -> None:
    sink = MockSink()
    processor = NiriZanSpanProcessor(sink, orphan_policy="emit")

    try:
        orphan_span = create_mock_span(
            span_id=0x3333,
            trace_id=0x8888,
            parent_span_id=0x9999,
            name="orphan-child",
        )

        processor.on_end(orphan_span)
        processor.force_flush()

        assert len(sink.traces) == 1
        trace = sink.traces[0]
        assert len(trace.spans) == 1

        # Assert derived parent_span_id strictly equals deterministic conversion of parent OTel ID
        assert trace.spans[0].parent_span_id == otel_span_id_to_uuid(0x9999)
    finally:
        processor.shutdown()


def test_processor_buffer_cap_eviction_order() -> None:
    sink = MockSink()
    fake_time = 100.0

    def clock() -> float:
        return fake_time

    processor = NiriZanSpanProcessor(
        sink,
        max_buffered_traces=2,
        clock=clock,
    )

    try:
        span1 = create_mock_span(trace_id=0x1, span_id=0x10)
        fake_time += 1.0
        span2 = create_mock_span(trace_id=0x2, span_id=0x20)
        fake_time += 1.0
        span3 = create_mock_span(trace_id=0x3, span_id=0x30)

        processor.on_end(span1)
        processor.on_end(span2)
        processor.on_end(span3)

        processor.force_flush()

        # Eviction flushes the oldest trace first upon cap breach
        assert len(sink.traces) == 3
        flushed_trace_ids = [t.spans[0].attributes["otel.span_id"] for t in sink.traces]
        assert flushed_trace_ids[0] == format(0x10, "016x")
    finally:
        processor.shutdown()


def test_null_and_invalid_span_context_handling() -> None:
    sink = MockSink()
    processor = NiriZanSpanProcessor(sink)

    try:
        null_ctx_span = create_mock_span(invalid_context=True)
        zero_trace_span = create_mock_span(trace_id=0x0, span_id=0x10)
        zero_span_id_span = create_mock_span(trace_id=0x10, span_id=0x0)

        processor.on_end(null_ctx_span)
        processor.on_end(zero_trace_span)
        processor.on_end(zero_span_id_span)

        processor.force_flush()
        assert len(sink.traces) == 0
    finally:
        processor.shutdown()


def test_processor_late_arriving_span_dropped() -> None:
    sink = MockSink()
    processor = NiriZanSpanProcessor(sink)

    try:
        span1 = create_mock_span(trace_id=0xABCD, span_id=0x1)
        processor.on_end(span1)
        processor.force_flush()

        assert len(sink.traces) == 1

        late_span = create_mock_span(trace_id=0xABCD, span_id=0x2)
        processor.on_end(late_span)
        processor.force_flush()

        assert len(sink.traces) == 1
    finally:
        processor.shutdown()


def test_processor_sink_exception_resilience() -> None:
    sink = MockSink(raise_on_enqueue=True)
    processor = NiriZanSpanProcessor(sink)

    try:
        span = create_mock_span(trace_id=0x7777, span_id=0x1)
        processor.on_end(span)

        # Force flush should complete without throwing consumer thread exception
        flushed = processor.force_flush()
        assert flushed is True
    finally:
        processor.shutdown()


def test_processor_shutdown_cleans_up() -> None:
    sink = MockSink()
    processor = NiriZanSpanProcessor(sink)

    span = create_mock_span(trace_id=0x5555, span_id=0x1)
    processor.on_end(span)
    processor.shutdown()

    assert not processor._consumer.is_alive()
    assert len(sink.traces) == 1
