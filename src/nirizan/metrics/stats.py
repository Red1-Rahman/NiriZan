# src/nirizan/metrics/stats.py
"""Shared statistical primitives used across NiriZan's regression detection
and CI gate. This is the single authoritative implementation; regression
and gate depend on it, not the reverse.
"""
from __future__ import annotations

from typing import Mapping

import numpy as np
from scipy.stats import mannwhitneyu

from nirizan._logging import get_logger

logger = get_logger(__name__)

DEFAULT_ALPHA: float = 0.05
MIN_MANN_WHITNEY_SAMPLE_SIZE: int = 5


def validate_scores(scores: np.ndarray) -> np.ndarray:
    """Validate a metric-score distribution before statistical analysis.

    Scores must be one-dimensional, non-empty, finite, and normalized to
    [0, 1]. Inputs are coerced via np.asarray(..., dtype=float) and returned.
    """
    scores = np.asarray(scores, dtype=float)

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
    return scores


def mann_whitney_regression(
    candidate: np.ndarray,
    baseline: np.ndarray,
) -> tuple[float, float]:
    """Test whether candidate scores are stochastically lower than baseline.

    Requires at least MIN_MANN_WHITNEY_SAMPLE_SIZE observations per group;
    below that the test's normal approximation and power are unreliable.
    """
    candidate = validate_scores(candidate)
    baseline = validate_scores(baseline)

    if candidate.size < MIN_MANN_WHITNEY_SAMPLE_SIZE or baseline.size < MIN_MANN_WHITNEY_SAMPLE_SIZE:
        logger.error(
            "Mann-Whitney regression failed: at least %d observations required per group "
            "(got candidate_n=%d, baseline_n=%d).",
            MIN_MANN_WHITNEY_SAMPLE_SIZE,
            candidate.size,
            baseline.size,
        )
        raise ValueError(
            f"At least {MIN_MANN_WHITNEY_SAMPLE_SIZE} observations are required in each group."
        )

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


def bootstrap_delta_ci(
    candidate: np.ndarray,
    baseline: np.ndarray,
    *,
    n_bootstrap: int = 5000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """Bootstrap a confidence interval for the candidate-baseline mean delta."""
    candidate = validate_scores(candidate)
    baseline = validate_scores(baseline)

    if n_bootstrap < 1:
        logger.error("Bootstrap CI failed: n_bootstrap must be positive, got %d", n_bootstrap)
        raise ValueError("n_bootstrap must be positive.")

    if not 0.0 < confidence < 1.0:
        logger.error("Bootstrap CI failed: confidence must be between 0 and 1, got %.4f", confidence)
        raise ValueError("confidence must be between 0 and 1.")

    rng = np.random.default_rng(seed)
    candidate_samples = rng.choice(candidate, size=(n_bootstrap, candidate.size), replace=True)
    baseline_samples = rng.choice(baseline, size=(n_bootstrap, baseline.size), replace=True)

    deltas = candidate_samples.mean(axis=1) - baseline_samples.mean(axis=1)
    alpha = 1.0 - confidence

    ci_low = float(np.quantile(deltas, alpha / 2.0))
    ci_high = float(np.quantile(deltas, 1.0 - alpha / 2.0))

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

    logger.info("Applying Holm-Bonferroni correction for %d hypotheses at alpha=%.4f", total, alpha)

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
