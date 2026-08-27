# src/nirizan/metrics/stats.py
"""Centralized statistical utilities and validation helpers for NiriZan metrics, regression, and gate layers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal
import numpy as np
from scipy.stats import mannwhitneyu, norm

from nirizan._logging import get_logger

logger = get_logger(__name__)


def validate_scores(scores: np.ndarray | Sequence[float]) -> np.ndarray:
    """Validate metric score arrays for finite values and bounded range [0, 1]."""
    arr = np.asarray(scores, dtype=float)
    if arr.ndim != 1:
        raise ValueError("Scores must be one-dimensional.")
    if arr.size == 0:
        raise ValueError("Score distribution is empty.")
    if not np.isfinite(arr).all():
        raise ValueError("Scores contain non-finite values (NaN/Inf).")
    if np.any(arr < 0.0) or np.any(arr > 1.0):
        raise ValueError("NiriZan metric scores must be normalized to [0, 1].")
    logger.debug("Successfully validated %d score observations", arr.size)
    return arr


def bootstrap_delta_ci(
    candidate_scores: np.ndarray | Sequence[float],
    baseline_scores: np.ndarray | Sequence[float],
    *,
    confidence_level: float = 0.95,
    n_bootstrap: int = 10000,
    seed: int | None = None,
) -> tuple[float, float, float]:
    """Compute bootstrap confidence interval for the mean delta (candidate - baseline)."""
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
    *,
    alternative: Literal["less", "greater", "two-sided"] = "less",
) -> tuple[float, float]:
    """Perform Mann-Whitney U test to evaluate score regression between candidate and baseline."""
    cand = validate_scores(candidate_scores)
    base = validate_scores(baseline_scores)
    if len(cand) < 5 or len(base) < 5:
        raise ValueError("At least five observations are required in each group.")

    res = mannwhitneyu(cand, base, alternative=alternative)
    return float(res.statistic), float(res.pvalue)


def holm_bonferroni(
    p_values: Mapping[str, float],
    *,
    alpha: float = 0.05,
) -> dict[str, bool]:
    """Apply Holm-Bonferroni step-down correction for multiple hypothesis testing."""
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


def calculate_sample_size(
    *,
    baseline_std: float,
    target_delta: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Calculate approximate required sample size per group for target delta using two-sided alpha."""
    if baseline_std <= 0:
        raise ValueError("baseline_std must be positive.")
    if target_delta <= 0:
        raise ValueError("target_delta must be positive.")
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be between 0 and 1.")
    if not (0.0 < power < 1.0):
        raise ValueError("power must be between 0 and 1.")

    z_alpha = norm.ppf(1.0 - alpha / 2.0)
    z_beta = norm.ppf(power)
    n = 2.0 * ((z_alpha + z_beta) * baseline_std / target_delta) ** 2
    return int(np.ceil(n))


def compute_calibration_metrics(
    predictions: np.ndarray | Sequence[float],
    gold_labels: np.ndarray | Sequence[float],
) -> dict[str, float]:
    """Calculate calibration error metrics (MAE, MSE, RMSE) against gold labels."""
    preds = np.asarray(predictions, dtype=float)
    labels = np.asarray(gold_labels, dtype=float)
    if preds.shape != labels.shape:
        raise ValueError("predictions and gold_labels must have the same shape.")

    mae = float(np.mean(np.abs(preds - labels)))
    mse = float(np.mean((preds - labels) ** 2))
    rmse = float(np.sqrt(mse))
    return {"mae": mae, "mse": mse, "rmse": rmse}


# Aliases for backward compatibility
calculate_bootstrap_ci = bootstrap_delta_ci
compute_holm_bonferroni = holm_bonferroni
compute_mann_whitney_u = mann_whitney_regression

__all__ = [
    "bootstrap_delta_ci",
    "calculate_bootstrap_ci",
    "calculate_sample_size",
    "compute_calibration_metrics",
    "compute_holm_bonferroni",
    "compute_mann_whitney_u",
    "holm_bonferroni",
    "mann_whitney_regression",
    "validate_scores",
]
