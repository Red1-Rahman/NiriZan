from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime
from typing import Optional, Protocol, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from nirizan.storage.models import MetricResult, Run


class RunDiff(BaseModel):
    """Structured difference between two runs; computes only, never judges whether it's a regression."""

    model_config = ConfigDict(strict=True)

    run_a: UUID
    run_b: UUID
    metric_deltas: dict[str, float]  # metric_name -> score_b - score_a


class ExperimentStore(Protocol):
    async def record_run(self, run: Run) -> None: ...
    async def get_run(self, run_id: UUID) -> Optional[Run]: ...
    async def diff(self, run_a: UUID, run_b: UUID) -> RunDiff: ...


class SQLiteExperimentStore:
    """SQLite-backed ExperimentStore; metric_results stored as a JSON column, not a relational table."""

    def __init__(self, db_path: str = "nirizan_experiments.db") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    code_commit TEXT NOT NULL,
                    data_snapshot_id TEXT NOT NULL,
                    metric_results_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_runs_trace_id ON runs(trace_id);
                CREATE INDEX IF NOT EXISTS idx_runs_commit ON runs(code_commit);
                """
            )

    async def record_run(self, run: Run) -> None:
        metric_results_json = json.dumps([m.model_dump(mode="json") for m in run.metric_results])

        def _insert() -> None:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO runs (
                        run_id, trace_id, code_commit, data_snapshot_id,
                        metric_results_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(run.run_id),
                        str(run.trace_id),
                        run.code_commit,
                        run.data_snapshot_id,
                        metric_results_json,
                        run.created_at.isoformat(),
                    ),
                )

        await asyncio.to_thread(_insert)

    async def get_run(self, run_id: UUID) -> Optional[Run]:
        run_id_str = str(run_id)

        def _query() -> Optional[sqlite3.Row]:
            row = self._conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id_str,)
            ).fetchone()
            return cast(Optional[sqlite3.Row], row)

        row = await asyncio.to_thread(_query)
        if row is None:
            return None

        metric_results = [
            MetricResult.model_validate(m, strict=False)
            for m in json.loads(row["metric_results_json"])
        ]
        return Run(
            run_id=UUID(row["run_id"]),
            trace_id=UUID(row["trace_id"]),
            code_commit=row["code_commit"],
            data_snapshot_id=row["data_snapshot_id"],
            metric_results=metric_results,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def diff(self, run_a: UUID, run_b: UUID) -> RunDiff:
        a = await self.get_run(run_a)
        b = await self.get_run(run_b)
        if a is None or b is None:
            raise ValueError(f"diff requires both runs to exist: run_a={run_a}, run_b={run_b}")

        scores_a = {m.metric_name: m.score for m in a.metric_results}
        scores_b = {m.metric_name: m.score for m in b.metric_results}
        shared_metrics = set(scores_a) & set(scores_b)

        deltas = {name: scores_b[name] - scores_a[name] for name in shared_metrics}
        return RunDiff(run_a=run_a, run_b=run_b, metric_deltas=deltas)

    def close(self) -> None:
        self._conn.close()
