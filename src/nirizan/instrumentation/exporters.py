from abc import ABC, abstractmethod
import logging

from nirizan.instrumentation.spans import Trace

logger = logging.getLogger(__name__)


class BaseExporter(ABC):
    """Abstract base class for all trace exporters."""

    @abstractmethod
    async def export(self, trace: Trace) -> None:
        """Export a completed Trace to storage or a remote collector."""
        pass

    async def shutdown(self) -> None:
        """Release underlying connections or background workers."""
        pass


class InMemoryExporter(BaseExporter):
    """In-memory trace collector designed for unit tests and local experiments."""

    def __init__(self) -> None:
        self._traces: list[Trace] = []

    async def export(self, trace: Trace) -> None:
        self._traces.append(trace)

    def get_traces(self) -> list[Trace]:
        return list(self._traces)

    def clear(self) -> None:
        self._traces.clear()


class ConsoleExporter(BaseExporter):
    """Logs trace telemetry directly to standard logger output."""

    async def export(self, trace: Trace) -> None:
        logger.info(
            "Trace Exported | ID: %s | App: %s | Spans: %d",
            trace.trace_id,
            trace.application_name,
            len(trace.spans),
        )
