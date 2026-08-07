# src/nirizan/orchestrator/scheduler.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from nirizan.instrumentation.spans import Trace
from nirizan.orchestrator.dispatcher import MetricDispatcher
from nirizan.storage.models import Run

# Placeholder versioning until Phase 3 wires up real commit-hash/data-snapshot
# tracking. Per contracts.md: never optional, never blank; a fixed marker.
_UNVERSIONED_COMMIT = "phase2-unversioned"
_UNVERSIONED_SNAPSHOT = "unversioned"


class TraceSource(Protocol):
    """The shape RunScheduler needs from trace storage."""

    async def list_by_application(
        self,
        application_name: str,
        limit: int = 100,
    ) -> list[Trace]:
        ...


class RunSink(Protocol):
    """The shape RunScheduler needs from run persistence.

    Kept local to avoid coupling the scheduler to a broader repository
    interface, following the same pattern as TraceCollector's TraceSink.
    """

    async def save_run(self, run: Run) -> None:
        ...


class RunScheduler:
    """Triggers an evaluation run on demand."""

    def __init__(
        self,
        trace_source: TraceSource,
        dispatcher: MetricDispatcher,
        run_repository: RunSink,
    ) -> None:
        self.trace_source = trace_source
        self.dispatcher = dispatcher
        self.run_repository = run_repository

    async def run_on_demand(
        self,
        application_name: str,
        system_type: str,
    ) -> list[Run]:
        traces = await self.trace_source.list_by_application(application_name)
        runs: list[Run] = []

        for trace in traces:
            metric_results = await self.dispatcher.dispatch(trace, system_type)

            run = Run(
                run_id=uuid4(),
                trace_id=trace.trace_id,
                code_commit=_UNVERSIONED_COMMIT,
                data_snapshot_id=_UNVERSIONED_SNAPSHOT,
                metric_results=metric_results,
                created_at=datetime.now(timezone.utc),
            )

            await self.run_repository.save_run(run)
            runs.append(run)

        return runs
