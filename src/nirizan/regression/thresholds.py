# src/nirizan/regression/thresholds.py
from __future__ import annotations

from typing import Mapping

import numpy as np
from scipy.stats import mannwhitneyu


DEFAULT_ALPHA = 0.05
DEFAULT_WARNING_EFFECT = -0.20
DEFAULT_BLOCKING_EFFECT = -0.50


def mann_whitney_regression(
    candidate: np.ndarray,
    baseline: np.ndarray,
) -> tuple[float, float]:
    """Test whether candidate scores are stochastically lower than baseline."""
    if candidate.size == 0 or baseline.size == 0:
        raise ValueError("Both distributions must contain observations.")

    statistic, p_value = mannwhitneyu(
        candidate,
        baseline,
        alternative="less",
    )

    return float(statistic), float(p_value)


def holm_bonferroni(
    p_values: Mapping[str, float],
    *,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, bool]:
    """Apply Holm-Bonferroni correction across one decision family."""
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1.")

    if not p_values:
        return {}

    ordered = sorted(p_values.items(), key=lambda item: item[1])
    rejected = {metric_name: False for metric_name in p_values}

    total = len(ordered)

    for index, (metric_name, p_value) in enumerate(ordered):
        threshold = alpha / (total - index)

        if p_value <= threshold:
            rejected[metric_name] = True
        else:
            break

    return rejected


def validate_scores(scores: np.ndarray) -> None:
    """Validate a metric-score distribution before statistical analysis."""
    if scores.ndim != 1:
        raise ValueError("Scores must be one-dimensional.")

    if scores.size == 0:
        raise ValueError("Scores must contain at least one observation.")

    if not np.all(np.isfinite(scores)):
        raise ValueError("Scores must contain only finite values.")

    if np.any(scores < 0.0) or np.any(scores > 1.0):
        raise ValueError("NiriZan metric scores must be in [0, 1].")
