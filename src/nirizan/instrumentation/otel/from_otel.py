# src/nirizan/instrumentation/otel/from_otel.py
"""OpenTelemetry span processor that assembles NiriZan Traces from OTel spans.

This module implements the OTel -> NiriZan direction of the bridge. It hooks
into the OpenTelemetry SDK through the ``SpanProcessor`` interface and
produces plain NiriZan ``Trace`` objects, indistinguishable at the type level
from traces assembled by NiriZan's own ``Tracer``.

Importing this module has no effect on standalone NiriZan use: nothing is
registered with OpenTelemetry, and no thread starts, until a
``NiriZanSpanProcessor`` is constructed.
"""

from __future__ import annotations

import math
import os
import queue
import threading
import time
import weakref
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, Protocol
from uuid import UUID

from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.trace import SpanContext, TraceFlags
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from nirizan._logging import get_logger
from nirizan.instrumentation.otel._id_mapping import (
    is_valid_otel_span_id,
    is_valid_otel_trace_id,
    otel_span_id_to_uuid,
    otel_trace_id_to_uuid,
)
from nirizan.instrumentation.otel.semconv import (
    GEN_AI_COMPLETION,
    GEN_AI_PROMPT,
    ID_SOURCE_DERIVED,
    ID_SOURCE_ROUNDTRIP,
    NIRIZAN_INSTRUMENTATION_SCOPE,
    NIRIZAN_PLANNING_CONTEXT,
    NIRIZAN_PLANNING_OUTPUT,
    NIRIZAN_RETRIEVAL_QUERY,
    NIRIZAN_RETRIEVAL_RESULTS,
    NIRIZAN_SESSION_ID,
    NIRIZAN_SPAN_ID,
    NIRIZAN_SPAN_ID_SOURCE,
    NIRIZAN_SPAN_KIND,
    NIRIZAN_TOOL_ARGUMENTS,
    NIRIZAN_TOOL_RESULT,
    NIRIZAN_TRACE_ID,
    NIRIZAN_TRACE_ID_SOURCE,
    OTEL_SAMPLED,
    OTEL_SPAN_ID,
    OTEL_STATUS_CODE,
    OTEL_STATUS_DESCRIPTION,
    OTEL_TRACE_STATE,
    encode_sequence_attribute_value,
    encode_sequence_key,
    is_sequence_key,
    truncate_attribute_value,
)
from nirizan.instrumentation.spans import Span, SpanKind, Trace

logger = get_logger(__name__)

__all__ = ["NiriZanSpanProcessor", "ProcessorConfig", "StatReason", "ThreadSafeTraceSink"]


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_SERVICE_NAME_RESOURCE_KEY: str = "service.name"
_OTEL_SERVICE_NAME: str = "otel.service.name"

_FLUSH_SENTINEL: object = object()
_SHUTDOWN_SENTINEL: object = object()
_START_MARKER: object = object()

_RECENT_FLUSHES_MAX: int = 10_000
_MAX_SPAN_NAME_LENGTH: int = 200

_DEFAULT_MAX_QUEUE_SIZE: int = 50_000
_DEFAULT_MAX_SPANS_PER_TRACE: int = 10_000

_PAYLOAD_SUFFIX: str = "...[truncated]"
_DEFAULT_MAX_PAYLOAD_CHARS: int = 65_536
_DEFAULT_MAX_BUFFERED_SPANS: int = 100_000

_QUEUE_FULL_WARNING_INTERVAL_SECONDS: float = 5.0

_SIG_ROOT: str = "root"
_SIG_ATTACH: str = "attach_to"
_SIG_MISSING: str = "missing"

# ---------------------------------------------------------------------------
# Stat reasons and configuration
# ---------------------------------------------------------------------------


class StatReason(StrEnum):
    """Keys of the counters returned by ``NiriZanSpanProcessor.get_stats``.

    The members are strings, so ``stats["late_arrival"]`` and
    ``stats[StatReason.LATE_ARRIVAL]`` read the same counter. Most reasons
    count dropped data, but some count notable-but-lossless events (an emitted
    orphan, a broken cycle), so the enum is named for what it is: a counter key.
    """

    INVALID_SPAN_CONTEXT = "invalid_span_context"
    INVALID_TRACE_ID = "invalid_trace_id"
    INVALID_SPAN_ID = "invalid_span_id"
    LATE_ARRIVAL = "late_arrival"
    DUPLICATE_SPAN_ID = "duplicate_span_id"
    DUPLICATE_NIRIZAN_SPAN_ID = "duplicate_nirizan_span_id"
    CONFLICTING_TRACE_ID = "conflicting_trace_id"
    UNRECOGNIZED_KIND = "unrecognized_kind"
    ORPHAN_PARENT_MISSING = "orphan_parent_missing"
    ORPHAN_EMITTED = "orphan_emitted"
    CYCLE_BROKEN = "cycle_broken"
    CONVERSION_ERROR = "conversion_error"
    QUEUE_FULL = "queue_full"
    OWN_SCOPE_SKIPPED = "own_scope_skipped"
    EVICTED_OPEN_TRACE = "evicted_open_trace"
    TRACE_SPAN_CAP = "trace_span_cap"
    CONSUMER_ERROR = "consumer_error"


class ProcessorConfig(BaseModel):
    """Validated settings for ``NiriZanSpanProcessor``.

    ``NiriZanSpanProcessor`` accepts the same fields as keyword arguments and
    builds one of these internally, so invalid values are rejected in one place.
    Validation failures are ``pydantic.ValidationError`` (a ``ValueError``
    subclass) whose message contains the text shown below.
    """

    model_config = ConfigDict(strict=True, frozen=True)

    idle_timeout_seconds: float = 5.0
    max_trace_age_seconds: float = 300.0
    max_buffered_traces: int = 1000
    max_queue_size: int = _DEFAULT_MAX_QUEUE_SIZE
    max_spans_per_trace: int = _DEFAULT_MAX_SPANS_PER_TRACE
    orphan_policy: Literal["emit", "drop"] = "emit"
    unrecognized_span_policy: Literal["drop", "generation"] = "drop"
    ignore_own_scope: bool = True
    trust_stashed_ids: bool = False
    max_payload_chars: int = _DEFAULT_MAX_PAYLOAD_CHARS
    max_buffered_spans: int = _DEFAULT_MAX_BUFFERED_SPANS

    @field_validator("idle_timeout_seconds")
    @classmethod
    def _idle_timeout_positive(cls, value: float) -> float:
        if not value > 0 or math.isinf(value):
            raise ValueError("idle_timeout_seconds must be positive and finite.")
        return value

    @field_validator("max_trace_age_seconds")
    @classmethod
    def _max_age_finite(cls, value: float) -> float:
        if math.isnan(value) or math.isinf(value):
            raise ValueError("max_trace_age_seconds must be finite.")
        return value

    @field_validator("max_buffered_traces")
    @classmethod
    def _max_buffered_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_buffered_traces must be at least 1.")
        return value

    @field_validator("max_queue_size")
    @classmethod
    def _max_queue_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_queue_size must be at least 1.")
        return value

    @field_validator("max_spans_per_trace")
    @classmethod
    def _max_spans_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_spans_per_trace must be at least 1.")
        return value

    @field_validator("max_payload_chars")
    @classmethod
    def _payload_limit(cls, value: int) -> int:
        if value <= len(_PAYLOAD_SUFFIX):
            raise ValueError("max_payload_chars must exceed the truncation suffix length.")
        return value

    @field_validator("max_buffered_spans")
    @classmethod
    def _max_buffered_spans_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_buffered_spans must be at least 1.")
        return value

    @field_validator("orphan_policy", mode="before")
    @classmethod
    def _orphan_policy_known(cls, value: object) -> object:
        if value not in ("emit", "drop"):
            raise ValueError("orphan_policy must be 'emit' or 'drop'.")
        return value

    @field_validator("unrecognized_span_policy", mode="before")
    @classmethod
    def _unrecognized_policy_known(cls, value: object) -> object:
        if value not in ("drop", "generation"):
            raise ValueError("unrecognized_span_policy must be 'drop' or 'generation'.")
        return value

    @model_validator(mode="after")
    def _age_exceeds_idle(self) -> ProcessorConfig:
        if self.max_trace_age_seconds <= self.idle_timeout_seconds:
            raise ValueError("max_trace_age_seconds must be greater than idle_timeout_seconds.")
        return self


# ---------------------------------------------------------------------------
# Sink protocol
# ---------------------------------------------------------------------------


class ThreadSafeTraceSink(Protocol):
    """Minimal sync interface for handing an assembled ``Trace`` to a consumer.

    ``enqueue_trace`` is called from the processor's consumer thread, not from
    the event loop, so implementations must be thread-safe and must not block.
    Renamed from ``TraceSink`` to avoid colliding with the differently-shaped
    (async) ``TraceSink`` protocol in ``orchestrator/collector.py``; the two
    are not interchangeable, and a collector cannot be passed here directly
    (see ``orchestrator/loop_sink.py::LoopTraceSink``, which bridges the two).
    """

    def enqueue_trace(self, trace: Trace) -> None:
        """Hand a completed ``Trace`` to the sink's consumer."""
        pass


# ---------------------------------------------------------------------------
# Defensive accessors
# ---------------------------------------------------------------------------


def _get_span_context(span: ReadableSpan) -> SpanContext | None:
    """Return the span's ``SpanContext``, or ``None`` if unavailable."""
    ctx = span.get_span_context()
    return ctx if ctx is not None else None


def _get_parent_context(span: ReadableSpan) -> SpanContext | None:
    """Return the span's parent ``SpanContext``, or ``None`` if it has no parent."""
    parent = span.parent
    return parent if parent is not None else None


def _scope_name(span: Any) -> str | None:
    """Return the instrumentation scope name that created ``span``, if known.

    Only ``instrumentation_scope`` is consulted. The older ``instrumentation_info``
    property is deprecated since OpenTelemetry 1.11.1 and warns on access, and the
    ``otel`` extra requires a version that always provides the scope.
    """
    scope = getattr(span, "instrumentation_scope", None)
    name = getattr(scope, "name", None)
    return name if isinstance(name, str) else None


def _is_flush_request(item: Any) -> bool:
    """Return ``True`` if ``item`` is a ``(_FLUSH_SENTINEL, Event)`` tuple."""
    return isinstance(item, tuple) and len(item) == 2 and item[0] is _FLUSH_SENTINEL


def _is_start_marker(item: Any) -> bool:
    """Return ``True`` if ``item`` is a ``(_START_MARKER, trace_id, timestamp)`` tuple."""
    return isinstance(item, tuple) and len(item) == 3 and item[0] is _START_MARKER


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _ns_to_datetime(ns: int | None) -> datetime:
    """Convert nanoseconds-since-epoch to a timezone-aware UTC ``datetime``."""
    if ns is None:
        return datetime.now(UTC)
    seconds, remainder = divmod(int(ns), 1_000_000_000)
    return datetime.fromtimestamp(seconds, tz=UTC).replace(microsecond=remainder // 1000)


def _parse_stashed_uuid(value: object) -> UUID | None:
    """Parse a stashed ``nirizan.*`` id attribute, rejecting malformed and nil UUIDs.

    The nil UUID is rejected because it can never be mapped back to a valid
    OTel id, so accepting it would produce a trace that cannot be re-exported.
    """
    if not isinstance(value, str):
        return None
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        return None
    return None if parsed.int == 0 else parsed


def _extract_nirizan_span_id(
    span: ReadableSpan, ctx: SpanContext, trust: bool
) -> tuple[UUID, str]:
    """Return ``(NiriZan span_id, provenance source)`` for an OTel span.

    A stashed ``nirizan.span_id`` is recovered as-is, but only when ``trust``
    is ``True``. A stashed span id cannot be verified against anything the
    OTel SDK generated, so an untrusted ingest path always falls back to the
    id derived from the OTel span id. Its provenance is ``derived`` if the
    stashed ``nirizan.span_id.source`` says the id was originally derived
    from an OTel id, and ``roundtrip`` otherwise.
    """
    attrs = getattr(span, "attributes", None) or {}
    stashed = attrs.get(NIRIZAN_SPAN_ID)
    if trust and isinstance(stashed, str):
        parsed = _parse_stashed_uuid(stashed)
        if parsed is not None:
            prior = attrs.get(NIRIZAN_SPAN_ID_SOURCE)
            source = ID_SOURCE_DERIVED if prior == ID_SOURCE_DERIVED else ID_SOURCE_ROUNDTRIP
            return parsed, source
        logger.debug(
            "Ignoring invalid nirizan.span_id attribute '%s' on OTel span '%s'",
            stashed,
            span.name,
        )
    return otel_span_id_to_uuid(ctx.span_id), ID_SOURCE_DERIVED


def _extract_nirizan_trace_id(
    spans: Mapping[int, ReadableSpan], otel_trace_id: int, trust: bool
) -> tuple[UUID, str]:
    """Return ``(NiriZan trace_id, provenance source)`` for a buffered OTel trace.

    Spans are examined in start-time order so the result does not depend on
    arrival order. A stashed id wins over a derived one, but only when
    ``trust`` is ``True``. When it is ``False``, every span's id is derived
    from the OTel trace id, so an ingested span cannot claim an existing
    stored trace's id.
    """
    if not trust:
        return otel_trace_id_to_uuid(otel_trace_id), ID_SOURCE_DERIVED

    ordered = sorted(
        spans.items(),
        key=lambda item: (_int_or_zero(getattr(item[1], "start_time", None)), item[0]),
    )
    for _, span in ordered:
        attrs = getattr(span, "attributes", None) or {}
        stashed = attrs.get(NIRIZAN_TRACE_ID)
        if isinstance(stashed, str):
            parsed = _parse_stashed_uuid(stashed)
            if parsed is not None:
                prior = attrs.get(NIRIZAN_TRACE_ID_SOURCE)
                source = ID_SOURCE_DERIVED if prior == ID_SOURCE_DERIVED else ID_SOURCE_ROUNDTRIP
                return parsed, source
            logger.debug(
                "Ignoring invalid nirizan.trace_id attribute '%s' found on span '%s'",
                stashed,
                getattr(span, "name", "<unnamed>"),
            )
    return otel_trace_id_to_uuid(otel_trace_id), ID_SOURCE_DERIVED


def _has_conflicting_trace_ids(spans: Mapping[int, ReadableSpan]) -> bool:
    """Return ``True`` if buffered spans stash more than one distinct valid trace id."""
    seen: set[UUID] = set()
    for span in spans.values():
        attrs = getattr(span, "attributes", None) or {}
        parsed = _parse_stashed_uuid(attrs.get(NIRIZAN_TRACE_ID))
        if parsed is not None:
            seen.add(parsed)
    return len(seen) > 1


def _int_or_zero(value: object) -> int:
    """Return ``value`` if it is an ``int``, else ``0`` (tolerates missing timestamps)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _infer_span_kind(attrs: Mapping[str, Any]) -> SpanKind | None:
    """Determine NiriZan ``SpanKind`` from an OTel span's attributes."""
    raw = attrs.get(NIRIZAN_SPAN_KIND)
    if isinstance(raw, str):
        normalized = raw.upper().split(".")[-1]
        if normalized in ("PLANNING", "RETRIEVAL", "TOOL_USE", "GENERATION"):
            return SpanKind[normalized]

    if GEN_AI_PROMPT in attrs or GEN_AI_COMPLETION in attrs:
        return SpanKind.GENERATION
    if NIRIZAN_RETRIEVAL_QUERY in attrs or NIRIZAN_RETRIEVAL_RESULTS in attrs:
        return SpanKind.RETRIEVAL
    if NIRIZAN_TOOL_ARGUMENTS in attrs or NIRIZAN_TOOL_RESULT in attrs:
        return SpanKind.TOOL_USE
    if NIRIZAN_PLANNING_CONTEXT in attrs or NIRIZAN_PLANNING_OUTPUT in attrs:
        return SpanKind.PLANNING

    return None


def _to_str_or_none(value: Any) -> str | None:
    """Coerce an arbitrary attribute value to ``str`` or ``None``."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _extract_payloads(kind: SpanKind, attrs: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Extract ``(input_payload, output_payload)`` for a given span kind."""
    if kind is SpanKind.GENERATION:
        return (
            _to_str_or_none(attrs.get(GEN_AI_PROMPT)),
            _to_str_or_none(attrs.get(GEN_AI_COMPLETION)),
        )
    if kind is SpanKind.RETRIEVAL:
        return (
            _to_str_or_none(attrs.get(NIRIZAN_RETRIEVAL_QUERY)),
            _to_str_or_none(attrs.get(NIRIZAN_RETRIEVAL_RESULTS)),
        )
    if kind is SpanKind.TOOL_USE:
        return (
            _to_str_or_none(attrs.get(NIRIZAN_TOOL_ARGUMENTS)),
            _to_str_or_none(attrs.get(NIRIZAN_TOOL_RESULT)),
        )
    if kind is SpanKind.PLANNING:
        return (
            _to_str_or_none(attrs.get(NIRIZAN_PLANNING_CONTEXT)),
            _to_str_or_none(attrs.get(NIRIZAN_PLANNING_OUTPUT)),
        )
    return None, None


def _cap_payload(value: str | None, limit: int) -> str | None:
    """Truncate ``value`` to at most ``limit`` characters, marking truncation.

    The tail of an oversized payload is lost; the remaining text is shortened
    just enough that the appended ``_PAYLOAD_SUFFIX`` still fits inside
    ``limit``. ``limit`` must exceed ``len(_PAYLOAD_SUFFIX)``, which
    ``ProcessorConfig`` enforces for ``max_payload_chars``.
    """
    if value is None or len(value) <= limit:
        return value
    return value[: limit - len(_PAYLOAD_SUFFIX)] + _PAYLOAD_SUFFIX


def _convert_attributes(
    otel_attrs: Mapping[str, Any],
    *,
    service_name: str | None,
    span_id_hex: str | None,
    span_id_source: str,
    trace_id_source: str,
    sampled: bool | None,
    trace_state: str | None,
    status_code: str | None,
    status_description: str | None,
) -> dict[str, str | int | float | bool]:
    """Convert OTel attributes plus captured metadata into NiriZan form."""
    result: dict[str, str | int | float | bool] = {}

    for key, value in otel_attrs.items():
        if value is None:
            continue
        if isinstance(value, str):
            result[key] = truncate_attribute_value(value)
        elif isinstance(value, (int, float, bool)):
            result[key] = value
        elif isinstance(value, (list, tuple)):
            try:
                encoded_key = key if is_sequence_key(key) else encode_sequence_key(key)
                result[encoded_key] = encode_sequence_attribute_value(value)
            except ValueError as err:
                logger.warning("Dropping sequence attribute '%s' from OTel span: %s", key, err)
        else:
            result[key] = truncate_attribute_value(str(value))

    if service_name:
        result[_OTEL_SERVICE_NAME] = service_name
    if span_id_hex:
        result[OTEL_SPAN_ID] = span_id_hex
    result[NIRIZAN_SPAN_ID_SOURCE] = span_id_source
    result[NIRIZAN_TRACE_ID_SOURCE] = trace_id_source
    if sampled is not None:
        result[OTEL_SAMPLED] = sampled
    if trace_state:
        result[OTEL_TRACE_STATE] = truncate_attribute_value(trace_state)
    if status_code:
        result[OTEL_STATUS_CODE] = status_code
    if status_description:
        result[OTEL_STATUS_DESCRIPTION] = truncate_attribute_value(status_description)

    return result


# ---------------------------------------------------------------------------
# Per-trace buffer
# ---------------------------------------------------------------------------


class _TraceBuffer:
    """Per-trace buffer of ``ReadableSpan`` objects awaiting assembly."""

    __slots__ = (
        "otel_trace_id",
        "spans",
        "first_seen",
        "last_seen",
        "open_spans",
        "has_untracked_start",
        "has_untracked_end",
        "cap_warned",
    )

    def __init__(self, otel_trace_id: int, now: float) -> None:
        self.otel_trace_id = otel_trace_id
        self.spans: dict[int, ReadableSpan] = {}
        self.first_seen = now
        self.last_seen = now
        self.open_spans = 0
        # True once a start marker for this trace was dropped on queue
        # saturation, so the open-span count can no longer be trusted to
        # reach zero on its own. See _consume_dropped_start.
        self.has_untracked_start = False
        # True once an ended span for this trace was dropped on queue
        # saturation. The open-span count is then too high and will never
        # reach zero, so idle detection must not wait for it.
        self.has_untracked_end = False
        self.cap_warned = False

    def mark_started(self, now: float) -> None:
        """Increment active open span count and update last_seen timestamp."""
        self.open_spans += 1
        self.last_seen = now

    def add(self, span: ReadableSpan, now: float) -> bool:
        """Add a span to the buffer, keyed by its OTel span_id."""
        ctx = _get_span_context(span)
        if ctx is None:
            return False
        is_duplicate = ctx.span_id in self.spans
        self.spans[ctx.span_id] = span
        self.last_seen = now
        if self.open_spans > 0:
            self.open_spans -= 1
        return is_duplicate

    def discard(self, now: float) -> None:
        """Account for an ended span that is deliberately not stored."""
        self.last_seen = now
        if self.open_spans > 0:
            self.open_spans -= 1


def _start_key(buf: _TraceBuffer, otel_span_id: int) -> tuple[int, int]:
    """Deterministic ordering key: start time, then OTel span id."""
    span = buf.spans.get(otel_span_id)
    return (_int_or_zero(getattr(span, "start_time", None)), otel_span_id)


# ---------------------------------------------------------------------------
# Parent resolution
# ---------------------------------------------------------------------------


class _ParentResolution:
    """Output of ``_resolve_parents``: per-candidate effective parent linkage."""

    __slots__ = ("parent_of", "synthetic_origin", "dropped", "cycles_broken")

    def __init__(self) -> None:
        self.parent_of: dict[int, int | None] = {}
        self.synthetic_origin: dict[int, int] = {}
        self.dropped: set[int] = set()
        self.cycles_broken = 0


def _resolve_parents(
    buf: _TraceBuffer,
    kind_map: Mapping[int, SpanKind],
    orphan_policy: Literal["emit", "drop"],
) -> _ParentResolution:
    """Resolve every kind-recognized candidate's effective parent.

    Each candidate is linked to its nearest surviving ancestor. Spans that
    were skipped (for example because their kind was not recognized) are
    transparent: their children are re-attached to the next ancestor up.

    * A span with no parent, or whose parent is a **remote** parent that is not
      part of this trace buffer (the parent lives in an upstream service), is a
      root. It is not an orphan.
    * A span whose local parent is simply missing is an orphan, handled
      according to ``orphan_policy``.
    * A cyclic parent chain, which a conformant SDK cannot produce, is broken
      by promoting one span to a root. Candidates are visited in start-time
      order, so which span is promoted does not depend on arrival order.

    The walk is iterative with memoization, so very deep chains cannot hit the
    interpreter's recursion limit and each span is resolved exactly once.
    """
    result = _ParentResolution()
    memo: dict[int, tuple[str, int | None]] = {}

    def physical_parent(otel_span_id: int) -> int | None:
        span = buf.spans.get(otel_span_id)
        if span is None:
            return None
        parent_ctx = _get_parent_context(span)
        if parent_ctx is None or not is_valid_otel_span_id(parent_ctx.span_id):
            return None
        if getattr(parent_ctx, "is_remote", False) is True and parent_ctx.span_id not in buf.spans:
            return None
        return parent_ctx.span_id

    for start in sorted(kind_map, key=lambda oid: _start_key(buf, oid)):
        if start in memo:
            continue

        # Climb until we reach a root, a missing ancestor, a memoized node, or a cycle.
        path: list[int] = []
        on_path: set[int] = set()
        current = start
        while True:
            cached = memo.get(current)
            if cached is not None:
                upstream = cached
                break
            if current in on_path:
                # The previous span on the path points back into the path.
                upstream = (_SIG_ROOT, None)
                result.cycles_broken += 1
                break
            if current not in buf.spans:
                upstream = (_SIG_MISSING, current)
                break
            on_path.add(current)
            path.append(current)
            parent_id = physical_parent(current)
            if parent_id is None:
                upstream = (_SIG_ROOT, None)
                break
            current = parent_id

        # Descend from the ancestor end of the path back to ``start``.
        for x in reversed(path):
            if x in kind_map:
                if upstream[0] == _SIG_ROOT:
                    result.parent_of[x] = None
                elif upstream[0] == _SIG_ATTACH:
                    result.parent_of[x] = upstream[1]
                else:
                    origin = upstream[1]
                    assert origin is not None
                    if orphan_policy == "drop":
                        result.dropped.add(x)
                    else:
                        result.parent_of[x] = origin
                        result.synthetic_origin[x] = origin

                signal = (_SIG_ATTACH, x) if x not in result.dropped else upstream
            else:
                signal = upstream
            memo[x] = signal
            upstream = signal

    return result


# ---------------------------------------------------------------------------
# Fork handling
# ---------------------------------------------------------------------------

# Processors that are alive in this process. After ``fork`` the child has none
# of the parent's threads, so every live processor must restart its consumer.
# This mirrors what the OpenTelemetry SDK's own batch processors do.
_LIVE_PROCESSORS: weakref.WeakSet[NiriZanSpanProcessor] = weakref.WeakSet()


def _reinit_processors_after_fork() -> None:
    for processor in list(_LIVE_PROCESSORS):
        try:
            processor._reinit_after_fork()
        except Exception:
            logger.exception("Failed to reinitialize NiriZanSpanProcessor after fork")


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reinit_processors_after_fork)


# ---------------------------------------------------------------------------
# Span processor
# ---------------------------------------------------------------------------


class NiriZanSpanProcessor(SpanProcessor):
    """OTel ``SpanProcessor`` that assembles NiriZan ``Trace`` objects.

    Inherits from ``opentelemetry.sdk.trace.SpanProcessor`` to provide safe default
    no-op implementations for internal SDK hooks such as ``_on_ending``.

    Spans created by NiriZan's own OTel exporter (instrumentation scope
    ``nirizan``) are skipped by default, so attaching both bridge directions to
    one provider cannot create an export/ingest loop. Pass
    ``ignore_own_scope=False`` to ingest them, for example in round-trip tests.
    """

    def __init__(
        self,
        sink: ThreadSafeTraceSink,
        *,
        idle_timeout_seconds: float = 5.0,
        max_trace_age_seconds: float = 300.0,
        max_buffered_traces: int = 1000,
        max_queue_size: int = _DEFAULT_MAX_QUEUE_SIZE,
        max_spans_per_trace: int = _DEFAULT_MAX_SPANS_PER_TRACE,
        orphan_policy: Literal["emit", "drop"] = "emit",
        unrecognized_span_policy: Literal["drop", "generation"] = "drop",
        ignore_own_scope: bool = True,
        trust_stashed_ids: bool = False,
        max_payload_chars: int = _DEFAULT_MAX_PAYLOAD_CHARS,
        max_buffered_spans: int = _DEFAULT_MAX_BUFFERED_SPANS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        config = ProcessorConfig(
            idle_timeout_seconds=idle_timeout_seconds,
            max_trace_age_seconds=max_trace_age_seconds,
            max_buffered_traces=max_buffered_traces,
            max_queue_size=max_queue_size,
            max_spans_per_trace=max_spans_per_trace,
            orphan_policy=orphan_policy,
            unrecognized_span_policy=unrecognized_span_policy,
            ignore_own_scope=ignore_own_scope,
            trust_stashed_ids=trust_stashed_ids,
            max_payload_chars=max_payload_chars,
            max_buffered_spans=max_buffered_spans,
        )

        self._config = config
        self._sink = sink
        self._idle_timeout = config.idle_timeout_seconds
        self._max_age = config.max_trace_age_seconds
        self._max_buffered = config.max_buffered_traces
        self._max_queue_size = config.max_queue_size
        self._orphan_policy = config.orphan_policy
        self._unrecognized_span_policy = config.unrecognized_span_policy
        self._clock = clock
        # Running count of spans currently held across every buffered trace.
        # Written only by the consumer thread (in _buffer_span and
        # _flush_trace), so no lock is needed; _enforce_buffer_cap reads it
        # from the same thread.
        self._buffered_spans: int = 0

        self._queue: queue.Queue[Any] = queue.Queue(maxsize=config.max_queue_size)
        self._buffers: dict[int, _TraceBuffer] = {}
        self._recent_flushes: dict[int, None] = {}
        # Trace IDs whose start marker (or ended span) was dropped on queue
        # saturation, keyed in insertion order so the oldest can be evicted once
        # the bound is hit. Written by the producer thread (on_start/on_end),
        # read and cleared by the consumer thread. Both sides go through
        # _stats_lock.
        self._dropped_start_traces: dict[int, None] = {}
        self._dropped_end_traces: dict[int, None] = {}
        self._stats: dict[str, int] = {}
        self._stats_lock = threading.Lock()
        self._shutdown = threading.Event()

        self._last_sweep: float = self._clock()
        self._last_queue_full_warning: float = 0.0

        _LIVE_PROCESSORS.add(self)
        self._start_consumer()

        if config.unrecognized_span_policy == "generation":
            logger.warning(
                "NiriZanSpanProcessor started with unrecognized_span_policy="
                "'generation': every span with no recognizable NiriZan or "
                "gen_ai.* attribute will be labeled GENERATION."
            )

        logger.debug("NiriZanSpanProcessor started (%s)", config.model_dump())

    @classmethod
    def from_config(
        cls,
        sink: ThreadSafeTraceSink,
        config: ProcessorConfig,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> NiriZanSpanProcessor:
        """Build a processor from an already validated ``ProcessorConfig``."""
        return cls(sink, clock=clock, **config.model_dump())

    @property
    def config(self) -> ProcessorConfig:
        """The validated settings this processor was built with."""
        return self._config

    def _start_consumer(self) -> None:
        # The thread is handed the queue and shutdown event it must serve, instead
        # of reading them from ``self`` on every iteration. If ``_reinit_after_fork``
        # replaces them, a thread that predates the replacement notices it has been
        # superseded and retires, rather than competing with its replacement for
        # the new queue and the shared buffers.
        self._consumer = threading.Thread(
            target=self._consume_loop,
            args=(self._queue, self._shutdown),
            name="nirizan-otel-span-consumer",
            daemon=True,
        )
        self._consumer.start()

    def _reinit_after_fork(self) -> None:
        """Rebuild thread-bound state in a forked child process.

        The child inherits copies of the parent's queue, buffers and locks, but
        none of its threads, so a lock that another thread held at fork time
        would never be released. Everything is replaced and the consumer is
        restarted. Spans buffered by the parent belong to the parent and are
        not re-emitted by the child. Items still waiting in the superseded queue
        are discarded. A processor that was already shut down stays shut down.
        """
        if self._shutdown.is_set():
            return
        self._queue = queue.Queue(maxsize=self._config.max_queue_size)
        self._buffers = {}
        self._buffered_spans = 0
        self._recent_flushes = {}
        self._dropped_start_traces = {}
        self._dropped_end_traces = {}
        self._stats = {}
        self._stats_lock = threading.Lock()
        self._shutdown = threading.Event()
        self._last_sweep = self._clock()
        self._start_consumer()

    # -- SpanProcessor interface ------------------------------------------------

    def on_start(
        self,
        span: ReadableSpan,
        parent_context: Context | None = None,
    ) -> None:
        """Callback executed when an OTel span starts.

        Enqueues a start marker to increment the active open span count, preventing
        long-running spans from being prematurely flushed by the idle sweep.
        """
        if self._shutdown.is_set():
            return
        if self._is_own_scope(span):
            return
        ctx = _get_span_context(span)
        if ctx is None or not is_valid_otel_trace_id(ctx.trace_id):
            return
        try:
            self._queue.put_nowait((_START_MARKER, ctx.trace_id, self._clock()))
        except queue.Full:
            # Drop start marker non-blocking on queue saturation to avoid stalling
            # app execution. Record which trace missed it so the consumer thread
            # can avoid idle-flushing that specific trace while one of its spans
            # may still be open (see _consume_dropped_start, _sweep_idle_traces).
            self._note_dropped_marker(self._dropped_start_traces, ctx.trace_id)

    def on_end(self, span: ReadableSpan) -> None:
        """Push a completed OTel span to the consumer thread."""
        if self._shutdown.is_set():
            return
        if self._is_own_scope(span):
            self._record_stat(StatReason.OWN_SCOPE_SKIPPED)
            return
        try:
            self._queue.put_nowait(span)
        except queue.Full:
            # The span is lost, and so is the signal that it ended. Remember the
            # trace so its open-span count is not waited on forever.
            ctx = _get_span_context(span)
            if ctx is not None and is_valid_otel_trace_id(ctx.trace_id):
                self._note_dropped_marker(self._dropped_end_traces, ctx.trace_id)
            else:
                self._record_stat(StatReason.QUEUE_FULL)
            now = self._clock()
            if now - self._last_queue_full_warning >= _QUEUE_FULL_WARNING_INTERVAL_SECONDS:
                self._last_queue_full_warning = now
                logger.warning(
                    "NiriZanSpanProcessor queue is full (max_queue_size=%d); "
                    "dropping OTel span '%s'.",
                    self._max_queue_size,
                    getattr(span, "name", "<unnamed>"),
                )
        except Exception:
            logger.exception("Failed to enqueue OTel span in NiriZanSpanProcessor")

    def shutdown(self) -> None:
        """Stop the consumer thread, flush all open traces, and join."""
        self._shutdown.set()
        try:
            self._queue.put_nowait(_SHUTDOWN_SENTINEL)
        except queue.Full:
            # Saturated queue; consumer thread will observe self._shutdown on next timeout
            self._record_stat(StatReason.QUEUE_FULL)

        self._consumer.join(timeout=5.0)
        if self._consumer.is_alive():
            logger.warning("NiriZanSpanProcessor consumer thread did not exit within 5s.")

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Block until the consumer has flushed every trace that has finished.

        Like the OpenTelemetry SDK's own processors, this exports what has
        already ended. A trace that still has open spans stays buffered, so its
        remaining spans are not lost as late arrivals; it is flushed once it
        finishes, goes idle, or reaches its maximum age. ``shutdown`` flushes
        everything regardless.

        Returns ``True`` if flush completed before timeout, or ``False`` if shutdown
        or queue saturation prevented the flush request from being enqueued.
        """
        if self._shutdown.is_set():
            return False

        done_event = threading.Event()
        deadline = self._clock() + (timeout_millis / 1000.0)
        try:
            self._queue.put(
                (_FLUSH_SENTINEL, done_event),
                timeout=max(0.0, deadline - self._clock()),
            )
        except queue.Full:
            return False

        remaining = max(0.0, deadline - self._clock())
        return done_event.wait(timeout=remaining)

    def get_stats(self) -> dict[str, int]:
        """Return a snapshot of drop/duplicate counters, keyed by reason.

        Keys are the values of ``StatReason``.
        """
        with self._stats_lock:
            return dict(self._stats)

    def _record_stat(self, reason: StatReason | str) -> None:
        key = str(reason)
        with self._stats_lock:
            self._stats[key] = self._stats.get(key, 0) + 1

    def _is_own_scope(self, span: Any) -> bool:
        return self._config.ignore_own_scope and _scope_name(span) == NIRIZAN_INSTRUMENTATION_SCOPE

    def _note_dropped_marker(self, table: dict[int, None], otel_trace_id: int) -> None:
        """Remember that a start marker or ended span for this trace was dropped."""
        with self._stats_lock:
            table[otel_trace_id] = None
            if len(table) > _RECENT_FLUSHES_MAX:
                oldest = next(iter(table))
                del table[oldest]
            key = str(StatReason.QUEUE_FULL)
            self._stats[key] = self._stats.get(key, 0) + 1

    def _consume_flag(self, table: dict[int, None], otel_trace_id: int) -> bool:
        with self._stats_lock:
            if otel_trace_id in table:
                del table[otel_trace_id]
                return True
            return False

    def _consume_dropped_start(self, otel_trace_id: int) -> bool:
        """Return ``True`` and forget the flag if a start marker for this trace was dropped.

        Called from the consumer thread only, whenever it creates or reuses a
        ``_TraceBuffer`` for ``otel_trace_id``, so the resulting
        ``has_untracked_start`` flag is set at most once per drop.
        """
        return self._consume_flag(self._dropped_start_traces, otel_trace_id)

    def _consume_dropped_end(self, otel_trace_id: int) -> bool:
        """Return ``True`` and forget the flag if an ended span for this trace was dropped."""
        return self._consume_flag(self._dropped_end_traces, otel_trace_id)

    def _apply_pending_flags(self, otel_trace_id: int, buf: _TraceBuffer) -> None:
        if self._consume_dropped_start(otel_trace_id):
            buf.has_untracked_start = True
        if self._consume_dropped_end(otel_trace_id):
            buf.has_untracked_end = True

    # -- Consumer thread --------------------------------------------------------

    def _guarded(self, fn: Callable[..., None], *args: Any) -> None:
        """Run one unit of consumer work; an unexpected error must not kill the thread."""
        try:
            fn(*args)
        except Exception:
            self._record_stat(StatReason.CONSUMER_ERROR)
            logger.exception("Unexpected error in NiriZanSpanProcessor consumer; continuing.")

    def _consume_loop(self, work_queue: queue.Queue[Any], shutdown: threading.Event) -> None:
        """Drain the queue, buffer spans, flush traces on idle or age.

        ``work_queue`` and ``shutdown`` are the objects this thread was started for.
        A thread whose queue is no longer the processor's current queue has been
        superseded by ``_reinit_after_fork``. It exits without processing any item,
        including one it had already taken from its old queue, so it touches no
        shared state.
        """
        while not shutdown.is_set():
            try:
                item = work_queue.get(timeout=self._idle_timeout / 2.0)
            except queue.Empty:
                if work_queue is not self._queue:
                    return
                self._guarded(self._idle_tick)
                continue

            if work_queue is not self._queue:
                return

            if item is _SHUTDOWN_SENTINEL:
                break

            self._guarded(self._process_item, item)

        # Only a thread serving the current queue can leave the loop above: a
        # superseded thread returns early, and the shutdown event and sentinel
        # always belong to the current queue.
        self._guarded(self._drain_and_flush)

    def _idle_tick(self) -> None:
        self._sweep_idle_traces()
        self._last_sweep = self._clock()

    def _process_item(self, item: Any) -> None:
        if _is_flush_request(item):
            try:
                self._flush_quiescent(reason="force_flush")
            finally:
                item[1].set()
            return

        if _is_start_marker(item):
            _, otel_trace_id, ts = item
            self._mark_span_started(otel_trace_id, ts)
            self._enforce_buffer_cap()
            return

        self._buffer_span(item)
        self._enforce_buffer_cap()

        now = self._clock()
        if self._queue.empty() or (now - self._last_sweep) >= self._idle_timeout / 2.0:
            self._last_sweep = now
            self._sweep_idle_traces()

    def _drain_and_flush(self) -> None:
        """Shutdown path: process whatever is still queued, then flush everything."""
        pending_flush_events: list[threading.Event] = []
        try:
            while True:
                try:
                    item = self._queue.get_nowait()
                except queue.Empty:
                    break
                if item is _SHUTDOWN_SENTINEL:
                    continue
                if _is_flush_request(item):
                    pending_flush_events.append(item[1])
                    continue
                if _is_start_marker(item):
                    _, otel_trace_id, ts = item
                    self._guarded(self._mark_span_started, otel_trace_id, ts)
                    continue
                self._guarded(self._buffer_span, item)

            self._flush_all(reason="shutdown")
        finally:
            for event in pending_flush_events:
                event.set()

    def _mark_span_started(self, otel_trace_id: int, now: float) -> None:
        if otel_trace_id in self._recent_flushes:
            return
        buf = self._buffers.get(otel_trace_id)
        if buf is None:
            buf = _TraceBuffer(otel_trace_id, now)
            self._buffers[otel_trace_id] = buf
        self._apply_pending_flags(otel_trace_id, buf)
        buf.mark_started(now)

    def _buffer_span(self, span: ReadableSpan) -> None:
        ctx = _get_span_context(span)
        if ctx is None:
            logger.warning(
                "Skipping OTel span '%s': get_span_context() returned None",
                getattr(span, "name", "<unnamed>"),
            )
            self._record_stat(StatReason.INVALID_SPAN_CONTEXT)
            return

        if not is_valid_otel_trace_id(ctx.trace_id):
            logger.warning(
                "Skipping OTel span '%s': invalid all-zeros trace_id",
                getattr(span, "name", "<unnamed>"),
            )
            self._record_stat(StatReason.INVALID_TRACE_ID)
            return

        if not is_valid_otel_span_id(ctx.span_id):
            logger.warning(
                "Skipping OTel span '%s': invalid all-zeros span_id",
                getattr(span, "name", "<unnamed>"),
            )
            self._record_stat(StatReason.INVALID_SPAN_ID)
            return

        if ctx.trace_id in self._recent_flushes:
            logger.warning(
                "Dropping late-arriving span '%s' for already-flushed OTel trace_id=%d",
                getattr(span, "name", "<unnamed>"),
                ctx.trace_id,
            )
            self._record_stat(StatReason.LATE_ARRIVAL)
            return

        now = self._clock()
        buf = self._buffers.get(ctx.trace_id)
        if buf is None:
            buf = _TraceBuffer(ctx.trace_id, now)
            self._buffers[ctx.trace_id] = buf
        self._apply_pending_flags(ctx.trace_id, buf)

        if (
            ctx.span_id not in buf.spans
            and len(buf.spans) >= self._config.max_spans_per_trace
        ):
            self._record_stat(StatReason.TRACE_SPAN_CAP)
            if not buf.cap_warned:
                buf.cap_warned = True
                logger.warning(
                    "OTel trace_id=%d reached max_spans_per_trace=%d; "
                    "further spans of this trace are dropped.",
                    ctx.trace_id,
                    self._config.max_spans_per_trace,
                )
            buf.discard(now)
            return

        was_duplicate = buf.add(span, now)
        if not was_duplicate:
            self._buffered_spans += 1
        if was_duplicate:
            logger.warning(
                "Duplicate OTel span_id=%016x within trace_id=%d",
                ctx.span_id,
                ctx.trace_id,
            )
            self._record_stat(StatReason.DUPLICATE_SPAN_ID)

    def _is_idle_flushable(self, buf: _TraceBuffer, now: float) -> bool:
        """Whether an idle trace may be flushed.

        Normally a trace is flushed on idle only when no spans are open, and only
        when the open-span count can be trusted. A dropped start marker makes the
        count too low (it could reach zero early), so such a trace waits for its
        maximum age. A dropped ended span makes the count too high (it can never
        reach zero), so such a trace is flushed after the idle timeout alone.
        """
        if now - buf.last_seen < self._idle_timeout:
            return False
        if buf.has_untracked_start:
            return False
        if buf.has_untracked_end:
            return True
        return buf.open_spans == 0

    @staticmethod
    def _is_quiescent(buf: _TraceBuffer) -> bool:
        """Whether a trace has demonstrably finished: no open spans, count trustworthy."""
        return buf.open_spans == 0 and not buf.has_untracked_start and not buf.has_untracked_end

    def _sweep_idle_traces(self) -> None:
        now = self._clock()
        to_flush: list[tuple[int, str]] = []
        for trace_id, buf in self._buffers.items():
            self._apply_pending_flags(trace_id, buf)
            if now - buf.first_seen >= self._max_age:
                to_flush.append((trace_id, "max_age"))
            elif self._is_idle_flushable(buf, now):
                to_flush.append((trace_id, "idle"))
        for trace_id, reason in to_flush:
            self._flush_trace(trace_id, reason=reason)

    def _over_buffer_cap(self) -> bool:
        return (
            len(self._buffers) > self._max_buffered
            or self._buffered_spans > self._config.max_buffered_spans
        )

    def _enforce_buffer_cap(self) -> None:
        if not self._over_buffer_cap():
            return
        # Evict traces that look finished first, oldest first. A trace that still
        # has open spans is evicted last, because evicting it loses the rest of
        # its spans as late arrivals. Unlike the trace-count cap, the number of
        # traces that must be evicted to clear the span budget is not known in
        # advance (each trace holds a different number of spans), so eviction
        # proceeds one trace at a time until both budgets are satisfied.
        while self._over_buffer_cap() and self._buffers:
            trace_id, buf = min(
                self._buffers.items(),
                key=lambda kv: (not self._is_quiescent(kv[1]), kv[1].first_seen),
            )
            if not self._is_quiescent(buf):
                self._record_stat(StatReason.EVICTED_OPEN_TRACE)
            logger.warning(
                "Evicting incomplete OTel trace_id=%d: buffer cap %d traces / %d spans exceeded",
                trace_id,
                self._max_buffered,
                self._config.max_buffered_spans,
            )
            self._flush_trace(trace_id, reason="buffer_cap")

    def _flush_all(self, *, reason: str) -> None:
        for trace_id in list(self._buffers.keys()):
            self._flush_trace(trace_id, reason=reason)

    def _flush_quiescent(self, *, reason: str) -> None:
        """Flush only traces that have finished; leave in-flight traces buffered."""
        for trace_id, buf in list(self._buffers.items()):
            self._apply_pending_flags(trace_id, buf)
            if self._is_quiescent(buf):
                self._flush_trace(trace_id, reason=reason)

    def _flush_trace(self, otel_trace_id: int, *, reason: str) -> None:
        buf = self._buffers.pop(otel_trace_id, None)
        if buf is None:
            return
        self._buffered_spans -= len(buf.spans)

        self._recent_flushes[otel_trace_id] = None
        if len(self._recent_flushes) > _RECENT_FLUSHES_MAX:
            oldest = next(iter(self._recent_flushes))
            del self._recent_flushes[oldest]

        try:
            trace = self._assemble_trace(buf)
        except Exception:
            logger.exception(
                "Failed to assemble NiriZan Trace from OTel trace_id=%d (reason=%s)",
                otel_trace_id,
                reason,
            )
            return

        if trace is None or not trace.spans:
            logger.debug(
                "Skipping empty Trace for OTel trace_id=%d (reason=%s)",
                otel_trace_id,
                reason,
            )
            return

        try:
            self._sink.enqueue_trace(trace)
        except Exception:
            logger.exception(
                "ThreadSafeTraceSink.enqueue_trace raised for OTel trace_id=%d", otel_trace_id
            )

    # -- Trace assembly ---------------------------------------------------------

    def _assemble_trace(self, buf: _TraceBuffer) -> Trace | None:
        if not buf.spans:
            return None

        nirizan_trace_id, trace_id_source = _extract_nirizan_trace_id(
            buf.spans, buf.otel_trace_id, self._config.trust_stashed_ids
        )
        if self._config.trust_stashed_ids and _has_conflicting_trace_ids(buf.spans):
            self._record_stat(StatReason.CONFLICTING_TRACE_ID)
            logger.warning(
                "OTel trace_id=%d carries more than one distinct nirizan.trace_id; using %s",
                buf.otel_trace_id,
                nirizan_trace_id,
            )

        ordered_ids = sorted(buf.spans, key=lambda oid: _start_key(buf, oid))

        # Pass 1: decide which spans become NiriZan spans, and of which kind.
        kind_map: dict[int, SpanKind] = {}
        for otel_span_id in ordered_ids:
            otel_attrs = getattr(buf.spans[otel_span_id], "attributes", None) or {}
            inferred_kind = _infer_span_kind(otel_attrs)
            if inferred_kind is not None:
                kind_map[otel_span_id] = inferred_kind
            elif self._unrecognized_span_policy == "generation":
                kind_map[otel_span_id] = SpanKind.GENERATION
            else:
                self._record_stat(StatReason.UNRECOGNIZED_KIND)

        if not kind_map:
            return None

        # Pass 2: give every surviving span a NiriZan id that is unique in this trace.
        id_map, source_map = self._assign_nirizan_ids(buf, kind_map)
        kind_map = {oid: kind for oid, kind in kind_map.items() if oid in id_map}

        # Pass 3: build and validate every span now, with no parent. A span that
        # cannot be converted leaves the candidate set here, so the parent
        # resolution below treats it like any other skipped span and children are
        # re-attached to the next ancestor instead of pointing at a missing span.
        base_spans: dict[int, Span] = {}
        for otel_span_id in list(kind_map):
            converted = self._convert_span(
                span=buf.spans[otel_span_id],
                nirizan_trace_id=nirizan_trace_id,
                nirizan_span_id=id_map[otel_span_id],
                parent_nirizan_id=None,
                kind=kind_map[otel_span_id],
                span_id_source=source_map[otel_span_id],
                trace_id_source=trace_id_source,
            )
            if converted is None:
                del kind_map[otel_span_id]
            else:
                base_spans[otel_span_id] = converted

        if not kind_map:
            return None

        # Pass 4: resolve parents among the spans that will actually be emitted.
        resolution = _resolve_parents(buf, kind_map, self._orphan_policy)
        for _ in range(resolution.cycles_broken):
            self._record_stat(StatReason.CYCLE_BROKEN)

        parent_map: dict[int, UUID | None] = {}
        kept_ids: list[int] = []
        for otel_span_id in kind_map:
            if otel_span_id in resolution.dropped:
                self._record_stat(StatReason.ORPHAN_PARENT_MISSING)
                continue

            ancestor_id = resolution.parent_of.get(otel_span_id)
            if ancestor_id is None:
                parent_map[otel_span_id] = None
            elif otel_span_id in resolution.synthetic_origin:
                parent_map[otel_span_id] = otel_span_id_to_uuid(ancestor_id)
                self._record_stat(StatReason.ORPHAN_EMITTED)
            else:
                parent_map[otel_span_id] = id_map[ancestor_id]
            kept_ids.append(otel_span_id)

        if not kept_ids:
            return None

        kept_ids.sort(key=lambda oid: _start_key(buf, oid))

        root_span = self._find_root_span(buf, kept_ids, parent_map)
        application_name = self._resolve_application_name(buf, kept_ids, root_span)
        session_id = self._find_session_id({oid: buf.spans[oid] for oid in kept_ids})

        nirizan_spans: list[Span] = []
        for otel_span_id in kept_ids:
            base = base_spans[otel_span_id]
            parent = parent_map[otel_span_id]
            nirizan_spans.append(
                base if parent is None else base.model_copy(update={"parent_span_id": parent})
            )

        return Trace(
            trace_id=nirizan_trace_id,
            application_name=application_name,
            spans=nirizan_spans,
            created_at=datetime.now(UTC),
            session_id=session_id,
        )

    def _assign_nirizan_ids(
        self,
        buf: _TraceBuffer,
        kind_map: Mapping[int, SpanKind],
    ) -> tuple[dict[int, UUID], dict[int, str]]:
        """Assign a NiriZan span id to each candidate, unique within the trace.

        ``Span.span_id`` is unique per span. Two OTel spans can nevertheless stash
        the same ``nirizan.span_id`` (a span exported twice, or a faulty
        producer). The earlier span, by start time, keeps the stashed id. Later
        ones fall back to the id derived from their own OTel span id, which is
        unique because OTel span ids are, and are marked as derived.
        """
        id_map: dict[int, UUID] = {}
        source_map: dict[int, str] = {}
        used: set[UUID] = set()
        for otel_span_id in kind_map:
            span = buf.spans[otel_span_id]
            ctx = _get_span_context(span)
            if ctx is None:
                continue
            nirizan_id, source = _extract_nirizan_span_id(
                span, ctx, self._config.trust_stashed_ids
            )
            if nirizan_id in used:
                self._record_stat(StatReason.DUPLICATE_NIRIZAN_SPAN_ID)
                derived = otel_span_id_to_uuid(ctx.span_id)
                logger.warning(
                    "Duplicate NiriZan span_id %s on OTel span '%s'; using derived id %s",
                    nirizan_id,
                    getattr(span, "name", "<unnamed>"),
                    derived,
                )
                if derived in used:
                    continue
                nirizan_id, source = derived, ID_SOURCE_DERIVED
            used.add(nirizan_id)
            id_map[otel_span_id] = nirizan_id
            source_map[otel_span_id] = source
        return id_map, source_map

    @staticmethod
    def _find_root_span(
        buf: _TraceBuffer,
        kept_ids: Sequence[int],
        parent_map: Mapping[int, UUID | None],
    ) -> ReadableSpan | None:
        """Return the first surviving span with no effective parent."""
        for otel_span_id in kept_ids:
            if parent_map.get(otel_span_id) is None:
                return buf.spans[otel_span_id]
        return None

    @staticmethod
    def _get_service_name(span: ReadableSpan) -> str | None:
        resource = getattr(span, "resource", None)
        if resource is None:
            return None
        attrs = getattr(resource, "attributes", None)
        if not attrs:
            return None
        value = attrs.get(_SERVICE_NAME_RESOURCE_KEY)
        return value if isinstance(value, str) else None

    def _resolve_application_name(
        self,
        buf: _TraceBuffer,
        kept_ids: Sequence[int],
        root_span: ReadableSpan | None,
    ) -> str:
        """Resolve the trace's ``application_name`` from ``service.name``."""
        if root_span is not None:
            name = self._get_service_name(root_span)
            if name:
                return name
        for otel_span_id in kept_ids:
            name = self._get_service_name(buf.spans[otel_span_id])
            if name:
                return name
        return "unknown"

    @staticmethod
    def _find_session_id(spans: Mapping[int, ReadableSpan]) -> UUID | None:
        for span in spans.values():
            attrs = getattr(span, "attributes", None) or {}
            raw = attrs.get(NIRIZAN_SESSION_ID)
            if isinstance(raw, str):
                try:
                    parsed = UUID(raw)
                except ValueError:
                    continue
                if parsed.int != 0:
                    return parsed
        return None

    def _convert_span(
        self,
        *,
        span: ReadableSpan,
        nirizan_trace_id: UUID,
        nirizan_span_id: UUID,
        parent_nirizan_id: UUID | None,
        kind: SpanKind,
        span_id_source: str,
        trace_id_source: str,
    ) -> Span | None:
        """Build the final NiriZan ``Span`` from already-resolved values.

        Any failure (an out-of-range timestamp, a validation error) is counted and
        logged, and the span is skipped; it never aborts the whole trace.
        """
        ctx = _get_span_context(span)
        if ctx is None:
            return None

        try:
            otel_attrs = getattr(span, "attributes", None) or {}
            input_payload, output_payload = _extract_payloads(kind, otel_attrs)
            input_payload = _cap_payload(input_payload, self._config.max_payload_chars)
            output_payload = _cap_payload(output_payload, self._config.max_payload_chars)

            started_at = _ns_to_datetime(span.start_time)
            ended_at = _ns_to_datetime(span.end_time)

            name = (span.name or "unnamed")[:_MAX_SPAN_NAME_LENGTH]
            if not name:
                name = "unnamed"

            sampled: bool | None = None
            trace_flags = getattr(ctx, "trace_flags", None)
            if trace_flags is not None:
                try:
                    sampled = bool(trace_flags & TraceFlags.SAMPLED)
                except TypeError:
                    sampled = None

            trace_state_str: str | None = None
            trace_state = getattr(ctx, "trace_state", None)
            if trace_state:
                # ``str(TraceState)`` is a Python list repr, not the W3C value.
                # ``to_header()`` is the standard "k1=v1,k2=v2" serialization.
                try:
                    trace_state_str = trace_state.to_header()
                except Exception:
                    trace_state_str = None

            status_code_str: str | None = None
            status_description: str | None = None
            status = getattr(span, "status", None)
            if status is not None:
                code = getattr(status, "status_code", None)
                if code is None:
                    code = getattr(status, "code", None)
                if code is not None:
                    status_code_str = getattr(code, "name", str(code)).lower()
                desc = getattr(status, "description", None)
                if desc:
                    status_description = str(desc)

            attributes = _convert_attributes(
                otel_attrs,
                service_name=self._get_service_name(span),
                span_id_hex=format(ctx.span_id, "016x"),
                span_id_source=span_id_source,
                trace_id_source=trace_id_source,
                sampled=sampled,
                trace_state=trace_state_str,
                status_code=status_code_str,
                status_description=status_description,
            )

            return Span(
                span_id=nirizan_span_id,
                trace_id=nirizan_trace_id,
                parent_span_id=parent_nirizan_id,
                kind=kind,
                name=name,
                started_at=started_at,
                ended_at=ended_at,
                attributes=attributes,
                input_payload=input_payload,
                output_payload=output_payload,
            )
        except Exception as err:
            self._record_stat(StatReason.CONVERSION_ERROR)
            logger.warning(
                "Failed to convert OTel span '%s' (otel_span_id=%016x): %s",
                getattr(span, "name", "<unnamed>"),
                ctx.span_id,
                err,
            )
            return None
