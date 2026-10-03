# tests/instrumentation/otel/test_to_otel.py
"""Unit tests for NiriZan -> OpenTelemetry span/trace exporter.

The tests exercise three layers:
  1. Pure conversion helpers (_to_nanoseconds, _format_payload_value,
     convert_span_to_otel_attributes, _topological_sort_spans).
  2. Export functions that interact with the OTel SDK's Tracer interface
     (export_span_to_otel, export_trace_to_otel).
  3. The NiriZanToOTelExporter class as the BaseExporter implementation.

Tests use MagicMock for the tracer and for spans, because the goal is to
verify the arguments the exporter hands to OTel, not to exercise OTel itself.
One test uses a real NiriZan Span object as a guard against attribute-name
drift between the exporter and the pydantic model it reads from.
"""

import pytest

pytest.importorskip("opentelemetry")
pytest.importorskip("opentelemetry.sdk")

from collections.abc import Mapping  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402
from uuid import uuid4  # noqa: E402

from opentelemetry.trace import (  # noqa: E402
    SpanContext,
    TraceFlags,
    get_current_span,
)
from opentelemetry.trace.status import StatusCode  # noqa: E402

from nirizan.instrumentation.otel.semconv import (  # noqa: E402
    GEN_AI_COMPLETION,
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROMPT,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_USAGE_COMPLETION_TOKENS,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    GEN_AI_USAGE_PROMPT_TOKENS,
    MAX_ATTR_VALUE_LENGTH,
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
    SEQ_ATTR_PREFIX,
    SPAN_ID_SOURCE_DERIVED,
    SPAN_ID_SOURCE_ROUNDTRIP,
)
from nirizan.instrumentation.otel.to_otel import (  # noqa: E402
    NiriZanToOTelExporter,
    _format_payload_value,
    _to_nanoseconds,
    _topological_sort_spans,
    convert_span_to_otel_attributes,
    export_span_to_otel,
    export_trace_to_otel,
)


# ---------------------------------------------------------------------------
# Test helpers
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
    attributes: Mapping[str, object] | None = None,
    started_at: datetime | int | None = 1_600_000_000_000_000_000,
    ended_at: datetime | int | None = 1_600_000_005_000_000_000,
    status: str | None = None,
    status_message: str = "",
    events: list[object] | None = None,
    exception: BaseException | None = None,
    session_id: str | None = None,
    span_id_source: str = SPAN_ID_SOURCE_ROUNDTRIP,
) -> MagicMock:
    """Produce a MagicMock configured to look like a NiriZan ``Span``.

    Every attribute the exporter reads via ``getattr`` is set explicitly.
    Without this, ``MagicMock`` would auto-create attributes on access,
    returning a new Mock instead of the intended default and hiding bugs.

    ``attributes`` is typed as ``Mapping`` rather than ``dict`` so that
    callers can pass any ``dict`` literal without tripping Pylance's dict
    invariance rule. The mapping is copied into a fresh ``dict`` on
    assignment.
    """
    span = MagicMock()
    span.span_id = span_id
    span.trace_id = trace_id
    span.parent_span_id = parent_span_id
    span.name = name
    span.kind = kind
    span.input_payload = input_payload
    span.output_payload = output_payload
    span.attributes = dict(attributes) if attributes is not None else {}
    span.started_at = started_at
    span.ended_at = ended_at
    span.status = status
    span.status_message = status_message
    span.events = events or []
    span.exception = exception
    span.session_id = session_id
    span.span_id_source = span_id_source
    return span


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------


def test_to_nanoseconds_returns_none_for_none() -> None:
    assert _to_nanoseconds(None) is None


def test_to_nanoseconds_passes_through_int() -> None:
    """An int is already interpreted as nanoseconds-since-epoch."""
    assert _to_nanoseconds(1000) == 1000


def test_to_nanoseconds_converts_naive_datetime_as_utc() -> None:
    """A naive datetime is assumed UTC, matching NiriZan's own Tracer behavior."""
    dt_naive = datetime(2020, 1, 1, 0, 0, 0)
    expected_ns = int(dt_naive.replace(tzinfo=UTC).timestamp() * 1_000_000_000)
    assert _to_nanoseconds(dt_naive) == expected_ns


def test_to_nanoseconds_converts_aware_datetime() -> None:
    dt_aware = datetime(2020, 1, 1, tzinfo=UTC)
    expected_ns = int(dt_aware.timestamp() * 1_000_000_000)
    assert _to_nanoseconds(dt_aware) == expected_ns


def test_to_nanoseconds_returns_none_for_unsupported_type() -> None:
    """Anything that is not ``datetime``, ``int``, or ``None`` yields ``None``.

    This is defensive: the exporter's callers pass values from ``Span`` fields
    that are already typed correctly, but a regression could pass a string.
    """
    assert _to_nanoseconds("invalid") is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Payload formatting
# ---------------------------------------------------------------------------


def test_format_payload_value_returns_none_for_none() -> None:
    assert _format_payload_value(None) is None


def test_format_payload_value_passes_through_short_string() -> None:
    assert _format_payload_value("hello") == "hello"


def test_format_payload_value_truncates_long_string() -> None:
    long_str = "a" * (MAX_ATTR_VALUE_LENGTH + 100)
    result = _format_payload_value(long_str)
    assert result is not None
    assert len(result) == MAX_ATTR_VALUE_LENGTH
    assert result.endswith("...[truncated]")


def test_format_payload_value_serializes_small_dict_as_json() -> None:
    result = _format_payload_value({"key": "val"})
    assert result == '{"key": "val"}'


def test_format_payload_value_serializes_small_list_as_json() -> None:
    assert _format_payload_value(["a", "b"]) == '["a", "b"]'


def test_format_payload_value_serializes_small_tuple_as_json_array() -> None:
    """Tuples serialize as JSON arrays, matching the OTel data model."""
    assert _format_payload_value(("a", "b")) == '["a", "b"]'


def test_format_payload_value_wraps_oversized_dict_in_envelope() -> None:
    """A dict too large to fit becomes a valid-JSON envelope, not a prefix.

    Regression: an earlier version returned a truncated JSON string, which
    is not parseable. The current behavior wraps in a dict that carries a
    marker and a preview, so ``json.loads`` always succeeds.
    """
    import json

    large = {"key": "x" * (MAX_ATTR_VALUE_LENGTH * 3)}
    result = _format_payload_value(large)
    assert result is not None

    parsed = json.loads(result)
    assert parsed["_nirizan_truncated"] is True
    assert parsed["type"] == "dict"
    assert "...[truncated]" in parsed["preview"]


def test_format_payload_value_coerces_other_types_via_str() -> None:
    assert _format_payload_value(42) == "42"
    assert _format_payload_value(3.14) == "3.14"


def test_format_payload_value_handles_unserializable_dict_key() -> None:
    """A dict whose key isn't JSON-serializable falls back to ``str``.

    ``json.dumps`` with ``default=str`` does not apply ``default`` to keys,
    so a tuple or object key raises ``TypeError`` and the outer handler
    catches it.
    """
    bad_payload = {(1, 2): "value"}
    result = _format_payload_value(bad_payload)
    assert result is not None
    assert "(1, 2)" in result


# ---------------------------------------------------------------------------
# Span-kind-specific attribute mapping
# ---------------------------------------------------------------------------


def test_convert_attributes_generation_kind() -> None:
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

    attrs = convert_span_to_otel_attributes(span, session_id="sess_123")

    assert attrs[NIRIZAN_SPAN_ID] == str(span.span_id)
    assert attrs[NIRIZAN_TRACE_ID] == str(span.trace_id)
    assert attrs[NIRIZAN_SPAN_ID_SOURCE] == SPAN_ID_SOURCE_ROUNDTRIP
    assert attrs[NIRIZAN_SPAN_KIND] == "generation"
    assert attrs[NIRIZAN_SESSION_ID] == "sess_123"
    assert attrs[GEN_AI_PROMPT] == "hello prompt"
    assert attrs[GEN_AI_COMPLETION] == "hi completion"
    assert attrs[GEN_AI_SYSTEM] == "openai"
    assert attrs[GEN_AI_REQUEST_MODEL] == "gpt-4"
    assert attrs[GEN_AI_RESPONSE_MODEL] == "gpt-4"
    assert attrs[GEN_AI_USAGE_PROMPT_TOKENS] == 10
    assert attrs[GEN_AI_USAGE_COMPLETION_TOKENS] == 20
    assert attrs[GEN_AI_USAGE_INPUT_TOKENS] == 10
    assert attrs[GEN_AI_USAGE_OUTPUT_TOKENS] == 20
    assert attrs[GEN_AI_OPERATION_NAME] == "chat"


def test_convert_attributes_retrieval_kind() -> None:
    span = create_dummy_span(
        kind="RETRIEVAL",
        input_payload="query text",
        output_payload=["doc1", "doc2"],
        attributes={"top_k": 5},
    )

    attrs = convert_span_to_otel_attributes(span)

    assert attrs[NIRIZAN_RETRIEVAL_QUERY] == "query text"
    assert attrs[NIRIZAN_RETRIEVAL_RESULTS] == '["doc1", "doc2"]'
    assert attrs[NIRIZAN_RETRIEVAL_TOP_K] == 5


def test_convert_attributes_tool_use_kind() -> None:
    span = create_dummy_span(
        kind="TOOL_USE",
        input_payload={"arg": 1},
        output_payload={"res": 2},
        attributes={"tool_name": "search"},
    )

    attrs = convert_span_to_otel_attributes(span)

    assert attrs[NIRIZAN_TOOL_NAME] == "search"
    assert attrs[NIRIZAN_TOOL_ARGUMENTS] == '{"arg": 1}'
    assert attrs[NIRIZAN_TOOL_RESULT] == '{"res": 2}'


def test_convert_attributes_planning_kind() -> None:
    span = create_dummy_span(
        kind="PLANNING",
        input_payload="plan context",
        output_payload="plan output",
    )

    attrs = convert_span_to_otel_attributes(span)

    assert attrs[NIRIZAN_PLANNING_CONTEXT] == "plan context"
    assert attrs[NIRIZAN_PLANNING_OUTPUT] == "plan output"


def test_convert_attributes_unknown_kind_uses_generic_payload_keys() -> None:
    """A span whose kind doesn't match any known value still exports its
    payloads, under ``nirizan.input`` / ``nirizan.output``.
    """
    span = create_dummy_span(
        kind="CUSTOM",
        input_payload="custom in",
        output_payload="custom out",
    )

    attrs = convert_span_to_otel_attributes(span)

    assert attrs["nirizan.input"] == "custom in"
    assert attrs["nirizan.output"] == "custom out"


def test_convert_attributes_kind_from_string_with_enum_prefix() -> None:
    """``str(SpanKind.GENERATION)`` yields ``"SpanKind.GENERATION"`` in some
    contexts. The exporter's split-on-dot logic must still map it to
    ``"generation"``.
    """
    span = create_dummy_span(kind="SpanKind.GENERATION")
    attrs = convert_span_to_otel_attributes(span)
    assert attrs[NIRIZAN_SPAN_KIND] == "generation"


def test_convert_attributes_uses_derived_span_id_source_when_set() -> None:
    """A span carrying ``span_id_source=derived`` (as from_otel.py would set)
    must round-trip that marker to the exported attribute.
    """
    span = create_dummy_span(span_id_source=SPAN_ID_SOURCE_DERIVED)
    attrs = convert_span_to_otel_attributes(span)
    assert attrs[NIRIZAN_SPAN_ID_SOURCE] == SPAN_ID_SOURCE_DERIVED


def test_convert_attributes_prefers_explicit_session_id_over_span() -> None:
    span = create_dummy_span(session_id="from-span")
    attrs = convert_span_to_otel_attributes(span, session_id="from-arg")
    assert attrs[NIRIZAN_SESSION_ID] == "from-arg"


def test_convert_attributes_falls_back_to_span_session_id() -> None:
    span = create_dummy_span(session_id="from-span")
    attrs = convert_span_to_otel_attributes(span)
    assert attrs[NIRIZAN_SESSION_ID] == "from-span"


def test_convert_attributes_omits_session_when_absent() -> None:
    span = create_dummy_span(session_id=None)
    attrs = convert_span_to_otel_attributes(span)
    assert NIRIZAN_SESSION_ID not in attrs


# ---------------------------------------------------------------------------
# Custom attribute encoding edge cases
# ---------------------------------------------------------------------------


def test_convert_attributes_sequence_encoding_error_drops_attribute() -> None:
    span = create_dummy_span(kind="CUSTOM", attributes={"tags": ["a", "b"]})

    with patch(
        "nirizan.instrumentation.otel.to_otel.encode_sequence_attribute_value",
        side_effect=ValueError("Encoding failed"),
    ):
        attrs = convert_span_to_otel_attributes(span)
        assert f"{SEQ_ATTR_PREFIX}tags" not in attrs


def test_convert_attributes_sequence_encodes_with_prefixed_key() -> None:
    span = create_dummy_span(kind="CUSTOM", attributes={"tags": ["a", "b"]})
    attrs = convert_span_to_otel_attributes(span)
    assert attrs[f"{SEQ_ATTR_PREFIX}tags"] == '["a", "b"]'


def test_convert_attributes_none_valued_custom_attribute_is_skipped() -> None:
    span = create_dummy_span(kind="CUSTOM", attributes={"maybe": None})
    attrs = convert_span_to_otel_attributes(span)
    assert "maybe" not in attrs


def test_convert_attributes_does_not_overwrite_already_set_keys() -> None:
    """A custom attribute with the same key as a mapped payload must not
    silently overwrite the mapped value.
    """
    span = create_dummy_span(
        kind="GENERATION",
        input_payload="prompt value",
        attributes={GEN_AI_PROMPT: "attempted override"},
    )
    attrs = convert_span_to_otel_attributes(span)
    assert attrs[GEN_AI_PROMPT] == "prompt value"


def test_convert_attributes_dict_valued_custom_attribute_uses_payload_formatter() -> None:
    span = create_dummy_span(kind="CUSTOM", attributes={"meta": {"k": "v"}})
    attrs = convert_span_to_otel_attributes(span)
    assert attrs["meta"] == '{"k": "v"}'


def test_convert_attributes_truncates_long_custom_string() -> None:
    long_val = "x" * (MAX_ATTR_VALUE_LENGTH + 50)
    span = create_dummy_span(kind="CUSTOM", attributes={"note": long_val})
    attrs = convert_span_to_otel_attributes(span)
    assert len(attrs["note"]) == MAX_ATTR_VALUE_LENGTH
    assert attrs["note"].endswith("...[truncated]")


def test_convert_attributes_coerces_arbitrary_types_via_str() -> None:
    class Custom:
        def __str__(self) -> str:
            return "custom-repr"

    span = create_dummy_span(kind="CUSTOM", attributes={"obj": Custom()})
    attrs = convert_span_to_otel_attributes(span)
    assert attrs["obj"] == "custom-repr"


def test_convert_attributes_is_pure_no_mutation_of_input_span() -> None:
    """The exporter must not modify the span's ``attributes`` dict in place."""
    original = {"tags": ["a", "b"]}
    span = create_dummy_span(kind="CUSTOM", attributes=original)

    convert_span_to_otel_attributes(span)

    assert original == {"tags": ["a", "b"]}


def test_convert_attributes_is_idempotent() -> None:
    span = create_dummy_span(kind="GENERATION", input_payload="in", output_payload="out")
    first = convert_span_to_otel_attributes(span)
    second = convert_span_to_otel_attributes(span)
    assert first == second


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------


def test_topological_sort_orders_parents_before_children() -> None:
    root = create_dummy_span(span_id="1", parent_span_id=None)
    child = create_dummy_span(span_id="2", parent_span_id="1")
    grandchild = create_dummy_span(span_id="3", parent_span_id="2")

    ordered = _topological_sort_spans([grandchild, root, child])
    assert [s.span_id for s in ordered] == ["1", "2", "3"]


def test_topological_sort_handles_empty_input() -> None:
    assert _topological_sort_spans([]) == []


def test_topological_sort_reclassifies_missing_parent_as_root() -> None:
    """A span whose parent is not in the input list is treated as a root."""
    orphan = create_dummy_span(span_id="orphan", parent_span_id="not-present")
    ordered = _topological_sort_spans([orphan])
    assert [s.span_id for s in ordered] == ["orphan"]


def test_topological_sort_includes_all_spans_with_cycle() -> None:
    """A cycle is a pathological input; the sort must not drop spans."""
    a = create_dummy_span(span_id="a", parent_span_id="b")
    b = create_dummy_span(span_id="b", parent_span_id="a")
    ordered = _topological_sort_spans([a, b])
    assert {s.span_id for s in ordered} == {"a", "b"}


def test_topological_sort_preserves_root_order_for_siblings() -> None:
    """Sibling subtrees preserve insertion order within their parent."""
    r = create_dummy_span(span_id="r", parent_span_id=None)
    c1 = create_dummy_span(span_id="c1", parent_span_id="r")
    c2 = create_dummy_span(span_id="c2", parent_span_id="r")
    ordered = _topological_sort_spans([r, c1, c2])
    assert [s.span_id for s in ordered] == ["r", "c1", "c2"]


# ---------------------------------------------------------------------------
# export_span_to_otel
# ---------------------------------------------------------------------------


def test_export_span_creates_otel_span_with_expected_kwargs() -> None:
    mock_tracer = MagicMock()
    mock_otel_span = MagicMock()
    mock_tracer.start_span.return_value = mock_otel_span

    span = create_dummy_span(
        name="my-span",
        kind="GENERATION",
        input_payload="prompt",
        output_payload="completion",
    )

    result = export_span_to_otel(span, tracer=mock_tracer)

    assert result is mock_otel_span
    kwargs = mock_tracer.start_span.call_args.kwargs
    assert kwargs["name"] == "my-span"
    assert kwargs["attributes"][GEN_AI_PROMPT] == "prompt"
    assert kwargs["attributes"][GEN_AI_COMPLETION] == "completion"
    assert isinstance(kwargs["start_time"], int)


def test_export_span_sets_error_status_with_description() -> None:
    mock_tracer = MagicMock()
    mock_otel_span = MagicMock()
    mock_tracer.start_span.return_value = mock_otel_span

    span = create_dummy_span(status="ERROR", status_message="Failed execution")
    export_span_to_otel(span, tracer=mock_tracer)

    mock_otel_span.set_status.assert_called_once()
    status_arg = mock_otel_span.set_status.call_args[0][0]
    assert status_arg.status_code == StatusCode.ERROR
    assert status_arg.description == "Failed execution"


def test_export_span_sets_ok_status_without_description() -> None:
    mock_tracer = MagicMock()
    mock_otel_span = MagicMock()
    mock_tracer.start_span.return_value = mock_otel_span

    span = create_dummy_span(status="OK")
    export_span_to_otel(span, tracer=mock_tracer)

    mock_otel_span.set_status.assert_called_once()
    status_arg = mock_otel_span.set_status.call_args[0][0]
    assert status_arg.status_code == StatusCode.OK


def test_export_span_does_not_set_status_when_unset() -> None:
    mock_tracer = MagicMock()
    mock_otel_span = MagicMock()
    mock_tracer.start_span.return_value = mock_otel_span

    span = create_dummy_span(status=None)
    export_span_to_otel(span, tracer=mock_tracer)

    mock_otel_span.set_status.assert_not_called()


def test_export_span_records_base_exception() -> None:
    mock_tracer = MagicMock()
    mock_otel_span = MagicMock()
    mock_tracer.start_span.return_value = mock_otel_span

    exc = RuntimeError("boom")
    span = create_dummy_span(exception=exc)

    export_span_to_otel(span, tracer=mock_tracer)

    mock_otel_span.record_exception.assert_called_once_with(exc)


def test_export_span_records_non_exception_as_event() -> None:
    """A non-BaseException in the ``exception`` field is added as an event."""
    mock_tracer = MagicMock()
    mock_otel_span = MagicMock()
    mock_tracer.start_span.return_value = mock_otel_span

    span = create_dummy_span(exception="not an exception")  # type: ignore[arg-type]
    export_span_to_otel(span, tracer=mock_tracer)

    mock_otel_span.record_exception.assert_not_called()
    mock_otel_span.add_event.assert_called_once()
    event_call = mock_otel_span.add_event.call_args
    # ``to_otel.py`` calls ``add_event`` positionally for the exception branch:
    #     otel_span.add_event("exception", attributes={...})
    # whereas the event-loop branch calls it with keyword ``name=...``.
    # This test pins the exception branch's calling convention.
    assert event_call.args[0] == "exception"
    assert event_call.kwargs["attributes"]["exception.message"] == "not an exception"


def test_export_span_emits_events() -> None:
    mock_tracer = MagicMock()
    mock_otel_span = MagicMock()
    mock_tracer.start_span.return_value = mock_otel_span

    event = MagicMock()
    event.name = "cache_miss"
    event.timestamp = 1_600_000_000_000_000_000
    event.attributes = {"key": "value"}

    span = create_dummy_span(events=[event])
    export_span_to_otel(span, tracer=mock_tracer)

    mock_otel_span.add_event.assert_called_once()
    kwargs = mock_otel_span.add_event.call_args.kwargs
    assert kwargs["name"] == "cache_miss"
    assert kwargs["attributes"] == {"key": "value"}
    assert kwargs["timestamp"] == 1_600_000_000_000_000_000


def test_export_span_warns_when_parent_context_missing(caplog: pytest.LogCaptureFixture) -> None:
    """A span with a declared parent but no parent_context is exported as a
    root, with a warning that names both the span and the missing parent.
    """
    mock_tracer = MagicMock()
    mock_otel_span = MagicMock()
    mock_tracer.start_span.return_value = mock_otel_span

    span = create_dummy_span(span_id="child", parent_span_id="missing-parent")

    with caplog.at_level("WARNING", logger="nirizan.instrumentation.otel.to_otel"):
        export_span_to_otel(span, tracer=mock_tracer)

    assert any("missing-parent" in record.message for record in caplog.records)
    # Still called start_span (no crash), with no parent context.
    assert mock_tracer.start_span.call_args.kwargs["context"] is None


def test_export_span_calls_end_with_end_time() -> None:
    mock_tracer = MagicMock()
    mock_otel_span = MagicMock()
    mock_tracer.start_span.return_value = mock_otel_span

    span = create_dummy_span(ended_at=1_600_000_005_000_000_000)
    export_span_to_otel(span, tracer=mock_tracer)

    mock_otel_span.end.assert_called_once_with(end_time=1_600_000_005_000_000_000)


def test_export_span_with_real_nirizan_span() -> None:
    """Integration guard: use a real NiriZan ``Span``, not a MagicMock.

    This catches attribute-name drift between the exporter's ``getattr``
    calls and the pydantic model's actual field names. If a field is renamed
    in ``spans.py`` without updating the exporter, this test fails.
    """
    from nirizan.instrumentation.spans import Span as RealSpan
    from nirizan.instrumentation.spans import SpanKind as RealSpanKind

    mock_tracer = MagicMock()
    mock_otel_span = MagicMock()
    mock_tracer.start_span.return_value = mock_otel_span

    span = RealSpan(
        span_id=uuid4(),
        trace_id=uuid4(),
        parent_span_id=None,
        kind=RealSpanKind.GENERATION,
        name="real_span",
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        ended_at=datetime(2024, 1, 1, 0, 0, 1, tzinfo=UTC),
        attributes={},
        input_payload="prompt",
        output_payload="completion",
    )

    result = export_span_to_otel(span, tracer=mock_tracer)

    assert result is mock_otel_span
    kwargs = mock_tracer.start_span.call_args.kwargs
    assert kwargs["name"] == "real_span"
    assert kwargs["attributes"][NIRIZAN_SPAN_KIND] == "generation"
    assert kwargs["attributes"][GEN_AI_PROMPT] == "prompt"
    assert kwargs["attributes"][GEN_AI_COMPLETION] == "completion"
    assert kwargs["attributes"][NIRIZAN_SPAN_ID_SOURCE] == SPAN_ID_SOURCE_ROUNDTRIP
    assert isinstance(kwargs["start_time"], int)


# ---------------------------------------------------------------------------
# export_trace_to_otel
# ---------------------------------------------------------------------------


def test_export_trace_links_child_to_real_parent_context() -> None:
    """The exported child span's ``context`` argument must resolve to the
    actual parent span context that the SDK returned for the root, not a
    fabricated ``SpanContext``.
    """
    mock_tracer = MagicMock()

    root = create_dummy_span(span_id="10", parent_span_id=None)
    child = create_dummy_span(span_id="20", parent_span_id="10")

    ctx_root = SpanContext(
        trace_id=0x1234567890ABCDEF1234567890ABCDEF,
        span_id=0x10,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    ctx_child = SpanContext(
        trace_id=0x1234567890ABCDEF1234567890ABCDEF,
        span_id=0x20,
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )

    otel_span_root = MagicMock()
    otel_span_root.get_span_context.return_value = ctx_root
    otel_span_child = MagicMock()
    otel_span_child.get_span_context.return_value = ctx_child
    mock_tracer.start_span.side_effect = [otel_span_root, otel_span_child]

    trace_mock = MagicMock()
    trace_mock.spans = [root, child]
    trace_mock.session_id = None

    exported = export_trace_to_otel(trace_mock, tracer=mock_tracer)

    assert len(exported) == 2
    assert mock_tracer.start_span.call_count == 2

    # The child call must carry a context whose current span is the root.
    child_kwargs = mock_tracer.start_span.call_args_list[1].kwargs
    child_context = child_kwargs["context"]
    assert child_context is not None
    parent_from_ctx = get_current_span(child_context)
    assert parent_from_ctx.get_span_context().span_id == ctx_root.span_id


def test_export_trace_accepts_bare_sequence_of_spans() -> None:
    """``export_trace_to_otel`` accepts either a ``Trace`` or a raw sequence."""
    mock_tracer = MagicMock()
    mock_tracer.start_span.return_value = MagicMock()

    spans = [create_dummy_span(span_id="a"), create_dummy_span(span_id="b")]

    exported = export_trace_to_otel(spans, tracer=mock_tracer)

    assert len(exported) == 2
    assert mock_tracer.start_span.call_count == 2


def test_export_trace_handles_empty_sequence() -> None:
    mock_tracer = MagicMock()
    exported = export_trace_to_otel([], tracer=mock_tracer)
    assert exported == []
    mock_tracer.start_span.assert_not_called()


def test_export_trace_orders_spans_topologically_before_export() -> None:
    """Even when input spans are unordered, start_span is called parents-first."""
    mock_tracer = MagicMock()
    mock_tracer.start_span.return_value = MagicMock()

    root = create_dummy_span(span_id="r", parent_span_id=None)
    child = create_dummy_span(span_id="c", parent_span_id="r")

    export_trace_to_otel([child, root], tracer=mock_tracer)

    # Distinguish by span_id in the attributes.
    first_attrs = mock_tracer.start_span.call_args_list[0].kwargs["attributes"]
    second_attrs = mock_tracer.start_span.call_args_list[1].kwargs["attributes"]
    assert first_attrs[NIRIZAN_SPAN_ID] == "r"
    assert second_attrs[NIRIZAN_SPAN_ID] == "c"


def test_export_trace_propagates_session_id_to_each_span() -> None:
    mock_tracer = MagicMock()
    mock_tracer.start_span.return_value = MagicMock()

    trace_mock = MagicMock()
    trace_mock.spans = [create_dummy_span()]
    trace_mock.session_id = "sess_999"

    export_trace_to_otel(trace_mock, tracer=mock_tracer)

    attrs = mock_tracer.start_span.call_args.kwargs["attributes"]
    assert attrs[NIRIZAN_SESSION_ID] == "sess_999"


# ---------------------------------------------------------------------------
# NiriZanToOTelExporter class
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exporter_export_is_awaitable_and_exports_trace() -> None:
    mock_tracer = MagicMock()
    mock_tracer.start_span.return_value = MagicMock()

    exporter = NiriZanToOTelExporter(tracer=mock_tracer)

    trace_mock = MagicMock()
    trace_mock.spans = [create_dummy_span()]
    trace_mock.session_id = None

    await exporter.export(trace_mock)

    mock_tracer.start_span.assert_called_once()


def test_exporter_export_span_returns_otel_span() -> None:
    mock_tracer = MagicMock()
    mock_otel_span = MagicMock()
    mock_tracer.start_span.return_value = mock_otel_span

    exporter = NiriZanToOTelExporter(tracer=mock_tracer)

    result = exporter.export_span(create_dummy_span())

    assert result is mock_otel_span


def test_exporter_export_trace_returns_list_of_otel_spans() -> None:
    mock_tracer = MagicMock()
    mock_tracer.start_span.return_value = MagicMock()

    exporter = NiriZanToOTelExporter(tracer=mock_tracer)
    spans = [create_dummy_span(span_id="x"), create_dummy_span(span_id="y")]

    result = exporter.export_trace(spans)

    assert len(result) == 2


def test_exporter_uses_shared_tracer_across_calls() -> None:
    """The exporter captures one tracer at construction and reuses it."""
    mock_tracer = MagicMock()
    mock_tracer.start_span.return_value = MagicMock()

    exporter = NiriZanToOTelExporter(tracer=mock_tracer)
    exporter.export_span(create_dummy_span(span_id="a"))
    exporter.export_span(create_dummy_span(span_id="b"))

    assert mock_tracer.start_span.call_count == 2


def test_exporter_satisfies_base_exporter_contract() -> None:
    """Regression: the class must remain assignable to ``BaseExporter``."""
    from nirizan.instrumentation.exporters import BaseExporter

    exporter = NiriZanToOTelExporter(tracer=MagicMock())
    assert isinstance(exporter, BaseExporter)
