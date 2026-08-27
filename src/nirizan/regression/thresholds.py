# src/nirizan/regression/thresholds.py
from __future__ import annotations

from typing import Mapping

import numpy as np

from nirizan._logging import get_logger
from nirizan.metrics.stats import (
    compute_holm_bonferroni,
    compute_mann_whitney_u,
    validate_scores as stats_validate_scores,
)

logger = get_logger(__name__)

DEFAULT_ALPHA = 0.05
DEFAULT_WARNING_EFFECT = -0.20
DEFAULT_BLOCKING_EFFECT = -0.50


def validate_scores(scores: np.ndarray) -> np.ndarray:
    """Validate a metric-score distribution before statistical analysis."""
    if scores.ndim != 1:
        logger.error("Score validation failed: scores must be 1D, got ndim=%d.", scores.ndim)
        raise ValueError("Scores must be one-dimensional.")

    return stats_validate_scores(scores)


def mann_whitney_regression(
    candidate: np.ndarray,
    baseline: np.ndarray,
) -> tuple[float, float]:
    """Test whether candidate scores are stochastically lower than baseline."""
    candidate_arr = np.asarray(candidate, dtype=float)
    baseline_arr = np.asarray(baseline, dtype=float)

    if candidate_arr.size == 0 or baseline_arr.size == 0:
        logger.error(
            "Mann-Whitney regression failed: both distributions must contain observations (candidate size=%d, baseline size=%d).",
            candidate_arr.size,
            baseline_arr.size,
        )
        raise ValueError("Both distributions must contain observations.")

    statistic, p_value = compute_mann_whitney_u(
        candidate_arr,
        baseline_arr,
        alternative="less",
    )

    logger.info(
        "Mann-Whitney U test computed: statistic=%.4f, p_value=%.6e (candidate_n=%d, baseline_n=%d)",
        statistic,
        p_value,
        candidate_arr.size,
        baseline_arr.size,
    )

    return statistic, p_value


def holm_bonferroni(
    p_values: Mapping[str, float],
    *,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, bool]:
    """Apply Holm-Bonferroni correction across one decision family."""
    if not 0.0 < alpha < 1.0:
        logger.error("Invalid alpha for Holm-Bonferroni: alpha=%.4f (must be in (0, 1)).", alpha)
        raise ValueError("alpha must be between 0 and 1.")

    if not p_values:
        logger.debug("Holm-Bonferroni invoked with empty p_values mapping.")
        return {}

    logger.info(
        "Applying Holm-Bonferroni correction for %d hypotheses at alpha=%.4f",
        len(p_values),
        alpha,
    )

    return compute_holm_bonferroni(p_values, alpha=alpha)
