from datetime import UTC, datetime
from uuid import uuid4

import pytest

from nirizan.storage.models import Run
from nirizan.storage.run_repository import InMemoryRunRepository


@pytest.mark.asyncio
async def test_get_run_returns_none_without_affecting_saved_runs() -> None:
    repo = InMemoryRunRepository()
    missing_id = uuid4()
    assert await repo.get_run(missing_id) is None

    run = Run(
        run_id=uuid4(),
        trace_id=uuid4(),
        code_commit="test-commit",
        data_snapshot_id="snapshot-v1",
        metric_results=[],
        created_at=datetime.now(UTC),
    )
    await repo.save_run(run)

    assert await repo.get_run(missing_id) is None
    assert await repo.get_run(run.run_id) == run
    assert await InMemoryRunRepository().get_run(run.run_id) is None


@pytest.mark.asyncio
async def test_get_run_returns_replacement_for_existing_id() -> None:
    repo = InMemoryRunRepository()
    run = Run(
        run_id=uuid4(),
        trace_id=uuid4(),
        code_commit="old-commit",
        data_snapshot_id="snapshot-v1",
        metric_results=[],
        created_at=datetime.now(UTC),
    )
    await repo.save_run(run)
    replacement = run.model_copy(update={"code_commit": "new-commit"})
    await repo.save_run(replacement)

    assert await repo.get_run(run.run_id) == replacement
