# src/nirizan/trust/anchor_set.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class AnchorItem(BaseModel):
    model_config = ConfigDict(strict=True)

    anchor_id: str
    input_payload: str
    expected_output: str
    human_label: float = Field(ge=0.0, le=1.0)


class AnchorSet(BaseModel):
    model_config = ConfigDict(strict=True)

    anchor_set_id: str
    items: list[AnchorItem] = Field(min_length=1)
    created_at: datetime
