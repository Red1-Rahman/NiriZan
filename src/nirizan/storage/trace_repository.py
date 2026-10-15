# src\nirizan\storage\trace_repository.py
import asyncio
import sqlite3
import threading
from abc import ABC, abstractmethod
from uuid import UUID

from nirizan.instrumentation.spans import Trace
from nirizan.storage.models import SpanRecord, TraceRecord

# SQLite builds older than 3.32.0 cap bound variables per statement at 999
# (SQLITE_MAX_VARIABLE_NUMBER). Stale-span deletes are batched well under that
# cap, leaving headroom for the extra trace_id parameter in each statement.
_STALE_DELETE_BATCH_SIZE = 500


class BaseTraceRepository(ABC):
    """Abstract storage interface for persisting, querying, and managing traces.

    Per docs/contracts.md's TraceRepository interface, this operates on Trace
    directly at the public boundary. TraceRecord is a storage-internal
    serialization detail (see storage/models.py) and never crosses this
    interface; callers outside storage/ (e.g. orchestrator/collector.py)
    should never need to import TraceRecord to use a repository.
    """

    @abstractmethod
    async def save(self, trace: Trace) -> None:
        """Persist a Trace and its child spans."""
        pass

    @abstractmethod
    async def get(self, trace_id: UUID) -> Trace | None:
        """Retrieve a Trace by trace_id. Returns None if not found, never raises
        for a missing trace (see contracts.md: "the repository stays a dumb,
        honest store")."""
        pass

    @abstractmethod
    async def list_by_application(
        self,
        application_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Trace]:
        """Retrieve paginated traces filtered by application name."""
        pass

    @abstractmethod
    async def purge_older_than(self, created_before_iso: str) -> int:
        """Purge traces and associated spans created before a target ISO timestamp."""
        pass


class SQLiteTraceRepository(BaseTraceRepository):
    """Async SQLite persistence engine with indexes and query/purge capabilities."""

    def __init__(self, db_path: str = "nirizan_traces.db") -> None:
        self.db_path = db_path
        self._conn_lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._init_db()

    def _init_db(self) -> None:
        """Initialize relational schema and indexes for query optimization."""
        with self._conn_lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    application_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    code_commit TEXT,
                    data_snapshot_id TEXT,
                    session_id TEXT
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

    async def save(self, trace: Trace) -> None:
        trace_record = TraceRecord.from_trace(trace)

        def _insert() -> None:
            with self._conn_lock, self._conn:
                self._conn.execute(
                    """
                    INSERT INTO traces (
                        trace_id, application_name, created_at,
                        code_commit, data_snapshot_id, session_id
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(trace_id) DO UPDATE SET
                        application_name = excluded.application_name,
                        created_at = excluded.created_at,
                        code_commit = excluded.code_commit,
                        data_snapshot_id = excluded.data_snapshot_id,
                        session_id = excluded.session_id
                    """,
                    (
                        trace_record.trace_id,
                        trace_record.application_name,
                        trace_record.created_at,
                        trace_record.code_commit,
                        trace_record.data_snapshot_id,
                        trace_record.session_id,
                    ),
                )
                for span in trace_record.spans:
                    # A plain insert, or an update of a span that already belongs
                    # to this same trace, both touch exactly one row. A span_id
                    # that collides with a span stored under a different
                    # trace_id is excluded by the WHERE clause, so the ON
                    # CONFLICT branch updates nothing and rowcount is 0. That is
                    # the signal that a span is being stolen from another trace,
                    # so the save is aborted and rolled back by the `with
                    # self._conn:` context instead of silently cascading a
                    # delete the way INSERT OR REPLACE did.
                    cur = self._conn.execute(
                        """
                        INSERT INTO spans (
                            span_id, trace_id, parent_span_id, kind, name,
                            started_at, ended_at, attributes_json, input_payload, output_payload
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(span_id) DO UPDATE SET
                            parent_span_id = excluded.parent_span_id,
                            kind = excluded.kind,
                            name = excluded.name,
                            started_at = excluded.started_at,
                            ended_at = excluded.ended_at,
                            attributes_json = excluded.attributes_json,
                            input_payload = excluded.input_payload,
                            output_payload = excluded.output_payload
                        WHERE spans.trace_id = excluded.trace_id
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
                    if cur.rowcount == 0:
                        raise ValueError(
                            f"span {span.span_id!r} already belongs to another trace "
                            f"(attempted trace_id={span.trace_id!r})"
                        )

                # Remove spans that were stored for this trace but are absent
                # from the incoming trace. The stale set is computed in Python
                # and deleted in bounded batches, so no statement ever binds
                # more than _STALE_DELETE_BATCH_SIZE + 1 variables, however
                # many spans the trace has. All of this runs inside the same
                # transaction as the upserts above, so the save stays atomic.
                incoming_span_ids = {span.span_id for span in trace_record.spans}
                existing_span_ids = [
                    row["span_id"]
                    for row in self._conn.execute(
                        "SELECT span_id FROM spans WHERE trace_id = ?",
                        (trace_record.trace_id,),
                    )
                ]
                stale_span_ids = [
                    span_id
                    for span_id in existing_span_ids
                    if span_id not in incoming_span_ids
                ]
                for start in range(0, len(stale_span_ids), _STALE_DELETE_BATCH_SIZE):
                    batch = stale_span_ids[start : start + _STALE_DELETE_BATCH_SIZE]
                    placeholders = ", ".join("?" for _ in batch)
                    self._conn.execute(
                        f"DELETE FROM spans WHERE trace_id = ? "
                        f"AND span_id IN ({placeholders})",
                        (trace_record.trace_id, *batch),
                    )

        await asyncio.to_thread(_insert)

    async def get(self, trace_id: UUID) -> Trace | None:
        trace_id_str = str(trace_id)

        def _query() -> TraceRecord | None:
            with self._conn_lock:
                trace_row = self._conn.execute(
                    "SELECT * FROM traces WHERE trace_id = ?", (trace_id_str,)
                ).fetchone()

                if not trace_row:
                    return None

                span_rows = self._conn.execute(
                    "SELECT * FROM spans WHERE trace_id = ? ORDER BY started_at ASC",
                    (trace_id_str,),
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
                    code_commit=trace_row["code_commit"],
                    data_snapshot_id=trace_row["data_snapshot_id"],
                    session_id=trace_row["session_id"],
                )

        record = await asyncio.to_thread(_query)
        return record.to_trace(validate=False) if record is not None else None

    async def list_by_application(
        self,
        application_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Trace]:
        def _query_list() -> list[TraceRecord]:
            with self._conn_lock:
                return _query_list_locked()

        def _query_list_locked() -> list[TraceRecord]:
            query = (
                "SELECT * FROM traces WHERE application_name = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            params = (application_name, limit, offset)

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
                        code_commit=row["code_commit"],
                        data_snapshot_id=row["data_snapshot_id"],
                        session_id=row["session_id"],
                    )
                )
            return results

        records = await asyncio.to_thread(_query_list)
        return [r.to_trace(validate=False) for r in records]

    async def purge_older_than(self, created_before_iso: str) -> int:
        def _delete() -> int:
            with self._conn_lock, self._conn:
                cursor = self._conn.execute(
                    "DELETE FROM traces WHERE created_at < ?",
                    (created_before_iso,),
                )
                return cursor.rowcount

        return await asyncio.to_thread(_delete)

    def close(self) -> None:
        """Close database connection."""
        with self._conn_lock:
            self._conn.close()