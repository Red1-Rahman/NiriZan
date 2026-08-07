# tests/storage/test_experiment_store.py
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from nirizan.metrics.base import MetricResult
from nirizan.storage.experiment_store import SQLiteExperimentStore
from nirizan.storage.models import Run


@pytest.fixture
def experiment_store(tmp_path: Path) -> SQLiteExperimentStore:
    db_file = tmp_path / "test_experiments.db"
    store = SQLiteExperimentStore(db_path=str(db_file))
    yield store
    store.close()


@pytest.mark.asyncio
async def test_record_and_get_run(experiment_store: SQLiteExperimentStore) -> None:
    run_id = uuid4()
    trace_id = uuid4()
    now = datetime.now(timezone.utc)

    run = Run(
        run_id=run_id,
        trace_id=trace_id,
        code_commit="abcdef1234567890",
        data_snapshot_id="snapshot_v1",
        metric_results=[
            MetricResult(metric_name="latency", score=120.5),
            MetricResult(metric_name="accuracy", score=0.92),
        ],
        created_at=now,
    )

    await experiment_store.record_run(run)
    retrieved = await experiment_store.get_run(run_id)

    assert retrieved is not None
    assert retrieved.run_id == run_id
    assert retrieved.trace_id == trace_id
    assert retrieved.code_commit == "abcdef1234567890"
    assert retrieved.data_snapshot_id == "snapshot_v1"
    assert retrieved.created_at == now
    assert len(retrieved.metric_results) == 2
    assert retrieved.metric_results[0].metric_name == "latency"
    assert retrieved.metric_results[0].score == 120.5


@pytest.mark.asyncio
async def test_get_nonexistent_run_returns_none(experiment_store: SQLiteExperimentStore) -> None:
    result = await experiment_store.get_run(uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_diff_runs(experiment_store: SQLiteExperimentStore) -> None:
    run_a_id = uuid4()
    run_b_id = uuid4()
    now = datetime.now(timezone.utc)

    run_a = Run(
        run_id=run_a_id,
        trace_id=uuid4(),
        code_commit="commit_a_12345",
        data_snapshot_id="snap_1",
        metric_results=[
            MetricResult(metric_name="accuracy", score=0.80),
            MetricResult(metric_name="latency", score=200.0),
            MetricResult(metric_name="only_in_a", score=1.0),
        ],
        created_at=now,
    )

    run_b = Run(
        run_id=run_b_id,
        trace_id=uuid4(),
        code_commit="commit_b_67890",
        data_snapshot_id="snap_1",
        metric_results=[
            MetricResult(metric_name="accuracy", score=0.88),  # delta = +0.08
            MetricResult(metric_name="latency", score=150.0),   # delta = -50.0
            MetricResult(metric_name="only_in_b", score=5.0),
        ],
        created_at=now,
    )

    await experiment_store.record_run(run_a)
    await experiment_store.record_run(run_b)

    diff_result = await experiment_store.diff(run_a_id, run_b_id)

    assert diff_result.run_a == run_a_id
    assert diff_result.run_b == run_b_id
    assert pytest.approx(diff_result.metric_deltas["accuracy"], abs=1e-5) == 0.08
    assert pytest.approx(diff_result.metric_deltas["latency"], abs=1e-5) == -50.0
    assert "only_in_a" not in diff_result.metric_deltas
    assert "only_in_b" not in diff_result.metric_deltas


@pytest.mark.asyncio
async def test_diff_missing_run_raises_value_error(experiment_store: SQLiteExperimentStore) -> None:
    existing_id = uuid4()
    missing_id = uuid4()

    run = Run(
        run_id=existing_id,
        trace_id=uuid4(),
        code_commit="commit_1234567",
        data_snapshot_id="snap_1",
        metric_results=[],
        created_at=datetime.now(timezone.utc),
    )
    await experiment_store.record_run(run)

    with pytest.raises(ValueError, match="diff requires both runs to exist"):
        await experiment_store.diff(existing_id, missing_id)
