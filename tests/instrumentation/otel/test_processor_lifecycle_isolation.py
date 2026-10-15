# tests/instrumentation/otel/test_processor_lifecycle_isolation.py
"""L5 isolation layer: buffer caps and stats are honored on *every* intake path.

The OTel bridge processor enforces ``max_buffered_traces`` / ``max_buffered_spans``
while the consumer thread is running: every buffered span and start marker is
followed by a cap check that evicts (flushes) the oldest traces until the
budget is met again. This file pins the same guarantee on the paths that do
not go through the live consumer loop, most importantly the shutdown drain:
a backlog that accumulated while the consumer was blocked must not be
buffered in one unbounded gulp when ``shutdown`` finally drains the queue.

These tests run against an *inert* processor (constructed, then shut down, so
its consumer thread is gone) and drive the internals synchronously, exactly
like the deterministic state-machine tests in ``test_from_otel.py``. No sleeps,
no thread scheduling races.

This module requires the optional ``otel`` extra and is deselected with
``pytest -m "not otel"``.
"""

import pytest

pytest.importorskip("opentelemetry")
pytest.importorskip("opentelemetry.sdk")

import queue  # noqa: E402
import threading  # noqa: E402
from collections.abc import Callable  # noqa: E402
from typing import Any  # noqa: E402
from unittest.mock import patch  # noqa: E402

from opentelemetry.sdk.resources import Resource  # noqa: E402
from opentelemetry.sdk.trace import ReadableSpan  # noqa: E402
from opentelemetry.sdk.util.instrumentation import InstrumentationScope  # noqa: E402
from opentelemetry.trace import SpanContext, TraceFlags, TraceState  # noqa: E402
from opentelemetry.trace.status import Status, StatusCode  # noqa: E402

from nirizan.instrumentation.otel.from_otel import (  # noqa: E402
    _FLUSH_SENTINEL,
    NiriZanSpanProcessor,
    _TraceBuffer,
)
from nirizan.instrumentation.otel.semconv import NIRIZAN_SPAN_KIND  # noqa: E402
from nirizan.instrumentation.spans import Trace  # noqa: E402

pytestmark = pytest.mark.otel

T0 = 1_600_000_000_000_000_000
SECOND = 1_000_000_000


def make_span(span_id: int, *, trace_id: int, name: str = "span") -> ReadableSpan:
    """A finished, kind-recognized single-span trace member."""
    start_ns = T0 + span_id
    return ReadableSpan(
        name=name,
        context=SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
            trace_state=TraceState(),
        ),
        parent=None,
        resource=Resource({"service.name": "l5-service"}),
        attributes={NIRIZAN_SPAN_KIND: "generation"},
        status=Status(StatusCode.UNSET),
        start_time=start_ns,
        end_time=start_ns + SECOND,
        instrumentation_scope=InstrumentationScope("tests"),
    )


class RecordingSink:
    """Thread-safe sink that records traces in arrival order."""

    def __init__(self) -> None:
        self.traces: list[Trace] = []
        self._lock = threading.Lock()

    def enqueue_trace(self, trace: Trace) -> None:
        with self._lock:
            self.traces.append(trace)


class FakeClock:
    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def sink() -> RecordingSink:
    return RecordingSink()


@pytest.fixture
def make_inert(
    sink: RecordingSink,
) -> Callable[..., NiriZanSpanProcessor]:
    """Factory for inert processors: constructed, consumer thread joined."""

    def factory(**kwargs: Any) -> NiriZanSpanProcessor:
        kwargs.setdefault("clock", FakeClock())
        processor = NiriZanSpanProcessor(kwargs.pop("sink", sink), **kwargs)
        processor.shutdown()
        assert not processor._consumer.is_alive()
        return processor

    return factory


def queue_backlog(processor: NiriZanSpanProcessor, *, trace_count: int) -> None:
    """Fill the processor's queue with one finished single-span trace each."""
    for i in range(trace_count):
        processor._queue.put_nowait(make_span(i + 1, trace_id=0x1000 + i))


# ---------------------------------------------------------------------------
# The shutdown drain honors the buffer caps
# ---------------------------------------------------------------------------


def test_shutdown_drain_keeps_the_trace_count_within_its_cap(
    make_inert: Callable[..., NiriZanSpanProcessor],
    sink: RecordingSink,
) -> None:
    """Regression: the shutdown drain buffered an unbounded backlog at once.

    ``_process_item`` enforces the cap after every buffered span, but the
    shutdown drain used to buffer everything still queued and only flush at
    the end, so a backlog accumulated while the consumer was blocked could
    grow the buffers far past ``max_buffered_traces``. The drain must enforce
    the same cap as the live path.
    """
    processor = make_inert(max_buffered_traces=2, max_buffered_spans=1000)
    queue_backlog(processor, trace_count=10)

    peak_traces: list[int] = []
    original_buffer_span = processor._buffer_span

    def recording_buffer_span(span: ReadableSpan) -> None:
        original_buffer_span(span)
        peak_traces.append(len(processor._buffers))

    with patch.object(processor, "_buffer_span", recording_buffer_span):
        processor._drain_and_flush()

    # Every trace was delivered: evictions flushed the overflow mid-drain and
    # the final _flush_all caught the remainder.
    assert len(sink.traces) == 10
    # The buffer never held more than the cap plus the single span that
    # triggered enforcement.
    assert max(peak_traces) <= 3


def test_shutdown_drain_keeps_the_span_count_within_its_cap(
    make_inert: Callable[..., NiriZanSpanProcessor],
    sink: RecordingSink,
) -> None:
    """The span budget (``max_buffered_spans``) is honored during shutdown too."""
    processor = make_inert(max_buffered_traces=1000, max_buffered_spans=3)
    queue_backlog(processor, trace_count=10)

    peak_spans: list[int] = []
    original_buffer_span = processor._buffer_span

    def recording_buffer_span(span: ReadableSpan) -> None:
        original_buffer_span(span)
        peak_spans.append(processor._buffered_spans)

    with patch.object(processor, "_buffer_span", recording_buffer_span):
        processor._drain_and_flush()

    assert len(sink.traces) == 10
    assert max(peak_spans) <= 4


def test_shutdown_drain_delivers_every_queued_span_exactly_once(
    make_inert: Callable[..., NiriZanSpanProcessor],
    sink: RecordingSink,
) -> None:
    """Cap enforcement during the drain must not lose or duplicate traces."""
    processor = make_inert(max_buffered_traces=2)
    queue_backlog(processor, trace_count=6)

    processor._drain_and_flush()

    delivered = [str(t.trace_id) for t in sink.traces]
    assert len(delivered) == 6
    assert len(set(delivered)) == 6
    assert processor._buffers == {}
    assert processor._buffered_spans == 0


def test_shutdown_drain_flushes_pending_force_flush_events_after_enforcing_the_cap(
    make_inert: Callable[..., NiriZanSpanProcessor],
    sink: RecordingSink,
) -> None:
    """A force_flush queued behind an oversized backlog is still released."""
    processor = make_inert(max_buffered_traces=1)
    queue_backlog(processor, trace_count=4)
    flush_event = threading.Event()
    processor._queue.put_nowait((_FLUSH_SENTINEL, flush_event))

    processor._drain_and_flush()

    assert flush_event.is_set()
    assert len(sink.traces) == 4


def test_shutdown_drain_is_a_no_op_on_an_empty_queue(
    make_inert: Callable[..., NiriZanSpanProcessor],
    sink: RecordingSink,
) -> None:
    processor = make_inert()

    processor._drain_and_flush()

    assert sink.traces == []
    assert processor._buffers == {}


def test_the_live_path_still_enforces_the_cap_after_each_item(
    make_inert: Callable[..., NiriZanSpanProcessor],
    sink: RecordingSink,
) -> None:
    """The cap contract on the live intake path stays exactly as documented."""
    processor = make_inert(max_buffered_traces=2)

    for i in range(4):
        processor._process_item(make_span(i + 1, trace_id=0x2000 + i))
        assert len(processor._buffers) <= 2

    assert len(sink.traces) >= 2


def test_drain_enforcement_records_the_same_eviction_stats_as_the_live_path(
    make_inert: Callable[..., NiriZanSpanProcessor],
    sink: RecordingSink,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mid-drain evictions are logged and counted, not silent."""
    processor = make_inert(max_buffered_traces=1)
    queue_backlog(processor, trace_count=3)

    with caplog.at_level("WARNING"):
        processor._drain_and_flush()

    assert len(sink.traces) == 3
    assert "Evicting incomplete OTel trace_id=" in caplog.text


def test_a_drained_flush_request_does_not_count_against_the_cap(
    make_inert: Callable[..., NiriZanSpanProcessor],
    sink: RecordingSink,
) -> None:
    """Flush requests and sentinels never create buffers, so they cannot evict."""
    processor = make_inert(max_buffered_traces=1)
    processor._queue.put_nowait((_FLUSH_SENTINEL, threading.Event()))
    processor._queue.put_nowait(object())  # an unknown item is ignored by the drain

    processor._drain_and_flush()

    assert sink.traces == []
    assert processor._buffers == {}


def test_trace_buffer_counts_spans_for_the_budget() -> None:
    """Sanity: the budget unit is stored spans, so the cap math is grounded."""
    buf = _TraceBuffer(0x1, 0.0)
    buf.add(make_span(1, trace_id=0x1), 0.0)
    buf.add(make_span(2, trace_id=0x1), 0.0)

    assert len(buf.spans) == 2


def test_queue_backlog_helper_produces_a_genuine_backlog() -> None:
    """Guard against a no-op setup: the queue really holds the whole backlog."""
    processor = NiriZanSpanProcessor(RecordingSink(), clock=FakeClock())
    try:
        queue_backlog(processor, trace_count=5)
        assert processor._queue.qsize() == 5
    finally:
        processor.shutdown()
        assert not processor._consumer.is_alive()


def test_the_drain_reads_the_current_queue_not_a_snapshot() -> None:
    """_drain_and_flush drains self._queue, so items added before it run are seen."""
    sink = RecordingSink()
    processor = NiriZanSpanProcessor(sink, clock=FakeClock())
    processor.shutdown()
    assert isinstance(processor._queue, queue.Queue)

    queue_backlog(processor, trace_count=3)
    processor._drain_and_flush()

    assert len(sink.traces) == 3
