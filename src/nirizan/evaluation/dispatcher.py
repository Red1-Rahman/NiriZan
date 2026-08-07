# src/nirizan/evaluation/dispatcher.py
from __future__ import annotations

from nirizan.instrumentation.spans import Trace
from nirizan.metrics.base import Metric, MetricResult


class MetricDispatcher:
    """Routes traces to registered metrics by system type.

    Registration is explicit and performed at application startup.
    Metrics are never discovered through import-time side effects,
    preserving a deterministic dependency graph.
    """

    def __init__(self) -> None:
        self._registry: dict[str, list[Metric]] = {}

    def register(self, metric: Metric, applies_to: set[str]) -> None:
        """Register a metric for one or more system types."""
        for system_type in applies_to:
            self._registry.setdefault(system_type, []).append(metric)

    async def dispatch(
        self,
        trace: Trace,
        system_type: str,
    ) -> list[MetricResult]:
        """Evaluate all metrics registered for the given system type."""

        metrics = self._registry.get(system_type, [])

        results: list[MetricResult] = []

        for metric in metrics:
            results.extend(await metric.evaluate(trace))

        return results
