# tests/storage/test_otel_boundary_isolation.py
"""L4 isolation layer: storage persists OTel-shaped traces without OpenTelemetry.

Traces that originated on the OpenTelemetry bridge carry data shapes the core
tracer never produces on its own: synthetic-parent markers, provenance
attributes, session ids recovered from stashed identifiers, and spans whose
parents were re-attached during ingestion. All of that is plain core data by
the time it reaches the repository, and this layer proves the storage layer
persists and returns it faithfully with no OpenTelemetry dependency.

Core-only file: never imports ``opentelemetry`` (the core-only CI leg runs it
with the extra absent).
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from nirizan.instrumentation.spans import (
    SYNTHETIC_PARENT_ATTRIBUTE,
    Span,
    SpanKind,
    Trace,
)
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
    name: str,
    parent_span_id: UUID | None = None,
    attributes: dict[str, str | int | float | bool] | None = None,
) -> Span:
    return Span(
        span_id=uuid4(),
        trace_id=trace_id,
        parent_span_id=parent_span_id,
        kind=SpanKind.GENERATION,
        name=name,
        started_at=START,
        ended_at=START,
        attributes=attributes or {},
    )


def otel_shaped_trace() -> Trace:
    """A trace with every data shape the OTel ingestion path can produce."""
    trace_id = uuid4()
    root_id = uuid4()
    orphan_id = uuid4()
    return Trace(
        trace_id=trace_id,
        application_name="otel-shaped",
        created_at=START,
        session_id=uuid4(),
        spans=[
            Span(
                span_id=root_id,
                trace_id=trace_id,
                parent_span_id=None,
                kind=SpanKind.PLANNING,
                name="root",
                started_at=START,
                ended_at=START,
                attributes={"nirizan.id.source": "derived"},
            ),
            Span(
                span_id=orphan_id,
                trace_id=trace_id,
                parent_span_id=uuid4(),  # dangling: parent lives upstream
                kind=SpanKind.GENERATION,
                name="orphan-child",
                started_at=START,
                ended_at=START,
                attributes={
                    SYNTHETIC_PARENT_ATTRIBUTE: True,
                    "nirizan.id.source": "roundtrip",
                },
            ),
        ],
    )


async def test_otel_shaped_trace_round_trips_through_storage(
    repository: SQLiteTraceRepository,
) -> None:
    trace = otel_shaped_trace()

    await repository.save(trace)
    stored = await repository.get(trace.trace_id)

    assert stored is not None
    assert stored.session_id == trace.session_id
    by_name = {s.name: s for s in stored.spans}
    assert by_name["orphan-child"].parent_span_id == trace.spans[1].parent_span_id
    assert by_name["orphan-child"].attributes[SYNTHETIC_PARENT_ATTRIBUTE] is True
    assert by_name["root"].attributes["nirizan.id.source"] == "derived"


async def test_synthetic_parent_traces_are_listed_like_any_other(
    repository: SQLiteTraceRepository,
) -> None:
    trace = otel_shaped_trace()
    await repository.save(trace)

    listed = await repository.list_by_application("otel-shaped")

    assert [t.trace_id for t in listed] == [trace.trace_id]


async def test_re_saving_an_ingested_trace_replaces_its_spans(
    repository: SQLiteTraceRepository,
) -> None:
    """The ingestion-to-storage replacement contract holds for otel shapes too."""
    trace = otel_shaped_trace()
    await repository.save(trace)
    trimmed = trace.model_copy(update={"spans": trace.spans[:1]})

    await repository.save(trimmed)
    stored = await repository.get(trace.trace_id)

    assert stored is not None
    assert len(stored.spans) == 1
    assert stored.spans[0].name == "root"
