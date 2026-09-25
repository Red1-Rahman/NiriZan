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
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry.trace import SpanContext, TraceFlags

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

_SERVICE_NAME_RESOURCE_KEY: str = "service.name"
_OTEL_SERVICE_NAME: str = "otel.service.name"

_FLUSH_SENTINEL: object = object()
_SHUTDOWN_SENTINEL: object = object()
_START_MARKER: object = object()

_RECENT_FLUSHES_MAX: int = 10_000
_MAX_SPAN_NAME_LENGTH: int = 200

_DEFAULT_MAX_QUEUE_SIZE: int = 50_000

_QUEUE_FULL_WARNING_INTERVAL_SECONDS: float = 5.0

_SIG_ROOT: str = "root"
_SIG_ATTACH: str = "attach_to"
_SIG_MISSING: str = "missing"
_SIG_CYCLE: str = "cycle"


# ---------------------------------------------------------------------------
# Sink protocol
# ---------------------------------------------------------------------------


class TraceSink(Protocol):
    """Minimal sync interface for handing an assembled ``Trace`` to a consumer."""

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


def _extract_nirizan_span_id(span: ReadableSpan, ctx: SpanContext) -> tuple[UUID, str]:
    """Return ``(NiriZan span_id, provenance source)`` for an OTel span."""
    attrs = getattr(span, "attributes", None) or {}
    stashed = attrs.get(NIRIZAN_SPAN_ID)
    if isinstance(stashed, str):
        try:
            return UUID(stashed), SPAN_ID_SOURCE_ROUNDTRIP
        except (ValueError, AttributeError):
            logger.debug(
                "Ignoring invalid nirizan.span_id attribute '%s' on OTel span '%s'",
                stashed,
                span.name,
            )
    return otel_span_id_to_uuid(ctx.span_id), SPAN_ID_SOURCE_DERIVED


def _extract_nirizan_trace_id(
    spans: Mapping[int, ReadableSpan], otel_trace_id: int
) -> tuple[UUID, str]:
    """Return ``(NiriZan trace_id, provenance source)`` for a buffered OTel trace."""
    for span in spans.values():
        attrs = getattr(span, "attributes", None) or {}
        stashed = attrs.get(NIRIZAN_TRACE_ID)
        if isinstance(stashed, str):
            try:
                return UUID(stashed), SPAN_ID_SOURCE_ROUNDTRIP
            except (ValueError, AttributeError):
                logger.debug(
                    "Ignoring invalid nirizan.trace_id attribute '%s' found on span '%s'",
                    stashed,
                    getattr(span, "name", "<unnamed>"),
                )
    return otel_trace_id_to_uuid(otel_trace_id), SPAN_ID_SOURCE_DERIVED


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
        if isinstance(value, (str, int, float, bool)):
            result[key] = value
        elif isinstance(value, (list, tuple)):
            encoded_key = key if is_sequence_key(key) else encode_sequence_key(key)
            try:
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


# ---------------------------------------------------------------------------
# Parent resolution
# ---------------------------------------------------------------------------


class _ParentResolution:
    """Output of ``_resolve_parents``: per-candidate effective parent linkage."""

    __slots__ = ("parent_of", "synthetic_origin", "dropped")

    def __init__(self) -> None:
        self.parent_of: dict[int, int | None] = {}
        self.synthetic_origin: dict[int, int] = {}
        self.dropped: set[int] = set()


def _resolve_parents(
    buf: _TraceBuffer,
    kind_map: Mapping[int, SpanKind],
    orphan_policy: Literal["emit", "drop"],
) -> _ParentResolution:
    """Resolve every kind-recognized candidate's effective parent, in one pass."""
    result = _ParentResolution()
    memo: dict[int, tuple[str, int | None]] = {}
    in_progress: set[int] = set()

    def physical_parent(otel_span_id: int) -> int | None:
        span = buf.spans.get(otel_span_id)
        if span is None:
            return None
        parent_ctx = _get_parent_context(span)
        if parent_ctx is None or not is_valid_otel_span_id(parent_ctx.span_id):
            return None
        return parent_ctx.span_id

    def upward(x: int) -> tuple[str, int | None]:
        cached = memo.get(x)
        if cached is not None:
            return cached

        if x in in_progress:
            return (_SIG_CYCLE, None)

        in_progress.add(x)
        try:
            if x not in buf.spans:
                signal: tuple[str, int | None] = (_SIG_MISSING, x)
            else:
                parent_id = physical_parent(x)
                if parent_id is None:
                    upstream: tuple[str, int | None] = (_SIG_ROOT, None)
                else:
                    upstream = upward(parent_id)
                    if upstream[0] == _SIG_CYCLE:
                        upstream = (_SIG_ROOT, None)

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
        finally:
            in_progress.discard(x)

        memo[x] = signal
        return signal

    for start in kind_map:
        upward(start)

    return result


# ---------------------------------------------------------------------------
# Span processor
# ---------------------------------------------------------------------------


class NiriZanSpanProcessor(SpanProcessor):
    """OTel ``SpanProcessor`` that assembles NiriZan ``Trace`` objects.

    Inherits from ``opentelemetry.sdk.trace.SpanProcessor`` to provide safe default
    no-op implementations for internal SDK hooks such as ``_on_ending``.
    """

    def __init__(
        self,
        sink: TraceSink,
        *,
        idle_timeout_seconds: float = 5.0,
        max_trace_age_seconds: float = 300.0,
        max_buffered_traces: int = 1000,
        max_queue_size: int = _DEFAULT_MAX_QUEUE_SIZE,
        orphan_policy: Literal["emit", "drop"] = "emit",
        unrecognized_span_policy: Literal["drop", "generation"] = "drop",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if idle_timeout_seconds <= 0:
            raise ValueError("idle_timeout_seconds must be positive.")
        if max_trace_age_seconds <= idle_timeout_seconds:
            raise ValueError("max_trace_age_seconds must be greater than idle_timeout_seconds.")
        if max_buffered_traces < 1:
            raise ValueError("max_buffered_traces must be at least 1.")
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be at least 1.")
        if orphan_policy not in ("emit", "drop"):
            raise ValueError("orphan_policy must be 'emit' or 'drop'.")
        if unrecognized_span_policy not in ("drop", "generation"):
            raise ValueError("unrecognized_span_policy must be 'drop' or 'generation'.")

        self._sink = sink
        self._idle_timeout = idle_timeout_seconds
        self._max_age = max_trace_age_seconds
        self._max_buffered = max_buffered_traces
        self._max_queue_size = max_queue_size
        self._orphan_policy = orphan_policy
        self._unrecognized_span_policy = unrecognized_span_policy
        self._clock = clock

        self._queue: queue.Queue[Any] = queue.Queue(maxsize=max_queue_size)
        self._buffers: dict[int, _TraceBuffer] = {}
        self._recent_flushes: dict[int, None] = {}
        # Trace IDs whose start marker was dropped on queue saturation, keyed
        # in insertion order so the oldest can be evicted once the bound is
        # hit. Written by the producer thread (on_start), read and cleared by
        # the consumer thread (_consume_dropped_start). Both sides go through
        # _stats_lock.
        self._dropped_start_traces: dict[int, None] = {}
        self._stats: dict[str, int] = {}
        self._stats_lock = threading.Lock()
        self._shutdown = threading.Event()

        self._last_sweep: float = self._clock()
        self._last_queue_full_warning: float = 0.0

        self._consumer = threading.Thread(
            target=self._consume_loop,
            name="nirizan-otel-span-consumer",
            daemon=True,
        )
        self._consumer.start()

        if unrecognized_span_policy == "generation":
            logger.warning(
                "NiriZanSpanProcessor started with unrecognized_span_policy="
                "'generation': every span with no recognizable NiriZan or "
                "gen_ai.* attribute will be labeled GENERATION."
            )

        logger.debug(
            "NiriZanSpanProcessor started (idle=%.1fs, max_age=%.1fs, "
            "max_buffered=%d, max_queue_size=%d, orphan_policy=%s, "
            "unrecognized_span_policy=%s)",
            idle_timeout_seconds,
            max_trace_age_seconds,
            max_buffered_traces,
            max_queue_size,
            orphan_policy,
            unrecognized_span_policy,
        )

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
            with self._stats_lock:
                self._dropped_start_traces[ctx.trace_id] = None
                if len(self._dropped_start_traces) > _RECENT_FLUSHES_MAX:
                    oldest = next(iter(self._dropped_start_traces))
                    del self._dropped_start_traces[oldest]
                self._stats["queue_full"] = self._stats.get("queue_full", 0) + 1

    def on_end(self, span: ReadableSpan) -> None:
        """Push a completed OTel span to the consumer thread."""
        if self._shutdown.is_set():
            return
        try:
            self._queue.put_nowait(span)
        except queue.Full:
            self._record_stat("queue_full")
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
            self._record_stat("queue_full")

        self._consumer.join(timeout=5.0)
        if self._consumer.is_alive():
            logger.warning("NiriZanSpanProcessor consumer thread did not exit within 5s.")

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Block until the consumer has flushed all currently-buffered traces.

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
        """Return a snapshot of drop/duplicate counters, keyed by reason."""
        with self._stats_lock:
            return dict(self._stats)

    def _record_stat(self, reason: str) -> None:
        with self._stats_lock:
            self._stats[reason] = self._stats.get(reason, 0) + 1

    def _consume_dropped_start(self, otel_trace_id: int) -> bool:
        """Return ``True`` and forget the flag if a start marker for this trace was dropped.

        Called from the consumer thread only, whenever it creates or reuses a
        ``_TraceBuffer`` for ``otel_trace_id``, so the resulting
        ``has_untracked_start`` flag is set at most once per drop.
        """
        with self._stats_lock:
            if otel_trace_id in self._dropped_start_traces:
                del self._dropped_start_traces[otel_trace_id]
                return True
            return False

    # -- Consumer thread --------------------------------------------------------

    def _consume_loop(self) -> None:
        """Drain the queue, buffer spans, flush traces on idle or age."""
        while not self._shutdown.is_set():
            try:
                item = self._queue.get(timeout=self._idle_timeout / 2.0)
            except queue.Empty:
                self._sweep_idle_traces()
                self._last_sweep = self._clock()
                continue

            if item is _SHUTDOWN_SENTINEL:
                break

            if _is_flush_request(item):
                self._flush_all(reason="force_flush")
                item[1].set()
                continue

            if _is_start_marker(item):
                _, otel_trace_id, ts = item
                self._mark_span_started(otel_trace_id, ts)
                self._enforce_buffer_cap()
                continue

            self._buffer_span(item)
            self._enforce_buffer_cap()

            now = self._clock()
            if self._queue.empty() or (now - self._last_sweep) >= self._idle_timeout / 2.0:
                self._last_sweep = now
                self._sweep_idle_traces()

        # Shutdown drain
        pending_flush_events: list[threading.Event] = []
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
                self._mark_span_started(otel_trace_id, ts)
                continue
            self._buffer_span(item)

        self._flush_all(reason="shutdown")
        for event in pending_flush_events:
            event.set()

    def _mark_span_started(self, otel_trace_id: int, now: float) -> None:
        if otel_trace_id in self._recent_flushes:
            return
        buf = self._buffers.get(otel_trace_id)
        if buf is None:
            buf = _TraceBuffer(otel_trace_id, now)
            self._buffers[otel_trace_id] = buf
        if self._consume_dropped_start(otel_trace_id):
            buf.has_untracked_start = True
        buf.mark_started(now)

    def _buffer_span(self, span: ReadableSpan) -> None:
        ctx = _get_span_context(span)
        if ctx is None:
            logger.warning(
                "Skipping OTel span '%s': get_span_context() returned None",
                getattr(span, "name", "<unnamed>"),
            )
            self._record_stat("invalid_span_context")
            return

        if not is_valid_otel_trace_id(ctx.trace_id):
            logger.warning(
                "Skipping OTel span '%s': invalid all-zeros trace_id",
                getattr(span, "name", "<unnamed>"),
            )
            self._record_stat("invalid_trace_id")
            return

        if not is_valid_otel_span_id(ctx.span_id):
            logger.warning(
                "Skipping OTel span '%s': invalid all-zeros span_id",
                getattr(span, "name", "<unnamed>"),
            )
            self._record_stat("invalid_span_id")
            return

        if ctx.trace_id in self._recent_flushes:
            logger.warning(
                "Dropping late-arriving span '%s' for already-flushed OTel trace_id=%d",
                getattr(span, "name", "<unnamed>"),
                ctx.trace_id,
            )
            self._record_stat("late_arrival")
            return

        now = self._clock()
        buf = self._buffers.get(ctx.trace_id)
        if buf is None:
            buf = _TraceBuffer(ctx.trace_id, now)
            self._buffers[ctx.trace_id] = buf
        if self._consume_dropped_start(ctx.trace_id):
            buf.has_untracked_start = True

        was_duplicate = buf.add(span, now)
        if was_duplicate:
            logger.warning(
                "Duplicate OTel span_id=%016x within trace_id=%d",
                ctx.span_id,
                ctx.trace_id,
            )
            self._record_stat("duplicate_span_id")

    def _sweep_idle_traces(self) -> None:
        now = self._clock()
        to_flush: list[tuple[int, str]] = []
        for trace_id, buf in self._buffers.items():
            if now - buf.first_seen >= self._max_age:
                to_flush.append((trace_id, "max_age"))
            elif (
                not buf.has_untracked_start
                and now - buf.last_seen >= self._idle_timeout
                and buf.open_spans == 0
            ):
                # Flush on idle ONLY when no open spans remain active in the
                # trace, and only when open_spans is actually trustworthy for
                # this trace (no dropped start marker left it undercounted).
                to_flush.append((trace_id, "idle"))
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

        nirizan_trace_id, trace_id_source = _extract_nirizan_trace_id(
            buf.spans, buf.otel_trace_id
        )

        kind_map: dict[int, SpanKind] = {}
        for otel_span_id, span in buf.spans.items():
            otel_attrs = getattr(span, "attributes", None) or {}
            inferred_kind = _infer_span_kind(otel_attrs)
            if inferred_kind is not None:
                kind_map[otel_span_id] = inferred_kind
            elif self._unrecognized_span_policy == "generation":
                kind_map[otel_span_id] = SpanKind.GENERATION
            else:
                self._record_stat("unrecognized_kind")

        if not kind_map:
            return None

        id_map: dict[int, UUID] = {}
        source_map: dict[int, str] = {}
        for otel_span_id in kind_map:
            span = buf.spans[otel_span_id]
            ctx = _get_span_context(span)
            if ctx is None:
                continue
            nirizan_id, source = _extract_nirizan_span_id(span, ctx)
            id_map[otel_span_id] = nirizan_id
            source_map[otel_span_id] = source

        resolution = _resolve_parents(buf, kind_map, self._orphan_policy)

        parent_map: dict[int, UUID | None] = {}
        kept_ids: list[int] = []
        for otel_span_id in kind_map:
            if otel_span_id not in id_map:
                continue

            if otel_span_id in resolution.dropped:
                self._record_stat("orphan_parent_missing")
                continue

            ancestor_id = resolution.parent_of.get(otel_span_id)
            if ancestor_id is None:
                parent_map[otel_span_id] = None
            elif otel_span_id in resolution.synthetic_origin:
                parent_map[otel_span_id] = otel_span_id_to_uuid(ancestor_id)
            else:
                parent_map[otel_span_id] = id_map[ancestor_id]
            kept_ids.append(otel_span_id)

        if not kept_ids:
            return None

        kept_ids.sort(key=lambda oid: (buf.spans[oid].start_time or 0, oid))

        root_span = self._find_root_span(buf, kept_ids, parent_map)
        application_name = self._resolve_application_name(buf, kept_ids, root_span)
        session_id = self._find_session_id({oid: buf.spans[oid] for oid in kept_ids})

        nirizan_spans: list[Span] = []
        for otel_span_id in kept_ids:
            converted = self._convert_span(
                span=buf.spans[otel_span_id],
                nirizan_trace_id=nirizan_trace_id,
                nirizan_span_id=id_map[otel_span_id],
                parent_nirizan_id=parent_map[otel_span_id],
                kind=kind_map[otel_span_id],
                span_id_source=source_map[otel_span_id],
                trace_id_source=trace_id_source,
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
        parent_nirizan_id: UUID | None,
        kind: SpanKind,
        span_id_source: str,
        trace_id_source: str,
    ) -> Span | None:
        """Build the final NiriZan ``Span`` from already-resolved values."""
        ctx = _get_span_context(span)
        if ctx is None:
            return None

        otel_attrs = getattr(span, "attributes", None) or {}
        input_payload, output_payload = _extract_payloads(kind, otel_attrs)

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
            try:
                trace_state_str = str(trace_state)
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
            self._record_stat("conversion_error")
            logger.warning(
                "Failed to convert OTel span '%s' (otel_span_id=%016x): %s",
                span.name,
                ctx.span_id,
                err,
            )
            return None
