from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime
from typing import Optional, Protocol, cast
from uuid import UUID

from nirizan.storage.models import Baseline


class BaselineRepository(Protocol):
    async def save_baseline(self, baseline: Baseline) -> None: ...
    async def get_baseline(self, baseline_id: UUID) -> Optional[Baseline]: ...
    async def list_baselines(self, system_type: str) -> list[Baseline]: ...


class SQLiteBaselineRepository:
    """SQLite-backed BaselineRepository; run_ids stored as a JSON column, not a junction table."""

    def __init__(self, db_path: str = "nirizan_baselines.db") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS baselines (
                    baseline_id TEXT PRIMARY KEY,
                    system_type TEXT NOT NULL,
                    run_ids_json TEXT NOT NULL,
                    established_at TEXT NOT NULL,
                    label TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_baselines_system_type ON baselines(system_type);
                """
            )

    async def save_baseline(self, baseline: Baseline) -> None:
        run_ids_json = json.dumps([str(rid) for rid in baseline.run_ids])

        def _insert() -> None:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO baselines (
                        baseline_id, system_type, run_ids_json, established_at, label
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(baseline.baseline_id),
                        baseline.system_type,
                        run_ids_json,
                        baseline.established_at.isoformat(),
                        baseline.label,
                    ),
                )

        await asyncio.to_thread(_insert)

    async def get_baseline(self, baseline_id: UUID) -> Optional[Baseline]:
        baseline_id_str = str(baseline_id)

        def _query() -> Optional[sqlite3.Row]:
            row = self._conn.execute(
                "SELECT * FROM baselines WHERE baseline_id = ?", (baseline_id_str,)
            ).fetchone()
            return cast(Optional[sqlite3.Row], row)

        row = await asyncio.to_thread(_query)
        if row is None:
            return None
        return self._row_to_baseline(row)

    async def list_baselines(self, system_type: str) -> list[Baseline]:
        def _query() -> list[sqlite3.Row]:
            return self._conn.execute(
                "SELECT * FROM baselines WHERE system_type = ? ORDER BY established_at DESC",
                (system_type,),
            ).fetchall()

        rows = await asyncio.to_thread(_query)
        return [self._row_to_baseline(row) for row in rows]

    def _row_to_baseline(self, row: sqlite3.Row) -> Baseline:
        return Baseline(
            baseline_id=UUID(row["baseline_id"]),
            system_type=row["system_type"],
            run_ids=[UUID(rid) for rid in json.loads(row["run_ids_json"])],
            established_at=datetime.fromisoformat(row["established_at"]),
            label=row["label"],
        )

    def close(self) -> None:
        self._conn.close()
