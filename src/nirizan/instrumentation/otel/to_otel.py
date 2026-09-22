# src\nirizan\instrumentation\otel\to_otel.py
"""OpenTelemetry trace exporter for NiriZan.

Converts NiriZan Span and Trace data structures into OpenTelemetry Spans,
mapping span kinds, GenAI attributes, sequence attributes, and span context IDs.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
import json
import logging
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    TraceFlags,
    Tracer,
    set_span_in_context,
)
from opentelemetry.trace.status import Status, StatusCode

from nirizan.instrumentation.otel._id_mapping import (
    uuid_to_otel_span_id,
    uuid_to_otel_trace_id,
)
from nirizan.instrumentation.otel.semconv import (
    GEN_AI_COMPLETION,
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROMPT,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_MODEL,
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
    SPAN_ID_SOURCE_ROUNDTRIP,
    encode_sequence_attribute_value,
    encode_sequence_key,
    truncate_attribute_value,
)

if TYPE_CHECKING:
    from nirizan.instrumentation.spans import Trace

logger = logging.getLogger(__name__)

__all__ = [
    "NiriZanOTelExporter",
    "convert_span_to_otel_attributes",
    "export_span_to_otel",
    "export_trace_to_otel",
]


def _to_nanoseconds(ts: Any) -> int | None:
    """Convert datetime, float seconds, or integer timestamps to nanoseconds."""
    if ts is None:
        return None
    if isinstance(ts, int):
        if ts > 1_000_000_000_000_000_000:
            return ts
        if ts > 1_000_000_000_000_000:
            return ts * 1_000
        if ts > 1_000_000_000_000:
            return ts * 1_000_000
        return ts * 1_000_000_000
    if isinstance(ts, float):
        return int(ts * 1_000_000_000)
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return int(ts.timestamp() * 1_000_000_000)
    try:
        val = float(ts)
        return int(val * 1_000_000_000)
    except (ValueError, TypeError):
        return None


def _format_payload_value(payload: Any) -> str | None:
    """Format payload objects into truncated attribute strings."""
    if payload is None:
        return None
    if isinstance(payload, str):
        return truncate_attribute_value(payload)
    if isinstance(payload, (dict, list, tuple)):
        try:
            return truncate_attribute_value(json.dumps(payload, default=str))
        except TypeError:
            return truncate_attribute_value(str(payload))
    return truncate_attribute_value(str(payload))


def convert_span_to_otel_attributes(span: Any) -> dict[str, Any]:
    """Extract and map NiriZan Span properties into OpenTelemetry span attributes."""
    attributes: dict[str, Any] = {}

    # Span Identity & Context Attributes
    span_id_str = str(getattr(span, "span_id", getattr(span, "id", "")))
    trace_id_str = str(getattr(span, "trace_id", ""))
    if span_id_str:
        attributes[NIRIZAN_SPAN_ID] = span_id_str
    if trace_id_str:
        attributes[NIRIZAN_TRACE_ID] = trace_id_str

    attributes[NIRIZAN_SPAN_ID_SOURCE] = getattr(span, "span_id_source", SPAN_ID_SOURCE_ROUNDTRIP)

    kind_raw = str(getattr(span, "kind", "SPAN")).upper()
    attributes[NIRIZAN_SPAN_KIND] = kind_raw.lower()

    session_id = getattr(span, "session_id", None)
    if session_id:
        attributes[NIRIZAN_SESSION_ID] = str(session_id)

    # Domain Payload Mapping according to Plan §3.1
    input_payload = getattr(span, "input_payload", None)
    output_payload = getattr(span, "output_payload", None)

    if kind_raw in ("GENERATION", "LLM", "CHAT"):
        if input_payload is not None:
            attributes[GEN_AI_PROMPT] = _format_payload_value(input_payload)
        if output_payload is not None:
            attributes[GEN_AI_COMPLETION] = _format_payload_value(output_payload)

        provider = getattr(span, "provider", None)
        if provider:
            attributes[GEN_AI_SYSTEM] = str(provider)

        model_name = getattr(span, "model_name", getattr(span, "model", None))
        if model_name:
            attributes[GEN_AI_REQUEST_MODEL] = str(model_name)
            attributes[GEN_AI_RESPONSE_MODEL] = str(model_name)

        prompt_tokens = getattr(span, "prompt_tokens", None)
        if isinstance(prompt_tokens, int):
            attributes[GEN_AI_USAGE_PROMPT_TOKENS] = prompt_tokens

        completion_tokens = getattr(span, "completion_tokens", None)
        if isinstance(completion_tokens, int):
            attributes[GEN_AI_USAGE_COMPLETION_TOKENS] = completion_tokens

        attributes[GEN_AI_OPERATION_NAME] = "chat"

    elif kind_raw == "RETRIEVAL":
        if input_payload is not None:
            attributes[NIRIZAN_RETRIEVAL_QUERY] = _format_payload_value(input_payload)
        if output_payload is not None:
            attributes[NIRIZAN_RETRIEVAL_RESULTS] = _format_payload_value(output_payload)

        top_k = getattr(span, "top_k", None)
        if isinstance(top_k, int):
            attributes[NIRIZAN_RETRIEVAL_TOP_K] = top_k

    elif kind_raw in ("TOOL_USE", "TOOL"):
        tool_name = getattr(span, "tool_name", getattr(span, "name", None))
        if tool_name:
            attributes[NIRIZAN_TOOL_NAME] = str(tool_name)
        if input_payload is not None:
            attributes[NIRIZAN_TOOL_ARGUMENTS] = _format_payload_value(input_payload)
        if output_payload is not None:
            attributes[NIRIZAN_TOOL_RESULT] = _format_payload_value(output_payload)

    elif kind_raw == "PLANNING":
        if input_payload is not None:
            attributes[NIRIZAN_PLANNING_CONTEXT] = _format_payload_value(input_payload)
        if output_payload is not None:
            attributes[NIRIZAN_PLANNING_OUTPUT] = _format_payload_value(output_payload)

    else:
        if input_payload is not None:
            attributes["nirizan.input"] = _format_payload_value(input_payload)
        if output_payload is not None:
            attributes["nirizan.output"] = _format_payload_value(output_payload)

    # Custom Attributes
    custom_attributes = getattr(span, "attributes", {}) or {}
    if isinstance(custom_attributes, dict):
        for k, v in custom_attributes.items():
            if v is None:
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
                try:
                    attributes[k] = truncate_attribute_value(json.dumps(v, default=str))
                except TypeError:
                    attributes[k] = truncate_attribute_value(str(v))
            else:
                attributes[k] = truncate_attribute_value(str(v))

    return attributes


def _convert_status(span: Any) -> Status:
    """Map NiriZan status representations to OpenTelemetry Status."""
    raw_status = getattr(span, "status", None)
    status_msg = getattr(span, "status_message", None) or getattr(span, "error_message", None)

    if raw_status is None:
        return Status(StatusCode.UNSET)

    status_str = str(getattr(raw_status, "value", raw_status)).upper()

    if status_str in ("OK", "SUCCESS", "STATUSCODE.OK"):
        return Status(StatusCode.OK)
    if status_str in ("ERROR", "FAIL", "FAILURE", "EXCEPTION", "STATUSCODE.ERROR"):
        return Status(StatusCode.ERROR, description=str(status_msg or ""))

    return Status(StatusCode.UNSET)


def export_span_to_otel(
    span: Any,
    tracer: Tracer | None = None,
) -> trace.Span:
    """Convert and export a single NiriZan Span into an OpenTelemetry Span."""
    if tracer is None:
        tracer = trace.get_tracer("nirizan.instrumentation.otel")

    span_name = str(getattr(span, "name", "nirizan_span"))
    attributes = convert_span_to_otel_attributes(span)
    start_ns = _to_nanoseconds(getattr(span, "start_time", None))
    end_ns = _to_nanoseconds(getattr(span, "end_time", None))

    # Construct Parent Trace Context if parent_span_id is available
    context = None
    trace_id_str = getattr(span, "trace_id", None)
    parent_span_id_str = getattr(span, "parent_span_id", None)

    if trace_id_str:
        otel_trace_id = uuid_to_otel_trace_id(trace_id_str)
        if parent_span_id_str:
            otel_parent_id = uuid_to_otel_span_id(parent_span_id_str)
            parent_ctx = SpanContext(
                trace_id=otel_trace_id,
                span_id=otel_parent_id,
                is_remote=True,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
            )
            context = set_span_in_context(NonRecordingSpan(parent_ctx))

    otel_span = tracer.start_span(
        name=span_name,
        context=context,
        attributes=attributes,
        start_time=start_ns,
    )

    otel_span.set_status(_convert_status(span))

    events = getattr(span, "events", []) or []
    for evt in events:
        evt_name = str(getattr(evt, "name", "event"))
        evt_ts = _to_nanoseconds(getattr(evt, "timestamp", None))
        evt_attrs = getattr(evt, "attributes", None)
        otel_span.add_event(name=evt_name, attributes=evt_attrs, timestamp=evt_ts)

    exc = getattr(span, "exception", None)
    if exc is not None:
        if isinstance(exc, BaseException):
            otel_span.record_exception(exc)
        else:
            otel_span.add_event("exception", attributes={"exception.message": str(exc)})

    otel_span.end(end_time=end_ns)
    return otel_span


def export_trace_to_otel(
    trace_obj: Trace | Sequence[Any],
    tracer: Tracer | None = None,
) -> list[trace.Span]:
    """Convert and export a full NiriZan trace (sequence of spans) to OpenTelemetry."""
    spans = getattr(trace_obj, "spans", trace_obj)
    exported_spans: list[trace.Span] = []

    for span in spans:
        exported = export_span_to_otel(span, tracer=tracer)
        exported_spans.append(exported)

    return exported_spans


class NiriZanOTelExporter:
    """Trace exporter bridging NiriZan traces and spans into OpenTelemetry."""

    def __init__(self, tracer: Tracer | None = None) -> None:
        self._tracer = tracer or trace.get_tracer("nirizan.instrumentation.otel")

    def export_span(self, span: Any) -> trace.Span:
        """Export a single NiriZan span to OpenTelemetry."""
        return export_span_to_otel(span, tracer=self._tracer)

    def export_trace(self, trace_obj: Trace | Sequence[Any]) -> list[trace.Span]:
        """Export an entire NiriZan trace to OpenTelemetry."""
        return export_trace_to_otel(trace_obj, tracer=self._tracer)
