# tests/security/test_resource_bounds.py
"""Resource exhaustion regression tests."""

import numpy as np
import pytest

from nirizan.instrumentation.spans import SpanKind
from nirizan.instrumentation.tracer import Tracer
from nirizan.metrics.stats import cohens_d
from nirizan.orchestrator.collector import TraceCollector


@pytest.mark.xfail(strict=True, reason="tracked: NZ-SEC-004")
@pytest.mark.asyncio
async def test_native_tracer_retains_only_bounded_span_history():
    # Finding NZ-SEC-004: native tracer appends spans indefinitely unless clear() is called.
    tracer = Tracer("resource-test")
    for _ in range(100):
        async with tracer.start_span("root", SpanKind.PLANNING):
            pass
    assert len(tracer._spans) <= 10


@pytest.mark.xfail(strict=True, reason="tracked: NZ-SEC-007")
def test_trace_collector_queue_has_a_finite_capacity():
    # Finding NZ-SEC-007: asyncio.Queue defaults to maxsize=0 (unbounded).
    class Repository:
        async def save(self, trace):
            pass

    assert TraceCollector(Repository()).queue.maxsize > 0


@pytest.mark.xfail(strict=True, reason="tracked: NZ-SEC-005")
def test_cohens_d_rejects_single_observation_samples():
    # Finding NZ-SEC-005: ddof=1 yields NaN for singleton arrays.
    result = cohens_d(np.array([0.5]), np.array([0.4]))
    assert np.isfinite(result)
