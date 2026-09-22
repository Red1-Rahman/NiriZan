# src/nirizan/instrumentation/otel/from_otel.py
"""OpenTelemetry span processor that assembles NiriZan Traces from OTel spans.

This module implements the OTel -> NiriZan direction of the bridge. It hooks
into the OpenTelemetry SDK through the ``SpanProcessor`` interface and
produces plain NiriZan ``Trace`` objects, indistinguishable at the type level
from traces assembled by NiriZan's own ``Tracer``.
"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import SpanKind as OTelSpanKind
from opentelemetry.trace import TraceFlags

from nirizan._logging import get_logger
from nirizan.instrumentation.otel.id_mapping import (
    is_valid_otel_span_id,
    is_valid_otel_trace_id,
    otel_span_id_to_uuid,
    otel_trace_id_to_uuid,
)
from nirizan.instrumentation.otel.semconv import (
    GEN_AI_COMPLETION,
    GEN_AI_PROMPT,
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
    OTEL_SAMPLED,
    OTEL_SPAN_ID,
    OTEL_STATUS_CODE,
    OTEL_STATUS_DESCRIPTION,
    OTEL_TRACE_STATE,
    SPAN_ID_SOURCE_DERIVED,
    SPAN_ID_SOURCE_ROUNDTRIP,
    encode_sequence_attribute_value,
    encode_sequence_key,
    is_sequence_key,
    truncate_attribute_value,
)
from nirizan.instrumentation.spans import Span, SpanKind, Trace

logger = get_logger(__name__)

__all__ = ["NiriZanSpanProcessor", "TraceSink"]


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# OTel resource attribute key carrying the service name.
_SERVICE_NAME_RESOURCE_KEY: str = "service.name"

# NiriZan-side attribute key carrying the originating service name for
# non-root spans in a distributed trace. Should be promoted to semconv in a
# follow-up; kept local for now to avoid churning that module on every change.
_OTEL_SERVICE_NAME: str = "otel.service.name"

# Consumer-queue sentinels. Unique objects so they can never be confused with
# a ReadableSpan.
_FLUSH_SENTINEL: object = object()
_SHUTDOWN_SENTINEL: object = object()

# Bound on the set of recently-flushed OTel trace IDs, used to drop late
# spans that would otherwise produce duplicate NiriZan Traces.
_RECENT_FLUSHES_MAX: int = 10_000

# NiriZan Span.name is bounded to 200 chars; OTel does not enforce this.
_MAX_SPAN_NAME_LENGTH: int = 200


# ---------------------------------------------------------------------------
# Sink protocol
# ---------------------------------------------------------------------------


class TraceSink(Protocol):
    """Minimal sync interface for handing an assembled ``Trace`` to a consumer.

    The canonical sink is ``TraceCollector.enqueue_trace``, which stamps
    ``code_commit`` and ``data_snapshot_id`` at ingest time from environment
    variables before persisting. Any object with a matching method satisfies
    this Protocol.

    The method is sync because ``SpanProcessor.on_end`` is sync and the
    consumer thread has no event loop. If a caller's sink is async, they
    should wrap it in a sync adapter that schedules the coroutine onto an
    event loop from the calling thread.
    """

    def enqueue_trace(self, trace: Trace) -> None: ...


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _ns_to_datetime(ns: int | None) -> datetime:
    """Convert nanoseconds-since-epoch to a timezone-aware UTC ``datetime``.

    ``None`` is interpreted as "no timestamp available"; the current time is
    returned in that case rather than raising, since a missing timestamp on an
    ended span is a data-quality issue, not a reason to drop the span.
    """
    if ns is None:
        return datetime.now(UTC)
    seconds, remainder = divmod(int(ns), 1_000_000_000)
    return datetime.fromtimestamp(seconds, tz=UTC).replace(microsecond=remainder // 1000)


def _extract_nirizan_span_id(span: ReadableSpan) -> tuple[UUID, str]:
    """Return ``(NiriZan span_id, provenance source)`` for an OTel span.

    If the OTel span carries a ``nirizan.span_id`` attribute that parses as a
    UUID, that value is used verbatim and the source is marked as
    ``SPAN_ID_SOURCE_ROUNDTRIP``. Otherwise a deterministic UUID is derived
    via ``otel_span_id_to_uuid`` and the source is marked
    ``SPAN_ID_SOURCE_DERIVED``.
    """
    ctx = span.get_span_context()
    attrs = getattr(span, "attributes", None) or {}
    stashed = attrs.get(NIRIZAN_SPAN_ID)
    if isinstance(stashed, str):
        try:
            return UUID(stashed), SPAN_ID_SOURCE_ROUNDTRIP
        except (ValueError, AttributeError):
            # Attribute present but not a valid UUID; fall through to
            # derivation and log at debug level, since this can happen if a
            # user manually set a non-UUID value under the reserved key.
            logger.debug(
                "Ignoring invalid nirizan.span_id attribute '%s' on OTel span '%s'",
                stashed,
                span.name,
            )
    return otel_span_id_to_uuid(ctx.span_id), SPAN_ID_SOURCE_DERIVED


def _infer_span_kind(attrs: Mapping[str, Any]) -> SpanKind:
    """Determine NiriZan ``SpanKind`` from an OTel span's attributes.

    Priority order:

    1. ``nirizan.span.kind`` if present and recognizable. This is the
       lossless value written by ``to_otel.py`` for NiriZan-exported spans.
    2. Attribute-based heuristics for OTel-native spans produced by
       third-party auto-instrumentation, which will not have set the
       NiriZan kind.
    3. Default to ``SpanKind.GENERATION``, since user-facing OTel spans
       without any of the other hints are overwhelmingly LLM calls.
    """
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

    return SpanKind.GENERATION


def _to_str_or_none(value: Any) -> str | None:
    """Coerce an arbitrary attribute value to ``str`` or ``None``."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _extract_payloads(kind: SpanKind, attrs: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Extract ``(input_payload, output_payload)`` for a given span kind.

    This is the inverse of ``to_otel.py``'s per-kind payload mapping. The
    payload attributes are left in the resulting ``Span.attributes`` as well,
    so that OTel-native consumers who do not know about NiriZan can still
    read them.
    """
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


def _convert_attributes(
    otel_attrs: Mapping[str, Any],
    *,
    service_name: str | None,
    span_id_hex: str | None,
    span_id_source: str,
    sampled: bool | None,
    trace_state: str | None,
    status_code: str | None,
    status_description: str | None,
) -> dict[str, str | int | float | bool]:
    """Convert OTel attributes plus captured metadata into NiriZan form.

    NiriZan's ``Span.attributes`` is restricted to primitives. OTel's
    attribute value type is a superset that adds homogeneous sequences; those
    are JSON-encoded into a string under a ``nirizan.seq.``-prefixed key, per
    the plan's conversion rule. All other values are coerced to strings, and
    truncated to ``MAX_ATTR_VALUE_LENGTH`` where applicable.
    """
    result: dict[str, str | int | float | bool] = {}

    for key, value in otel_attrs.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            # bool is a subclass of int in Python; both are valid NiriZan
            # attribute values, so no special handling is required.
            result[key] = value
        elif isinstance(value, (list, tuple)):
            encoded_key = key if is_sequence_key(key) else encode_sequence_key(key)
            try:
                result[encoded_key] = encode_sequence_attribute_value(value)
            except ValueError as err:
                logger.warning("Dropping sequence attribute '%s' from OTel span: %s", key, err)
        else:
            result[key] = truncate_attribute_value(str(value))

    # Bridge-specific metadata.
    if service_name:
        result[_OTEL_SERVICE_NAME] = service_name
    if span_id_hex:
        result[OTEL_SPAN_ID] = span_id_hex
    result[NIRIZAN_SPAN_ID_SOURCE] = span_id_source
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
    """Per-trace buffer of ``ReadableSpan`` objects awaiting assembly.

    Owned exclusively by the consumer thread; no locking required.
    """

    __slots__ = ("otel_trace_id", "spans", "first_seen", "last_seen")

    def __init__(self, otel_trace_id: int, now: float) -> None:
        self.otel_trace_id = otel_trace_id
        self.spans: dict[int, ReadableSpan] = {}
        self.first_seen = now
        self.last_seen = now

    def add(self, span: ReadableSpan, now: float) -> None:
        ctx = span.get_span_context()
        self.spans[ctx.span_id] = span
        self.last_seen = now


# ---------------------------------------------------------------------------
# Span processor
# ---------------------------------------------------------------------------


class NiriZanSpanProcessor:
    """OTel ``SpanProcessor`` that assembles NiriZan ``Trace`` objects.

    See the module docstring for the design rationale. The processor owns one
    background consumer thread; the thread starts in ``__init__`` and is
    stopped by ``shutdown``. Callers who construct a processor and never call
    ``shutdown`` will leak the thread; use a try/finally or a context manager
    in production code.
    """

    def __init__(
        self,
        sink: TraceSink,
        *,
        idle_timeout_seconds: float = 5.0,
        max_trace_age_seconds: float = 300.0,
        max_buffered_traces: int = 1000,
        orphan_policy: Literal["emit", "drop"] = "emit",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if idle_timeout_seconds <= 0:
            raise ValueError("idle_timeout_seconds must be positive.")
        if max_trace_age_seconds <= idle_timeout_seconds:
            raise ValueError("max_trace_age_seconds must be greater than idle_timeout_seconds.")
        if max_buffered_traces < 1:
            raise ValueError("max_buffered_traces must be at least 1.")
        if orphan_policy not in ("emit", "drop"):
            raise ValueError("orphan_policy must be 'emit' or 'drop'.")

        self._sink = sink
        self._idle_timeout = idle_timeout_seconds
        self._max_age = max_trace_age_seconds
        self._max_buffered = max_buffered_traces
        self._orphan_policy = orphan_policy
        self._clock = clock

        self._queue: queue.Queue[Any] = queue.Queue()
        self._buffers: dict[int, _TraceBuffer] = {}
        # Bounded set of OTel trace IDs that have already been flushed, so
        # that late-arriving spans can be dropped rather than producing a
        # duplicate Trace with the same trace_id. Plain dict preserves
        # insertion order on Python 3.7+, so the oldest key can be evicted
        # with `next(iter(...))`.
        self._recent_flushes: dict[int, None] = {}
        self._shutdown = threading.Event()

        self._consumer = threading.Thread(
            target=self._consume_loop,
            name="nirizan-otel-span-consumer",
            daemon=True,
        )
        self._consumer.start()
        logger.debug(
            "NiriZanSpanProcessor started (idle=%.1fs, max_age=%.1fs, "
            "max_buffered=%d, orphan_policy=%s)",
            idle_timeout_seconds,
            max_trace_age_seconds,
            max_buffered_traces,
            orphan_policy,
        )

    # -- SpanProcessor interface ------------------------------------------------

    def on_start(
        self,
        span: ReadableSpan,
        parent_context: Context | None = None,
    ) -> None:
        """No-op: span start is not needed for trace assembly."""

    def on_end(self, span: ReadableSpan) -> None:
        """Push a completed OTel span to the consumer thread.

        This is the hot path. It must not raise (the OTel SDK calls it from
        the instrumented application's threads) and must not block. The
        queue is unbounded, so ``put_nowait`` never blocks.
        """
        if self._shutdown.is_set():
            return
        try:
            self._queue.put_nowait(span)
        except Exception:
            # The queue is unbounded, so this should be unreachable. Log
            # rather than raise, to honour the SpanProcessor contract.
            logger.exception("Failed to enqueue OTel span in NiriZanSpanProcessor")

    def shutdown(self) -> None:
        """Stop the consumer thread, flush all open traces, and join."""
        self._shutdown.set()
        # Wake the consumer if it is blocked on queue.get().
        self._queue.put_nowait(_SHUTDOWN_SENTINEL)
        self._consumer.join(timeout=5.0)
        if self._consumer.is_alive():
            logger.warning("NiriZanSpanProcessor consumer thread did not exit within 5s.")

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Signal the consumer to flush all open traces, then wait briefly.

        Returns ``True`` if the buffer drained before the timeout, ``False``
        otherwise. The check is best-effort: a trace arriving concurrently
        may cause the return value to be ``False`` even though the flush
        succeeded for every trace that existed at signal time.
        """
        if self._shutdown.is_set():
            return True
        self._queue.put_nowait(_FLUSH_SENTINEL)
        deadline = time.monotonic() + (timeout_millis / 1000.0)
        while self._buffers and time.monotonic() < deadline:
            time.sleep(0.005)
        return not self._buffers

    # -- Consumer thread --------------------------------------------------------

    def _consume_loop(self) -> None:
        """Drain the queue, buffer spans, flush traces on idle or age."""
        while not self._shutdown.is_set():
            try:
                item = self._queue.get(timeout=self._idle_timeout / 2.0)
            except queue.Empty:
                self._sweep_idle_traces()
                continue

            if item is _SHUTDOWN_SENTINEL:
                break
            if item is _FLUSH_SENTINEL:
                self._flush_all(reason="force_flush")
                continue

            self._buffer_span(item)
            # Only sweep when the queue is drained, to avoid O(n) work per
            # span during a burst.
            if self._queue.empty():
                self._sweep_idle_traces()
                self._enforce_buffer_cap()

        # Drain any remaining items, then flush everything.
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is _SHUTDOWN_SENTINEL or item is _FLUSH_SENTINEL:
                continue
            self._buffer_span(item)

        self._flush_all(reason="shutdown")

    def _buffer_span(self, span: ReadableSpan) -> None:
        ctx = span.get_span_context()

        if not is_valid_otel_trace_id(ctx.trace_id):
            logger.warning("Skipping OTel span '%s': invalid all-zeros trace_id", span.name)
            return
        if not is_valid_otel_span_id(ctx.span_id):
            logger.warning("Skipping OTel span '%s': invalid all-zeros span_id", span.name)
            return

        if ctx.trace_id in self._recent_flushes:
            logger.warning(
                "Dropping late-arriving span '%s' for already-flushed OTel trace_id=%d",
                span.name,
                ctx.trace_id,
            )
            return

        now = self._clock()
        buf = self._buffers.get(ctx.trace_id)
        if buf is None:
            buf = _TraceBuffer(ctx.trace_id, now)
            self._buffers[ctx.trace_id] = buf
        buf.add(span, now)

    def _sweep_idle_traces(self) -> None:
        now = self._clock()
        to_flush: list[tuple[int, str]] = []
        for trace_id, buf in self._buffers.items():
            if now - buf.last_seen >= self._idle_timeout:
                to_flush.append((trace_id, "idle"))
            elif now - buf.first_seen >= self._max_age:
                to_flush.append((trace_id, "max_age"))
        for trace_id, reason in to_flush:
            self._flush_trace(trace_id, reason=reason)

    def _enforce_buffer_cap(self) -> None:
        if len(self._buffers) <= self._max_buffered:
            return
        ordered = sorted(self._buffers.items(), key=lambda kv: kv[1].first_seen)
        excess = len(self._buffers) - self._max_buffered
        for trace_id, _ in ordered[:excess]:
            logger.warning(
                "Evicting oldest incomplete OTel trace_id=%d: buffer cap %d exceeded",
                trace_id,
                self._max_buffered,
            )
            self._flush_trace(trace_id, reason="buffer_cap")

    def _flush_all(self, *, reason: str) -> None:
        for trace_id in list(self._buffers.keys()):
            self._flush_trace(trace_id, reason=reason)

    def _flush_trace(self, otel_trace_id: int, *, reason: str) -> None:
        buf = self._buffers.pop(otel_trace_id, None)
        if buf is None:
            return

        # Record the flush before assembling, so a concurrent late span for
        # this trace is dropped rather than creating a second buffer.
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
            logger.exception("TraceSink.enqueue_trace raised for OTel trace_id=%d", otel_trace_id)

    # -- Trace assembly ---------------------------------------------------------

    def _assemble_trace(self, buf: _TraceBuffer) -> Trace | None:
        if not buf.spans:
            return None

        nirizan_trace_id = otel_trace_id_to_uuid(buf.otel_trace_id)

        # Pass 1: compute NiriZan span IDs and provenance for every span.
        id_map: dict[int, UUID] = {}
        source_map: dict[int, str] = {}
        for otel_span_id, span in buf.spans.items():
            nirizan_id, source = _extract_nirizan_span_id(span)
            id_map[otel_span_id] = nirizan_id
            source_map[otel_span_id] = source

        # Identify the root span (parent is absent or invalid).
        root_span = self._find_root_span(buf)

        application_name = self._resolve_application_name(buf, root_span)
        session_id = self._find_session_id(buf.spans)

        # Pass 2: convert each ReadableSpan to a NiriZan Span.
        nirizan_spans: list[Span] = []
        for otel_span_id, span in buf.spans.items():
            converted = self._convert_span(
                span=span,
                nirizan_trace_id=nirizan_trace_id,
                nirizan_span_id=id_map[otel_span_id],
                span_id_source=source_map[otel_span_id],
                otel_id_map=id_map,
            )
            if converted is not None:
                nirizan_spans.append(converted)

        if not nirizan_spans:
            return None

        return Trace(
            trace_id=nirizan_trace_id,
            application_name=application_name,
            spans=nirizan_spans,
            created_at=datetime.now(UTC),
            session_id=session_id,
        )

    @staticmethod
    def _find_root_span(buf: _TraceBuffer) -> ReadableSpan | None:
        for span in buf.spans.values():
            parent = span.parent
            if parent is None or not is_valid_otel_span_id(parent.span_id):
                return span
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

    def _resolve_application_name(self, buf: _TraceBuffer, root_span: ReadableSpan | None) -> str:
        if root_span is not None:
            name = self._get_service_name(root_span)
            if name:
                return name
        # Fallback: first span that declares a service name.
        for span in buf.spans.values():
            name = self._get_service_name(span)
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
                    return UUID(raw)
                except ValueError:
                    continue
        return None

    def _convert_span(
        self,
        *,
        span: ReadableSpan,
        nirizan_trace_id: UUID,
        nirizan_span_id: UUID,
        span_id_source: str,
        otel_id_map: Mapping[int, UUID],
    ) -> Span | None:
        ctx = span.get_span_context()
        otel_attrs = getattr(span, "attributes", None) or {}

        kind = _infer_span_kind(otel_attrs)
        input_payload, output_payload = _extract_payloads(kind, otel_attrs)

        # Resolve parent ID, preferring the in-trace map (so an original
        # stashed UUID is preserved) and falling back to uuid5 derivation for
        # parents outside this trace.
        parent_nirizan_id: UUID | None = None
        parent = span.parent
        if parent is not None and is_valid_otel_span_id(parent.span_id):
            parent_nirizan_id = otel_id_map.get(parent.span_id)
            if parent_nirizan_id is None:
                try:
                    parent_nirizan_id = otel_span_id_to_uuid(parent.span_id)
                except ValueError:
                    parent_nirizan_id = None
            if parent_nirizan_id is None and self._orphan_policy == "drop":
                logger.debug(
                    "Dropping orphan span '%s' (parent not resolvable)",
                    span.name,
                )
                return None

        started_at = _ns_to_datetime(span.start_time)
        ended_at = _ns_to_datetime(span.end_time)

        name = (span.name or "unnamed")[:_MAX_SPAN_NAME_LENGTH]
        if not name:
            name = "unnamed"

        # Trace flags: the sampled bit is defined by OTel as 0x01.
        trace_flags = ctx.trace_flags
        sampled: bool | None = None
        if trace_flags is not None:
            sampled = bool(trace_flags & TraceFlags.SAMPLED)

        # Trace state is a vendor-specific key/value map. Serialize as a
        # string for storage in NiriZan's primitive-only attributes dict.
        trace_state_str: str | None = None
        trace_state = getattr(ctx, "trace_state", None)
        if trace_state:
            try:
                trace_state_str = str(trace_state)
            except Exception:
                trace_state_str = None

        # Status is `(StatusCode, description)`; store as two primitive
        # attributes rather than a nested object, per the plan's decision to
        # defer a first-class Span.status field.
        status_code_str: str | None = None
        status_description: str | None = None
        status = getattr(span, "status", None)
        if status is not None:
            code = getattr(status, "status_code", None)
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
            sampled=sampled,
            trace_state=trace_state_str,
            status_code=status_code_str,
            status_description=status_description,
        )

        try:
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
            logger.warning(
                "Failed to convert OTel span '%s' (otel_span_id=%016x): %s",
                span.name,
                ctx.span_id,
                err,
            )
            return None
