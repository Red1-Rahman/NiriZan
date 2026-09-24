# src/nirizan/instrumentation/otel/from_otel.py
"""OpenTelemetry span processor that assembles NiriZan Traces from OTel spans.

This module implements the OTel -> NiriZan direction of the bridge. It hooks
into the OpenTelemetry SDK through the ``SpanProcessor`` interface and
produces plain NiriZan ``Trace`` objects, indistinguishable at the type level
from traces assembled by NiriZan's own ``Tracer``.

Trace assembly proceeds in passes over a buffered trace's spans:

1. Kind classification (``_infer_span_kind`` plus ``unrecognized_span_policy``)
   decides which spans are candidates for emission at all.
2. NiriZan id + provenance assignment for every candidate.
3. Parent resolution (``_resolve_parents``) walks each candidate's OTel
   parent chain, transparently skipping any ancestor that will not be
   emitted -- whether because its kind was unrecognized, or because it is
   itself an orphan under ``orphan_policy="drop"`` -- so a span is
   re-parented onto the nearest surviving ancestor, or promoted to root if
   every ancestor was skipped. This is a single memoized pass, and it is
   deliberately traversal-order-independent: a cyclic parent chain (only
   reachable via a pathological exporter, since a conformant OTel SDK fixes
   a span's parent at start time, before the span exists as a completed
   ``ReadableSpan``) is neutralized once, in the call frame that first
   discovers it, and that decision is never later overwritten regardless of
   which candidate's resolution happened to trigger the walk.
4. Conversion (``_convert_span``) builds the final NiriZan ``Span`` objects
   from the already-resolved kind and parent, so every field required by
   the ``Span`` model is non-optional and the model's strict validation is
   an assertion of correctness rather than an incidental drop mechanism.
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

_RECENT_FLUSHES_MAX: int = 10_000
_MAX_SPAN_NAME_LENGTH: int = 200

# Internal signal tags used by _resolve_parents' upward walk. Not part of
# the module's public surface; module-level only so _resolve_parents' inner
# closures don't re-allocate them per call.
_SIG_ROOT: str = "root"
_SIG_ATTACH: str = "attach_to"
_SIG_MISSING: str = "missing"
_SIG_CYCLE: str = "cycle"


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
    """Return ``(NiriZan trace_id, provenance source)`` for a buffered OTel trace.

    Mirrors ``_extract_nirizan_span_id``: if any span in the buffer carries a
    stashed ``nirizan.trace_id`` attribute (written by ``to_otel.py`` on every
    span it exports), that value is recovered verbatim so a NiriZan trace that
    is exported to OTel and later re-ingested keeps its original identity,
    instead of silently receiving a new, unrelated trace_id derived from the
    freshly-generated OTel trace id. Falls back to the derived mapping for
    traces with no such attribute, which is the normal, correct case for a
    trace that originated in a genuinely external OTel-instrumented app.
    """
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
    """Determine NiriZan ``SpanKind`` from an OTel span's attributes.

    Returns ``None`` when the span carries no recognizable NiriZan or
    ``gen_ai.*`` signal at all, rather than guessing. Callers decide what to
    do with an unrecognized span via ``unrecognized_span_policy``; silently
    defaulting every unrecognized span to ``GENERATION`` would pollute the
    one kind NiriZan's trust and safety metrics read from.
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

    __slots__ = ("otel_trace_id", "spans", "first_seen", "last_seen")

    def __init__(self, otel_trace_id: int, now: float) -> None:
        self.otel_trace_id = otel_trace_id
        self.spans: dict[int, ReadableSpan] = {}
        self.first_seen = now
        self.last_seen = now

    def add(self, span: ReadableSpan, now: float) -> bool:
        """Add a span to the buffer, keyed by its OTel span_id.

        Policy: last-write-wins. If a span with the same OTel span_id has
        already been buffered for this trace, it is silently replaced.

        Returns:
            ``True`` if this call overwrote an existing entry for the same
            span_id (a duplicate span_id within one trace), ``False``
            otherwise. This method does not itself log or record metrics for
            a duplicate; callers that care (e.g. to warn or increment a
            stats counter) should act on the return value, keeping this
            class a plain data structure with no logging side effects.
        """
        ctx = _get_span_context(span)
        if ctx is None:
            return False
        is_duplicate = ctx.span_id in self.spans
        self.spans[ctx.span_id] = span
        self.last_seen = now
        return is_duplicate


# ---------------------------------------------------------------------------
# Parent resolution
# ---------------------------------------------------------------------------


class _ParentResolution:
    """Output of ``_resolve_parents``: per-candidate effective parent linkage.

    ``parent_of[x]`` is the OTel span_id of ``x``'s effective ancestor, or
    ``None`` if ``x`` is an effective root (a true root, or an orphan
    promoted to root because every ancestor above it was skipped). Populated
    for every kind-recognized candidate that is not in ``dropped``.

    ``synthetic_origin`` holds the subset of ``parent_of`` keys whose value
    is the id of a genuinely missing ancestor rather than another emitted
    candidate's id (only populated when ``orphan_policy == "emit"``); the
    caller must map these through ``otel_span_id_to_uuid`` directly, not
    through the trace's ``id_map``, since no ``Span`` will ever exist for
    that id.

    ``dropped`` holds every kind-recognized candidate that must not be
    emitted at all (only populated when ``orphan_policy == "drop"``, for a
    candidate whose chain runs off the buffer).
    """

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
    """Resolve every kind-recognized candidate's effective parent, in one pass.

    Each candidate's physical OTel parent chain is walked upward, skipping
    transparently over any node that will not itself be emitted --
    unrecognized kind, or (cascading) itself unresolvable -- until the walk
    lands on a real kept ancestor, a true root, or a parent reference that
    never arrived in this buffer.

    Implementation note on correctness under cycles: the walk is memoized
    per OTel span_id via a single dict populated as a side effect of one
    depth-first traversal, with an ``in_progress`` set as a recursion guard.
    A conformant OTel SDK cannot produce a cyclic parent chain -- a span's
    parent context is fixed when the span starts, strictly before that span
    can appear as another span's completed ``ReadableSpan`` ancestor -- so a
    cycle here only reaches this code via a pathological exporter or a
    hand-constructed ``ReadableSpan`` in a test. When the walk revisits a
    node still ``in_progress``, that is reported as a ``"cycle"`` signal to
    the *caller* (the node's descendant in the walk), and it is that
    descendant's own resolution that is committed as a root, once, in the
    same stack frame that discovered the cycle. No later frame -- including
    the frame for the node that was being revisited -- ever overwrites that
    commitment, because each node's final signal is written to ``memo``
    exactly once, at the end of its own (and only its own) call. This makes
    the result independent of which candidate's resolution happens to start
    the walk: every participant in a cycle is treated the same way no
    matter the traversal order.
    """
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
        """What should a descendant do when its chain reaches node ``x``?

        Returns one of:
          - ``(_SIG_ROOT, None)``
          - ``(_SIG_ATTACH, x)`` -- attach to ``x`` itself (x is kept)
          - ``(_SIG_MISSING, origin)`` -- the chain ran off the buffer at
            OTel span_id ``origin``
          - ``(_SIG_CYCLE, None)`` -- ``x`` is still being resolved further
            down this same call stack; the caller must neutralize this
            into its own final answer rather than propagate it further.
        """
        cached = memo.get(x)
        if cached is not None:
            return cached

        if x in in_progress:
            # Do not cache: this is a transient signal for the frame that
            # is CURRENTLY resolving x's descendant. That frame commits its
            # own final answer to memo exactly once, below; this branch
            # itself must never write to memo, or a later, unrelated call
            # that legitimately reaches x again would replay a stale cycle
            # signal instead of resolving x fresh.
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
                        # x's own edge closes a cycle. Sever it here: this
                        # is x's final, once-committed answer, not a
                        # value any other frame will revisit or replace.
                        upstream = (_SIG_ROOT, None)

                if x in kind_map:
                    if upstream[0] == _SIG_ROOT:
                        result.parent_of[x] = None
                    elif upstream[0] == _SIG_ATTACH:
                        result.parent_of[x] = upstream[1]
                    else:  # _SIG_MISSING
                        origin = upstream[1]
                        assert origin is not None
                        if orphan_policy == "drop":
                            result.dropped.add(x)
                        else:
                            result.parent_of[x] = origin
                            result.synthetic_origin[x] = origin

                    # x is now resolved (kept or dropped): descendants
                    # attach to x itself if kept, or -- if x was dropped --
                    # x's own upstream signal passes through untouched, so
                    # a dropped orphan's children still cascade correctly
                    # to whatever x would have attached to.
                    signal = (_SIG_ATTACH, x) if x not in result.dropped else upstream
                else:
                    # x is invisible to the emitted trace (unrecognized
                    # kind): pass the upstream signal straight through.
                    signal = upstream
        finally:
            in_progress.discard(x)

        memo[x] = signal
        return signal

    for start in kind_map:
        upward(start)  # populates result.* as a side effect; return value unused here

    return result


# ---------------------------------------------------------------------------
# Span processor
# ---------------------------------------------------------------------------


class NiriZanSpanProcessor:
    """OTel ``SpanProcessor`` that assembles NiriZan ``Trace`` objects."""

    def __init__(
        self,
        sink: TraceSink,
        *,
        idle_timeout_seconds: float = 5.0,
        max_trace_age_seconds: float = 300.0,
        max_buffered_traces: int = 1000,
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
        if orphan_policy not in ("emit", "drop"):
            raise ValueError("orphan_policy must be 'emit' or 'drop'.")
        if unrecognized_span_policy not in ("drop", "generation"):
            raise ValueError("unrecognized_span_policy must be 'drop' or 'generation'.")

        self._sink = sink
        self._idle_timeout = idle_timeout_seconds
        self._max_age = max_trace_age_seconds
        self._max_buffered = max_buffered_traces
        self._orphan_policy = orphan_policy
        self._unrecognized_span_policy = unrecognized_span_policy
        self._clock = clock

        self._queue: queue.Queue[Any] = queue.Queue()
        self._buffers: dict[int, _TraceBuffer] = {}
        self._recent_flushes: dict[int, None] = {}
        self._stats: dict[str, int] = {}
        self._stats_lock = threading.Lock()
        self._shutdown = threading.Event()

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
                "gen_ai.* attribute will be labeled GENERATION. This can "
                "dilute NiriZan's trust and safety metrics, which read from "
                "that one kind; prefer 'drop' unless every OTel span must "
                "be represented in the resulting trace."
            )

        logger.debug(
            "NiriZanSpanProcessor started (idle=%.1fs, max_age=%.1fs, "
            "max_buffered=%d, orphan_policy=%s, unrecognized_span_policy=%s)",
            idle_timeout_seconds,
            max_trace_age_seconds,
            max_buffered_traces,
            orphan_policy,
            unrecognized_span_policy,
        )

    # -- SpanProcessor interface ------------------------------------------------

    def on_start(
        self,
        span: ReadableSpan,
        parent_context: Context | None = None,
    ) -> None:
        """No-op: span start is not needed for trace assembly.

        The buffer is populated in ``on_end`` because a span is only complete
        once it has ended; there is no useful work to do on start.
        """
        pass

    def on_end(self, span: ReadableSpan) -> None:
        """Push a completed OTel span to the consumer thread."""
        if self._shutdown.is_set():
            return
        try:
            self._queue.put_nowait(span)
        except Exception:
            logger.exception("Failed to enqueue OTel span in NiriZanSpanProcessor")

    def shutdown(self) -> None:
        """Stop the consumer thread, flush all open traces, and join."""
        self._shutdown.set()
        self._queue.put_nowait(_SHUTDOWN_SENTINEL)
        self._consumer.join(timeout=5.0)
        if self._consumer.is_alive():
            logger.warning("NiriZanSpanProcessor consumer thread did not exit within 5s.")

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Block until the consumer has flushed all currently-buffered traces.

        Enqueues a flush request carrying a completion event. The consumer
        sets the event only after ``_flush_all`` has returned, so a caller
        that observes ``True`` is guaranteed that every trace buffered at
        request time has been passed to the sink. Spans that arrive *after*
        this call are not included; ``force_flush`` is a barrier over the
        current buffer, not a promise about future spans.

        Returns ``True`` if the flush completed before ``timeout_millis``,
        ``False`` otherwise (including when the processor has already been
        shut down).
        """
        if self._shutdown.is_set():
            return True

        done_event = threading.Event()
        self._queue.put_nowait((_FLUSH_SENTINEL, done_event))
        return done_event.wait(timeout=timeout_millis / 1000.0)

    def get_stats(self) -> dict[str, int]:
        """Return a snapshot of drop/duplicate counters, keyed by reason.

        Safe to call from any thread. Current reasons: ``invalid_span_context``,
        ``invalid_trace_id``, ``invalid_span_id``, ``late_arrival``,
        ``duplicate_span_id``, ``unrecognized_kind``, ``orphan_parent_missing``,
        ``conversion_error``. Absence of a key means that reason has not
        occurred yet, not that it is impossible.
        """
        with self._stats_lock:
            return dict(self._stats)

    def _record_stat(self, reason: str) -> None:
        with self._stats_lock:
            self._stats[reason] = self._stats.get(reason, 0) + 1

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

            if _is_flush_request(item):
                self._flush_all(reason="force_flush")
                # Set the event only after the flush has completed, so the
                # caller's force_flush() return value is a real guarantee.
                item[1].set()
                continue

            self._buffer_span(item)
            if self._queue.empty():
                self._sweep_idle_traces()
                self._enforce_buffer_cap()

        # Shutdown drain: process any remaining spans, collect pending flush
        # requests, run the final flush, then unblock the waiters. Setting
        # the events before _flush_all would let a caller observe an
        # unflushed sink.
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
            self._buffer_span(item)

        self._flush_all(reason="shutdown")
        for event in pending_flush_events:
            event.set()

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

        was_duplicate = buf.add(span, now)
        if was_duplicate:
            logger.warning(
                "Duplicate OTel span_id=%016x within trace_id=%d: overwriting "
                "the previous span for this id (last-write-wins).",
                ctx.span_id,
                ctx.trace_id,
            )
            self._record_stat("duplicate_span_id")

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

        # Pass 1: classify every span's kind. A span with no recognizable
        # kind is dropped up front unless unrecognized_span_policy is
        # "generation", in which case it is labeled GENERATION explicitly
        # (see the constructor's warning about the metric-pollution risk).
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
                logger.debug(
                    "Dropping span '%s' (otel_span_id=%016x): no recognizable "
                    "NiriZan or gen_ai.* signal and unrecognized_span_policy='drop'.",
                    getattr(span, "name", "<unnamed>"),
                    otel_span_id,
                )

        if not kind_map:
            return None

        # Pass 2: NiriZan span id and provenance for every kind-recognized
        # candidate. Computed for all candidates up front (independent of
        # parent resolution) so Pass 3 can look up any ancestor's id freely.
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

        # Pass 3: resolve every candidate's effective parent in a single,
        # order-independent pass. See _resolve_parents for the cascading
        # -drop and cycle-safety guarantees.
        resolution = _resolve_parents(buf, kind_map, self._orphan_policy)

        parent_map: dict[int, UUID | None] = {}
        kept_ids: set[int] = set()
        for otel_span_id in kind_map:
            if otel_span_id not in id_map:
                continue

            if otel_span_id in resolution.dropped:
                self._record_stat("orphan_parent_missing")
                logger.debug(
                    "Dropping orphan span (otel_span_id=%016x): no ancestor "
                    "path back to a real parent or root, and orphan_policy='drop'.",
                    otel_span_id,
                )
                continue

            ancestor_id = resolution.parent_of.get(otel_span_id)
            if ancestor_id is None:
                parent_map[otel_span_id] = None
            elif otel_span_id in resolution.synthetic_origin:
                parent_map[otel_span_id] = otel_span_id_to_uuid(ancestor_id)
                logger.debug(
                    "Span (otel_span_id=%016x) has a parent that never arrived "
                    "in this buffer; emitting with a synthetic parent id "
                    "(orphan_policy='emit').",
                    otel_span_id,
                )
            else:
                parent_map[otel_span_id] = id_map[ancestor_id]
            kept_ids.add(otel_span_id)

        if not kept_ids:
            return None

        # Root resolution runs on the filtered set only, so application_name
        # can't degrade to "unknown" just because the original root was
        # dropped while a perfectly good service.name exists one level down.
        root_span = self._find_root_span(buf, kept_ids, parent_map)
        application_name = self._resolve_application_name(buf, kept_ids, root_span)
        session_id = self._find_session_id({oid: buf.spans[oid] for oid in kept_ids})

        # Pass 4: build the final NiriZan Span objects from fully-resolved data.
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
        kept_ids: set[int],
        parent_map: Mapping[int, UUID | None],
    ) -> ReadableSpan | None:
        """Return the first surviving span with no effective parent.

        This is the structural root of the trace *after* unrecognized-kind
        filtering and re-parenting. If the original root was dropped, the
        promoted orphan that inherits its position (``parent_map[...] is
        None``) is returned instead.
        """
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
        kept_ids: set[int],
        root_span: ReadableSpan | None,
    ) -> str:
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
        """Build the final NiriZan ``Span`` from already-resolved values.

        By the time this is called, kind and parent have already been
        resolved by ``_assemble_trace`` (Passes 1-3), so every field handed
        to the ``Span`` constructor below is non-optional. This keeps
        pydantic's strict validation an assertion of correctness rather than
        an incidental drop mechanism.
        """
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
