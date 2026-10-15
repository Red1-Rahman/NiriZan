from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4
import sqlite3

import pytest

from nirizan.instrumentation.spans import Span, SpanKind, Trace
from nirizan.storage.trace_repository import SQLiteTraceRepository

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
async def repository(tmp_path: Path) -> SQLiteTraceRepository:
    repo = SQLiteTraceRepository(str(tmp_path / "traces.db"))
    yield repo
    repo.close()


def make_span(
    trace_id: UUID,
    *,
    span_id: UUID | None = None,
    parent_span_id: UUID | None = None,
    kind: SpanKind = SpanKind.GENERATION,
    name: str = "span",
    started_at: datetime = START,
    ended_at: datetime | None = None,
    attributes: dict[str, str | int | float | bool] | None = None,
    input_payload: str | None = None,
    output_payload: str | None = None,
) -> Span:
    return Span(
        span_id=span_id or uuid4(),
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        kind=kind,
        name=name,
        started_at=started_at,
        ended_at=ended_at or started_at + timedelta(seconds=1),
        attributes=attributes or {},
        input_payload=input_payload,
        output_payload=output_payload,
    )


def make_trace(trace_id: UUID, *spans: Span) -> Trace:
    return Trace(
        trace_id=trace_id,
        application_name="storage-tests",
        spans=list(spans),
        created_at=START,
    )


def make_trace_with_span_count(
    trace_id: UUID, span_count: int, application_name: str = "storage-tests"
) -> Trace:
    """Create a trace with the specified number of spans, each with a unique span_id."""
    spans = [
        make_span(trace_id, name=f"span-{i}")
        for i in range(span_count)
    ]
    return Trace(
        trace_id=trace_id,
        application_name=application_name,
        spans=spans,
        created_at=START,
    )


@pytest.mark.asyncio
async def test_save_many_stale_spans_under_low_variable_limit(
    repository: SQLiteTraceRepository,
) -> None:
    if not hasattr(repository._conn, "setlimit"):
        pytest.skip("sqlite3.Connection.setlimit not available (Python < 3.11)")

    repository._conn.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 999)

    trace_id = uuid4()
    trace = make_trace_with_span_count(trace_id, 3000)
    await repository.save(trace)

    kept_span_ids = {s.span_id for s in trace.spans[:1200]}
    updated_trace = trace.model_copy(update={"spans": trace.spans[:1200]})
    await repository.save(updated_trace)

    stored = await repository.get(trace_id)
    assert stored is not None
    assert len(stored.spans) == 1200
    assert {s.span_id for s in stored.spans} == kept_span_ids


@pytest.mark.asyncio
@pytest.mark.parametrize("stale_count", [0, 1, 2, 3, 4, 5, 7])
async def test_stale_delete_batch_boundaries(
    repository: SQLiteTraceRepository,
    stale_count: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "nirizan.storage.trace_repository._STALE_DELETE_BATCH_SIZE", 2
    )

    trace_id = uuid4()
    trace = make_trace_with_span_count(trace_id, 10)
    await repository.save(trace)

    kept_spans = trace.spans[: 10 - stale_count]
    updated_trace = trace.model_copy(update={"spans": kept_spans})
    await repository.save(updated_trace)

    stored = await repository.get(trace_id)
    assert stored is not None
    assert len(stored.spans) == 10 - stale_count
    assert {s.span_id for s in stored.spans} == {s.span_id for s in kept_spans}


@pytest.mark.asyncio
async def test_replace_all_spans_with_new_ids(
    repository: SQLiteTraceRepository,
) -> None:
    trace_id = uuid4()
    original = make_trace_with_span_count(trace_id, 1500)
    await repository.save(original)

    new_trace = make_trace_with_span_count(trace_id, 1500)
    await repository.save(new_trace)

    stored = await repository.get(trace_id)
    assert stored is not None
    assert len(stored.spans) == 1500
    assert {s.span_id for s in stored.spans} == {s.span_id for s in new_trace.spans}


@pytest.mark.asyncio
async def test_save_with_no_spans_uses_single_direct_delete(
    repository: SQLiteTraceRepository,
) -> None:
    if not hasattr(repository._conn, "set_trace_callback"):
        pytest.skip("sqlite3.Connection.set_trace_callback not available")

    trace_id = uuid4()
    trace = make_trace_with_span_count(trace_id, 600)
    await repository.save(trace)

    executed_sql: list[str] = []

    def capture_sql(stmt: str) -> None:
        executed_sql.append(stmt)

    repository._conn.set_trace_callback(capture_sql)
    try:
        await repository.save(make_trace(trace_id))
    finally:
        repository._conn.set_trace_callback(None)

    delete_statements = [s for s in executed_sql if "DELETE FROM spans" in s]
    assert len(delete_statements) == 1
    assert "span_id IN" not in delete_statements[0]

    stored = await repository.get(trace_id)
    assert stored is not None
    assert stored.spans == []


@pytest.mark.asyncio
async def test_stale_delete_does_not_touch_other_traces(
    repository: SQLiteTraceRepository,
) -> None:
    trace_a_id = uuid4()
    trace_b_id = uuid4()

    trace_a = make_trace_with_span_count(trace_a_id, 10)
    trace_b = make_trace_with_span_count(trace_b_id, 15)
    await repository.save(trace_a)
    await repository.save(trace_b)

    updated_a = trace_a.model_copy(update={"spans": trace_a.spans[:3]})
    await repository.save(updated_a)

    stored_a = await repository.get(trace_a_id)
    stored_b = await repository.get(trace_b_id)

    assert stored_a is not None
    assert len(stored_a.spans) == 3
    assert stored_b is not None
    assert len(stored_b.spans) == 15
    assert {s.span_id for s in stored_b.spans} == {s.span_id for s in trace_b.spans}


@pytest.mark.asyncio
async def test_cross_trace_span_collision_rolls_back_stale_delete(
    repository: SQLiteTraceRepository,
) -> None:
    trace_a_id = uuid4()
    trace_b_id = uuid4()

    trace_a = make_trace_with_span_count(trace_a_id, 5)
    trace_b = make_trace_with_span_count(trace_b_id, 5)
    await repository.save(trace_a)
    await repository.save(trace_b)

    stolen_span_id = trace_b.spans[0].span_id
    kept_spans = trace_a.spans[:3]
    stolen_span = make_span(trace_a_id, span_id=stolen_span_id, name="stolen")
    updated_a = trace_a.model_copy(update={"spans": list(kept_spans) + [stolen_span]})

    with pytest.raises(ValueError, match="already belongs to another trace"):
        await repository.save(updated_a)

    stored_a = await repository.get(trace_a_id)
    stored_b = await repository.get(trace_b_id)

    assert stored_a is not None
    assert len(stored_a.spans) == 5
    assert {s.span_id for s in stored_a.spans} == {s.span_id for s in trace_a.spans}

    assert stored_b is not None
    assert len(stored_b.spans) == 5
    assert {s.span_id for s in stored_b.spans} == {s.span_id for s in trace_b.spans}


@pytest.mark.asyncio
async def test_resave_same_trace_is_idempotent(
    repository: SQLiteTraceRepository,
) -> None:
    trace_id = uuid4()
    trace = make_trace_with_span_count(trace_id, 20)
    await repository.save(trace)
    await repository.save(trace)

    stored = await repository.get(trace_id)
    assert stored is not None
    assert len(stored.spans) == 20
    assert {s.span_id for s in stored.spans} == {s.span_id for s in trace.spans}
    assert stored.spans == trace.spans


@pytest.mark.asyncio
async def test_save_replaces_mutable_fields_and_removes_stale_spans(
    repository: SQLiteTraceRepository,
) -> None:
    trace_id = uuid4()
    root_id, stale_id = uuid4(), uuid4()
    original_root = make_span(trace_id, span_id=root_id, name="old")
    stale = make_span(trace_id, span_id=stale_id, parent_span_id=root_id)
    await repository.save(make_trace(trace_id, original_root, stale))

    updated_start = START + timedelta(minutes=1)
    updated_root = make_span(
        trace_id,
        span_id=root_id,
        kind=SpanKind.RETRIEVAL,
        name="new",
        started_at=updated_start,
        attributes={"changed": True},
        input_payload="new input",
        output_payload="new output",
    )
    await repository.save(make_trace(trace_id, updated_root))

    stored = await repository.get(trace_id)
    assert stored is not None
    assert stored.spans == [updated_root]
    stored.model_validate(stored.model_dump())


@pytest.mark.asyncio
async def test_save_empty_trace_removes_previous_spans(repository: SQLiteTraceRepository) -> None:
    trace_id = uuid4()
    await repository.save(make_trace(trace_id, make_span(trace_id)))

    await repository.save(make_trace(trace_id))

    stored = await repository.get(trace_id)
    assert stored is not None
    assert stored.spans == []


@pytest.mark.asyncio
async def test_cross_trace_span_collision_preserves_ownership_and_rolls_back(
    repository: SQLiteTraceRepository,
) -> None:
    first_trace_id, second_trace_id = uuid4(), uuid4()
    first_id, second_id = uuid4(), uuid4()
    original_first = make_span(first_trace_id, span_id=first_id, name="original")
    original_second = make_span(second_trace_id, span_id=second_id, name="owner")
    await repository.save(make_trace(first_trace_id, original_first))
    await repository.save(make_trace(second_trace_id, original_second))

    attempted_update = make_span(first_trace_id, span_id=first_id, name="should rollback")
    stolen = make_span(first_trace_id, span_id=second_id, name="stolen")
    with pytest.raises(ValueError, match="already belongs to another trace"):
        await repository.save(make_trace(first_trace_id, attempted_update, stolen))

    first_stored = await repository.get(first_trace_id)
    second_stored = await repository.get(second_trace_id)
    assert first_stored is not None and first_stored.spans == [original_first]
    assert second_stored is not None and second_stored.spans == [original_second]


@pytest.mark.asyncio
async def test_repeated_identical_saves_are_deterministic_and_valid(
    repository: SQLiteTraceRepository,
) -> None:
    trace_id = uuid4()
    span = make_span(trace_id, attributes={"stable": "yes"}, input_payload="in")
    trace = make_trace(trace_id, span)

    await repository.save(trace)
    first = await repository.get(trace_id)
    await repository.save(trace)
    second = await repository.get(trace_id)

    assert first == second == trace
    assert second is not None
    assert {stored.trace_id for stored in second.spans} == {trace_id}


@pytest.mark.asyncio
async def test_get_loads_legacy_trace_with_unmarked_dangling_parent(
    repository: SQLiteTraceRepository,
) -> None:
    trace_id = uuid4()
    span_id = uuid4()
    parent_id = uuid4()
    repository._conn.execute(
        """
        INSERT INTO traces (trace_id, application_name, created_at)
        VALUES (?, ?, ?)
        """,
        (str(trace_id), "storage-tests", START.isoformat()),
    )
    repository._conn.execute(
        """
        INSERT INTO spans (
            span_id, trace_id, parent_span_id, kind, name,
            started_at, ended_at, attributes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(span_id),
            str(trace_id),
            str(parent_id),
            SpanKind.GENERATION.value,
            "legacy",
            START.isoformat(),
            (START + timedelta(seconds=1)).isoformat(),
            "{}",
        ),
    )
    repository._conn.commit()

    stored = await repository.get(trace_id)

    assert stored is not None
    assert stored.spans[0].parent_span_id == parent_id


@pytest.mark.asyncio
async def test_list_loads_legacy_trace_with_unmarked_dangling_parent(
    repository: SQLiteTraceRepository,
) -> None:
    trace_id = uuid4()
    span_id = uuid4()
    parent_id = uuid4()
    repository._conn.execute(
        """
        INSERT INTO traces (trace_id, application_name, created_at)
        VALUES (?, ?, ?)
        """,
        (str(trace_id), "storage-tests", START.isoformat()),
    )
    repository._conn.execute(
        """
        INSERT INTO spans (
            span_id, trace_id, parent_span_id, kind, name,
            started_at, ended_at, attributes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(span_id),
            str(trace_id),
            str(parent_id),
            SpanKind.GENERATION.value,
            "legacy",
            START.isoformat(),
            (START + timedelta(seconds=1)).isoformat(),
            "{}",
        ),
    )
    repository._conn.commit()

    stored = await repository.list_by_application("storage-tests")

    assert len(stored) == 1
    assert stored[0].spans[0].parent_span_id == parent_id
