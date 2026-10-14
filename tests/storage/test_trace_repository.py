from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from nirizan.instrumentation.spans import Span, SpanKind, Trace
from nirizan.storage.trace_repository import SQLiteTraceRepository

START = datetime(2026, 1, 1, tzinfo=UTC)


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
