# src/nirizan/gate/verdict.py
from __future__ import annotations

from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from nirizan._logging import get_logger
from nirizan.regression.comparator import (
    RegressionSeverity,
    RegressionVerdict,
)

logger = get_logger(__name__)


class GateVerdict(BaseModel):
    model_config = ConfigDict(strict=True)

    passed: bool
    confidence_interval: tuple[float, float]
    regression_verdicts: list[RegressionVerdict] = Field(
        default_factory=list
    )
    run_id: UUID


SEVERITY_WEIGHT = {
    RegressionSeverity.BLOCKING: 3,
    RegressionSeverity.WARNING: 2,
    RegressionSeverity.NONE: 1,
}


def bootstrap_delta_ci(
    candidate: np.ndarray,
    baseline: np.ndarray,
    *,
    n_bootstrap: int = 5000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    if candidate.size == 0 or baseline.size == 0:
        raise ValueError(
            "Both distributions must contain observations."
        )

    if n_bootstrap < 1:
        raise ValueError("n_bootstrap must be positive.")

    if not 0.0 < confidence < 1.0:
        raise ValueError(
            "confidence must be between 0 and 1."
        )

    logger.debug(
        "Computing bootstrap delta CI: n_bootstrap=%d, confidence=%.2f, candidate_n=%d, baseline_n=%d",
        n_bootstrap,
        confidence,
        candidate.size,
        baseline.size,
    )

    rng = np.random.default_rng(seed)

    candidate_samples = rng.choice(
        candidate,
        size=(n_bootstrap, candidate.size),
        replace=True,
    )

    baseline_samples = rng.choice(
        baseline,
        size=(n_bootstrap, baseline.size),
        replace=True,
    )

    deltas = (
        candidate_samples.mean(axis=1)
        - baseline_samples.mean(axis=1)
    )

    alpha = 1.0 - confidence

    ci = (
        float(np.quantile(deltas, alpha / 2.0)),
        float(np.quantile(deltas, 1.0 - alpha / 2.0)),
    )
    logger.debug("Bootstrap CI computed: [%.6f, %.6f]", ci[0], ci[1])
    return ci


def select_decision_metric(
    verdicts: list[RegressionVerdict],
) -> RegressionVerdict:
    if not verdicts:
        raise ValueError("At least one verdict is required.")

    selected = min(
        verdicts,
        key=lambda verdict: (
            -SEVERITY_WEIGHT[verdict.severity],
            (
                verdict.effect_size
                if verdict.effect_size is not None
                else 0.0
            ),
        ),
    )
    logger.debug(
        "Selected decision metric '%s' (severity=%s, effect_size=%s)",
        selected.metric_name,
        selected.severity.value,
        selected.effect_size,
    )
    return selected


def evaluate_gate(
    *,
    verdicts: list[RegressionVerdict],
    scores_by_metric: dict[
        str,
        tuple[np.ndarray, np.ndarray],
    ],
) -> GateVerdict:
    if not verdicts:
        raise ValueError(
            "Gate requires at least one regression verdict."
        )

    logger.info("Evaluating gate across %d regression verdict(s)", len(verdicts))

    decision_metric = select_decision_metric(verdicts)

    candidate_scores, baseline_scores = scores_by_metric[
        decision_metric.metric_name
    ]

    confidence_interval = bootstrap_delta_ci(
        candidate_scores,
        baseline_scores,
    )

    blocking_verdicts = [
        verdict
        for verdict in verdicts
        if verdict.severity == RegressionSeverity.BLOCKING
    ]
    passed = len(blocking_verdicts) == 0

    if passed:
        logger.info(
            "Gate evaluation result: PASSED for run_id=%s",
            decision_metric.run_id,
        )
    else:
        logger.warning(
            "Gate evaluation result: BLOCKED for run_id=%s (%d blocking regression(s))",
            decision_metric.run_id,
            len(blocking_verdicts),
        )

    return GateVerdict(
        passed=passed,
        confidence_interval=confidence_interval,
        regression_verdicts=verdicts,
        run_id=decision_metric.run_id,
    )
