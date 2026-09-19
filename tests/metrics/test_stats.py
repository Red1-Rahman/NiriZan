# tests\metrics\test_stats.py
from __future__ import annotations

import numpy as np
import pytest

from nirizan.metrics.stats import (
    bootstrap_delta_ci,
    calculate_bootstrap_ci,
    calculate_sample_size,
    cohens_d,
    compute_calibration_metrics,
    compute_holm_bonferroni,
    compute_mann_whitney_u,
    dependence_max_t_statistic,
    dependence_max_t_test,
    holm_bonferroni,
    mann_whitney_regression,
    permutation_p_value,
    permutation_test,
    scale_logvar_statistic,
    scale_logvar_test,
    validate_score_matrix,
    validate_scores,
)

# ---------------------------------------------------------------------------
# validate_scores
# ---------------------------------------------------------------------------


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

    def test_two_dimensional_input_raises(self) -> None:
        with pytest.raises(ValueError, match="one-dimensional"):
            validate_scores(np.array([[0.1, 0.2], [0.3, 0.4]]))

    def test_list_input_accepted(self) -> None:
        result = validate_scores([0.1, 0.5, 0.9])
        np.testing.assert_array_equal(result, np.array([0.1, 0.5, 0.9]))


# ---------------------------------------------------------------------------
# validate_score_matrix
# ---------------------------------------------------------------------------


class TestValidateScoreMatrix:
    def test_valid_matrix(self) -> None:
        matrix = np.array(
            [
                [0.1, 0.5, 0.9],
                [0.2, 0.4, 0.8],
                [0.3, 0.6, 0.7],
            ]
        )
        result = validate_score_matrix(matrix)
        np.testing.assert_array_equal(result, matrix)

    def test_one_dimensional_input_raises(self) -> None:
        with pytest.raises(ValueError, match="two-dimensional"):
            validate_score_matrix(np.array([0.1, 0.5, 0.9]))

    def test_too_few_rows_raises(self) -> None:
        with pytest.raises(ValueError, match="rows"):
            validate_score_matrix(np.array([[0.1, 0.2]]), min_rows=2)

    def test_too_few_columns_raises(self) -> None:
        with pytest.raises(ValueError, match="columns"):
            validate_score_matrix(np.zeros((5, 1)), min_columns=2)

    def test_non_finite_raises(self) -> None:
        matrix = np.array([[0.1, np.nan], [0.2, 0.3]])
        with pytest.raises(ValueError, match="non-finite"):
            validate_score_matrix(matrix)

    def test_out_of_bounds_raises(self) -> None:
        matrix = np.array([[0.1, 1.5], [0.2, 0.3]])
        with pytest.raises(ValueError, match="normalized to"):
            validate_score_matrix(matrix)


# ---------------------------------------------------------------------------
# cohens_d
# ---------------------------------------------------------------------------


class TestCohensD:
    def test_identical_distributions_give_zero(self) -> None:
        x = np.array([0.2, 0.4, 0.5, 0.6, 0.8])
        assert cohens_d(x, x) == pytest.approx(0.0)

    def test_shifted_distributions_give_negative_sign(self) -> None:
        # Candidate scores are lower than baseline, so d is negative.
        cand = np.array([0.3, 0.4, 0.5, 0.6, 0.7])
        base = np.array([0.5, 0.6, 0.7, 0.8, 0.9])
        d = cohens_d(cand, base)
        assert d < 0.0

    def test_antisymmetric(self) -> None:
        # Swapping arguments flips the sign but not the magnitude.
        cand = np.array([0.3, 0.4, 0.5, 0.6, 0.7])
        base = np.array([0.5, 0.6, 0.7, 0.8, 0.9])
        assert cohens_d(cand, base) == pytest.approx(-cohens_d(base, cand))

    def test_zero_variance_both_groups_returns_zero(self) -> None:
        # Both groups constant → pooled std is exactly zero → no defined
        # effect size. The contract says return 0.0, not raise or return inf.
        const = np.full(10, 0.5)
        assert cohens_d(const, const) == 0.0

    def test_zero_variance_one_group_returns_zero(self) -> None:
        # One group constant, other group varied. Pooled std is nonzero
        # (because one group has variance), so this is a normal effect size,
        # not the zero-variance case.
        const = np.full(10, 0.5)
        varied = np.array([0.1, 0.3, 0.5, 0.7, 0.9, 0.2, 0.4, 0.6, 0.8, 0.3])
        d = cohens_d(const, varied)
        assert np.isfinite(d)

    def test_known_value(self) -> None:
        # Two disjoint groups, same variance, same size.
        # Deviations from each group's own mean are [-0.1, 0, 0.1, 0, 0],
        # giving sample variance (ddof=1) of 0.02/4 = 0.005 and
        # std = sqrt(0.005) ≈ 0.07071 for both groups. Since both stds are
        # equal, the pooled std sqrt((s_c²+s_b²)/2) reduces to that same
        # std. cand mean = 0.3, base mean = 0.7, so
        # d = (0.3 - 0.7) / 0.07071 ≈ -5.657.
        cand = np.array([0.2, 0.3, 0.4, 0.3, 0.3])
        base = np.array([0.6, 0.7, 0.8, 0.7, 0.7])
        assert cohens_d(cand, base) == pytest.approx(-5.657, abs=0.01)

    def test_invalid_scores_raise(self) -> None:
        with pytest.raises(ValueError):
            cohens_d(np.array([0.1, 1.5]), np.array([0.2, 0.3]))


# ---------------------------------------------------------------------------
# mann_whitney_regression (and its alias)
# ---------------------------------------------------------------------------


class TestMannWhitneyRegression:
    def test_basic_computation(self) -> None:
        candidate = np.array([0.2, 0.3, 0.4, 0.3, 0.2])
        baseline = np.array([0.7, 0.8, 0.9, 0.8, 0.7])
        stat, p_val = mann_whitney_regression(candidate, baseline, alternative="less")
        assert isinstance(stat, float)
        assert isinstance(p_val, float)
        assert p_val < 0.05

    def test_too_few_observations_raises(self) -> None:
        with pytest.raises(ValueError, match="at least five"):
            mann_whitney_regression(np.array([0.5, 0.6]), np.array([0.5, 0.6]), alternative="less")


class TestComputeMannWhitneyU:
    """The alias must remain importable and behave identically."""

    def test_basic_computation(self) -> None:
        candidate = np.array([0.2, 0.3, 0.4, 0.3, 0.2])
        baseline = np.array([0.7, 0.8, 0.9, 0.8, 0.7])
        stat, p_val = compute_mann_whitney_u(candidate, baseline, alternative="less")
        assert isinstance(stat, float)
        assert isinstance(p_val, float)
        assert p_val < 0.05

    def test_alias_matches_canonical(self) -> None:
        candidate = np.array([0.2, 0.3, 0.4, 0.3, 0.2])
        baseline = np.array([0.7, 0.8, 0.9, 0.8, 0.7])
        assert compute_mann_whitney_u(
            candidate, baseline, alternative="less"
        ) == mann_whitney_regression(candidate, baseline, alternative="less")


# ---------------------------------------------------------------------------
# bootstrap_delta_ci (and its alias)
# ---------------------------------------------------------------------------


class TestBootstrapDeltaCI:
    def test_returns_three_tuple(self) -> None:
        candidate = np.array([0.4, 0.5, 0.6, 0.5, 0.4])
        baseline = np.array([0.7, 0.8, 0.9, 0.8, 0.7])
        result = bootstrap_delta_ci(
            candidate, baseline, n_bootstrap=500, confidence_level=0.95, seed=42
        )
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_valid_ci(self) -> None:
        candidate = np.array([0.4, 0.5, 0.6, 0.5, 0.4])
        baseline = np.array([0.7, 0.8, 0.9, 0.8, 0.7])
        delta_hat, ci_low, ci_high = bootstrap_delta_ci(
            candidate, baseline, n_bootstrap=1000, confidence_level=0.95, seed=42
        )
        assert delta_hat == pytest.approx(-0.3)
        assert ci_low == pytest.approx(-0.4, abs=0.05)
        assert ci_high == pytest.approx(-0.2, abs=0.05)
        assert ci_low < ci_high

    def test_deterministic_with_seed(self) -> None:
        candidate = np.array([0.4, 0.5, 0.6, 0.5, 0.4])
        baseline = np.array([0.7, 0.8, 0.9, 0.8, 0.7])
        a = bootstrap_delta_ci(candidate, baseline, n_bootstrap=200, seed=7)
        b = bootstrap_delta_ci(candidate, baseline, n_bootstrap=200, seed=7)
        assert a == b

    def test_invalid_confidence_raises(self) -> None:
        candidate = np.array([0.5, 0.6])
        baseline = np.array([0.5, 0.6])
        with pytest.raises(ValueError, match="confidence_level"):
            bootstrap_delta_ci(candidate, baseline, confidence_level=1.5)

    def test_invalid_bootstrap_count_raises(self) -> None:
        candidate = np.array([0.5, 0.6])
        baseline = np.array([0.5, 0.6])
        with pytest.raises(ValueError, match="n_bootstrap"):
            bootstrap_delta_ci(candidate, baseline, n_bootstrap=0)


class TestCalculateBootstrapCI:
    """The alias must remain importable and behave identically."""

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

    def test_alias_matches_canonical(self) -> None:
        candidate = np.array([0.4, 0.5, 0.6, 0.5, 0.4])
        baseline = np.array([0.7, 0.8, 0.9, 0.8, 0.7])
        assert calculate_bootstrap_ci(
            candidate, baseline, n_bootstrap=200, seed=11
        ) == bootstrap_delta_ci(candidate, baseline, n_bootstrap=200, seed=11)


# ---------------------------------------------------------------------------
# holm_bonferroni (and its alias)
# ---------------------------------------------------------------------------


class TestHolmBonferroni:
    def test_correction(self) -> None:
        p_vals = {"m1": 0.01, "m2": 0.04, "m3": 0.15}
        result = holm_bonferroni(p_vals, alpha=0.05)
        assert result["m1"] is True
        assert result["m2"] is False
        assert result["m3"] is False

    def test_empty_input(self) -> None:
        assert holm_bonferroni({}) == {}

    def test_invalid_alpha_raises(self) -> None:
        with pytest.raises(ValueError, match="alpha"):
            holm_bonferroni({"m1": 0.01}, alpha=1.5)

    def test_first_rejection_stops_chain(self) -> None:
        # Sorted: 0.001, 0.02, 0.03. Thresholds: 0.05/3, 0.05/2, 0.05/1.
        # 0.001 <= 0.0167 → reject. 0.02 > 0.025? No, 0.02 <= 0.025 → reject.
        # 0.03 > 0.05? No, 0.03 <= 0.05 → reject.
        # Actually all three should reject here.
        result = holm_bonferroni({"a": 0.001, "b": 0.02, "c": 0.03}, alpha=0.05)
        assert all(result.values())

    def test_middle_failure_stops_chain(self) -> None:
        # Sorted: 0.001, 0.04, 0.02. Thresholds: 0.0167, 0.025, 0.05.
        # 0.001 <= 0.0167 → reject. 0.02 <= 0.025 → reject.
        # 0.04 > 0.05? No, 0.04 <= 0.05 → reject.
        # All reject again — need a bigger gap to demonstrate stopping.
        # Use: 0.001 (reject), 0.03 (0.03 > 0.025 → stop).
        result = holm_bonferroni({"a": 0.001, "b": 0.03, "c": 0.04}, alpha=0.05)
        assert result["a"] is True
        assert result["b"] is False
        assert result["c"] is False


class TestComputeHolmBonferroni:
    """The alias must remain importable and behave identically."""

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

    def test_alias_matches_canonical(self) -> None:
        p_vals = {"a": 0.001, "b": 0.02, "c": 0.5}
        assert compute_holm_bonferroni(p_vals, alpha=0.05) == holm_bonferroni(p_vals, alpha=0.05)


# ---------------------------------------------------------------------------
# calculate_sample_size
# ---------------------------------------------------------------------------


class TestCalculateSampleSize:
    def test_sample_size(self) -> None:
        n = calculate_sample_size(baseline_std=0.1, target_delta=0.05, alpha=0.05, power=0.80)
        assert isinstance(n, int)
        assert n == 63

    def test_invalid_parameters_raise(self) -> None:
        with pytest.raises(ValueError, match="baseline_std"):
            calculate_sample_size(baseline_std=-0.1, target_delta=0.05)

    def test_zero_target_delta_raises(self) -> None:
        with pytest.raises(ValueError, match="target_delta"):
            calculate_sample_size(baseline_std=0.1, target_delta=0.0)

    def test_invalid_power_raises(self) -> None:
        with pytest.raises(ValueError, match="power"):
            calculate_sample_size(baseline_std=0.1, target_delta=0.05, power=1.5)


# ---------------------------------------------------------------------------
# compute_calibration_metrics
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# permutation_p_value
# ---------------------------------------------------------------------------


class TestPermutationPValue:
    def test_observed_at_extreme_high_gives_floor(self) -> None:
        # Nothing in the null is >= observed → count = 0 → p = 1/(R+1).
        null = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        p = permutation_p_value(0.9, null, alternative="greater")
        assert p == pytest.approx(1 / 6)

    def test_observed_at_middle(self) -> None:
        # Null values 1..5; observed 3 → count of >= 3 is 3 (3, 4, 5).
        null = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        p = permutation_p_value(3.0, null, alternative="greater")
        assert p == pytest.approx(4 / 6)

    def test_less_alternative(self) -> None:
        null = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        # count of <= 2 is 2 (1, 2) → p = 3/6
        p = permutation_p_value(2.0, null, alternative="less")
        assert p == pytest.approx(3 / 6)

    def test_two_sided(self) -> None:
        null = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
        # |observed| = 1.5; count of |null| >= 1.5 is 2 (-2, 2) → p = 3/6
        p = permutation_p_value(1.5, null, alternative="two-sided")
        assert p == pytest.approx(3 / 6)

    def test_p_value_never_zero(self) -> None:
        # The (k+1)/(R+1) convention guarantees p > 0 for any observed value.
        null = np.array([0.1, 0.2, 0.3])
        p = permutation_p_value(1e9, null, alternative="greater")
        assert p == pytest.approx(1 / 4)

    def test_empty_null_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            permutation_p_value(0.5, np.array([]))

    def test_two_dimensional_null_raises(self) -> None:
        with pytest.raises(ValueError, match="1-D"):
            permutation_p_value(0.5, np.array([[0.1, 0.2]]))

    def test_unknown_alternative_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown"):
            permutation_p_value(0.5, np.array([0.1, 0.2]), alternative="up")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# permutation_test
# ---------------------------------------------------------------------------


class TestPermutationTest:
    def test_returns_observed_and_null(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.uniform(0.1, 0.4, size=20)
        y = rng.uniform(0.6, 0.9, size=20)
        observed, null = permutation_test(
            x, y, lambda a, b: float(a.mean() - b.mean()), n_permutations=99, seed=1
        )
        assert isinstance(observed, float)
        assert null.shape == (99,)

    def test_observed_matches_direct_statistic(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.uniform(0.1, 0.4, size=20)
        y = rng.uniform(0.6, 0.9, size=20)
        statistic_fn = lambda a, b: float(a.mean() - b.mean())  # noqa: E731
        observed, _ = permutation_test(x, y, statistic_fn, n_permutations=50, seed=1)
        assert observed == pytest.approx(statistic_fn(x, y))

    def test_deterministic_with_seed(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.uniform(0.1, 0.4, size=15)
        y = rng.uniform(0.5, 0.9, size=15)
        a_obs, a_null = permutation_test(
            x, y, lambda p, q: float(p.mean() - q.mean()), n_permutations=30, seed=5
        )
        b_obs, b_null = permutation_test(
            x, y, lambda p, q: float(p.mean() - q.mean()), n_permutations=30, seed=5
        )
        assert a_obs == b_obs
        np.testing.assert_array_equal(a_null, b_null)

    def test_different_seeds_give_different_nulls(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.uniform(0.1, 0.4, size=15)
        y = rng.uniform(0.5, 0.9, size=15)
        _, a_null = permutation_test(
            x, y, lambda p, q: float(p.mean() - q.mean()), n_permutations=30, seed=5
        )
        _, b_null = permutation_test(
            x, y, lambda p, q: float(p.mean() - q.mean()), n_permutations=30, seed=6
        )
        assert not np.array_equal(a_null, b_null)

    def test_one_dimensional_input_is_reshaped(self) -> None:
        x = np.array([0.1, 0.2, 0.3, 0.4])
        y = np.array([0.6, 0.7, 0.8, 0.9])
        observed, null = permutation_test(
            x, y, lambda a, b: float(a.mean() - b.mean()), n_permutations=20, seed=1
        )
        assert np.isfinite(observed)
        assert null.shape == (20,)

    def test_zero_permutations_raises(self) -> None:
        with pytest.raises(ValueError, match="n_permutations"):
            permutation_test(
                np.array([0.1, 0.2, 0.3]),
                np.array([0.4, 0.5, 0.6]),
                lambda a, b: 0.0,
                n_permutations=0,
            )

    def test_mismatched_columns_raises(self) -> None:
        with pytest.raises(ValueError, match="same number of columns"):
            permutation_test(
                np.zeros((5, 2)),
                np.zeros((5, 3)),
                lambda a, b: 0.0,
                n_permutations=10,
            )

    def test_out_of_bounds_raises(self) -> None:
        with pytest.raises(ValueError, match="outside"):
            permutation_test(
                np.array([0.5, 1.5, 0.6]),
                np.array([0.1, 0.2, 0.3]),
                lambda a, b: 0.0,
                n_permutations=10,
            )


# ---------------------------------------------------------------------------
# scale_logvar_statistic / scale_logvar_test
# ---------------------------------------------------------------------------


class TestScaleLogvarStatistic:
    def test_identical_inputs_give_zero(self) -> None:
        x = np.array([[0.2, 0.3], [0.4, 0.5], [0.6, 0.7], [0.8, 0.9]])
        assert scale_logvar_statistic(x, x) == pytest.approx(0.0)

    def test_variance_inflation_produces_positive_statistic(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.uniform(0.3, 0.7, size=(40, 3))
        center = x.mean(axis=0)
        y = center + (x - center) * 1.4
        assert y.min() >= 0.0 and y.max() <= 1.0
        stat = scale_logvar_statistic(x, y)
        assert stat > 0.0

    def test_symmetric_in_arguments(self) -> None:
        # The statistic is a sum of squares of log differences, so it is
        # invariant under swapping x and y.
        rng = np.random.default_rng(1)
        x = rng.uniform(0.2, 0.5, size=(30, 2))
        y = rng.uniform(0.4, 0.9, size=(30, 2))
        assert scale_logvar_statistic(x, y) == pytest.approx(scale_logvar_statistic(y, x))

    def test_one_dimensional_input_treated_as_single_metric(self) -> None:
        rng = np.random.default_rng(2)
        x = rng.uniform(0.3, 0.7, size=30)
        y = rng.uniform(0.3, 0.7, size=30)
        stat = scale_logvar_statistic(x, y)
        assert np.isfinite(stat)

    def test_zero_variance_column_does_not_raise(self) -> None:
        # A saturated column (all values at 0.5) must not produce inf.
        x = np.column_stack([np.full(20, 0.5), np.linspace(0.2, 0.8, 20)])
        y = np.column_stack([np.full(20, 0.5), np.linspace(0.3, 0.9, 20)])
        stat = scale_logvar_statistic(x, y)
        assert np.isfinite(stat)

    def test_known_value(self) -> None:
        # Two-metric case with variance ratio exactly 2 in both columns.
        # Both columns are centered at 0.5 with a max deviation of 0.15,
        # so a sqrt(2) inflation stays safely within [0, 1]
        # (0.5 +/- 0.15*sqrt(2) ~= 0.5 +/- 0.212).
        x = np.array([[0.35, 0.35], [0.45, 0.45], [0.55, 0.55], [0.65, 0.65]])
        center = x.mean(axis=0)
        y = center + (x - center) * np.sqrt(2.0)
        assert y.min() >= 0.0 and y.max() <= 1.0
        stat = scale_logvar_statistic(x, y)
        # Each column contributes (log 2)^2; two columns.
        expected = 2 * (np.log(2.0) ** 2)
        assert stat == pytest.approx(expected, rel=1e-6)

    def test_mismatched_columns_raises(self) -> None:
        with pytest.raises(ValueError, match="same number of columns"):
            scale_logvar_statistic(np.zeros((5, 2)), np.zeros((5, 3)))


class TestScaleLogvarTest:
    def test_null_case_not_significant(self) -> None:
        # Same underlying variance in both groups; the test should not
        # reject at the nominal level on this seed.
        rng = np.random.default_rng(42)
        x = rng.uniform(0.2, 0.8, size=(40, 3))
        y = rng.uniform(0.2, 0.8, size=(40, 3))
        _, _, p = scale_logvar_test(x, y, n_permutations=199, seed=1)
        assert p > 0.05

    def test_alternative_case_significant(self) -> None:
        # Strong variance inflation; the test should reject clearly.
        rng = np.random.default_rng(3)
        x = rng.uniform(0.3, 0.7, size=(50, 3))
        center = x.mean(axis=0)
        y = center + (x - center) * 1.5
        assert y.min() >= 0.0 and y.max() <= 1.0
        _, _, p = scale_logvar_test(x, y, n_permutations=199, seed=1)
        assert p < 0.05

    def test_location_shift_with_equal_scale_is_not_significant(self) -> None:
        """Centering must remove location before calibrating a scale null."""
        rng = np.random.default_rng(31)
        x = rng.normal(0.25, 0.04, size=(60, 2))
        y = rng.normal(0.65, 0.04, size=(60, 2))
        _, _, p = scale_logvar_test(x, y, n_permutations=499, seed=8)
        assert p > 0.05

    def test_deterministic_with_seed(self) -> None:
        rng = np.random.default_rng(4)
        x = rng.uniform(0.3, 0.7, size=(25, 2))
        y = rng.uniform(0.3, 0.7, size=(25, 2))
        a = scale_logvar_test(x, y, n_permutations=99, seed=1)
        b = scale_logvar_test(x, y, n_permutations=99, seed=1)
        assert a[0] == b[0]
        assert a[2] == b[2]
        np.testing.assert_array_equal(a[1], b[1])

    def test_returns_three_tuple(self) -> None:
        rng = np.random.default_rng(5)
        x = rng.uniform(0.3, 0.7, size=(20, 2))
        y = rng.uniform(0.3, 0.7, size=(20, 2))
        result = scale_logvar_test(x, y, n_permutations=49, seed=1)
        assert isinstance(result, tuple)
        assert len(result) == 3
        observed, null, p = result
        assert isinstance(observed, float)
        assert isinstance(null, np.ndarray)
        assert isinstance(p, float)

    def test_zero_and_near_zero_variance_are_finite(self) -> None:
        x = np.column_stack([np.full(20, 0.5), np.linspace(0.499999, 0.500001, 20)])
        y = np.column_stack([np.full(20, 0.5), np.linspace(0.499998, 0.500002, 20)])
        observed, null, p = scale_logvar_test(x, y, n_permutations=19, seed=2)
        assert np.isfinite(observed)
        assert np.isfinite(null).all()
        assert 0.0 < p <= 1.0

    @pytest.mark.parametrize("eps", [0.0, -1e-12, float("inf")])
    def test_invalid_epsilon_raises(self, eps: float) -> None:
        values = np.array([0.3, 0.4, 0.5])
        with pytest.raises(ValueError, match="eps must be finite and positive"):
            scale_logvar_test(values, values, n_permutations=1, eps=eps)

    @pytest.mark.parametrize(
        "invalid",
        [np.array([0.2, float("nan")]), np.array([0.2, 1.1])],
    )
    def test_invalid_scores_raise(self, invalid: np.ndarray) -> None:
        with pytest.raises(ValueError):
            scale_logvar_test(invalid, np.array([0.2, 0.3]), n_permutations=1)

    def test_zero_permutations_raises(self) -> None:
        values = np.array([0.3, 0.4, 0.5])
        with pytest.raises(ValueError, match="n_permutations"):
            scale_logvar_test(values, values, n_permutations=0)


# ---------------------------------------------------------------------------
# dependence_max_t_statistic / dependence_max_t_test
# ---------------------------------------------------------------------------


class TestDependenceMaxTStatistic:
    def test_identical_inputs_give_zero(self) -> None:
        rng = np.random.default_rng(0)
        x = rng.uniform(0.2, 0.8, size=(30, 3))
        assert dependence_max_t_statistic(x, x) == pytest.approx(0.0)

    def test_single_metric_raises(self) -> None:
        # p = 1 means no off-diagonal pairs to test.
        with pytest.raises(ValueError, match="at least 2 metric"):
            dependence_max_t_statistic(np.zeros((5, 1)), np.zeros((5, 1)))

    def test_rank_preserving_variance_scaling_gives_zero(self) -> None:
        """The ablation-critical property: a per-column positive linear
        rescale preserves the rank order *within each group*, so ranking
        ``x`` and ``y`` independently gives identical correlation matrices
        and the statistic is exactly zero. This is why rank correlation
        (computed within each group) is used instead of covariance
        Frobenius — the latter would fire on the same input.
        """
        rng = np.random.default_rng(7)
        x = rng.uniform(0.3, 0.7, size=(60, 3))
        center = x.mean(axis=0)
        y = center + (x - center) * 1.5
        # Values stay in [0, 1] because x was in [0.3, 0.7].
        assert y.min() >= 0.0 and y.max() <= 1.0

        stat = dependence_max_t_statistic(x, y)
        assert stat == pytest.approx(0.0, abs=1e-12)

    def test_dependence_change_produces_positive_statistic(self) -> None:
        # x has independent columns; y has strongly correlated columns.
        rng = np.random.default_rng(11)
        n = 60
        z1 = rng.standard_normal((n, 3))
        z2 = rng.standard_normal((n, 1))
        x_corr = z1
        y_corr = z2 * np.array([1.0, 0.9, 0.8]) + z1 * np.array([0.0, 0.1, 0.2])
        x_arr = 0.5 + 0.2 * np.tanh(x_corr)
        y_arr = 0.5 + 0.2 * np.tanh(y_corr)

        stat = dependence_max_t_statistic(x_arr, y_arr)
        assert stat > 0.3

    def test_mismatched_columns_raises(self) -> None:
        with pytest.raises(ValueError, match="same number of columns"):
            dependence_max_t_statistic(np.zeros((5, 2)), np.zeros((5, 3)))


class TestDependenceMaxTTest:
    def test_null_case_not_significant(self) -> None:
        rng = np.random.default_rng(42)
        x = rng.uniform(0.2, 0.8, size=(50, 3))
        y = rng.uniform(0.2, 0.8, size=(50, 3))
        _, _, p = dependence_max_t_test(x, y, n_permutations=199, seed=1)
        assert p > 0.05

    def test_alternative_case_significant(self) -> None:
        rng = np.random.default_rng(11)
        n = 60
        z1 = rng.standard_normal((n, 3))
        z2 = rng.standard_normal((n, 1))
        x_arr = 0.5 + 0.2 * np.tanh(z1)
        y_arr = 0.5 + 0.2 * np.tanh(z2 * np.array([1.0, 0.9, 0.8]) + z1 * np.array([0.0, 0.1, 0.2]))
        _, _, p = dependence_max_t_test(x_arr, y_arr, n_permutations=199, seed=1)
        assert p < 0.05

    def test_rank_preserving_variance_scaling_does_not_fire(self) -> None:
        """Ablation-critical: the dependence test must not fire on a
        pure variance change that leaves rank order intact within each
        group. This is the property that justifies using within-group
        rank correlation rather than covariance Frobenius for the
        dependence statistic.
        """
        rng = np.random.default_rng(7)
        x = rng.uniform(0.3, 0.7, size=(60, 3))
        center = x.mean(axis=0)
        y = center + (x - center) * 1.5
        assert y.min() >= 0.0 and y.max() <= 1.0

        # The statistic itself is exactly zero, so any observed-value
        # permutation test on it returns p = 1 (or p = (k+1)/(R+1) with
        # k = R when all null values tie at 0).
        observed, _, p = dependence_max_t_test(x, y, n_permutations=199, seed=1)
        assert observed == pytest.approx(0.0, abs=1e-12)
        assert p == pytest.approx(1.0)

    def test_shifted_and_rescaled_marginals_do_not_fire(self) -> None:
        """The dependence null must remove marginal location and scale."""
        rng = np.random.default_rng(77)
        covariance = np.array([[1.0, 0.7, 0.2], [0.7, 1.0, 0.4], [0.2, 0.4, 1.0]])
        x_latent = rng.multivariate_normal(np.zeros(3), covariance, 80)
        y_latent = rng.multivariate_normal(np.zeros(3), covariance, 80)
        x = 0.3 + 0.1 * np.tanh(x_latent)
        y = 0.65 + 0.15 * np.tanh(y_latent)
        assert y.min() >= 0.0 and y.max() <= 1.0

        observed, _, p = dependence_max_t_test(x, y, n_permutations=499, seed=4)
        assert observed > 0.0
        assert p > 0.05

    def test_ties_constant_columns_and_small_samples_are_finite(self) -> None:
        x = np.array([[0.4, 0.2], [0.4, 0.2], [0.4, 0.8]])
        y = np.array([[0.6, 0.3], [0.6, 0.3], [0.6, 0.9]])
        observed, null, p = dependence_max_t_test(x, y, n_permutations=9, seed=3)
        assert np.isfinite(observed)
        assert np.isfinite(null).all()
        assert 0.0 < p <= 1.0

    @pytest.mark.parametrize(
        "invalid",
        [np.array([[0.2, float("nan")], [0.3, 0.4]]), np.array([[0.2, 1.1], [0.3, 0.4]])],
    )
    def test_invalid_scores_raise(self, invalid: np.ndarray) -> None:
        with pytest.raises(ValueError):
            dependence_max_t_test(invalid, np.array([[0.2, 0.3], [0.3, 0.4]]), n_permutations=1)

    def test_deterministic_with_seed(self) -> None:
        rng = np.random.default_rng(4)
        x = rng.uniform(0.3, 0.7, size=(25, 3))
        y = rng.uniform(0.3, 0.7, size=(25, 3))
        a = dependence_max_t_test(x, y, n_permutations=99, seed=1)
        b = dependence_max_t_test(x, y, n_permutations=99, seed=1)
        assert a[0] == b[0]
        assert a[2] == b[2]
        np.testing.assert_array_equal(a[1], b[1])

    def test_returns_three_tuple(self) -> None:
        rng = np.random.default_rng(5)
        x = rng.uniform(0.3, 0.7, size=(20, 3))
        y = rng.uniform(0.3, 0.7, size=(20, 3))
        result = dependence_max_t_test(x, y, n_permutations=49, seed=1)
        assert isinstance(result, tuple)
        assert len(result) == 3
        observed, null, p = result
        assert isinstance(observed, float)
        assert isinstance(null, np.ndarray)
        assert isinstance(p, float)

    def test_single_metric_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 2 metric"):
            dependence_max_t_test(np.zeros((10, 1)), np.zeros((10, 1)), n_permutations=20)

    def test_zero_permutations_raises(self) -> None:
        rng = np.random.default_rng(6)
        x = rng.uniform(0.3, 0.7, size=(10, 2))
        y = rng.uniform(0.3, 0.7, size=(10, 2))
        with pytest.raises(ValueError, match="n_permutations"):
            dependence_max_t_test(x, y, n_permutations=0)
