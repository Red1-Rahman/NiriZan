from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from nirizan.instrumentation.spans import Trace


class MetricResult(BaseModel):
    """One score produced by a Metric for a trace; score is always normalized to [0.0, 1.0]."""

    model_config = ConfigDict(strict=True)

    metric_name: str
    trace_id: UUID
    score: float = Field(ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    details: dict[str, str | int | float | bool] = Field(default_factory=dict)
    computed_at: datetime


class Metric(Protocol):
    """The interface every metric module implements, unchanged from Phase 2 onward."""

    name: str

    async def evaluate(self, trace: Trace) -> list[MetricResult]:
        """Compute one or more scores for a trace; must not mutate the trace or persist results itself."""
        ...


class Scorer(Protocol):
    """Pairwise text scoring backend: two strings in, one float in [0.0, 1.0] out, swappable at the call site."""

    def __call__(self, text_a: str, text_b: str) -> float: ...
