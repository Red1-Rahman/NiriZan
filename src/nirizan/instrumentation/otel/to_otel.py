# src/nirizan/instrumentation/otel/to_otel.py
"""OpenTelemetry trace exporter for NiriZan.

Converts NiriZan ``Span`` and ``Trace`` objects into OpenTelemetry spans,
mapping span kinds, GenAI attributes, sequence attributes, and span context IDs.

Behavior worth knowing before wiring this into an application:

* **One NiriZan trace becomes one OpenTelemetry trace.** The OTel trace id is the
  NiriZan trace id, and every root (or orphan) span is parented to a synthetic
  *remote* parent in that trace, the same way a span that continues a trace from
  another service is. Backends may show such a root with a "missing parent"
  marker. ``OTelExporterConfig.link_roots_to_trace_id`` turns this off, at the
  cost that each root then starts its own OTel trace.
* **Exported spans never attach to whatever OTel span happens to be active.**
  Parenting is always explicit, so the result does not depend on where the
  exporter is called from.
* **Prompt and completion content is not exported unless asked for.** See
  ``OTelExporterConfig.capture_content``.
* **A failing OTel pipeline never reaches the instrumented application.**
  ``NiriZanToOTelExporter.export`` logs and counts failures instead of raising,
  as the ``TraceExporter`` contract requires.
"""

from __future__ import annotations

import importlib.metadata
from collections import deque
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from uuid import UUID

from opentelemetry import trace as otel_trace
from opentelemetry.context import Context
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    TraceFlags,
    Tracer,
    set_span_in_context,
)
from opentelemetry.trace.status import Status, StatusCode
from pydantic import BaseModel, ConfigDict

import nirizan
from nirizan._logging import get_logger
from nirizan.instrumentation.exporters import BaseExporter
from nirizan.instrumentation.otel._id_mapping import uuid_to_otel_trace_id
from nirizan.instrumentation.otel.semconv import (
    GEN_AI_COMPLETION,
    GEN_AI_OPERATION_NAME,
    GEN_AI_PROMPT,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_USAGE_COMPLETION_TOKENS,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
    GEN_AI_USAGE_PROMPT_TOKENS,
    ID_SOURCE_DERIVED,
    ID_SOURCE_ROUNDTRIP,
    NIRIZAN_INSTRUMENTATION_SCOPE,
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
    NIRIZAN_TRACE_ID_SOURCE,
    OTEL_STATUS_CODE,
    OTEL_STATUS_DESCRIPTION,
    decode_sequence_key,
    truncate_attribute_value,
)
from nirizan.instrumentation.spans import Span, SpanKind, Trace

logger = get_logger(__name__)

__all__ = [
    "NiriZanToOTelExporter",
    "OTelExporterConfig",
    "convert_span_to_otel_attributes",
    "export_span_to_otel",
    "export_trace_to_otel",
]

_EPOCH: datetime = datetime(1970, 1, 1, tzinfo=UTC)

# Span id of the synthetic remote parent that anchors roots and orphans to their
# trace. It is the ASCII bytes of "NiriZan" followed by 0x01, a fixed non-zero
# 64-bit value, so it is valid and recognizable in a backend.
_SYNTHETIC_PARENT_SPAN_ID: int = 0x4E6972695A616E01

# Payload attribute names (input, output) for each span kind. These carry
# prompt, retrieval, tool and planning *content*, so they are exported only when
# ``capture_content`` is on.
_PAYLOAD_ATTRIBUTES: Mapping[SpanKind, tuple[str, str]] = {
    SpanKind.GENERATION: (GEN_AI_PROMPT, GEN_AI_COMPLETION),
    SpanKind.RETRIEVAL: (NIRIZAN_RETRIEVAL_QUERY, NIRIZAN_RETRIEVAL_RESULTS),
    SpanKind.TOOL_USE: (NIRIZAN_TOOL_ARGUMENTS, NIRIZAN_TOOL_RESULT),
    SpanKind.PLANNING: (NIRIZAN_PLANNING_CONTEXT, NIRIZAN_PLANNING_OUTPUT),
}
_CONTENT_ATTRIBUTE_KEYS: frozenset[str] = frozenset(
    key for pair in _PAYLOAD_ATTRIBUTES.values() for key in pair
)

AttributeValue = str | int | float | bool


class OTelExporterConfig(BaseModel):
    """Settings for the NiriZan -> OpenTelemetry exporter."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    capture_content: bool = False
    """Export prompt, completion, retrieval, tool and planning content.

    Off by default: content often contains personal data and is sent to whatever
    OpenTelemetry backend is configured. Structural data (span kinds, names,
    timings, token counts, model names, tool names) is always exported. When this
    is off, content-bearing attributes that were copied from an ingested OTel
    span (``gen_ai.prompt`` and friends, including their sequence-encoded form)
    are withheld too.
    """

    emit_legacy_attributes: bool = True
    """Also emit the pre-rename GenAI names next to the current ones.

    ``gen_ai.usage.prompt_tokens`` / ``completion_tokens`` (renamed to
    ``input_tokens`` / ``output_tokens``) and ``gen_ai.system`` (superseded by
    ``gen_ai.provider.name``). Turn off once consumers have moved.
    """

    link_roots_to_trace_id: bool = True
    """Keep every span of a NiriZan trace in one OpenTelemetry trace.

    Roots and orphans are parented to a synthetic remote parent in the NiriZan
    trace's OTel trace, so the OTel trace id equals the NiriZan trace id. Some
    backends mark such a root as having a missing parent. When off, each root
    starts its own OTel trace, so a trace with several roots is split apart.
    """


_DEFAULT_CONFIG = OTelExporterConfig()


def _package_version() -> str | None:
    """Return NiriZan's version for the instrumentation scope, if it can be found."""
    version = getattr(nirizan, "__version__", None)
    if isinstance(version, str) and version:
        return version
    try:
        return importlib.metadata.version("nirizan")
    except importlib.metadata.PackageNotFoundError:
        return None


def _get_default_tracer() -> Tracer:
    """Retrieve the default OpenTelemetry Tracer with NiriZan's instrumentation scope.

    The scope name is the one ``NiriZanSpanProcessor`` skips by default, so a
    processor and this exporter on one provider do not feed each other.
    """
    return otel_trace.get_tracer(NIRIZAN_INSTRUMENTATION_SCOPE, _package_version())


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
    if isinstance(ts, int) and not isinstance(ts, bool):
        return ts
    return None


def _format_payload_value(payload: str | None) -> str | None:
    """Truncate a payload to the attribute length limit."""
    if payload is None:
        return None
    return truncate_attribute_value(payload)


def _first_str(attrs: Mapping[str, AttributeValue], *keys: str) -> str | None:
    for key in keys:
        value = attrs.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _first_int(attrs: Mapping[str, AttributeValue], *keys: str) -> int | None:
    """First integer under ``keys``. Zero is a real value; ``bool`` is not an integer here."""
    for key in keys:
        value = attrs.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _provenance(value: object) -> str:
    """A known provenance marker, or ``roundtrip`` for anything else."""
    return ID_SOURCE_DERIVED if value == ID_SOURCE_DERIVED else ID_SOURCE_ROUNDTRIP


def _add_generation_attributes(
    attributes: dict[str, AttributeValue],
    custom: Mapping[str, AttributeValue],
    config: OTelExporterConfig,
) -> None:
    provider = _first_str(custom, "provider", GEN_AI_PROVIDER_NAME, GEN_AI_SYSTEM)
    if provider:
        attributes[GEN_AI_PROVIDER_NAME] = provider
        if config.emit_legacy_attributes:
            attributes[GEN_AI_SYSTEM] = provider

    model = _first_str(custom, "model_name", "model", GEN_AI_REQUEST_MODEL)
    if model:
        attributes[GEN_AI_REQUEST_MODEL] = model
        attributes[GEN_AI_RESPONSE_MODEL] = _first_str(custom, GEN_AI_RESPONSE_MODEL) or model

    input_tokens = _first_int(
        custom, "prompt_tokens", GEN_AI_USAGE_INPUT_TOKENS, GEN_AI_USAGE_PROMPT_TOKENS
    )
    if input_tokens is not None:
        attributes[GEN_AI_USAGE_INPUT_TOKENS] = input_tokens
        if config.emit_legacy_attributes:
            attributes[GEN_AI_USAGE_PROMPT_TOKENS] = input_tokens

    output_tokens = _first_int(
        custom, "completion_tokens", GEN_AI_USAGE_OUTPUT_TOKENS, GEN_AI_USAGE_COMPLETION_TOKENS
    )
    if output_tokens is not None:
        attributes[GEN_AI_USAGE_OUTPUT_TOKENS] = output_tokens
        if config.emit_legacy_attributes:
            attributes[GEN_AI_USAGE_COMPLETION_TOKENS] = output_tokens

    attributes[GEN_AI_OPERATION_NAME] = _first_str(custom, GEN_AI_OPERATION_NAME) or "chat"


def convert_span_to_otel_attributes(
    span: Span,
    session_id: str | UUID | None = None,
    *,
    config: OTelExporterConfig | None = None,
) -> dict[str, AttributeValue]:
    """Map a NiriZan ``Span`` to OpenTelemetry span attributes.

    Identifiers, kind, provenance and any ``session_id`` are always included.
    Content (prompts, completions, retrieval and tool payloads) only when
    ``config.capture_content`` is on. All remaining span attributes are carried
    over so a later re-ingest loses nothing; a span attribute can never overwrite
    one of the attributes computed here.
    """
    cfg = config or _DEFAULT_CONFIG
    custom = span.attributes

    attributes: dict[str, AttributeValue] = {
        NIRIZAN_SPAN_ID: str(span.span_id),
        NIRIZAN_TRACE_ID: str(span.trace_id),
        NIRIZAN_SPAN_ID_SOURCE: _provenance(custom.get(NIRIZAN_SPAN_ID_SOURCE)),
        NIRIZAN_TRACE_ID_SOURCE: _provenance(custom.get(NIRIZAN_TRACE_ID_SOURCE)),
        NIRIZAN_SPAN_KIND: span.kind.value,
    }
    if session_id:
        attributes[NIRIZAN_SESSION_ID] = str(session_id)

    payload_keys = _PAYLOAD_ATTRIBUTES.get(span.kind)
    if cfg.capture_content and payload_keys is not None:
        input_key, output_key = payload_keys
        if span.input_payload is not None:
            attributes[input_key] = truncate_attribute_value(span.input_payload)
        if span.output_payload is not None:
            attributes[output_key] = truncate_attribute_value(span.output_payload)

    if span.kind is SpanKind.GENERATION:
        _add_generation_attributes(attributes, custom, cfg)
    elif span.kind is SpanKind.RETRIEVAL:
        top_k = _first_int(custom, "top_k", NIRIZAN_RETRIEVAL_TOP_K)
        if top_k is not None:
            attributes[NIRIZAN_RETRIEVAL_TOP_K] = top_k
    elif span.kind is SpanKind.TOOL_USE:
        tool_name = _first_str(custom, "tool_name", "name", NIRIZAN_TOOL_NAME)
        if tool_name:
            attributes[NIRIZAN_TOOL_NAME] = tool_name

    # Carry over the remaining attributes. Content-bearing ones are withheld when
    # content capture is off, including the sequence-encoded form of the same key.
    for key, value in custom.items():
        if key in attributes:
            continue
        if not cfg.capture_content and decode_sequence_key(key) in _CONTENT_ATTRIBUTE_KEYS:
            continue
        attributes[key] = truncate_attribute_value(value) if isinstance(value, str) else value

    return attributes


def _status_from_attributes(attrs: Mapping[str, AttributeValue]) -> Status | None:
    """Rebuild an OTel status from the ``otel.status_*`` attributes captured on ingest."""
    code = attrs.get(OTEL_STATUS_CODE)
    if not isinstance(code, str):
        return None
    normalized = code.lower()
    if normalized == "error":
        description = attrs.get(OTEL_STATUS_DESCRIPTION)
        return Status(
            StatusCode.ERROR,
            description if isinstance(description, str) and description else None,
        )
    if normalized == "ok":
        return Status(StatusCode.OK)
    return None


def export_span_to_otel(
    span: Span,
    tracer: Tracer | None = None,
    parent_context: SpanContext | None = None,
    session_id: str | UUID | None = None,
    *,
    config: OTelExporterConfig | None = None,
) -> otel_trace.Span:
    """Convert and export a single NiriZan ``Span`` into an OpenTelemetry span.

    With no ``parent_context`` the span is exported as a root of its own OTel
    trace. It is never parented to whichever OTel span is currently active.
    """
    if tracer is None:
        tracer = _get_default_tracer()

    attributes = convert_span_to_otel_attributes(span, session_id=session_id, config=config)
    start_ns = _to_nanoseconds(span.started_at)
    end_ns = _to_nanoseconds(span.ended_at)

    if parent_context is not None:
        context = set_span_in_context(NonRecordingSpan(parent_context))
    else:
        if span.parent_span_id is not None:
            logger.warning(
                "Parent span '%s' for span '%s' not found in exported parent context map. "
                "Exporting span as root span.",
                span.parent_span_id,
                span.span_id,
            )
        context = Context()

    otel_span = tracer.start_span(
        name=span.name,
        context=context,
        attributes=attributes,
        start_time=start_ns,
    )
    # An exported span must always be ended, or processors would see it as open forever.
    try:
        status = _status_from_attributes(span.attributes)
        if status is not None:
            otel_span.set_status(status)
    finally:
        otel_span.end(end_time=end_ns)
    return otel_span


def _topological_sort_spans(spans: Sequence[Span]) -> list[Span]:
    """Reorder spans so parents always precede their children during export.

    Spans whose parent is not in ``spans`` are treated as roots. Spans that are
    unreachable from any root (a cycle, which a valid trace cannot contain) are
    appended in their original order, so nothing is dropped. A span is returned
    exactly once even if span ids repeat.
    """
    first_index_by_id: dict[UUID, int] = {}
    for index, span in enumerate(spans):
        first_index_by_id.setdefault(span.span_id, index)

    children: dict[UUID | None, list[int]] = {}
    for index, span in enumerate(spans):
        parent = span.parent_span_id
        key = parent if parent in first_index_by_id else None
        children.setdefault(key, []).append(index)

    ordered: list[Span] = []
    seen: set[int] = set()
    queue: deque[int] = deque(children.get(None, []))
    while queue:
        index = queue.popleft()
        if index in seen:
            continue
        seen.add(index)
        ordered.append(spans[index])
        queue.extend(children.get(spans[index].span_id, []))

    ordered.extend(span for index, span in enumerate(spans) if index not in seen)
    return ordered


def _trace_anchor(trace_id: UUID) -> SpanContext | None:
    """The synthetic remote parent that places a span in the NiriZan trace's OTel trace."""
    try:
        otel_trace_id = uuid_to_otel_trace_id(trace_id)
    except ValueError:
        logger.warning(
            "NiriZan trace id %s cannot be used as an OTel trace id; "
            "its roots are exported as separate OTel traces.",
            trace_id,
        )
        return None
    return SpanContext(
        trace_id=otel_trace_id,
        span_id=_SYNTHETIC_PARENT_SPAN_ID,
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )


def export_trace_to_otel(
    trace_obj: Trace | Sequence[Span],
    tracer: Tracer | None = None,
    *,
    config: OTelExporterConfig | None = None,
) -> list[otel_trace.Span]:
    """Convert and export a NiriZan trace, keeping parents before children.

    Accepts a ``Trace`` or a bare sequence of spans. All spans land in one OTel
    trace (see ``OTelExporterConfig.link_roots_to_trace_id``).
    """
    cfg = config or _DEFAULT_CONFIG
    if tracer is None:
        tracer = _get_default_tracer()

    if isinstance(trace_obj, Trace):
        raw_spans: Sequence[Span] = trace_obj.spans
        session_id: UUID | None = trace_obj.session_id
        trace_id: UUID | None = trace_obj.trace_id
    else:
        raw_spans = trace_obj
        session_id = None
        trace_id = raw_spans[0].trace_id if raw_spans else None

    if not raw_spans or trace_id is None:
        return []

    anchor = _trace_anchor(trace_id) if cfg.link_roots_to_trace_id else None
    exported_spans: list[otel_trace.Span] = []
    span_context_map: dict[UUID, SpanContext] = {}

    for span in _topological_sort_spans(raw_spans):
        parent_ctx = span_context_map.get(span.parent_span_id) if span.parent_span_id else None
        if parent_ctx is None:
            if span.parent_span_id is not None:
                logger.warning(
                    "Parent span '%s' for span '%s' not found in exported parent context map. "
                    "Exporting span as root span.",
                    span.parent_span_id,
                    span.span_id,
                )
            parent_ctx = anchor

        exported = export_span_to_otel(
            span,
            tracer=tracer,
            parent_context=parent_ctx,
            session_id=session_id,
            config=cfg,
        )
        span_context_map[span.span_id] = exported.get_span_context()
        exported_spans.append(exported)

    return exported_spans


class NiriZanToOTelExporter(BaseExporter):
    """Trace exporter bridging NiriZan traces and spans into OpenTelemetry.

    ``export`` never raises (apart from task cancellation): a failure in the
    OpenTelemetry pipeline is logged and counted in ``export_failures`` and the
    trace is dropped, as the ``TraceExporter`` contract requires.
    """

    def __init__(
        self,
        tracer: Tracer | None = None,
        *,
        config: OTelExporterConfig | None = None,
    ) -> None:
        self._tracer = tracer or _get_default_tracer()
        self._config = config or _DEFAULT_CONFIG
        self._export_failures = 0

    @property
    def config(self) -> OTelExporterConfig:
        """The settings this exporter was built with."""
        return self._config

    @property
    def export_failures(self) -> int:
        """Number of traces dropped because exporting them raised."""
        return self._export_failures

    async def export(self, trace: Trace) -> None:
        """Export a NiriZan Trace to OpenTelemetry satisfying BaseExporter interface."""
        try:
            export_trace_to_otel(trace, tracer=self._tracer, config=self._config)
        except Exception:
            self._export_failures += 1
            logger.exception(
                "NiriZanToOTelExporter failed to export trace %s; the trace was dropped.",
                trace.trace_id,
            )

    def export_span(self, span: Span) -> otel_trace.Span:
        """Export a single NiriZan span to OpenTelemetry."""
        return export_span_to_otel(span, tracer=self._tracer, config=self._config)

    def export_trace(self, trace_obj: Trace | Sequence[Span]) -> list[otel_trace.Span]:
        """Export a full NiriZan trace structure to OpenTelemetry."""
        return export_trace_to_otel(trace_obj, tracer=self._tracer, config=self._config)
