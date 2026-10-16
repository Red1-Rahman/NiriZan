import asyncio
import subprocess
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from nirizan.instrumentation.spans import Trace
from nirizan.orchestrator import collector as collector_module
from nirizan.orchestrator.collector import TraceCollector


@pytest.mark.parametrize("timeout_count", [1, 3])
@pytest.mark.asyncio
async def test_worker_recovers_from_receive_timeouts(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    timeout_count: int,
) -> None:
    monkeypatch.setenv("GIT_COMMIT_SHA", "test-commit")
    monkeypatch.setenv("NIRIZAN_DATA_SNAPSHOT_ID", "test-snapshot")
    sink = SimpleNamespace(save=AsyncMock())
    collector = TraceCollector(sink)
    trace = Trace(trace_id=uuid4(), application_name="test-app", created_at=datetime.now(UTC))
    await collector.enqueue_trace(trace)
    original_get = collector.queue.get
    attempts = 0

    async def receive() -> Trace:
        nonlocal attempts
        attempts += 1
        if attempts <= timeout_count:
            raise TimeoutError
        return await original_get()

    monkeypatch.setattr(collector.queue, "get", receive)
    async with asyncio.timeout(1):
        await collector.start()
        try:
            await collector.queue.join()
        finally:
            await collector.stop()

    sink.save.assert_awaited_once()
    saved_trace = sink.save.await_args.args[0]
    assert saved_trace.trace_id == trace.trace_id
    assert saved_trace.code_commit == "test-commit"
    assert saved_trace.data_snapshot_id == "test-snapshot"
    assert trace.code_commit is None
    assert trace.data_snapshot_id is None
    assert attempts >= timeout_count + 1
    assert not [record for record in caplog.records if record.levelname == "ERROR"]


def test_code_commit_environment_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_COMMIT_SHA", "environment-commit")
    run = Mock(side_effect=AssertionError("git must not run when a commit is provided"))
    monkeypatch.setattr(collector_module.subprocess, "run", run)

    assert collector_module._resolve_code_commit() == "environment-commit"
    run.assert_not_called()


@pytest.mark.parametrize("environment_value", [None, ""])
def test_code_commit_falls_back_to_git(
    monkeypatch: pytest.MonkeyPatch, environment_value: str | None
) -> None:
    monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)
    if environment_value is not None:
        monkeypatch.setenv("GIT_COMMIT_SHA", environment_value)
    run = Mock(return_value=subprocess.CompletedProcess([], 0, stdout="git-commit\n"))
    monkeypatch.setattr(collector_module.subprocess, "run", run)

    assert collector_module._resolve_code_commit() == "git-commit"
    run.assert_called_once_with(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )


@pytest.mark.parametrize(
    "error", [FileNotFoundError(), subprocess.CalledProcessError(128, ["git", "rev-parse", "HEAD"])]
)
def test_unavailable_git_returns_none(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)
    monkeypatch.setattr(collector_module.subprocess, "run", Mock(side_effect=error))

    assert collector_module._resolve_code_commit() is None


@pytest.mark.parametrize("snapshot", [None, "", "snapshot-v2"])
def test_data_snapshot_preserves_optional_environment_value(
    monkeypatch: pytest.MonkeyPatch, snapshot: str | None
) -> None:
    monkeypatch.delenv("NIRIZAN_DATA_SNAPSHOT_ID", raising=False)
    if snapshot is not None:
        monkeypatch.setenv("NIRIZAN_DATA_SNAPSHOT_ID", snapshot)

    assert collector_module._resolve_data_snapshot_id() == snapshot
