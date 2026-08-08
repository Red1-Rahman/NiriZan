# src/nirizan/metrics/rag_triad.py
from __future__ import annotations

from datetime import datetime, timezone

from nirizan._logging import get_logger
from nirizan.instrumentation.spans import SpanKind, Trace
from nirizan.metrics.base import MetricResult, Scorer

logger = get_logger(__name__)


class RAGTriadMetric:
    """Reference-free RAG Triad (context relevance, groundedness, answer relevance), scorer-agnostic via injection."""

    name = "rag_triad"

    def __init__(self, scorer: Scorer) -> None:
        self._scorer = scorer

    def _extract_rag_fields(self, trace: Trace) -> dict[str, str | None]:
        """Query from the root PLANNING span's input, context from RETRIEVAL's output, answer from GENERATION's output."""
        planning_spans = trace.spans_of_kind(SpanKind.PLANNING)
        retrieval_spans = trace.spans_of_kind(SpanKind.RETRIEVAL)
        generation_spans = trace.spans_of_kind(SpanKind.GENERATION)

        query = planning_spans[0].input_payload if planning_spans else None
        context = retrieval_spans[0].output_payload if retrieval_spans else None
        answer = generation_spans[0].output_payload if generation_spans else None

        return {"query": query, "context": context, "answer": answer}

    async def evaluate(self, trace: Trace) -> list[MetricResult]:
        logger.info("Evaluating RAGTriadMetric for trace_id=%s", trace.trace_id)
        fields = self._extract_rag_fields(trace)
        query, context, answer = fields["query"], fields["context"], fields["answer"]
        now = datetime.now(timezone.utc)
        results: list[MetricResult] = []

        missing = [k for k, v in fields.items() if v is None]
        if missing:
            logger.warning(
                "Missing RAG triad fields for trace_id=%s: %s",
                trace.trace_id,
                ", ".join(missing),
            )
        details: dict[str, str | int | float | bool] = (
            {"missing_fields": ",".join(missing)} if missing else {}
        )

        if query is not None and context is not None:
            score = self._scorer(query, context)
            logger.debug(
                "Computed context_relevance score=%.4f for trace_id=%s",
                score,
                trace.trace_id,
            )
            results.append(
                MetricResult(
                    metric_name="context_relevance",
                    trace_id=trace.trace_id,
                    score=score,
                    computed_at=now,
                    details=details,
                )
            )

        if context is not None and answer is not None:
            score = self._scorer(context, answer)
            logger.debug(
                "Computed groundedness score=%.4f for trace_id=%s",
                score,
                trace.trace_id,
            )
            results.append(
                MetricResult(
                    metric_name="groundedness",
                    trace_id=trace.trace_id,
                    score=score,
                    computed_at=now,
                    details=details,
                )
            )

        if query is not None and answer is not None:
            score = self._scorer(query, answer)
            logger.debug(
                "Computed answer_relevance score=%.4f for trace_id=%s",
                score,
                trace.trace_id,
            )
            results.append(
                MetricResult(
                    metric_name="answer_relevance",
                    trace_id=trace.trace_id,
                    score=score,
                    computed_at=now,
                    details=details,
                )
            )

        logger.info(
            "RAGTriadMetric evaluation completed for trace_id=%s: computed %d metrics",
            trace.trace_id,
            len(results),
        )
        return results
