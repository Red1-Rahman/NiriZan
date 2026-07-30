from abc import ABC, abstractmethod
import asyncio
import sqlite3
from typing import Optional

from nirizan.storage.models import SpanRecord, TraceRecord


class BaseTraceRepository(ABC):
    """Abstract storage interface for persisting and retrieving traces."""

    @abstractmethod
    async def save_trace(self, trace_record: TraceRecord) -> None:
        """Persist a TraceRecord and its child spans."""
        pass

    @abstractmethod
    async def get_trace(self, trace_id: str) -> Optional[TraceRecord]:
        """Retrieve a TraceRecord by trace_id."""
        pass


class SQLiteTraceRepository(BaseTraceRepository):
    """Async SQLite persistence engine for durable trace storage."""

    def __init__(self, db_path: str = "nirizan_traces.db") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Initialize relational schema for traces and spans."""
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    application_name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS spans (
                    span_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    parent_span_id TEXT,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    attributes_json TEXT NOT NULL,
                    input_payload TEXT,
                    output_payload TEXT,
                    FOREIGN KEY(trace_id) REFERENCES traces(trace_id)
                );
                """
            )

    async def save_trace(self, trace_record: TraceRecord) -> None:
        def _insert() -> None:
            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO traces (trace_id, application_name, created_at) VALUES (?, ?, ?)",
                    (
                        trace_record.trace_id,
                        trace_record.application_name,
                        trace_record.created_at,
                    ),
                )
                for span in trace_record.spans:
                    self._conn.execute(
                        """
                        INSERT OR REPLACE INTO spans (
                            span_id, trace_id, parent_span_id, kind, name,
                            started_at, ended_at, attributes_json, input_payload, output_payload
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            span.span_id,
                            span.trace_id,
                            span.parent_span_id,
                            span.kind,
                            span.name,
                            span.started_at,
                            span.ended_at,
                            span.attributes_json,
                            span.input_payload,
                            span.output_payload,
                        ),
                    )

        await asyncio.to_thread(_insert)

    async def get_trace(self, trace_id: str) -> Optional[TraceRecord]:
        def _query() -> Optional[TraceRecord]:
            trace_row = self._conn.execute(
                "SELECT * FROM traces WHERE trace_id = ?", (trace_id,)
            ).fetchone()

            if not trace_row:
                return None

            span_rows = self._conn.execute(
                "SELECT * FROM spans WHERE trace_id = ?", (trace_id,)
            ).fetchall()

            spans = [
                SpanRecord(
                    span_id=row["span_id"],
                    trace_id=row["trace_id"],
                    parent_span_id=row["parent_span_id"],
                    kind=row["kind"],
                    name=row["name"],
                    started_at=row["started_at"],
                    ended_at=row["ended_at"],
                    attributes_json=row["attributes_json"],
                    input_payload=row["input_payload"],
                    output_payload=row["output_payload"],
                )
                for row in span_rows
            ]

            return TraceRecord(
                trace_id=trace_row["trace_id"],
                application_name=trace_row["application_name"],
                created_at=trace_row["created_at"],
                spans=spans,
            )

        return await asyncio.to_thread(_query)

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()
