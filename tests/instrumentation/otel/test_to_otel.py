# tests/instrumentation/otel/test_to_otel.py
"""Unit tests for NiriZan -> OpenTelemetry span/trace exporter."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
from opentelemetry.trace.status import StatusCode

from nirizan.instrumentation.otel.semconv import (
    GEN_AI_COMPLETION,
    GEN_AI_PROMPT,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_USAGE_COMPLETION_TOKENS,
    GEN_AI_USAGE_PROMPT_TOKENS,
    NIRIZAN_PLANNING_CONTEXT,
    NIRIZAN_PLANNING_OUTPUT,
    NIRIZAN_RETRIEVAL_QUERY,
    NIRIZAN_RETRIEVAL_RESULTS,
    NIRIZAN_RETRIEVAL_TOP_K,
    NIRIZAN_SESSION_ID,
    NIRIZAN_SPAN_ID,
    NIRIZAN_SPAN_ID_SOURCE,
    NIRIZAN_SPAN_KIND,
    NIRIZAN_TOOL_ARGUMENTS,
    NIRIZAN_TOOL_NAME,
    NIRIZAN_TOOL_RESULT,
    NIRIZAN_TRACE_ID,
)
from nirizan.instrumentation.otel.to_otel import (
    NiriZanToOTelExporter,
    _format_payload_value,
    _to_nanoseconds,
    _topological_sort_spans,
    convert_span_to_otel_attributes,
    export_span_to_otel,
    export_trace_to_otel,
)


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


def create_dummy_span(
    *,
    span_id: str = "12345678-1234-5678-1234-567812345678",
    trace_id: str = "87654321-4321-8765-4321-876543218765",
    parent_span_id: str | None = None,
    name: str = "test_span",
    kind: str = "GENERATION",
    input_payload: object = None,
    output_payload: object = None,
    attributes: dict[str, object] | None = None,
    started_at: datetime | int | None = 1_600_000_000_000_000_000,
    ended_at: datetime | int | None = 1_600_000_005_000_000_000,
    status: str | None = None,
    status_message: str = "",
    events: list[object] | None = None,
    exception: BaseException | None = None,
) -> MagicMock:
    span = MagicMock()
    span.span_id = span_id
    span.trace_id = trace_id
    span.parent_span_id = parent_span_id
    span.name = name
    span.kind = kind
    span.input_payload = input_payload
    span.output_payload = output_payload
    span.attributes = attributes or {}
    span.started_at = started_at
    span.ended_at = ended_at
    span.status = status
    span.status_message = status_message
    span.events = events or []
    span.exception = exception
    return span


# ---------------------------------------------------------------------------
# Timestamp & Payload Helpers
# ---------------------------------------------------------------------------


def test_to_nanoseconds() -> None:
    assert _to_nanoseconds(None) is None[cite:12]
    assert _to_nanoseconds(1000) == 1000[cite:12]

    # Naive datetime gets converted to UTC aware timestamp[cite: 12]
    dt_naive = datetime(2020, 1, 1, 0, 0, 0)
    expected_ns = int(dt_naive.replace(tzinfo=UTC).timestamp() * 1_000_000_000)[cite:12]
    assert _to_nanoseconds(dt_naive) == expected_ns[cite:12]

    # Non-int / non-datetime fallback[cite: 12]
    assert _to_nanoseconds("invalid") is None[cite:12]  # type: ignore[arg-type]


def test_format_payload_value() -> None:
    assert _format_payload_value(None) is None[cite:12]
    assert _format_payload_value("hello") == "hello"[cite:12]

    # Dict payload <= max length[cite: 12]
    d_payload = {"key": "val"}
    assert _format_payload_value(d_payload) == '{"key": "val"}'[cite:12]

    # Large dict payload triggering preview truncation[cite: 12]
    large_payload = {"key": "x" * 2000}
    formatted = _format_payload_value(large_payload)[cite:12]
    assert "_nirizan_truncated" in formatted[cite:12]


# ---------------------------------------------------------------------------
# Attribute Conversion Tests
# ---------------------------------------------------------------------------


def test_convert_span_to_otel_attributes_generation_kind() -> None:
    span = create_dummy_span(
        kind="GENERATION",
        input_payload="hello prompt",
        output_payload="hi completion",
        attributes={
            "provider": "openai",
            "model_name": "gpt-4",
            "prompt_tokens": 10,
            "completion_tokens": 20,
        },
    )

    attrs = convert_span_to_otel_attributes(span, session_id="sess_123")[cite:12]

    assert attrs[NIRIZAN_SPAN_ID] == str(span.span_id)[cite:12]
    assert attrs[NIRIZAN_TRACE_ID] == str(span.trace_id)[cite:12]
    assert attrs[NIRIZAN_SPAN_KIND] == "generation"[cite:12]
    assert attrs[NIRIZAN_SESSION_ID] == "sess_123"[cite:12]
    assert attrs[GEN_AI_PROMPT] == "hello prompt"[cite:12]
    assert attrs[GEN_AI_COMPLETION] == "hi completion"[cite:12]
    assert attrs[GEN_AI_SYSTEM] == "openai"[cite:12]
    assert attrs[GEN_AI_REQUEST_MODEL] == "gpt-4"[cite:12]
    assert attrs[GEN_AI_USAGE_PROMPT_TOKENS] == 10[cite:12]
    assert attrs[GEN_AI_USAGE_COMPLETION_TOKENS] == 20[cite:12]


def test_convert_span_to_otel_attributes_retrieval_kind() -> None:
    span = create_dummy_span(
        kind="RETRIEVAL",
        input_payload="query text",
        output_payload=["doc1", "doc2"],
        attributes={"top_k": 5},
    )

    attrs = convert_span_to_otel_attributes(span)[cite:12]
    assert attrs[NIRIZAN_RETRIEVAL_QUERY] == "query text"[cite:12]
    assert attrs[NIRIZAN_RETRIEVAL_RESULTS] == '["doc1", "doc2"]'[cite:12]
    assert attrs[NIRIZAN_RETRIEVAL_TOP_K] == 5[cite:12]


def test_convert_span_to_otel_attributes_tool_use_kind() -> None:
    span = create_dummy_span(
        kind="TOOL_USE",
        input_payload={"arg": 1},
        output_payload={"res": 2},
        attributes={"tool_name": "search"},
    )

    attrs = convert_span_to_otel_attributes(span)[cite:12]
    assert attrs[NIRIZAN_TOOL_NAME] == "search"[cite:12]
    assert attrs[NIRIZAN_TOOL_ARGUMENTS] == '{"arg": 1}'[cite:12]
    assert attrs[NIRIZAN_TOOL_RESULT] == '{"res": 2}'[cite:12]


def test_convert_span_to_otel_attributes_planning_kind() -> None:
    span = create_dummy_span(
        kind="PLANNING",
        input_payload="plan context",
        output_payload="plan output",
    )

    attrs = convert_span_to_otel_attributes(span)[cite:12]
    assert attrs[NIRIZAN_PLANNING_CONTEXT] == "plan context"[cite:12]
    assert attrs[NIRIZAN_PLANNING_OUTPUT] == "plan output"[cite:12]


def test_convert_span_to_otel_attributes_sequence_encoding_error_fallback() -> None:
    span = create_dummy_span(
        kind="CUSTOM",
        attributes={"tags": ["a", "b"]},
    )

    with patch(
        "nirizan.instrumentation.otel.to_otel.encode_sequence_attribute_value",
        side_effect=ValueError("Encoding failed"),
    ):
        attrs = convert_span_to_otel_attributes(span)[cite:12]
        # Should gracefully drop the tag attribute without raising[cite: 12]
        assert "nirizan.seq.tags" not in attrs[cite:12]


# ---------------------------------------------------------------------------
# Topological Sorting
# ---------------------------------------------------------------------------


def test_topological_sort_spans() -> None:
    s_root = create_dummy_span(span_id="1", parent_span_id=None)
    s_child = create_dummy_span(span_id="2", parent_span_id="1")
    s_grandchild = create_dummy_span(span_id="3", parent_span_id="2")

    # Pass in reverse order
    unordered = [s_grandchild, s_root, s_child]
    ordered = _topological_sort_spans(unordered)[cite:12]

    ordered_ids = [s.span_id for s in ordered]
    assert ordered_ids == ["1", "2", "3"][cite:12]


# ---------------------------------------------------------------------------
# Export Functions & Class Tests
# ---------------------------------------------------------------------------


def test_export_span_to_otel_with_status_and_exception() -> None:
    mock_tracer = MagicMock()
    mock_otel_span = MagicMock()
    mock_tracer.start_span.return_value = mock_otel_span

    exc = RuntimeError("Test Error")
    span = create_dummy_span(
        status="ERROR",
        status_message="Failed execution",
        exception=exc,
    )

    res_span = export_span_to_otel(span, tracer=mock_tracer)[cite:12]

    assert res_span == mock_otel_span
    mock_otel_span.set_status.assert_called_once()[cite:12]
    mock_otel_span.record_exception.assert_called_once_with(exc)[cite:12]
    mock_otel_span.end.assert_called_once()[cite:12]


def test_export_trace_to_otel_links_parent_contexts() -> None:
    mock_tracer = MagicMock()

    span_root = create_dummy_span(span_id="10", parent_span_id=None)
    span_child = create_dummy_span(span_id="20", parent_span_id="10")

    # Mock SpanContexts returned by OTel spans
    ctx_root = SpanContext(
        trace_id=0x1234567890ABCDEF1234567890ABCDEF,
        span_id=0x10,
        is_remote=False,
        trace_flags=TraceFlags.SAMPLED,
    )
    ctx_child = SpanContext(
        trace_id=0x1234567890ABCDEF1234567890ABCDEF,
        span_id=0x20,
        is_remote=False,
        trace_flags=TraceFlags.SAMPLED,
    )

    otel_span_root = MagicMock()
    otel_span_root.get_span_context.return_value = ctx_root

    otel_span_child = MagicMock()
    otel_span_child.get_span_context.return_value = ctx_child

    mock_tracer.start_span.side_effect = [otel_span_root, otel_span_child]

    trace_mock = MagicMock()
    trace_mock.spans = [span_root, span_child]
    trace_mock.session_id = "sess_456"

    exported = export_trace_to_otel(trace_mock, tracer=mock_tracer)[cite:12]

    assert len(exported) == 2[cite:12]
    assert mock_tracer.start_span.call_count == 2[cite:12]


@pytest.mark.asyncio
async def test_nirizan_to_otel_exporter_class() -> None:
    mock_tracer = MagicMock()
    exporter = NiriZanToOTelExporter(tracer=mock_tracer)[cite:12]

    trace_mock = MagicMock()
    trace_mock.spans = [create_dummy_span()]

    await exporter.export(trace_mock)[cite:12]
    mock_tracer.start_span.assert_called_once()[cite:12]
