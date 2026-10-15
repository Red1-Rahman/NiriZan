# src\nirizan\storage\trace_repository.py
import asyncio
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import UUID

from nirizan.instrumentation.spans import Trace
from nirizan.storage.models import SpanRecord, TraceRecord, _parse_utc_datetime

# SQLite builds older than 3.32.0 cap bound variables per statement at 999
# (SQLITE_MAX_VARIABLE_NUMBER). Stale-span deletes are batched well under that
# cap, leaving headroom for the extra trace_id parameter in each statement.
_STALE_DELETE_BATCH_SIZE = 500


def _normalize_cutoff_to_utc(created_before_iso: str) -> str:
    """Validate and normalize a timezone-aware ISO-8601 purge cutoff.

    A trailing ``Z`` (UTC designator) is accepted on every supported Python
    version by normalizing it to ``+00:00`` before parsing, rather than relying
    on interpreter-version-specific ``fromisoformat`` behavior.
    """
    candidate = created_before_iso
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        cutoff = datetime.fromisoformat(candidate)
    except ValueError as err:
        raise ValueError("created_before_iso must be a valid ISO-8601 datetime.") from err
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("created_before_iso must include a timezone offset.")
    return cutoff.astimezone(UTC).isoformat()


def _span_depths(records: list[SpanRecord]) -> dict[str, int]:
    """Parent depth per span_id (0 = root or out-of-trace parent).

    Walks parent links iteratively with memoization, so deep chains cannot hit
    the recursion limit. Records are visited in sorted span_id order, and a
    cycle is cut at the first repeated span, so the result depends only on the
    stored rows, never on fetch order.
    """
    parent_of: dict[str, str | None] = {record.span_id: record.parent_span_id for record in records}
    depths: dict[str, int] = {}

    for start in sorted(parent_of):
        if start in depths:
            continue
        chain: list[str] = []
        on_chain: set[str] = set()
        current: str | None = start
        base = 0
        while current is not None:
            cached = depths.get(current)
            if cached is not None:
                base = cached + 1
                break
            if current in on_chain:
                # A stored cycle: cut it here; every read makes the same cut.
                base = 0
                break
            if current not in parent_of:
                # The parent points outside this trace (or is None): treat as
                # a root for ordering purposes.
                base = 0
                break
            chain.append(current)
            on_chain.add(current)
            current = parent_of[current]
        else:
            base = 0
        level = base
        for node in reversed(chain):
            depths[node] = level
            level += 1
    return depths


def _span_record_from_row(row: sqlite3.Row) -> SpanRecord:
    """Build a SpanRecord from a stored span row, keeping timestamps as text."""
    return SpanRecord(
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


def _order_span_records(rows: list[tuple[int, SpanRecord]]) -> list[SpanRecord]:
    """Final read order for span rows: start instant, then parent depth, then stored order.

    The start instant comes from :func:`_parse_utc_datetime`, so legacy naive
    rows compare as UTC, exactly like SQLite's ``julianday()`` does on the SQL
    side. Timestamps are stored at text precision, but a fast nested execution
    (or a coarse wall clock) can give several spans an identical start value:
    for those exact ties a parent always precedes its children (parent depth),
    and any remaining tie keeps stored insertion order, so the result is a
    total, deterministic order that never invents timestamps.
    """
    if len(rows) < 2:
        return [record for _, record in rows]
    start_by_span_id = {
        record.span_id: _parse_utc_datetime(record.started_at) for _, record in rows
    }
    depths = _span_depths([record for _, record in rows])
    ordered = sorted(
        rows,
        key=lambda item: (
            start_by_span_id[item[1].span_id],
            depths.get(item[1].span_id, 0),
            item[0],
        ),
    )
    return [record for _, record in ordered]


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
                -- Instant-based ordering uses julianday(created_at); this
                -- expression index lets SQLite satisfy
                -- ORDER BY julianday(created_at) DESC, created_at DESC
                -- without a full scan + temp B-tree sort of every trace row.
                CREATE INDEX IF NOT EXISTS idx_traces_app_julianday 
                    ON traces(application_name, julianday(created_at));
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
                # from the incoming trace. With no incoming spans, a single
                # delete by trace_id clears the trace without reading any span
                # IDs. Otherwise the stale set is computed in Python and
                # deleted in bounded batches, so no statement binds more than
                # _STALE_DELETE_BATCH_SIZE + 1 variables, however many spans
                # the trace has. Everything runs inside the same transaction
                # as the upserts above, so the save stays atomic.
                incoming_span_ids = {span.span_id for span in trace_record.spans}
                if not incoming_span_ids:
                    self._conn.execute(
                        "DELETE FROM spans WHERE trace_id = ?",
                        (trace_record.trace_id,),
                    )
                else:
                    existing_span_ids = [
                        row["span_id"]
                        for row in self._conn.execute(
                            "SELECT span_id FROM spans WHERE trace_id = ?",
                            (trace_record.trace_id,),
                        )
                    ]
                    stale_span_ids = [
                        span_id for span_id in existing_span_ids if span_id not in incoming_span_ids
                    ]
                    for start in range(0, len(stale_span_ids), _STALE_DELETE_BATCH_SIZE):
                        batch = stale_span_ids[start : start + _STALE_DELETE_BATCH_SIZE]
                        placeholders = ", ".join("?" for _ in batch)
                        self._conn.execute(
                            f"DELETE FROM spans WHERE trace_id = ? AND span_id IN ({placeholders})",
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
                    "SELECT rowid, * FROM spans WHERE trace_id = ? "
                    "ORDER BY julianday(started_at) ASC, started_at ASC, span_id ASC",
                    (trace_id_str,),
                ).fetchall()

                spans = _order_span_records(
                    [(row["rowid"], _span_record_from_row(row)) for row in span_rows]
                )

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
                "ORDER BY julianday(created_at) DESC, created_at DESC, trace_id ASC "
                "LIMIT ? OFFSET ?"
            )
            params = (application_name, limit, offset)

            rows = self._conn.execute(query, params).fetchall()
            results = []
            for row in rows:
                trace_id = row["trace_id"]
                span_rows = self._conn.execute(
                    "SELECT rowid, * FROM spans WHERE trace_id = ? "
                    "ORDER BY julianday(started_at) ASC, started_at ASC, span_id ASC",
                    (trace_id,),
                ).fetchall()
                spans = _order_span_records(
                    [(s["rowid"], _span_record_from_row(s)) for s in span_rows]
                )
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
        normalized_cutoff = _normalize_cutoff_to_utc(created_before_iso)

        def _delete() -> int:
            with self._conn_lock, self._conn:
                # A malformed created_at makes julianday() return NULL, and
                # NULL < cutoff is never true, so such a row would silently
                # survive every purge. Fail loudly instead: the row must be
                # repaired (or removed) before purging can proceed.
                malformed = self._conn.execute(
                    "SELECT trace_id, created_at FROM traces WHERE julianday(created_at) IS NULL"
                ).fetchall()
                if malformed:
                    offenders = ", ".join(
                        f"{row['trace_id']}={row['created_at']!r}" for row in malformed
                    )
                    raise ValueError(
                        "Cannot purge: stored created_at values are not valid "
                        f"ISO-8601 datetimes: {offenders}."
                    )
                cursor = self._conn.execute(
                    "DELETE FROM traces WHERE julianday(created_at) < julianday(?)",
                    (normalized_cutoff,),
                )
                return cursor.rowcount

        return await asyncio.to_thread(_delete)

    def close(self) -> None:
        """Close database connection."""
        with self._conn_lock:
            self._conn.close()
