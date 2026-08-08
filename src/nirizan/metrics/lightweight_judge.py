# src/nirizan/metrics/lightweight_judge.py
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from nirizan.metrics.base import MetricResult


class ClassificationModel(Protocol):
    """Protocol for fine-tuned or local classifier model interfaces."""

    def predict_proba(self, text: str) -> dict[str, float]: ...


class RegexClassifier:
    """Fallback rule-based lightweight classifier for testing/offline scenarios."""

    def predict_proba(self, text: str) -> dict[str, float]:
        text_lower = text.lower()
        toxic_patterns = [r"\bhate\b", r"\bkill\b", r"\btoxic\b", r"\bbad\b"]
        matches = sum(1 for p in toxic_patterns if re.search(p, text_lower))
        score = min(1.0, matches * 0.33)
        return {"toxic": score, "safe": 1.0 - score}


class LightweightJudge(BaseModel):
    """Fast, local classifier judge for automated high-throughput metric scoring."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    metric_name: str = "lightweight_quality_score"
    classifier: Any = Field(default_factory=RegexClassifier)
    target_class: str = "safe"

    def evaluate_text(
        self,
        text: str,
        *,
        trace_id: UUID | None = None,
    ) -> MetricResult:
        if not text or not text.strip():
            score = 0.0
        else:
            probas = self.classifier.predict_proba(text)
            score = float(probas.get(self.target_class, 0.0))

        score = max(0.0, min(1.0, score))
        return MetricResult(
            metric_name=self.metric_name,
            trace_id=trace_id or uuid4(),
            score=score,
            computed_at=datetime.now(timezone.utc),
        )
