from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from nirizan.instrumentation.sessions import Session


class SessionRepository(Protocol):
    """Minimal Session persistence; get_session returns None for missing, never raises."""

    async def save_session(self, session: Session) -> None: ...
    async def get_session(self, session_id: UUID) -> Optional[Session]: ...


class InMemorySessionRepository:
    """Dict-backed SessionRepository."""

    def __init__(self) -> None:
        self._sessions: dict[UUID, Session] = {}

    async def save_session(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    async def get_session(self, session_id: UUID) -> Optional[Session]:
        return self._sessions.get(session_id)
