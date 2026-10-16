# src\nirizan\storage\run_repository.py
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from nirizan.storage.models import Run


class RunRepository(Protocol):
    """Minimal, additive Run persistence, narrower than Phase 3's ExperimentStore."""

    async def save_run(self, run: Run) -> None: ...
    async def get_run(self, run_id: UUID) -> Run | None: ...


class InMemoryRunRepository:
    """Dict-backed RunRepository; get_run returns None for a missing run, never raises."""

    def __init__(self) -> None:
        self._runs: dict[UUID, Run] = {}

    async def save_run(self, run: Run) -> None:
        self._runs[run.run_id] = run

    async def get_run(self, run_id: UUID) -> Run | None:
        return self._runs.get(run_id)
