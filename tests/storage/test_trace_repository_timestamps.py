# tests/storage/test_trace_repository_timestamps.py
"""Timestamp policy tests for SQLiteTraceRepository.

Covers the storage timestamp contract:
- WRITE strict: naive datetimes are rejected at save/purge boundaries.
- READ tolerant: legacy naive rows are read as UTC, returned aware, warned
  about once per process, and never rewritten on read.
- PURGE cutoff must be aware, accepts a trailing ``Z``, and compares by
  instant via ``julianday()``.
- Deterministic read ordering: start instant, then parent depth, then stored
  order, with ``julianday()``'s millisecond granularity characterized.
"""

import logging
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from nirizan.instrumentation.spans import Span, SpanKind, Trace
from nirizan.storage.models import TraceRecord, _OnceLatch
from nirizan.storage.trace_repository import SQLiteTraceRepository

START = datetime(2026, 1, 1, tzinfo=UTC)
MODELS_LOGGER = "nirizan.storage.models"


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
    name: str = "span",
    started_at: datetime = START,
    ended_at: datetime | None = None,
) -> Span:
    return Span(
        span_id=span_id or uuid4(),
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        kind=SpanKind.GENERATION,
        name=name,
        started_at=started_at,
        ended_at=ended_at or started_at + timedelta(seconds=1),
        attributes={},
    )


def insert_trace_row(
    repository: SQLiteTraceRepository,
    trace_id: UUID,
    created_at: str,
    application_name: str = "timestamp-tests",
) -> None:
    repository._conn.execute(
        "INSERT INTO traces (trace_id, application_name, created_at) VALUES (?, ?, ?)",
        (str(trace_id), application_name, created_at),
    )


def insert_span_row(
    repository: SQLiteTraceRepository,
    trace_id: UUID,
    span_id: UUID,
    *,
    parent_span_id: UUID | None = None,
    started_at: str,
    ended_at: str,
    name: str = "raw-span",
) -> None:
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
            str(parent_span_id) if parent_span_id else None,
            SpanKind.GENERATION.value,
            name,
            started_at,
            ended_at,
            "{}",
        ),
    )


def model_warning_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.name == MODELS_LOGGER and record.levelno == logging.WARNING
    ]


def raw_created_at(repository: SQLiteTraceRepository, trace_id: UUID) -> str | None:
    row = repository._conn.execute(
        "SELECT created_at FROM traces WHERE trace_id = ?", (str(trace_id),)
    ).fetchone()
    return row["created_at"] if row else None


# ---------------------------------------------------------------------------
# READ tolerant: legacy naive rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_reads_legacy_naive_row_as_utc_with_single_warning(
    repository: SQLiteTraceRepository,
    caplog: pytest.LogCaptureFixture,
    fresh_legacy_latch: _OnceLatch,
) -> None:
    trace_id = uuid4()
    span_id = uuid4()
    insert_trace_row(repository, trace_id, "2025-06-01T12:00:00")
    insert_span_row(
        repository,
        trace_id,
        span_id,
        started_at="2025-06-01T12:00:00",
        ended_at="2025-06-01T12:00:01",
    )
    repository._conn.commit()

    with caplog.at_level(logging.WARNING):
        stored = await repository.get(trace_id)
        # A second read in the same process must not warn again.
        again = await repository.get(trace_id)
        listed = await repository.list_by_application("timestamp-tests")

    assert stored is not None and again is not None
    assert stored.created_at == datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    assert stored.created_at.tzinfo is not None
    assert stored.spans[0].started_at == datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    assert stored.spans[0].ended_at == datetime(2025, 6, 1, 12, 0, 1, tzinfo=UTC)
    assert len(listed) == 1

    warnings = model_warning_records(caplog)
    assert len(warnings) == 1
    assert "2025-06-01T12:00:00" in warnings[0].getMessage()
    assert "UTC" in warnings[0].getMessage()

    # The read path never rewrites the stored row.
    assert raw_created_at(repository, trace_id) == "2025-06-01T12:00:00"


@pytest.mark.asyncio
async def test_list_reads_legacy_naive_row_as_utc(
    repository: SQLiteTraceRepository,
    fresh_legacy_latch: _OnceLatch,
) -> None:
    trace_id = uuid4()
    insert_trace_row(repository, trace_id, "2025-06-01T12:00:00")
    repository._conn.commit()

    listed = await repository.list_by_application("timestamp-tests")

    assert len(listed) == 1
    assert listed[0].created_at == datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    assert listed[0].created_at.tzinfo is not None
    assert raw_created_at(repository, trace_id) == "2025-06-01T12:00:00"


@pytest.mark.asyncio
async def test_get_with_validate_false_keeps_legacy_naive_read_working() -> None:
    record = TraceRecord(
        trace_id=str(uuid4()),
        application_name="timestamp-tests",
        created_at="2025-06-01T12:00:00",
        spans=[],
    )

    trace = record.to_trace(validate=False)

    assert trace.created_at == datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    assert trace.created_at.tzinfo is not None


@pytest.mark.asyncio
async def test_legacy_naive_span_ordering_matches_instant_order(
    repository: SQLiteTraceRepository,
    fresh_legacy_latch: _OnceLatch,
) -> None:
    """Naive spans order among aware spans by their implied UTC instant."""
    trace_id = uuid4()
    naive_id = uuid4()
    aware_id = uuid4()
    insert_trace_row(repository, trace_id, "2025-06-01T12:00:00")
    # Aware span at 11:59:59Z; naive span written as local-looking text at
    # 11:00:00 (interpreted as UTC, so it starts earlier).
    insert_span_row(
        repository,
        trace_id,
        naive_id,
        started_at="2025-06-01T11:00:00",
        ended_at="2025-06-01T11:00:01",
    )
    insert_span_row(
        repository,
        trace_id,
        aware_id,
        started_at="2025-06-01T11:59:59+00:00",
        ended_at="2025-06-01T12:00:00+00:00",
    )
    repository._conn.commit()

    stored = await repository.get(trace_id)

    assert stored is not None
    assert [span.span_id for span in stored.spans] == [naive_id, aware_id]


# ---------------------------------------------------------------------------
# Z suffix and mixed offsets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_reads_stored_z_suffix_timestamps(
    repository: SQLiteTraceRepository,
) -> None:
    trace_id = uuid4()
    span_id = uuid4()
    insert_trace_row(repository, trace_id, "2026-01-01T00:00:00Z")
    insert_span_row(
        repository,
        trace_id,
        span_id,
        started_at="2026-01-01T00:00:00Z",
        ended_at="2026-01-01T00:00:01Z",
    )
    repository._conn.commit()

    stored = await repository.get(trace_id)

    assert stored is not None
    assert stored.created_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert stored.created_at.utcoffset() == timedelta(0)
    assert stored.spans[0].started_at.utcoffset() == timedelta(0)


@pytest.mark.asyncio
async def test_purge_accepts_cutoff_with_trailing_z(
    repository: SQLiteTraceRepository,
) -> None:
    older_id, newer_id = uuid4(), uuid4()
    insert_trace_row(repository, older_id, "2026-01-01T00:00:00+00:00")
    insert_trace_row(repository, newer_id, "2026-01-03T00:00:00+00:00")
    repository._conn.commit()

    deleted = await repository.purge_older_than("2026-01-02T00:00:00Z")

    assert deleted == 1
    assert await repository.get(older_id) is None
    assert await repository.get(newer_id) is not None


@pytest.mark.asyncio
async def test_purge_rejects_a_cutoff_that_is_not_an_iso_datetime(
    repository: SQLiteTraceRepository,
) -> None:
    """A cutoff that is not a datetime at all is a ValueError, not a silent no-op.

    ``purge_older_than`` parses the cutoff before touching the database, so an
    unparseable string must leave every stored row exactly where it was.
    """
    trace_id = uuid4()
    insert_trace_row(repository, trace_id, "2026-01-01T00:00:00+00:00")
    repository._conn.commit()

    with pytest.raises(ValueError, match="valid ISO-8601"):
        await repository.purge_older_than("not-a-timestamp")

    assert raw_created_at(repository, trace_id) == "2026-01-01T00:00:00+00:00"


@pytest.mark.parametrize(
    ("stored", "expected_utc_text"),
    [
        # +06:00, +05:30 (a half-hour offset) and -03:30 (a negative half-hour
        # offset) all have to normalize to the same canonical UTC form.
        ("2026-01-01T06:00:00+06:00", "2026-01-01T00:00:00+00:00"),
        ("2026-01-01T05:30:00+05:30", "2026-01-01T00:00:00+00:00"),
        ("2025-12-31T20:30:00-03:30", "2026-01-01T00:00:00+00:00"),
        # A ``Z`` designator is the same instant written the other way; it is
        # canonicalized to ``+00:00`` rather than stored verbatim.
        ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00+00:00"),
    ],
)
@pytest.mark.asyncio
async def test_every_supported_offset_round_trips_to_canonical_utc_text(
    repository: SQLiteTraceRepository,
    stored: str,
    expected_utc_text: str,
) -> None:
    """Each supported offset form is stored as canonical UTC text and read back.

    The read-back assertions matter as much as the stored text: a row written
    with an offset has to come back as the same instant in UTC, not as a
    reinterpreted wall clock.
    """
    trace_id = uuid4()
    insert_trace_row(repository, trace_id, stored)
    insert_span_row(
        repository,
        trace_id,
        uuid4(),
        started_at=stored,
        ended_at="2026-01-01T00:00:01+00:00",
    )
    repository._conn.commit()

    read_back = await repository.get(trace_id)
    assert read_back is not None
    assert read_back.created_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert read_back.spans[0].started_at == datetime(2026, 1, 1, tzinfo=UTC)

    local = datetime.fromisoformat(stored)
    await repository.save(
        Trace(
            trace_id=trace_id,
            application_name="timestamp-tests",
            created_at=local,
            spans=[make_span(trace_id, started_at=local, ended_at=local)],
        )
    )

    assert raw_created_at(repository, trace_id) == expected_utc_text
    stored_span_row = repository._conn.execute(
        "SELECT started_at, ended_at FROM spans WHERE trace_id = ?", (str(trace_id),)
    ).fetchone()
    assert stored_span_row["started_at"] == expected_utc_text
    assert stored_span_row["ended_at"] == expected_utc_text


@pytest.mark.asyncio
async def test_mixed_offset_rows_order_by_instant_not_string(
    repository: SQLiteTraceRepository,
) -> None:
    trace_id = uuid4()
    first = uuid4()
    second = uuid4()
    insert_trace_row(repository, trace_id, "2026-01-01T00:00:00+00:00")
    # Same instant as 00:00:00Z but a lexicographically larger string.
    insert_span_row(
        repository,
        trace_id,
        first,
        started_at="2026-01-01T05:30:00+05:30",
        ended_at="2026-01-01T05:30:01+05:30",
    )
    insert_span_row(
        repository,
        trace_id,
        second,
        started_at="2026-01-01T00:00:01+00:00",
        ended_at="2026-01-01T00:00:02+00:00",
    )
    repository._conn.commit()

    stored = await repository.get(trace_id)

    assert stored is not None
    assert [span.span_id for span in stored.spans] == [first, second]
    assert stored.spans[0].started_at == datetime(2026, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Malformed stored timestamps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_raises_clear_error_for_malformed_span_timestamp(
    repository: SQLiteTraceRepository,
) -> None:
    trace_id = uuid4()
    insert_trace_row(repository, trace_id, "2026-01-01T00:00:00+00:00")
    insert_span_row(
        repository,
        trace_id,
        uuid4(),
        started_at="not-a-timestamp",
        ended_at="2026-01-01T00:00:01+00:00",
    )
    repository._conn.commit()

    with pytest.raises(ValueError) as excinfo:
        await repository.get(trace_id)
    # The clear-error contract: names the stored text AND says why.
    assert "not-a-timestamp" in str(excinfo.value)
    assert "not a valid ISO-8601 datetime" in str(excinfo.value)


@pytest.mark.asyncio
async def test_get_raises_clear_error_for_malformed_trace_timestamp(
    repository: SQLiteTraceRepository,
) -> None:
    trace_id = uuid4()
    insert_trace_row(repository, trace_id, "yesterday-ish")

    with pytest.raises(ValueError) as excinfo:
        await repository.get(trace_id)
    assert "yesterday-ish" in str(excinfo.value)
    assert "not a valid ISO-8601 datetime" in str(excinfo.value)


@pytest.mark.asyncio
async def test_list_raises_clear_error_for_malformed_timestamp(
    repository: SQLiteTraceRepository,
) -> None:
    trace_id = uuid4()
    insert_trace_row(repository, trace_id, "not-a-datetime")
    repository._conn.commit()

    with pytest.raises(ValueError) as excinfo:
        await repository.list_by_application("timestamp-tests")
    assert "not-a-datetime" in str(excinfo.value)
    assert "not a valid ISO-8601 datetime" in str(excinfo.value)


@pytest.mark.asyncio
async def test_purge_refuses_to_silently_skip_malformed_rows(
    repository: SQLiteTraceRepository,
) -> None:
    malformed_id, valid_old_id = uuid4(), uuid4()
    insert_trace_row(repository, malformed_id, "not-a-datetime")
    insert_trace_row(repository, valid_old_id, "2020-01-01T00:00:00+00:00")
    repository._conn.commit()

    with pytest.raises(ValueError, match="not-a-datetime"):
        await repository.purge_older_than("2026-01-01T00:00:00+00:00")

    # Nothing was deleted: the offending row and the deletable row both remain,
    # so a purge can never quietly leave malformed rows behind forever.
    assert raw_created_at(repository, malformed_id) == "not-a-datetime"
    assert raw_created_at(repository, valid_old_id) == "2020-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Purge boundary, cascade, and write atomicity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_purge_boundary_is_exclusive_at_exact_cutoff(
    repository: SQLiteTraceRepository,
) -> None:
    at_cutoff, just_before, just_after = uuid4(), uuid4(), uuid4()
    insert_trace_row(repository, at_cutoff, "2026-01-02T00:00:00+00:00")
    insert_trace_row(repository, just_before, "2026-01-01T23:59:59+00:00")
    insert_trace_row(repository, just_after, "2026-01-02T00:00:01+00:00")
    repository._conn.commit()

    deleted = await repository.purge_older_than("2026-01-02T00:00:00+00:00")

    assert deleted == 1
    assert await repository.get(at_cutoff) is not None
    assert await repository.get(just_before) is None
    assert await repository.get(just_after) is not None


@pytest.mark.asyncio
async def test_purge_cascades_span_delete_verified_by_query(
    repository: SQLiteTraceRepository,
) -> None:
    trace_id = uuid4()
    span_id = uuid4()
    insert_trace_row(repository, trace_id, "2020-01-01T00:00:00+00:00")
    insert_span_row(
        repository,
        trace_id,
        span_id,
        started_at="2020-01-01T00:00:00+00:00",
        ended_at="2020-01-01T00:00:01+00:00",
    )
    repository._conn.commit()

    deleted = await repository.purge_older_than("2026-01-01T00:00:00+00:00")

    assert deleted == 1
    remaining = repository._conn.execute(
        "SELECT count(*) AS n FROM spans WHERE trace_id = ?", (str(trace_id),)
    ).fetchone()
    assert remaining["n"] == 0


@pytest.mark.asyncio
async def test_failed_save_with_naive_span_leaves_database_untouched(
    repository: SQLiteTraceRepository,
) -> None:
    """A naive span timestamp aborts the whole save before any row is written."""
    trace_id = uuid4()
    trace = Trace(
        trace_id=trace_id,
        application_name="timestamp-tests",
        created_at=START,
        spans=[
            make_span(trace_id, name="valid"),
            make_span(trace_id, name="naive", started_at=datetime(2026, 1, 1)),
        ],
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        await repository.save(trace)

    traces_left = repository._conn.execute("SELECT count(*) AS n FROM traces").fetchone()
    spans_left = repository._conn.execute("SELECT count(*) AS n FROM spans").fetchone()
    assert traces_left["n"] == 0
    assert spans_left["n"] == 0


# ---------------------------------------------------------------------------
# Deterministic read ordering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_identical_start_instant_orders_parent_before_child(
    repository: SQLiteTraceRepository,
) -> None:
    """A parent precedes its children when every start timestamp is identical.

    The child row is inserted first and its span_id sorts before the parent's,
    so both insertion order and span_id order would put the child first; only
    parent-depth ordering produces the correct result.
    """
    trace_id = uuid4()
    parent_id = UUID("00000000-0000-0000-0000-000000000002")
    child_id = UUID("00000000-0000-0000-0000-000000000001")
    grandchild_id = UUID("00000000-0000-0000-0000-000000000003")
    unrelated_id = UUID("00000000-0000-0000-0000-000000000004")
    insert_trace_row(repository, trace_id, "2026-01-01T00:00:00+00:00")
    same_started = "2026-01-01T00:00:00.000000+00:00"
    same_ended = "2026-01-01T00:00:01.000000+00:00"
    # Insertion order: child, grandchild, parent, unrelated root.
    insert_span_row(
        repository,
        trace_id,
        child_id,
        parent_span_id=parent_id,
        started_at=same_started,
        ended_at=same_ended,
        name="child",
    )
    insert_span_row(
        repository,
        trace_id,
        grandchild_id,
        parent_span_id=child_id,
        started_at=same_started,
        ended_at=same_ended,
        name="grandchild",
    )
    insert_span_row(
        repository,
        trace_id,
        parent_id,
        started_at=same_started,
        ended_at=same_ended,
        name="parent",
    )
    insert_span_row(
        repository,
        trace_id,
        unrelated_id,
        started_at=same_started,
        ended_at=same_ended,
        name="unrelated",
    )
    repository._conn.commit()

    first = await repository.get(trace_id)
    second = await repository.get(trace_id)

    assert first is not None and second is not None
    # Roots (depth 0) keep stored order: parent was inserted third but is a
    # root, the unrelated span fourth and also a root. Then depth 1 (child),
    # then depth 2 (grandchild).
    expected = [parent_id, unrelated_id, child_id, grandchild_id]
    assert [span.span_id for span in first.spans] == expected
    # Reads are deterministic across repeated calls.
    assert [span.span_id for span in second.spans] == expected


@pytest.mark.asyncio
async def test_sub_millisecond_starts_order_by_exact_instant(
    repository: SQLiteTraceRepository,
) -> None:
    """Spans that collapse to the same julianday millisecond still order exactly.

    ``.000999`` and ``.001000`` round to the same millisecond in julianday(),
    so SQL's instant key cannot separate them; the stored-order tiebreak and
    the Python exact-instant ordering must agree on the true order.
    """
    trace_id = uuid4()
    earlier_id = UUID("00000000-0000-0000-0000-000000000009")
    later_id = UUID("00000000-0000-0000-0000-000000000008")
    insert_trace_row(repository, trace_id, "2026-01-01T00:00:00+00:00")
    # Insert the later span first; its span_id also sorts first, so neither
    # insertion order nor span_id order matches the true instant order.
    insert_span_row(
        repository,
        trace_id,
        later_id,
        started_at="2026-01-01T00:00:00.001000+00:00",
        ended_at="2026-01-01T00:00:01.000000+00:00",
    )
    insert_span_row(
        repository,
        trace_id,
        earlier_id,
        started_at="2026-01-01T00:00:00.000999+00:00",
        ended_at="2026-01-01T00:00:01.000000+00:00",
    )
    repository._conn.commit()

    stored = await repository.get(trace_id)

    assert stored is not None
    assert [span.span_id for span in stored.spans] == [earlier_id, later_id]


@pytest.mark.asyncio
async def test_parent_cycle_in_stored_rows_is_read_without_hanging(
    repository: SQLiteTraceRepository,
) -> None:
    """A stored parent cycle must not hang or raise; both spans are returned."""
    trace_id = uuid4()
    first_id = uuid4()
    second_id = uuid4()
    insert_trace_row(repository, trace_id, "2026-01-01T00:00:00+00:00")
    insert_span_row(
        repository,
        trace_id,
        first_id,
        parent_span_id=second_id,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:00:01+00:00",
    )
    insert_span_row(
        repository,
        trace_id,
        second_id,
        parent_span_id=first_id,
        started_at="2026-01-01T00:00:00+00:00",
        ended_at="2026-01-01T00:00:01+00:00",
    )
    repository._conn.commit()

    stored = await repository.get(trace_id)

    assert stored is not None
    assert {span.span_id for span in stored.spans} == {first_id, second_id}


@pytest.mark.asyncio
async def test_list_pagination_breaks_created_at_ties_deterministically(
    repository: SQLiteTraceRepository,
) -> None:
    """Traces sharing a created_at paginate without gaps or duplicates."""
    trace_ids = sorted(str(uuid4()) for _ in range(4))
    # Insert in a seeded-random order so neither rowid order nor index scan
    # order coincides with trace_id order; without the trace_id tiebreak the
    # pages then come back scrambled rather than accidentally sorted.
    shuffled = trace_ids[:]
    random.Random(1234).shuffle(shuffled)
    for trace_id in shuffled:
        insert_trace_row(repository, UUID(trace_id), "2026-01-01T00:00:00+00:00")
    repository._conn.commit()

    page_one = await repository.list_by_application("timestamp-tests", limit=2, offset=0)
    page_two = await repository.list_by_application("timestamp-tests", limit=2, offset=2)

    observed = [str(trace.trace_id) for trace in page_one + page_two]
    # Equal created_at ties fall back to trace_id ascending, which is stable
    # regardless of SQLite's unspecified row order.
    assert observed == trace_ids


@pytest.mark.asyncio
async def test_legacy_mixed_offset_rows_within_one_millisecond_paginate_deterministically(
    repository: SQLiteTraceRepository,
) -> None:
    """Characterization of the millisecond ordering limit for legacy rows.

    ``julianday()`` resolves to about a millisecond, and trace listing is
    ordered and paginated entirely in SQL, so two legacy rows whose instants
    land in the same millisecond cannot be separated by their exact instants:
    the stored text decides, then ``trace_id``. The order is still total, so
    pagination returns each row exactly once with no gaps.

    An implementation that compares exact instants instead of ``julianday()``
    would flip the tied pair here (the ``+01:00`` row is 999 microseconds
    *earlier* than the ``+00:00`` row but sorts later as text). A change like
    that is a behavior change, not a refactor, so it has to update this test
    deliberately rather than discover it in production.
    """
    tied_offset_text = "2026-01-01T01:00:00.000999+01:00"
    tied_utc_text = "2026-01-01T00:00:00.001000+00:00"
    later_text = "2026-01-01T02:00:00+00:00"

    # Premise, checked against SQLite directly: the two legacy values must
    # resolve to the same Julian day number, otherwise this test is not about
    # what it claims to be about.
    resolved = repository._conn.execute(
        "SELECT julianday(?), julianday(?)", (tied_offset_text, tied_utc_text)
    ).fetchone()
    assert resolved[0] is not None, "julianday() returned NULL for a legacy offset timestamp"
    assert resolved[0] == resolved[1], (
        "premise failed on this SQLite build: "
        f"julianday({tied_offset_text!r})={resolved[0]!r} and "
        f"julianday({tied_utc_text!r})={resolved[1]!r} are not equal, so the rows do "
        "not tie within a millisecond and this characterization does not apply"
    )

    # trace_id values chosen so that neither tiebreak agrees with insertion
    # order or with the other tiebreak: dropping either from the ORDER BY
    # changes the result, which is what makes this test able to detect it.
    later_id = UUID("00000000-0000-0000-0000-0000000000c0")
    tied_offset_id = UUID("00000000-0000-0000-0000-00000000ff00")
    tied_utc_id = UUID("00000000-0000-0000-0000-000000000000")
    for trace_id, created_at in (
        (tied_utc_id, tied_utc_text),
        (tied_offset_id, tied_offset_text),
        (later_id, later_text),
    ):
        insert_trace_row(repository, trace_id, created_at)
    repository._conn.commit()

    # Documented rule: instant descending (the later row first), then stored
    # text descending for rows that tie inside a millisecond. Text descending
    # puts the 01:00 row ahead of the 00:00 row, even though it is the earlier
    # instant.
    assert tied_offset_text > tied_utc_text
    expected = [str(later_id), str(tied_offset_id), str(tied_utc_id)]

    paged: list[str] = []
    for offset in range(3):
        page = await repository.list_by_application("timestamp-tests", limit=1, offset=offset)
        assert len(page) == 1
        paged.extend(str(trace.trace_id) for trace in page)

    assert paged == expected
    assert len(set(paged)) == 3, "a trace id appeared on more than one page"
    assert paged[0] == str(later_id)
    assert paged[1:] == [str(tied_offset_id), str(tied_utc_id)]

    single_call = await repository.list_by_application("timestamp-tests", limit=3)
    assert [str(trace.trace_id) for trace in single_call] == expected

    # The remaining tiebreak: rows with the same instant and the same stored
    # text are separated only by trace_id ascending. Six of them, inserted in a
    # seeded order that matches neither trace_id order nor reverse order,
    # because a smaller set can come back sorted by accident when the term is
    # missing from the ORDER BY.
    twins = [UUID(f"00000000-0000-0000-0001-0000000000{index:02x}") for index in range(6)]
    insertion_order = twins[:]
    random.Random(7).shuffle(insertion_order)
    for twin in insertion_order:
        insert_trace_row(repository, twin, "2026-01-01T03:00:00.000500+00:00", "twin-tests")
    repository._conn.commit()

    listed_twins = await repository.list_by_application("twin-tests")

    assert [str(trace.trace_id) for trace in listed_twins] == sorted(str(twin) for twin in twins)


@pytest.mark.asyncio
async def test_equal_start_and_depth_keep_stored_insertion_order(
    repository: SQLiteTraceRepository,
) -> None:
    """Sibling spans with the same start instant come back in stored order.

    The SQL key cannot separate them (identical ``julianday`` and identical
    text), and neither can parent depth, since they are all roots. The final
    tiebreak is stored insertion order, so the read is still total and
    deterministic; this pins that behavior so a future change to it is
    deliberate.
    """
    trace_id = uuid4()
    # Deliberately insert in an order that differs from span_id order.
    span_ids = [
        UUID("00000000-0000-0000-0000-0000000000ff"),
        UUID("00000000-0000-0000-0000-0000000000aa"),
        UUID("00000000-0000-0000-0000-000000000055"),
    ]
    insert_trace_row(repository, trace_id, "2026-01-01T00:00:00+00:00")
    for span_id in span_ids:
        insert_span_row(
            repository,
            trace_id,
            span_id,
            started_at="2026-01-01T00:00:00.000000+00:00",
            ended_at="2026-01-01T00:00:01.000000+00:00",
        )
    repository._conn.commit()

    first = await repository.get(trace_id)
    second = await repository.get(trace_id)

    assert first is not None and second is not None
    assert [span.span_id for span in first.spans] == span_ids
    assert [span.span_id for span in second.spans] == span_ids


@pytest.mark.asyncio
async def test_naive_trace_timestamp_is_rejected_before_any_row_is_written(
    repository: SQLiteTraceRepository,
) -> None:
    """A naive ``created_at`` fails the write path before the transaction opens."""
    trace_id = uuid4()

    with pytest.raises(ValueError, match="timezone-aware"):
        await repository.save(
            Trace(
                trace_id=trace_id,
                application_name="timestamp-tests",
                created_at=datetime(2026, 1, 1),
                spans=[make_span(trace_id, name="valid")],
            )
        )

    assert raw_created_at(repository, trace_id) is None
    traces_left = repository._conn.execute("SELECT count(*) AS n FROM traces").fetchone()
    spans_left = repository._conn.execute("SELECT count(*) AS n FROM spans").fetchone()
    assert traces_left["n"] == 0
    assert spans_left["n"] == 0
