# tests/metrics/test_rag_triad.py
import logging
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from nirizan.instrumentation.spans import Span, SpanKind, Trace
from nirizan.metrics.rag_triad import RAGTriadMetric


def dummy_scorer(text_a: str, text_b: str) -> float:
    return 0.85


def build_test_trace(
    *,
    query: str | None = "What is capital of France?",
    context: str | None = "Paris is the capital of France.",
    answer: str | None = "The capital of France is Paris.",
) -> Trace:
    trace_id = uuid4()
    now = datetime.now(timezone.utc)
    spans: list[Span] = []

    if query is not None:
        spans.append(
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.PLANNING,
                name="planning_span",
                started_at=now,
                ended_at=now,
                input_payload=query,
            )
        )

    if context is not None:
        spans.append(
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.RETRIEVAL,
                name="retrieval_span",
                started_at=now,
                ended_at=now,
                output_payload=context,
            )
        )

    if answer is not None:
        spans.append(
            Span(
                span_id=uuid4(),
                trace_id=trace_id,
                kind=SpanKind.GENERATION,
                name="generation_span",
                started_at=now,
                ended_at=now,
                output_payload=answer,
            )
        )

    return Trace(
        trace_id=trace_id,
        application_name="test_app",
        spans=spans,
        created_at=now,
    )


@pytest.mark.asyncio
async def test_rag_triad_full_evaluation(caplog: pytest.LogCaptureFixture) -> None:
    trace = build_test_trace()
    metric = RAGTriadMetric(scorer=dummy_scorer)

    with caplog.at_level(logging.INFO):
        results = await metric.evaluate(trace)

    assert len(results) == 3
    metric_names = {r.metric_name for r in results}
    assert metric_names == {"context_relevance", "groundedness", "answer_relevance"}
    assert all(r.score == 0.85 for r in results)
    assert all(r.trace_id == trace.trace_id for r in results)
    assert all(r.details == {} for r in results)
    assert f"Evaluating RAGTriadMetric for trace_id={trace.trace_id}" in caplog.text
    assert f"completed for trace_id={trace.trace_id}: computed 3 metrics" in caplog.text


@pytest.mark.asyncio
async def test_rag_triad_partial_missing_fields(caplog: pytest.LogCaptureFixture) -> None:
    # Omit context span
    trace = build_test_trace(context=None)
    metric = RAGTriadMetric(scorer=dummy_scorer)

    with caplog.at_level(logging.WARNING):
        results = await metric.evaluate(trace)

    assert len(results) == 1
    assert results[0].metric_name == "answer_relevance"
    assert results[0].details == {"missing_fields": "context"}
    assert f"Missing RAG triad fields for trace_id={trace.trace_id}: context" in caplog.text


@pytest.mark.asyncio
async def test_rag_triad_empty_trace(caplog: pytest.LogCaptureFixture) -> None:
    trace = build_test_trace(query=None, context=None, answer=None)
    metric = RAGTriadMetric(scorer=dummy_scorer)

    with caplog.at_level(logging.INFO):
        results = await metric.evaluate(trace)

    assert len(results) == 0
    assert "Missing RAG triad fields" in caplog.text
    assert f"completed for trace_id={trace.trace_id}: computed 0 metrics" in caplog.text
