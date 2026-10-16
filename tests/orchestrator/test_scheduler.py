from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, call
from uuid import uuid4

import pytest

from nirizan.instrumentation.spans import Trace
from nirizan.metrics.base import MetricResult
from nirizan.orchestrator.scheduler import RunScheduler


@pytest.mark.parametrize("with_metrics", [False, True])
@pytest.mark.asyncio
async def test_scheduled_runs_have_current_utc_timestamps(with_metrics: bool) -> None:
    traces = [
        Trace(trace_id=uuid4(), application_name="test-app", created_at=datetime.now(UTC))
        for _ in range(2)
    ]
    results = [
        [
            MetricResult(
                metric_name="quality",
                trace_id=trace.trace_id,
                score=0.8,
                computed_at=trace.created_at,
            )
        ]
        if with_metrics
        else []
        for trace in traces
    ]
    source = SimpleNamespace(list_by_application=AsyncMock(return_value=traces))
    dispatcher = SimpleNamespace(dispatch=AsyncMock(side_effect=results))
    sink = SimpleNamespace(save_run=AsyncMock())
    scheduler = RunScheduler(source, dispatcher, sink)

    before = datetime.now(UTC)
    runs = await scheduler.run_on_demand("test-app", "rag")
    after = datetime.now(UTC)

    assert len(runs) == 2
    assert runs[0].run_id != runs[1].run_id
    assert [run.trace_id for run in runs] == [trace.trace_id for trace in traces]
    assert [run.metric_results for run in runs] == results
    for run in runs:
        assert run.created_at.utcoffset() == timedelta(0)
        assert before <= run.created_at <= after
    source.list_by_application.assert_awaited_once_with("test-app")
    assert dispatcher.dispatch.await_args_list == [call(trace, "rag") for trace in traces]
    assert sink.save_run.await_args_list == [call(run) for run in runs]
