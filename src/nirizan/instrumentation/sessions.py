from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Session(BaseModel):
    """Groups multiple Trace ids belonging to one multi-turn conversation; not frozen, open until ended."""

    model_config = ConfigDict(strict=True)

    session_id: UUID
    application_name: str = Field(min_length=1)
    trace_ids: list[UUID] = Field(default_factory=list)
    started_at: datetime
    ended_at: datetime | None = None
