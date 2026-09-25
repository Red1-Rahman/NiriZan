# src/nirizan/instrumentation/otel/to_otel.py
"""OpenTelemetry trace exporter for NiriZan.

Converts NiriZan Span and Trace data structures into OpenTelemetry Spans,
mapping span kinds, GenAI attributes, sequence attributes, and span context IDs.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    Tracer,
    set_span_in_context,
)
from opentelemetry.trace.status import Status, StatusCode

import nirizan
from nirizan._logging import get_logger
from nirizan.instrumentation.exporters import BaseExporter
from nirizan.instrumentation.otel.semconv import (
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
    SPAN_ID_SOURCE_ROUNDTRIP,
    encode_sequence_attribute_value,
    encode_sequence_key,
    truncate_attribute_value,
)

if TYPE_CHECKING:
    from nirizan.instrumentation.spans import Span, Trace

logger = get_logger(__name__)

__all__ = [
    "NiriZanToOTelExporter",
    "convert_span_to_otel_attributes",
    "export_span_to_otel",
    "export_trace_to_otel",
]

_EPOCH: datetime = datetime(1970, 1, 1, tzinfo=UTC)


def _get_default_tracer() -> Tracer:
    """Retrieve default OpenTelemetry Tracer with NiriZan instrumentation scope."""
    version = getattr(nirizan, "__version__", None) or "0.5.0"
    return trace.get_tracer("nirizan", version)


def _to_nanoseconds(ts: datetime | int | None) -> int | None:
    """Convert datetime or nanoseconds-since-epoch integer to nanoseconds.

    Uses exact integer arithmetic on timedelta components rather than
    ``ts.timestamp() * 1_000_000_000`` to eliminate floating-point precision loss
    and prevent microsecond rounding shifts across round-trip conversions.
    """
    if ts is None:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        delta = ts - _EPOCH
        return (delta.days * 86_400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1_000
    if isinstance(ts, int):
        return ts
    return None


def _format_payload_value(payload: Any) -> str | None:
    """Format payload objects into truncated attribute strings while preserving JSON validity."""
    if payload is None:
        return None
    if isinstance(payload, str):
        return truncate_attribute_value(payload)
    if isinstance(payload, (dict, list, tuple)):
        try:
            dump_str = json.dumps(payload, default=str)
            if len(dump_str) <= MAX_ATTR_VALUE_LENGTH:
                return dump_str
            preview = str(payload)
            truncated_dict = {
                "_nirizan_truncated": True,
                "type": type(payload).__name__,
                "preview": truncate_attribute_value(preview),
            }
            return json.dumps(truncated_dict, default=str)
        except Exception:
            return truncate_attribute_value(str(payload))
    return truncate_attribute_value(str(payload))


def convert_span_to_otel_attributes(
    span: Span | Any, session_id: str | None = None
) -> dict[str, Any]:
    """Extract and map NiriZan Span properties into OpenTelemetry span attributes."""
    attributes: dict[str, Any] = {}

    # Core Identifiers
    span_id_str = str(getattr(span, "span_id", ""))
    trace_id_str = str(getattr(span, "trace_id", ""))
    if span_id_str:
        attributes[NIRIZAN_SPAN_ID] = span_id_str
    if trace_id_str:
        attributes[NIRIZAN_TRACE_ID] = trace_id_str

    span_attrs = getattr(span, "attributes", None) or {}
    attributes[NIRIZAN_SPAN_ID_SOURCE] = (
        span_attrs.get(NIRIZAN_SPAN_ID_SOURCE)
        or getattr(span, "span_id_source", None)
        or SPAN_ID_SOURCE_ROUNDTRIP
    )

    # Span Kind
    raw_kind = getattr(span, "kind", "SPAN")
    kind_val = str(getattr(raw_kind, "value", raw_kind))
    kind_upper = kind_val.split(".")[-1].upper()
    attributes[NIRIZAN_SPAN_KIND] = kind_upper.lower()

    # Session ID Attribute
    effective_session = session_id or getattr(span, "session_id", None)
    if effective_session:
        attributes[NIRIZAN_SESSION_ID] = str(effective_session)

    # Custom Attributes & Domain Sourcing
    custom_attrs = getattr(span, "attributes", {}) or {}

    input_payload = getattr(span, "input_payload", None)
    output_payload = getattr(span, "output_payload", None)

    if kind_upper in ("GENERATION", "LLM", "CHAT"):
        if input_payload is not None:
            attributes[GEN_AI_PROMPT] = _format_payload_value(input_payload)
        if output_payload is not None:
            attributes[GEN_AI_COMPLETION] = _format_payload_value(output_payload)

        provider = custom_attrs.get("provider") or custom_attrs.get(GEN_AI_SYSTEM)
        if provider:
            attributes[GEN_AI_SYSTEM] = str(provider)

        model_name = (
            custom_attrs.get("model_name")
            or custom_attrs.get("model")
            or custom_attrs.get(GEN_AI_REQUEST_MODEL)
        )
        if model_name:
            attributes[GEN_AI_REQUEST_MODEL] = str(model_name)
            attributes[GEN_AI_RESPONSE_MODEL] = str(model_name)

        prompt_tokens = custom_attrs.get("prompt_tokens") or custom_attrs.get(
            GEN_AI_USAGE_PROMPT_TOKENS
        )
        if isinstance(prompt_tokens, int):
            attributes[GEN_AI_USAGE_INPUT_TOKENS] = prompt_tokens
            attributes[GEN_AI_USAGE_PROMPT_TOKENS] = prompt_tokens

        completion_tokens = custom_attrs.get("completion_tokens") or custom_attrs.get(
            GEN_AI_USAGE_COMPLETION_TOKENS
        )
        if isinstance(completion_tokens, int):
            attributes[GEN_AI_USAGE_OUTPUT_TOKENS] = completion_tokens
            attributes[GEN_AI_USAGE_COMPLETION_TOKENS] = completion_tokens

        attributes[GEN_AI_OPERATION_NAME] = "chat"

    elif kind_upper == "RETRIEVAL":
        if input_payload is not None:
            attributes[NIRIZAN_RETRIEVAL_QUERY] = _format_payload_value(input_payload)
        if output_payload is not None:
            attributes[NIRIZAN_RETRIEVAL_RESULTS] = _format_payload_value(output_payload)

        top_k = custom_attrs.get("top_k") or custom_attrs.get(NIRIZAN_RETRIEVAL_TOP_K)
        if isinstance(top_k, int):
            attributes[NIRIZAN_RETRIEVAL_TOP_K] = top_k

    elif kind_upper in ("TOOL_USE", "TOOL"):
        tool_name = (
            custom_attrs.get("tool_name")
            or custom_attrs.get("name")
            or custom_attrs.get(NIRIZAN_TOOL_NAME)
        )
        if tool_name:
            attributes[NIRIZAN_TOOL_NAME] = str(tool_name)
        if input_payload is not None:
            attributes[NIRIZAN_TOOL_ARGUMENTS] = _format_payload_value(input_payload)
        if output_payload is not None:
            attributes[NIRIZAN_TOOL_RESULT] = _format_payload_value(output_payload)

    elif kind_upper == "PLANNING":
        if input_payload is not None:
            attributes[NIRIZAN_PLANNING_CONTEXT] = _format_payload_value(input_payload)
        if output_payload is not None:
            attributes[NIRIZAN_PLANNING_OUTPUT] = _format_payload_value(output_payload)

    else:
        if input_payload is not None:
            attributes["nirizan.input"] = _format_payload_value(input_payload)
        if output_payload is not None:
            attributes["nirizan.output"] = _format_payload_value(output_payload)

    # Encode Remaining Custom Attributes
    if isinstance(custom_attrs, dict):
        for k, v in custom_attrs.items():
            if v is None or k in attributes:
                continue
            if isinstance(v, (int, float, bool)):
                attributes[k] = v
            elif isinstance(v, str):
                attributes[k] = truncate_attribute_value(v)
            elif isinstance(v, (list, tuple)):
                encoded_key = encode_sequence_key(k)
                try:
                    attributes[encoded_key] = encode_sequence_attribute_value(v)
                except ValueError as err:
                    logger.warning(
                        "Dropping attribute '%s' due to sequence encoding truncation error: %s",
                        k,
                        err,
                    )
            elif isinstance(v, dict):
                attributes[k] = _format_payload_value(v)
            else:
                attributes[k] = truncate_attribute_value(str(v))

    return attributes


def export_span_to_otel(
    span: Span | Any,
    tracer: Tracer | None = None,
    parent_context: SpanContext | None = None,
    session_id: str | None = None,
) -> trace.Span:
    """Convert and export a single NiriZan Span into an OpenTelemetry Span."""
    if tracer is None:
        tracer = _get_default_tracer()

    span_name = str(getattr(span, "name", "nirizan_span"))
    attributes = convert_span_to_otel_attributes(span, session_id=session_id)
    start_ns = _to_nanoseconds(getattr(span, "started_at", None))
    end_ns = _to_nanoseconds(getattr(span, "ended_at", None))

    # Parent Context Linkage
    context = None
    if parent_context is not None:
        context = set_span_in_context(NonRecordingSpan(parent_context))
    else:
        raw_parent_id = getattr(span, "parent_span_id", None)
        if raw_parent_id is not None:
            logger.warning(
                "Parent span '%s' for span '%s' not found in exported parent context map. "
                "Exporting span as root span.",
                raw_parent_id,
                getattr(span, "span_id", "unknown"),
            )

    otel_span = tracer.start_span(
        name=span_name,
        context=context,
        attributes=attributes,
        start_time=start_ns,
    )

    # Status Handling
    raw_status = getattr(span, "status", None)
    if raw_status is not None:
        status_msg = getattr(span, "status_message", "")
        status_str = str(getattr(raw_status, "value", raw_status)).upper()
        if status_str in ("OK", "SUCCESS"):
            otel_span.set_status(Status(StatusCode.OK))
        elif status_str in ("ERROR", "FAIL", "FAILURE"):
            otel_span.set_status(Status(StatusCode.ERROR, description=str(status_msg)))

    # Events
    raw_events = getattr(span, "events", None)
    if raw_events:
        for evt in raw_events:
            evt_name = str(getattr(evt, "name", "event"))
            evt_ts = _to_nanoseconds(getattr(evt, "timestamp", None))
            evt_attrs = getattr(evt, "attributes", None)
            otel_span.add_event(name=evt_name, attributes=evt_attrs, timestamp=evt_ts)

    # Exceptions
    exc = getattr(span, "exception", None)
    if exc is not None:
        if isinstance(exc, BaseException):
            otel_span.record_exception(exc)
        else:
            otel_span.add_event("exception", attributes={"exception.message": str(exc)})

    otel_span.end(end_time=end_ns)
    return otel_span


def _topological_sort_spans(spans: Sequence[Span | Any]) -> list[Span | Any]:
    """Reorder spans so parents always precede their children during export."""
    by_id: dict[str, Span | Any] = {}
    children_map: dict[str | None, list[Span | Any]] = {}

    for s in spans:
        sid = str(getattr(s, "span_id", ""))
        if sid:
            by_id[sid] = s

    for s in spans:
        parent_id = getattr(s, "parent_span_id", None)
        pid_str = str(parent_id) if parent_id is not None else None

        if pid_str and pid_str not in by_id:
            pid_str = None

        children_map.setdefault(pid_str, []).append(s)

    sorted_spans: list[Span | Any] = []
    queue: deque[Span | Any] = deque(children_map.get(None, []))
    visited_ids: set[str] = set()

    while queue:
        current = queue.popleft()
        sorted_spans.append(current)
        cid = str(getattr(current, "span_id", ""))
        if cid:
            visited_ids.add(cid)
            if cid in children_map:
                queue.extend(children_map[cid])

    for s in spans:
        sid = str(getattr(s, "span_id", ""))
        if sid and sid not in visited_ids:
            sorted_spans.append(s)

    return sorted_spans


def export_trace_to_otel(
    trace_obj: Trace | Sequence[Span] | Any,
    tracer: Tracer | None = None,
) -> list[trace.Span]:
    """Convert and export a trace sequence maintaining topological parent-child order."""
    if tracer is None:
        tracer = _get_default_tracer()

    spans_attr = getattr(trace_obj, "spans", None)
    if spans_attr is not None:
        raw_spans: Sequence[Span | Any] = spans_attr
    elif isinstance(trace_obj, Sequence):
        raw_spans = trace_obj
    else:
        raw_spans = []

    spans = _topological_sort_spans(raw_spans)
    session_id = getattr(trace_obj, "session_id", None)
    exported_spans: list[trace.Span] = []
    span_context_map: dict[str, SpanContext] = {}

    for span in spans:
        span_id = str(getattr(span, "span_id", ""))
        parent_span_id = getattr(span, "parent_span_id", None)

        parent_ctx = None
        if parent_span_id and str(parent_span_id) in span_context_map:
            parent_ctx = span_context_map[str(parent_span_id)]

        exported = export_span_to_otel(
            span,
            tracer=tracer,
            parent_context=parent_ctx,
            session_id=session_id,
        )

        if span_id:
            span_context_map[span_id] = exported.get_span_context()

        exported_spans.append(exported)

    return exported_spans


class NiriZanToOTelExporter(BaseExporter):
    """Trace exporter bridging NiriZan traces and spans into OpenTelemetry."""

    def __init__(self, tracer: Tracer | None = None) -> None:
        self._tracer = tracer or _get_default_tracer()

    async def export(self, trace: Trace) -> None:
        """Export a NiriZan Trace to OpenTelemetry satisfying BaseExporter interface."""
        export_trace_to_otel(trace, tracer=self._tracer)

    def export_span(self, span: Span | Any) -> trace.Span:
        """Export a single NiriZan span to OpenTelemetry."""
        return export_span_to_otel(span, tracer=self._tracer)

    def export_trace(self, trace_obj: Trace | Sequence[Span] | Any) -> list[trace.Span]:
        """Export a full NiriZan trace structure to OpenTelemetry."""
        return export_trace_to_otel(trace_obj, tracer=self._tracer)
