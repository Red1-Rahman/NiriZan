# tests/metrics/test_behavioral_anchor.py
from datetime import datetime, timezone
import uuid
import numpy as np
import pytest

from nirizan.instrumentation.spans import Span, SpanKind, Trace
from nirizan.metrics.behavioral_anchor import BehavioralAnchorMetric


@pytest.fixture
def sample_trace():
    trace_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
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
