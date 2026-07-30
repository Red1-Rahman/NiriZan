from abc import ABC, abstractmethod
import asyncio
import sqlite3
from typing import Optional

from nirizan.storage.models import SpanRecord, TraceRecord


class BaseTraceRepository(ABC):
    """Abstract storage interface for persisting, querying, and managing traces."""

    @abstractmethod
    async def save_trace(self, trace_record: TraceRecord) -> None:
        """Persist a TraceRecord and its child spans."""
        pass

    @abstractmethod
    async def get_trace(self, trace_id: str) -> Optional[TraceRecord]:
        """Retrieve a TraceRecord by trace_id."""
        pass

    @abstractmethod
    async def list_traces(
        self,
        application_name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TraceRecord]:
        """Retrieve paginated traces with optional application filtering."""
        pass

    @abstractmethod
    async def purge_older_than(self, created_before_iso: str) -> int:
        """Purge traces and associated spans created before a target ISO timestamp."""
        pass


class SQLiteTraceRepository(BaseTraceRepository):
    """Async SQLite persistence engine with indexes and query/purge capabilities."""

    def __init__(self, db_path: str = "nirizan_traces.db") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._init_db()

    def _init_db(self) -> None:
        """Initialize relational schema and indexes for query optimization."""
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
                    FOREIGN KEY(trace_id) REFERENCES traces(trace_id) ON DELETE CASCADE
                );

                -- Indexes for fast filtering and time-range queries
                CREATE INDEX IF NOT EXISTS idx_traces_app_created 
                    ON traces(application_name, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_spans_trace_id 
                    ON spans(trace_id);
                CREATE INDEX IF NOT EXISTS idx_spans_kind_started 
                    ON spans(kind, started_at DESC);
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
                "SELECT * FROM spans WHERE trace_id = ? ORDER BY started_at ASC",
                (trace_id,),
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

    async def list_traces(
        self,
        application_name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TraceRecord]:
        def _query_list() -> list[TraceRecord]:
            if application_name:
                query = "SELECT * FROM traces WHERE application_name = ? ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params = (application_name, limit, offset)
            else:
                query = "SELECT * FROM traces ORDER BY created_at DESC LIMIT ? OFFSET ?"
                params = (limit, offset)

            rows = self._conn.execute(query, params).fetchall()
            results = []
            for row in rows:
                trace_id = row["trace_id"]
                span_rows = self._conn.execute(
                    "SELECT * FROM spans WHERE trace_id = ? ORDER BY started_at ASC",
                    (trace_id,),
                ).fetchall()
                spans = [
                    SpanRecord(
                        span_id=s["span_id"],
                        trace_id=s["trace_id"],
                        parent_span_id=s["parent_span_id"],
                        kind=s["kind"],
                        name=s["name"],
                        started_at=s["started_at"],
                        ended_at=s["ended_at"],
                        attributes_json=s["attributes_json"],
                        input_payload=s["input_payload"],
                        output_payload=s["output_payload"],
                    )
                    for s in span_rows
                ]
                results.append(
                    TraceRecord(
                        trace_id=row["trace_id"],
                        application_name=row["application_name"],
                        created_at=row["created_at"],
                        spans=spans,
                    )
                )
            return results

        return await asyncio.to_thread(_query_list)

    async def purge_older_than(self, created_before_iso: str) -> int:
        def _delete() -> int:
            with self._conn:
                cursor = self._conn.execute(
                    "DELETE FROM traces WHERE created_at < ?",
                    (created_before_iso,),
                )
                return cursor.rowcount

        return await asyncio.to_thread(_delete)

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()
