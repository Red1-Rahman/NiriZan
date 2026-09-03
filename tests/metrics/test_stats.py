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
    frobenius_covariance_permutation,
    validate_score_matrix,
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


class TestValidateScoreMatrix:
    def test_valid_matrix(self) -> None:
        matrix = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]])
        result = validate_score_matrix(matrix)
        np.testing.assert_array_equal(result, matrix)

    def test_non_two_dimensional_raises(self) -> None:
        with pytest.raises(ValueError, match="two-dimensional"):
            validate_score_matrix(np.array([0.1, 0.2, 0.3]))

    def test_empty_matrix_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            validate_score_matrix(np.empty((0, 3)))

    def test_single_metric_raises(self) -> None:
        with pytest.raises(ValueError, match="two metrics"):
            validate_score_matrix(np.array([[0.1], [0.2], [0.3]]))

    def test_non_finite_values_raise(self) -> None:
        matrix = np.array([[0.1, 0.2], [np.nan, 0.4]])
        with pytest.raises(ValueError, match="non-finite"):
            validate_score_matrix(matrix)

    def test_out_of_bounds_values_raise(self) -> None:
        matrix = np.array([[0.1, 1.5], [0.3, 0.4]])
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            validate_score_matrix(matrix)


class TestFrobeniusCovariancePermutation:
    @pytest.fixture
    def correlated(self) -> np.ndarray:
        rng = np.random.default_rng(0)
        corr = np.array([[1.0, 0.6], [0.6, 1.0]])
        L = np.linalg.cholesky(corr)
        z = rng.standard_normal(size=(100, 2)) @ L.T
        return 1.0 / (1.0 + np.exp(-z))

    def test_identical_groups_give_zero_statistic_and_p_one(self, correlated: np.ndarray) -> None:
        stat, p_value = frobenius_covariance_permutation(correlated, correlated, n_perm=100, seed=1)
        assert stat == pytest.approx(0.0)
        assert p_value == pytest.approx(1.0)

    def test_p_value_is_in_bounds(self, correlated: np.ndarray) -> None:
        rng = np.random.default_rng(2)
        other = rng.uniform(0.0, 1.0, size=correlated.shape)
        stat, p_value = frobenius_covariance_permutation(correlated, other, n_perm=100, seed=2)
        assert stat >= 0.0
        assert 0.0 <= p_value <= 1.0

    def test_mismatched_metric_counts_raise(self, correlated: np.ndarray) -> None:
        rng = np.random.default_rng(3)
        other = rng.uniform(0.0, 1.0, size=(50, 3))
        with pytest.raises(ValueError, match="same number of metrics"):
            frobenius_covariance_permutation(correlated, other)

    def test_non_positive_n_perm_raises(self, correlated: np.ndarray) -> None:
        with pytest.raises(ValueError, match="n_perm must be positive"):
            frobenius_covariance_permutation(correlated, correlated, n_perm=0)

    def test_zero_variance_metric_raises_when_using_correlation(self) -> None:
        constant = np.column_stack([np.full(20, 0.5), np.linspace(0.1, 0.9, 20)])
        with pytest.raises(ValueError, match="zero variance"):
            frobenius_covariance_permutation(constant, constant, use_correlation=True)

    def test_zero_variance_metric_is_fine_for_covariance(self) -> None:
        constant = np.column_stack([np.full(20, 0.5), np.linspace(0.1, 0.9, 20)])
        stat, p_value = frobenius_covariance_permutation(
            constant, constant, use_correlation=False, n_perm=50, seed=4
        )
        assert stat == pytest.approx(0.0)
        assert 0.0 <= p_value <= 1.0

    def test_affine_transform_preserves_p_value(self, correlated: np.ndarray) -> None:
        rng = np.random.default_rng(5)
        corr_flip = np.array([[1.0, -0.5], [-0.5, 1.0]])
        L = np.linalg.cholesky(corr_flip)
        z = rng.standard_normal(size=(100, 2)) @ L.T
        other = 1.0 / (1.0 + np.exp(-z))

        def affine(arr: np.ndarray, a: float, b: float = 0.5) -> np.ndarray:
            return b + a * (arr - b)

        _, p_original = frobenius_covariance_permutation(correlated, other, n_perm=150, seed=42)
        _, p_scaled = frobenius_covariance_permutation(
            affine(correlated, 0.5), affine(other, 0.5), n_perm=150, seed=42
        )
        assert p_original == pytest.approx(p_scaled)


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
        assert delta_hat == pytest.approx(-0.3)
        assert ci_low == pytest.approx(-0.4, abs=0.05)
        assert ci_high == pytest.approx(-0.2, abs=0.05)
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
        assert n == 63

    def test_invalid_parameters_raise(self) -> None:
        with pytest.raises(ValueError, match="baseline_std"):
            calculate_sample_size(baseline_std=-0.1, target_delta=0.05)


class TestComputeCalibrationMetrics:
    def test_calibration(self) -> None:
        preds = np.array([0.2, 0.4, 0.6])
        labels = np.array([0.2, 0.5, 0.5])
        metrics = compute_calibration_metrics(preds, labels)
        assert metrics["mae"] == pytest.approx(1 / 15)
        assert metrics["mse"] == pytest.approx(1 / 150)
        assert metrics["rmse"] == pytest.approx((1 / 150) ** 0.5)

    def test_shape_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="same shape"):
            compute_calibration_metrics(np.array([0.1]), np.array([0.1, 0.2]))
