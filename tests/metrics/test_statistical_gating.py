# tests/metrics/test_statistical_gating.py
import numpy as np
import pytest
from nirizan.metrics.statistical_gating import (
    approximate_sample_size,
    bootstrap_delta_ci,
    calibrate_gold_set,
    holm_bonferroni,
    mann_whitney_regression,
)


def test_mann_whitney_regression():
    baseline = np.array([0.9, 0.92, 0.89, 0.91, 0.88])
    candidate = np.array([0.6, 0.62, 0.59, 0.61, 0.58])
    stat, p_val = mann_whitney_regression(candidate, baseline)
    assert p_val < 0.05


def test_bootstrap_ci():
    baseline = np.array([0.9, 0.92, 0.89, 0.91, 0.88])
    candidate = np.array([0.9, 0.91, 0.89, 0.90, 0.88])
    ci_low, ci_high = bootstrap_delta_ci(candidate, baseline, n_bootstrap=500)
    assert ci_low <= ci_high


def test_holm_bonferroni():
    p_vals = {"m1": 0.001, "m2": 0.04, "m3": 0.20}
    res = holm_bonferroni(p_vals, alpha=0.05)
    assert res["m1"] is True
    assert res["m3"] is False


def test_sample_size_and_calibration():
    n = approximate_sample_size(baseline_std=0.02, target_delta=0.03)
    assert n > 0

    cal = calibrate_gold_set(np.array([0.8, 0.9]), np.array([0.85, 0.95]))
    assert pytest.approx(cal["mae"], 0.01) == 0.05
