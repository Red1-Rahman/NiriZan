# src/nirizan/metrics/statistical_gating.py
from __future__ import annotations

import math
import numpy as np
from scipy.stats import mannwhitneyu, norm


def validate_scores(scores: np.ndarray) -> np.ndarray:
    if scores.size == 0:
        raise ValueError("Score distribution is empty.")
    if not np.all(np.isfinite(scores)):
        raise ValueError("Score distribution contains non-finite values.")
    if np.any(scores < 0.0) or np.any(scores > 1.0):
        raise ValueError("Metric scores must be normalized to [0, 1].")
    return scores


def mann_whitney_regression(
    candidate: np.ndarray,
    baseline: np.ndarray,
) -> tuple[float, float]:
    candidate = validate_scores(np.asarray(candidate, dtype=float))
    baseline = validate_scores(np.asarray(baseline, dtype=float))

    if len(candidate) < 5 or len(baseline) < 5:
        raise ValueError("At least five observations are required in each group.")

    statistic, p_value = mannwhitneyu(
        candidate,
        baseline,
        alternative="less",
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
    candidate = validate_scores(np.asarray(candidate, dtype=float))
    baseline = validate_scores(np.asarray(baseline, dtype=float))

    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1.")

    rng = np.random.default_rng(seed)
    candidate_samples = rng.choice(candidate, size=(n_bootstrap, len(candidate)), replace=True)
    baseline_samples = rng.choice(baseline, size=(n_bootstrap, len(baseline)), replace=True)

    deltas = candidate_samples.mean(axis=1) - baseline_samples.mean(axis=1)
    alpha = 1.0 - confidence

    return (
        float(np.quantile(deltas, alpha / 2)),
        float(np.quantile(deltas, 1.0 - alpha / 2)),
    )


def holm_bonferroni(
    p_values: dict[str, float],
    alpha: float = 0.05,
) -> dict[str, bool]:
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


def approximate_sample_size(
    *,
    baseline_std: float,
    target_delta: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    if baseline_std <= 0:
        raise ValueError("baseline_std must be positive.")
    if target_delta <= 0:
        raise ValueError("target_delta must be positive.")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1.")
    if not 0 < power < 1:
        raise ValueError("power must be between 0 and 1.")

    z_alpha = norm.ppf(1 - alpha)
    z_power = norm.ppf(power)
    n_per_group = 2 * ((z_alpha + z_power) * baseline_std / target_delta) ** 2
    return int(math.ceil(n_per_group))


def calibrate_gold_set(
    predictions: np.ndarray,
    gold_labels: np.ndarray,
) -> dict[str, float]:
    """Calculate calibration error metrics against a gold set."""
    preds = np.asarray(predictions, dtype=float)
    labels = np.asarray(gold_labels, dtype=float)
    mae = float(np.mean(np.abs(preds - labels)))
    mse = float(np.mean((preds - labels) ** 2))
    return {"mae": mae, "mse": mse, "rmse": math.sqrt(mse)}
