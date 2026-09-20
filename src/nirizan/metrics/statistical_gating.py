# src/nirizan/metrics/statistical_gating.py
"""Logging-wrapped statistical helpers for the NiriZan metric engine.

This module predates the consolidation of `metrics/stats.py` as the single
source of truth for statistical primitives. It now provides two things:

1. Verbose, logging-wrapped entry points for callers that want INFO-level
   traces of every statistical decision (used by the Metric Engine's
   RuntimeGating step and the LLM-judge calibration path).
2. A backward-compatible `bootstrap_delta_ci` shim that returns the 2-tuple
   ``(ci_lower, ci_upper)``. The canonical implementation lives in
   ``nirizan.metrics.stats.bootstrap_delta_ci``, which returns the 3-tuple
   ``(delta_hat, ci_lower, ci_upper)``. New code should import from
   ``nirizan.metrics.stats`` (or ``nirizan.metrics``) directly.

Deprecation note for `bootstrap_delta_ci`: the 2-tuple shape is retained so
existing callers do not break, but it is considered deprecated. The 3-tuple
from `stats` is the canonical shape and is what `nirizan.metrics` re-exports
under the `bootstrap_delta_ci` name at package level.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from nirizan._logging import get_logger
from nirizan.metrics.stats import (
    bootstrap_delta_ci as stats_bootstrap_delta_ci,
    calculate_sample_size,
    compute_calibration_metrics,
    compute_holm_bonferroni,
    compute_mann_whitney_u,
    validate_scores as stats_validate_scores,
)

logger = get_logger(__name__)


def validate_scores(scores: np.ndarray) -> np.ndarray:
    """Validate score distribution bounds and finiteness."""
    return stats_validate_scores(scores)


def mann_whitney_regression(
    candidate: np.ndarray,
    baseline: np.ndarray,
) -> tuple[float, float]:
    """Perform Mann-Whitney U test between candidate and baseline distributions."""
    candidate = validate_scores(np.asarray(candidate, dtype=float))
    baseline = validate_scores(np.asarray(baseline, dtype=float))

    if len(candidate) < 5 or len(baseline) < 5:
        logger.error(
            "Mann-Whitney regression failed: at least 5 observations required in each group (got candidate_n=%d, baseline_n=%d).",
            len(candidate),
            len(baseline),
        )
        raise ValueError("At least five observations are required in each group.")

    statistic, p_value = compute_mann_whitney_u(candidate, baseline, alternative="less")

    logger.info(
        "Mann-Whitney U test computed: statistic=%.4f, p_value=%.6e (candidate_n=%d, baseline_n=%d)",
        statistic,
        p_value,
        len(candidate),
        len(baseline),
    )
    return statistic, p_value


def bootstrap_delta_ci(
    candidate: np.ndarray,
    baseline: np.ndarray,
    *,
    n_bootstrap: int = 5000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Compute bootstrap confidence interval for delta mean score.

    Backward-compatible wrapper around
    ``nirizan.metrics.stats.bootstrap_delta_ci``. That canonical function
    returns ``(delta_hat, ci_lower, ci_upper)``; this wrapper discards
    ``delta_hat`` and returns only ``(ci_lower, ci_upper)`` so the
    existing 2-tuple contract is preserved. New code should call the
    canonical function and unpack all three values.
    """
    if not 0.0 < confidence < 1.0:
        logger.error(
            "Bootstrap CI failed: confidence must be between 0 and 1, got %.4f",
            confidence,
        )
        raise ValueError("confidence must be between 0 and 1.")

    # Score validation happens inside stats_bootstrap_delta_ci, so we do not
    # duplicate it here. The confidence check above is done first so the
    # caller gets a specific error message rather than the generic one from
    # inside the stats layer.
    _, ci_low, ci_high = stats_bootstrap_delta_ci(
        candidate,
        baseline,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence,
        seed=seed,
    )

    logger.info(
        "Bootstrap delta CI computed (n_bootstrap=%d, confidence=%.2f): [%.6f, %.6f]",
        n_bootstrap,
        confidence,
        ci_low,
        ci_high,
    )

    return ci_low, ci_high


def holm_bonferroni(
    p_values: Mapping[str, float],
    alpha: float = 0.05,
) -> dict[str, bool]:
    """Apply Holm-Bonferroni correction to p-value mapping."""
    if not 0.0 < alpha < 1.0:
        logger.error(
            "Invalid alpha for Holm-Bonferroni: alpha=%.4f (must be between 0 and 1).",
            alpha,
        )
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


def approximate_sample_size(
    *,
    baseline_std: float,
    target_delta: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Approximate required sample size per group for target delta."""
    res = calculate_sample_size(
        baseline_std=baseline_std,
        target_delta=target_delta,
        alpha=alpha,
        power=power,
    )

    logger.info(
        "Approximated required sample size per group: n=%d (std=%.4f, delta=%.4f, alpha=%.4f, power=%.4f)",
        res,
        baseline_std,
        target_delta,
        alpha,
        power,
    )
    return res


def calibrate_gold_set(
    predictions: np.ndarray,
    gold_labels: np.ndarray,
) -> dict[str, float]:
    """Calculate calibration error metrics against a gold set."""
    metrics = compute_calibration_metrics(predictions, gold_labels)

    logger.info(
        "Gold set calibration computed across %d samples: MAE=%.4f, MSE=%.4f, RMSE=%.4f",
        len(predictions),
        metrics["mae"],
        metrics["mse"],
        metrics["rmse"],
    )
    return metrics
