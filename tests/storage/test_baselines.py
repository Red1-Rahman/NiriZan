# tests/storage/test_baselines.py
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from nirizan.storage.baselines import SQLiteBaselineRepository
from nirizan.storage.models import Baseline


@pytest.fixture
def baseline_repo(tmp_path: Path) -> SQLiteBaselineRepository:
    db_file = tmp_path / "test_baselines.db"
    repo = SQLiteBaselineRepository(db_path=str(db_file))
    yield repo
    repo.close()


@pytest.mark.asyncio
async def test_save_and_get_baseline(baseline_repo: SQLiteBaselineRepository) -> None:
    baseline_id = uuid4()
    run_1_id = uuid4()
    run_2_id = uuid4()
    now = datetime.now(timezone.utc)

    baseline = Baseline(
        baseline_id=baseline_id,
        system_type="rag_eval",
        run_ids=[run_1_id, run_2_id],
        established_at=now,
        label="prod-v1.2",
    )

    await baseline_repo.save_baseline(baseline)
    retrieved = await baseline_repo.get_baseline(baseline_id)

    assert retrieved is not None
    assert retrieved.baseline_id == baseline_id
    assert retrieved.system_type == "rag_eval"
    assert retrieved.run_ids == [run_1_id, run_2_id]
    assert retrieved.established_at == now
    assert retrieved.label == "prod-v1.2"


@pytest.mark.asyncio
async def test_get_nonexistent_baseline_returns_none(baseline_repo: SQLiteBaselineRepository) -> None:
    result = await baseline_repo.get_baseline(uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_list_baselines_filtering_and_ordering(baseline_repo: SQLiteBaselineRepository) -> None:
    now = datetime.now(timezone.utc)

    b1 = Baseline(
        baseline_id=uuid4(),
        system_type="agent_a",
        run_ids=[uuid4()],
        established_at=now - timedelta(days=2),
        label="agent_a_older",
    )
    b2 = Baseline(
        baseline_id=uuid4(),
        system_type="agent_a",
        run_ids=[uuid4()],
        established_at=now,
        label="agent_a_newer",
    )
    b3 = Baseline(
        baseline_id=uuid4(),
        system_type="agent_b",
        run_ids=[uuid4()],
        established_at=now,
        label="agent_b_baseline",
    )

    await baseline_repo.save_baseline(b1)
    await baseline_repo.save_baseline(b2)
    await baseline_repo.save_baseline(b3)

    agent_a_baselines = await baseline_repo.list_baselines("agent_a")
    assert len(agent_a_baselines) == 2
    # Ordered DESC by established_at
    assert agent_a_baselines[0].label == "agent_a_newer"
    assert agent_a_baselines[1].label == "agent_a_older"

    agent_b_baselines = await baseline_repo.list_baselines("agent_b")
    assert len(agent_b_baselines) == 1
    assert agent_b_baselines[0].label == "agent_b_baseline"

    empty_baselines = await baseline_repo.list_baselines("nonexistent")
    assert empty_baselines == []
