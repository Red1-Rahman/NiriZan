# src/nirizan/regression/thresholds.py
from __future__ import annotations

from typing import Mapping

import numpy as np
from scipy.stats import mannwhitneyu

from nirizan._logging import get_logger

logger = get_logger(__name__)

DEFAULT_ALPHA = 0.05
DEFAULT_WARNING_EFFECT = -0.20
DEFAULT_BLOCKING_EFFECT = -0.50


def mann_whitney_regression(
    candidate: np.ndarray,
    baseline: np.ndarray,
) -> tuple[float, float]:
    """Test whether candidate scores are stochastically lower than baseline."""
    if candidate.size == 0 or baseline.size == 0:
        logger.error(
            "Mann-Whitney regression failed: both distributions must contain observations (candidate size=%d, baseline size=%d).",
            candidate.size,
            baseline.size,
        )
        raise ValueError("Both distributions must contain observations.")

    statistic, p_value = mannwhitneyu(
        candidate,
        baseline,
        alternative="less",
    )

    logger.info(
        "Mann-Whitney U test computed: statistic=%.4f, p_value=%.6e (candidate_n=%d, baseline_n=%d)",
        float(statistic),
        float(p_value),
        candidate.size,
        baseline.size,
    )

    return float(statistic), float(p_value)


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

    ordered = sorted(p_values.items(), key=lambda item: item[1])
    rejected = {metric_name: False for metric_name in p_values}

    total = len(ordered)
    logger.info(
        "Applying Holm-Bonferroni correction for %d hypotheses at alpha=%.4f",
        total,
        alpha,
    )

    for index, (metric_name, p_value) in enumerate(ordered):
        threshold = alpha / (total - index)

        if p_value <= threshold:
            rejected[metric_name] = True
            logger.debug(
                "Hypothesis '%s' rejected (p_value=%.6e <= threshold=%.6e)",
                metric_name,
                p_value,
                threshold,
            )
        else:
            logger.debug(
                "Hypothesis '%s' retained (p_value=%.6e > threshold=%.6e). Stopping correction.",
                metric_name,
                p_value,
                threshold,
            )
            break

    return rejected


def validate_scores(scores: np.ndarray) -> None:
    """Validate a metric-score distribution before statistical analysis."""
    if scores.ndim != 1:
        logger.error("Score validation failed: scores must be 1D, got ndim=%d.", scores.ndim)
        raise ValueError("Scores must be one-dimensional.")

    if scores.size == 0:
        logger.error("Score validation failed: scores array is empty.")
        raise ValueError("Scores must contain at least one observation.")

    if not np.all(np.isfinite(scores)):
        logger.error("Score validation failed: scores contains non-finite values (NaN or Inf).")
        raise ValueError("Scores must contain only finite values.")

    if np.any(scores < 0.0) or np.any(scores > 1.0):
        logger.error("Score validation failed: scores out of bounds [0, 1].")
        raise ValueError("NiriZan metric scores must be in [0, 1].")

    logger.debug("Successfully validated %d score observations.", scores.size)
