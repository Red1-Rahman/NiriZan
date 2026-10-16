from datetime import UTC, datetime
from uuid import uuid4

import pytest

from nirizan.instrumentation.sessions import Session
from nirizan.storage.session_repository import InMemorySessionRepository


@pytest.mark.asyncio
async def test_get_session_returns_none_without_affecting_saved_sessions() -> None:
    repo = InMemorySessionRepository()
    missing_id = uuid4()
    assert await repo.get_session(missing_id) is None

    session = Session(session_id=uuid4(), application_name="test-app", started_at=datetime.now(UTC))
    await repo.save_session(session)

    assert await repo.get_session(missing_id) is None
    assert await repo.get_session(session.session_id) == session
    assert await InMemorySessionRepository().get_session(session.session_id) is None


@pytest.mark.asyncio
async def test_get_session_returns_replacement_for_existing_id() -> None:
    repo = InMemorySessionRepository()
    session = Session(session_id=uuid4(), application_name="test-app", started_at=datetime.now(UTC))
    await repo.save_session(session)
    replacement = session.model_copy(update={"trace_ids": [uuid4()], "ended_at": datetime.now(UTC)})
    await repo.save_session(replacement)

    assert await repo.get_session(session.session_id) == replacement
