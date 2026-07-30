from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from nirizan.instrumentation.spans import Span, SpanKind, Trace


def test_span_creation_and_immutability() -> None:
    span_id = uuid4()
    trace_id = uuid4()
    now = datetime.now(timezone.utc)

    span = Span(
        span_id=span_id,
        trace_id=trace_id,
        kind=SpanKind.RETRIEVAL,
        name="vector_search",
        started_at=now,
        ended_at=now,
        attributes={"top_k": 5, "query": "test"},
    )

    assert span.span_id == span_id
    assert span.kind == SpanKind.RETRIEVAL
    assert span.attributes["top_k"] == 5

    # Verify immutability (frozen=True)
    with pytest.raises(ValidationError):
        span.name = "new_name"  # type: ignore[misc]


def test_trace_span_id_mismatch_raises() -> None:
    trace_id_1 = uuid4()
    trace_id_2 = uuid4()
    now = datetime.now(timezone.utc)

    invalid_span = Span(
        span_id=uuid4(),
        trace_id=trace_id_2,
        kind=SpanKind.GENERATION,
        name="llm_call",
        started_at=now,
        ended_at=now,
    )

    with pytest.raises(ValidationError, match="does not match Trace trace_id"):
        Trace(
            trace_id=trace_id_1,
            application_name="rag_app",
            spans=[invalid_span],
            created_at=now,
        )


def test_trace_spans_of_kind_filtering() -> None:
    trace_id = uuid4()
    now = datetime.now(timezone.utc)

    span_retrieval = Span(
        span_id=uuid4(),
        trace_id=trace_id,
        kind=SpanKind.RETRIEVAL,
        name="retrieval_step",
        started_at=now,
        ended_at=now,
    )
    span_generation = Span(
        span_id=uuid4(),
        trace_id=trace_id,
        kind=SpanKind.GENERATION,
        name="generation_step",
        started_at=now,
        ended_at=now,
    )

    trace = Trace(
        trace_id=trace_id,
        application_name="rag_app",
        spans=[span_retrieval, span_generation],
        created_at=now,
    )

    retrieval_spans = trace.spans_of_kind(SpanKind.RETRIEVAL)
    assert len(retrieval_spans) == 1
    assert retrieval_spans[0].name == "retrieval_step"

    planning_spans = trace.spans_of_kind(SpanKind.PLANNING)
    assert len(planning_spans) == 0
