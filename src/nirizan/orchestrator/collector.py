import asyncio
import logging
from typing import Optional

from nirizan.instrumentation.exporters import BaseExporter
from nirizan.instrumentation.spans import Trace
from nirizan.storage.models import TraceRecord
from nirizan.storage.trace_repository import BaseTraceRepository

logger = logging.getLogger(__name__)


class TraceCollector:
    """Async ingestion orchestrator that buffers incoming traces for persistence."""

    def __init__(self, repository: BaseTraceRepository) -> None:
        self.repository = repository
        self.queue: asyncio.Queue[Trace] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the background worker processor."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())

    async def stop(self) -> None:
        """Flush remaining queue items and gracefully stop the worker task."""
        self._running = False
        await self.queue.join()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def enqueue_trace(self, trace: Trace) -> None:
        """Non-blocking trace push into the processing buffer."""
        await self.queue.put(trace)

    async def _process_queue(self) -> None:
        while self._running or not self.queue.empty():
            try:
                trace = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                record = TraceRecord.from_trace(trace)
                await self.repository.save_trace(record)
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as err:
                logger.error("Error persisting trace in collector worker: %s", err)
                self.queue.task_done()


class CollectorExporter(BaseExporter):
    """Exporter adapter that routes emitted traces into a TraceCollector."""

    def __init__(self, collector: TraceCollector) -> None:
        self.collector = collector

    async def export(self, trace: Trace) -> None:
        await self.collector.enqueue_trace(trace)
