# src/nirizan/metrics/statistical_gating.py
from __future__ import annotations

import math
from typing import Mapping

import numpy as np
from scipy.stats import mannwhitneyu, norm

from nirizan._logging import get_logger

logger = get_logger(__name__)


def validate_scores(scores: np.ndarray) -> np.ndarray:
    if scores.size == 0:
        logger.error("Score validation failed: distribution is empty.")
        raise ValueError("Score distribution is empty.")
    if not np.all(np.isfinite(scores)):
        logger.error("Score validation failed: distribution contains non-finite values.")
        raise ValueError("Score distribution contains non-finite values.")
    if np.any(scores < 0.0) or np.any(scores > 1.0):
        logger.error("Score validation failed: metric scores must be normalized to [0, 1].")
        raise ValueError("Metric scores must be normalized to [0, 1].")
    logger.debug("Successfully validated %d score observations.", scores.size)
    return scores


def mann_whitney_regression(
    candidate: np.ndarray,
    baseline: np.ndarray,
) -> tuple[float, float]:
    candidate = validate_scores(np.asarray(candidate, dtype=float))
    baseline = validate_scores(np.asarray(baseline, dtype=float))

    if len(candidate) < 5 or len(baseline) < 5:
        logger.error(
            "Mann-Whitney regression failed: at least 5 observations required in each group (got candidate_n=%d, baseline_n=%d).",
            len(candidate),
            len(baseline),
        )
        raise ValueError("At least five observations are required in each group.")

    statistic, p_value = mannwhitneyu(
        candidate,
        baseline,
        alternative="less",
    )

    logger.info(
        "Mann-Whitney U test computed: statistic=%.4f, p_value=%.6e (candidate_n=%d, baseline_n=%d)",
        float(statistic),
        float(p_value),
        len(candidate),
        len(baseline),
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
    if not 0.0 < confidence < 1.0:
        logger.error("Bootstrap CI failed: confidence must be between 0 and 1, got %.4f", confidence)
        raise ValueError("confidence must be between 0 and 1.")

    candidate = validate_scores(np.asarray(candidate, dtype=float))
    baseline = validate_scores(np.asarray(baseline, dtype=float))

    rng = np.random.default_rng(seed)
    candidate_samples = rng.choice(candidate, size=(n_bootstrap, len(candidate)), replace=True)
    baseline_samples = rng.choice(baseline, size=(n_bootstrap, len(baseline)), replace=True)

    deltas = candidate_samples.mean(axis=1) - baseline_samples.mean(axis=1)
    alpha = 1.0 - confidence

    ci_low = float(np.quantile(deltas, alpha / 2))
    ci_high = float(np.quantile(deltas, 1.0 - alpha / 2))

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
    if not 0.0 < alpha < 1.0:
        logger.error("Holm-Bonferroni failed: alpha must be between 0 and 1, got %.4f", alpha)
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


def approximate_sample_size(
    *,
    baseline_std: float,
    target_delta: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    if baseline_std <= 0:
        logger.error("Sample size estimation failed: baseline_std must be positive, got %.4f", baseline_std)
        raise ValueError("baseline_std must be positive.")
    if target_delta <= 0:
        logger.error("Sample size estimation failed: target_delta must be positive, got %.4f", target_delta)
        raise ValueError("target_delta must be positive.")
    if not 0 < alpha < 1:
        logger.error("Sample size estimation failed: alpha must be between 0 and 1, got %.4f", alpha)
        raise ValueError("alpha must be between 0 and 1.")
    if not 0 < power < 1:
        logger.error("Sample size estimation failed: power must be between 0 and 1, got %.4f", power)
        raise ValueError("power must be between 0 and 1.")

    z_alpha = norm.ppf(1 - alpha)
    z_power = norm.ppf(power)
    n_per_group = 2 * ((z_alpha + z_power) * baseline_std / target_delta) ** 2
    res = int(math.ceil(n_per_group))

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
    preds = np.asarray(predictions, dtype=float)
    labels = np.asarray(gold_labels, dtype=float)

    if preds.shape != labels.shape:
        logger.error(
            "Calibration error: predictions shape %s does not match gold_labels shape %s.",
            preds.shape,
            labels.shape,
        )
        raise ValueError("Predictions and gold_labels must have the same shape.")

    mae = float(np.mean(np.abs(preds - labels)))
    mse = float(np.mean((preds - labels) ** 2))
    rmse = math.sqrt(mse)

    logger.info(
        "Gold set calibration computed across %d samples: MAE=%.4f, MSE=%.4f, RMSE=%.4f",
        preds.size,
        mae,
        mse,
        rmse,
    )
    return {"mae": mae, "mse": mse, "rmse": rmse}
