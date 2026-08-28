import asyncio
import logging
import os
import subprocess
from typing import Optional, Protocol

from nirizan.instrumentation.exporters import BaseExporter
from nirizan.instrumentation.spans import Trace

logger = logging.getLogger(__name__)


def _resolve_code_commit() -> Optional[str]:
    """GIT_COMMIT_SHA env var first, then `git rev-parse HEAD`, else None (never fabricated)."""
    env_value = os.environ.get("GIT_COMMIT_SHA")
    if env_value:
        return env_value
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _resolve_data_snapshot_id() -> Optional[str]:
    """NIRIZAN_DATA_SNAPSHOT_ID env var only; no generic fallback exists, so None is honest if unset."""
    return os.environ.get("NIRIZAN_DATA_SNAPSHOT_ID")


class TraceSink(Protocol):
    """The shape TraceCollector needs from a repository; keeps orchestrator/ from importing storage/ (see docs/import-boundaries.md)."""

    async def save(self, trace: Trace) -> None: ...


class TraceCollector:
    """Async ingestion orchestrator that buffers incoming traces for persistence, tagging each with commit/snapshot at ingest."""

    def __init__(self, repository: TraceSink) -> None:
        self.repository = repository
        self.queue: asyncio.Queue[Trace] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._running = False
        # Resolved once per collector, not per-trace: the running commit and
        # data snapshot don't change mid-process, and a git subprocess call
        # on every single trace would be wasteful.
        self._code_commit = _resolve_code_commit()
        self._data_snapshot_id = _resolve_data_snapshot_id()

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
        """Tag the trace with commit hash + data snapshot at ingest, then push into the processing buffer."""
        tagged_trace = trace.model_copy(
            update={
                "code_commit": self._code_commit,
                "data_snapshot_id": self._data_snapshot_id,
            }
        )
        await self.queue.put(tagged_trace)

    async def _process_queue(self) -> None:
        while self._running or not self.queue.empty():
            try:
                trace = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                await self.repository.save(trace)
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
