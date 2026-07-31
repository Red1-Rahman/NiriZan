from __future__ import annotations

from nirizan.instrumentation.spans import Trace
from nirizan.metrics.base import Metric, MetricResult


class MetricDispatcher:
    """Routes traces to registered metrics by system type; registration is explicit, never import-time."""

    def __init__(self) -> None:
        self._registry: dict[str, list[Metric]] = {}

    def register(self, metric: Metric, applies_to: set[str]) -> None:
        for system_type in applies_to:
            self._registry.setdefault(system_type, []).append(metric)

    async def dispatch(self, trace: Trace, system_type: str) -> list[MetricResult]:
        metrics = self._registry.get(system_type, [])
        all_results: list[MetricResult] = []
        for metric in metrics:
            results = await metric.evaluate(trace)
            all_results.extend(results)
        return all_results
