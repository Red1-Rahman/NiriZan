# tests/metrics/test_stats.py
from __future__ import annotations

import numpy as np
import pytest

from nirizan.metrics.stats import (
    calculate_bootstrap_ci,
    calculate_sample_size,
    compute_calibration_metrics,
    compute_holm_bonferroni,
    compute_mann_whitney_u,
    validate_scores,
)


class TestValidateScores:
    def test_valid_scores(self) -> None:
        scores = np.array([0.1, 0.5, 0.9])
        result = validate_scores(scores)
        np.testing.assert_array_equal(result, scores)

    def test_empty_scores_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_scores(np.array([]))

    def test_non_finite_scores_raises(self) -> None:
        with pytest.raises(ValueError, match="non-finite"):
            validate_scores(np.array([0.1, np.nan, 0.5]))

    def test_out_of_bounds_scores_raises(self) -> None:
        with pytest.raises(ValueError, match="normalized to"):
            validate_scores(np.array([-0.1, 0.5, 1.2]))


class TestComputeMannWhitneyU:
    def test_basic_computation(self) -> None:
        candidate = np.array([0.2, 0.3, 0.4, 0.3, 0.2])
        baseline = np.array([0.7, 0.8, 0.9, 0.8, 0.7])
        stat, p_val = compute_mann_whitney_u(candidate, baseline, alternative="less")
        assert isinstance(stat, float)
        assert isinstance(p_val, float)
        assert p_val < 0.05


class TestCalculateBootstrapCI:
    def test_valid_ci(self) -> None:
        candidate = np.array([0.4, 0.5, 0.6, 0.5, 0.4])
        baseline = np.array([0.7, 0.8, 0.9, 0.8, 0.7])
        delta_hat, ci_low, ci_high = calculate_bootstrap_ci(
            candidate, baseline, n_bootstrap=1000, confidence_level=0.95, seed=42
        )
        assert isinstance(delta_hat, float)
        assert isinstance(ci_low, float)
        assert isinstance(ci_high, float)
        assert ci_low < ci_high

    def test_invalid_confidence_raises(self) -> None:
        candidate = np.array([0.5, 0.6])
        baseline = np.array([0.5, 0.6])
        with pytest.raises(ValueError, match="confidence_level"):
            calculate_bootstrap_ci(candidate, baseline, confidence_level=1.5)


class TestComputeHolmBonferroni:
    def test_correction(self) -> None:
        p_vals = {"m1": 0.01, "m2": 0.04, "m3": 0.15}
        result = compute_holm_bonferroni(p_vals, alpha=0.05)
        assert result["m1"] is True
        assert result["m2"] is False
        assert result["m3"] is False

    def test_empty_input(self) -> None:
        assert compute_holm_bonferroni({}) == {}

    def test_invalid_alpha_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            compute_holm_bonferroni({"m1": 0.01}, alpha=1.5)


class TestCalculateSampleSize:
    def test_sample_size(self) -> None:
        n = calculate_sample_size(baseline_std=0.1, target_delta=0.05, alpha=0.05, power=0.80)
        assert isinstance(n, int)
        assert n > 0

    def test_invalid_parameters_raise(self) -> None:
        with pytest.raises(ValueError, match="baseline_std"):
            calculate_sample_size(baseline_std=-0.1, target_delta=0.05)


class TestComputeCalibrationMetrics:
    def test_calibration(self) -> None:
        preds = np.array([0.2, 0.4, 0.6])
        labels = np.array([0.2, 0.5, 0.5])
        metrics = compute_calibration_metrics(preds, labels)
        assert "mae" in metrics
        assert "mse" in metrics
        assert "rmse" in metrics
        assert metrics["mae"] >= 0.0

    def test_shape_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="same shape"):
            compute_calibration_metrics(np.array([0.1]), np.array([0.1, 0.2]))
