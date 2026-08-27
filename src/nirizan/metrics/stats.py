# src/nirizan/metrics/stats.py
"""Centralized statistical utilities and validation helpers for NiriZan metrics, regression, and gate layers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import numpy as np
from scipy.stats import mannwhitneyu


def validate_scores(scores: np.ndarray | Sequence[float]) -> np.ndarray:
    """Validate metric score arrays for finite values and bounded range [0, 1].

    Args:
        scores: Input score sequence or array.

    Returns:
        Validated 1D float NumPy array.

    Raises:
        ValueError: If array is empty, contains NaNs/Infs, or falls outside [0, 1].
    """
    arr = np.asarray(scores, dtype=float)
    if arr.ndim != 1:
        raise ValueError("Scores must be one-dimensional.")
    if arr.size == 0:
        raise ValueError("Scores must contain at least one observation.")
    if not np.isfinite(arr).all():
        raise ValueError("Scores contain non-finite values (NaN/Inf).")
    if np.any(arr < 0.0) or np.any(arr > 1.0):
        raise ValueError("NiriZan metric scores must be in [0, 1].")
    return arr


def bootstrap_delta_ci(
    candidate_scores: np.ndarray | Sequence[float],
    baseline_scores: np.ndarray | Sequence[float],
    confidence_level: float = 0.95,
    n_bootstrap: int = 10000,
    seed: int | None = None,
) -> tuple[float, float, float]:
    """Compute bootstrap confidence interval for the mean delta (candidate - baseline).

    Args:
        candidate_scores: Candidate model score array or sequence.
        baseline_scores: Baseline model score array or sequence.
        confidence_level: Confidence level for the interval (default 0.95).
        n_bootstrap: Number of bootstrap resampling iterations (default 10000).
        seed: Optional random seed for reproducible sampling.

    Returns:
        Tuple containing (point_estimate_delta, ci_lower, ci_upper).

    Raises:
        ValueError: If n_bootstrap <= 0 or confidence_level is not in (0, 1).
    """
    if n_bootstrap <= 0:
        raise ValueError("n_bootstrap must be positive.")
    if not (0.0 < confidence_level < 1.0):
        raise ValueError("confidence_level must be strictly between 0 and 1.")

    cand = validate_scores(candidate_scores)
    base = validate_scores(baseline_scores)

    delta_hat = float(np.mean(cand) - np.mean(base))

    rng = np.random.default_rng(seed)
    cand_boot = rng.choice(cand, size=(n_bootstrap, len(cand)), replace=True)
    base_boot = rng.choice(base, size=(n_bootstrap, len(base)), replace=True)

    boot_deltas = np.mean(cand_boot, axis=1) - np.mean(base_boot, axis=1)

    alpha = 1.0 - confidence_level
    ci_lower = float(np.percentile(boot_deltas, (alpha / 2.0) * 100.0))
    ci_upper = float(np.percentile(boot_deltas, (1.0 - alpha / 2.0) * 100.0))

    return delta_hat, ci_lower, ci_upper


def mann_whitney_regression(
    candidate_scores: np.ndarray | Sequence[float],
    baseline_scores: np.ndarray | Sequence[float],
    alternative: str = "less",
) -> tuple[float, float]:
    """Perform Mann-Whitney U test to evaluate score regression between candidate and baseline.

    Args:
        candidate_scores: Candidate model score array or sequence.
        baseline_scores: Baseline model score array or sequence.
        alternative: Alternative hypothesis string ('less', 'greater', or 'two-sided').

    Returns:
        Tuple of (u_statistic, p_value).
    """
    cand = validate_scores(candidate_scores)
    base = validate_scores(baseline_scores)
    if len(cand) < 5 or len(base) < 5:
        raise ValueError("At least five observations are required in each group.")

    res = mannwhitneyu(cand, base, alternative=alternative)
    return float(res.statistic), float(res.pvalue)


def holm_bonferroni(
    p_values: Mapping[str, float],
    alpha: float = 0.05,
) -> dict[str, bool]:
    """Apply Holm-Bonferroni step-down correction for multiple hypothesis testing.

    Args:
        p_values: Mapping from metric/hypothesis identifier to raw p-value.
        alpha: Overall family-wise error rate threshold (default 0.05).

    Returns:
        Dictionary mapping identifier to boolean indicating if null hypothesis is rejected.

    Raises:
        ValueError: If alpha is not in (0, 1).
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be strictly between 0 and 1.")

    if not p_values:
        return {}

    sorted_items = sorted(p_values.items(), key=lambda item: item[1])
    m = len(sorted_items)

    rejected: dict[str, bool] = dict.fromkeys(p_values.keys(), False)

    stopped = False
    for k, (key, p_val) in enumerate(sorted_items, start=1):
        if stopped:
            rejected[key] = False
            continue

        threshold = alpha / (m - k + 1)
        if p_val <= threshold:
            rejected[key] = True
        else:
            stopped = True

    return rejected


# Aliases for backward compatibility across gate, regression, and legacy callers
calculate_bootstrap_ci = bootstrap_delta_ci
compute_holm_bonferroni = holm_bonferroni
compute_mann_whitney_u = mann_whitney_regression

__all__ = [
    "bootstrap_delta_ci",
    "calculate_bootstrap_ci",
    "compute_holm_bonferroni",
    "compute_mann_whitney_u",
    "holm_bonferroni",
    "mann_whitney_regression",
    "validate_scores",
]
