# tests/metrics/test_behavioral_anchor.py
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import numpy as np
import pytest

from nirizan.instrumentation.spans import Span, SpanKind, Trace
from nirizan.metrics.behavioral_anchor import BehavioralAnchorMetric


@pytest.fixture
def sample_trace():
    trace_id = uuid.uuid4()
    now = datetime.now(UTC)
    gen_span = Span(
        span_id=uuid.uuid4(),
        trace_id=trace_id,
        kind=SpanKind.GENERATION,
        name="llm_generation",
        started_at=now,
        ended_at=now,
        output_payload="I am a professional and helpful customer support assistant.",
    )
    return Trace(
        trace_id=trace_id,
        application_name="support_agent",
        spans=[gen_span],
        created_at=now,
    )


@pytest.mark.asyncio
async def test_behavioral_anchor_metric_aligned(sample_trace):
    target_vector = np.array([1.0, 0.0, 0.0])

    def mock_embedding_fn(text: str) -> np.ndarray:
        return np.array([0.99, 0.01, 0.0])  # Highly aligned

    metric = BehavioralAnchorMetric(
        target_embedding=target_vector,
        embedding_fn=mock_embedding_fn,
        threshold=0.85,
    )

    results = await metric.evaluate(sample_trace)

    assert len(results) == 1
    res = results[0]
    assert res.metric_name == "behavioral_anchor"
    assert res.trace_id == sample_trace.trace_id
    assert res.score >= 0.85
    assert res.details["band"] == "aligned"


@pytest.mark.asyncio
async def test_behavioral_anchor_metric_drifted(sample_trace):
    target_vector = np.array([1.0, 0.0, 0.0])

    def mock_embedding_fn(text: str) -> np.ndarray:
        return np.array([0.0, 1.0, 0.0])  # Orthogonal / drifted vector

    metric = BehavioralAnchorMetric(
        target_embedding=target_vector,
        embedding_fn=mock_embedding_fn,
        threshold=0.85,
    )

    results = await metric.evaluate(sample_trace)

    assert len(results) == 1
    res = results[0]
    assert res.score < 0.85
    assert res.details["band"] == "deviation"


@pytest.mark.parametrize(
    ("target", "embedding", "threshold", "score", "band"),
    [
        ([1.0, 0.0], [1.0, 0.0], 1.0, 1.0, "aligned"),
        ([1.0, 0.0], [0.6, 0.8], 0.85, 0.6, "neutral"),
        ([1.0, 0.0], [-1.0, 0.0], 0.85, 0.0, "deviation"),
        ([1.0, 0.0], [0.0, 0.0], 0.85, 0.0, "deviation"),
        ([0.0, 0.0], [1.0, 0.0], 0.85, 0.0, "deviation"),
    ],
    ids=["threshold-boundary", "neutral", "negative-similarity", "zero-output", "zero-target"],
)
@pytest.mark.asyncio
async def test_anchor_results_have_current_utc_timestamps(
    sample_trace: Trace,
    target: list[float],
    embedding: list[float],
    threshold: float,
    score: float,
    band: str,
) -> None:
    embedding_fn = Mock(return_value=np.array(embedding))
    metric = BehavioralAnchorMetric(
        np.array(target), threshold=threshold, embedding_fn=embedding_fn
    )

    before = datetime.now(UTC)
    results = await metric.evaluate(sample_trace)
    after = datetime.now(UTC)

    assert len(results) == 1
    result = results[0]
    assert result.score == pytest.approx(score)
    assert result.details["band"] == band
    assert result.details["span_id"] == str(sample_trace.spans[0].span_id)
    assert result.trace_id == sample_trace.trace_id
    assert result.computed_at.utcoffset() == timedelta(0)
    assert before <= result.computed_at <= after
    embedding_fn.assert_called_once_with(sample_trace.spans[0].output_payload)
