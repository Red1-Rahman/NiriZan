# src/nirizan/orchestrator/loop_sink.py
"""Thread-safe adapter from the OTel bridge's sync sink interface to an
async ``TraceCollector``.

``NiriZanSpanProcessor`` (``instrumentation/otel/from_otel.py``) calls its
sink's ``enqueue_trace`` synchronously, from its own consumer thread, and
expects the call to return immediately. ``TraceCollector.enqueue_trace`` is a
coroutine function that writes to an ``asyncio.Queue``, which is not
thread-safe. Passing a collector straight to the processor silently drops
every trace: the coroutine is created but never awaited.

``LoopTraceSink`` bridges the two. It implements the processor's
``ThreadSafeTraceSink`` protocol by scheduling the collector's coroutine onto
its own event loop with ``asyncio.run_coroutine_threadsafe``, which is safe
to call from any thread. A failure inside the collector, or a closed loop, is
logged rather than raised back into the processor's consumer thread, since
there is nothing further the adapter can do about it there.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import Future
from typing import TYPE_CHECKING, Protocol

from nirizan.instrumentation.spans import Trace

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

__all__ = ["LoopTraceSink"]


class _AsyncTraceCollector(Protocol):
    """The minimal async collector surface ``LoopTraceSink`` depends on."""

    async def enqueue_trace(self, trace: Trace) -> None: ...


class LoopTraceSink:
    """Hands traces from any thread to a ``TraceCollector`` running on an event loop.

    ``collector`` is the async collector to deliver traces to (typically an
    ``orchestrator.collector.TraceCollector``). ``loop`` must be the running
    event loop the collector's queue belongs to; it is the caller's
    responsibility to keep that loop alive for as long as this sink is in use.
    """

    def __init__(self, collector: _AsyncTraceCollector, loop: asyncio.AbstractEventLoop) -> None:
        self._collector = collector
        self._loop = loop

    def enqueue_trace(self, trace: Trace) -> None:
        """Schedule ``collector.enqueue_trace(trace)`` on the bound event loop.

        Safe to call from any thread, including the OTel processor's consumer
        thread. Does not block waiting for the coroutine to complete; failures
        (including a closed loop) surface only through the logged done
        callback, matching how any other sink failure is handled by the
        processor (logged and the trace is lost).
        """
        try:
            future: Future[None] = asyncio.run_coroutine_threadsafe(
                self._collector.enqueue_trace(trace), self._loop
            )
        except RuntimeError as err:
            # The loop is closed or not running; nothing left to schedule onto.
            logger.error("Failed to enqueue trace from OTel processor: %s", err)
            return
        future.add_done_callback(_log_failure)


def _log_failure(future: Future[None]) -> None:
    if future.cancelled():
        return
    error = future.exception()
    if error is not None:
        logger.error("Failed to enqueue trace from OTel processor: %s", error)