# src/nirizan/metrics/behavioral_anchor.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
import numpy as np

from nirizan.instrumentation.spans import SpanKind, Trace
from nirizan.metrics.base import MetricResult


class BehavioralAnchorMetric:
    name: str = "behavioral_anchor"

    def __init__(
        self,
        target_embedding: np.ndarray,
        threshold: float = 0.85,
        embedding_fn: Callable[[str], np.ndarray] | None = None,
    ) -> None:
        self.target_embedding = np.asarray(target_embedding, dtype=np.float64)
        self.threshold = threshold
        self.embedding_fn = embedding_fn or self._default_embedding_fn

    def _default_embedding_fn(self, text: str) -> np.ndarray:
        return np.ones_like(self.target_embedding, dtype=np.float64)

    async def evaluate(self, trace: Trace) -> list[MetricResult]:
        gen_spans = trace.spans_of_kind(SpanKind.GENERATION)
        if not gen_spans:
            return []

        results: list[MetricResult] = []
        for span in gen_spans:
            output_text = span.output_payload or ""
            emb = self.embedding_fn(output_text)

            dot_product = np.dot(emb, self.target_embedding)
            norm_emb = np.linalg.norm(emb)
            norm_target = np.linalg.norm(self.target_embedding)

            if norm_emb == 0 or norm_target == 0:
                similarity = 0.0
            else:
                similarity = float(dot_product / (norm_emb * norm_target))

            score = max(0.0, min(1.0, similarity))

            if score >= self.threshold:
                band = "aligned"
            elif score >= 0.50:
                band = "neutral"
            else:
                band = "deviation"

            results.append(
                MetricResult(
                    metric_name=self.name,
                    trace_id=trace.trace_id,
                    score=score,
                    confidence=1.0,
                    details={
                        "band": band,
                        "threshold": self.threshold,
                        "span_id": str(span.span_id),
                    },
                    computed_at=datetime.now(timezone.utc),
                )
            )

        return results
