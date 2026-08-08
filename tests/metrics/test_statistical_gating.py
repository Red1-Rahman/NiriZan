# tests/metrics/test_statistical_gating.py
import logging

import numpy as np
import pytest

from nirizan.metrics.statistical_gating import (
    approximate_sample_size,
    bootstrap_delta_ci,
    calibrate_gold_set,
    holm_bonferroni,
    mann_whitney_regression,
    validate_scores,
)


def test_validate_scores(caplog: pytest.LogCaptureFixture) -> None:
    valid = np.array([0.1, 0.5, 0.9])
    with caplog.at_level(logging.DEBUG):
        res = validate_scores(valid)
    assert np.array_equal(res, valid)
    assert "Successfully validated 3 score observations" in caplog.text

    with pytest.raises(ValueError, match="Score distribution is empty"):
        validate_scores(np.array([]))

    with pytest.raises(ValueError, match="non-finite values"):
        validate_scores(np.array([0.5, np.nan, 0.9]))

    with pytest.raises(ValueError, match="normalized to \\[0, 1\\]"):
        validate_scores(np.array([-0.1, 0.5]))


def test_mann_whitney_regression(caplog: pytest.LogCaptureFixture) -> None:
    baseline = np.array([0.9, 0.92, 0.89, 0.91, 0.88])
    candidate = np.array([0.6, 0.62, 0.59, 0.61, 0.58])

    with caplog.at_level(logging.INFO):
        stat, p_val = mann_whitney_regression(candidate, baseline)

    assert p_val < 0.05
    assert stat >= 0.0
    assert "Mann-Whitney U test computed" in caplog.text

    with pytest.raises(ValueError, match="At least five observations are required"):
        mann_whitney_regression(candidate[:3], baseline)


def test_bootstrap_ci(caplog: pytest.LogCaptureFixture) -> None:
    baseline = np.array([0.9, 0.92, 0.89, 0.91, 0.88])
    candidate = np.array([0.9, 0.91, 0.89, 0.90, 0.88])

    with caplog.at_level(logging.INFO):
        ci_low, ci_high = bootstrap_delta_ci(candidate, baseline, n_bootstrap=500)

    assert ci_low <= ci_high
    assert "Bootstrap delta CI computed" in caplog.text

    with pytest.raises(ValueError, match="confidence must be between 0 and 1"):
        bootstrap_delta_ci(candidate, baseline, confidence=1.5)


def test_holm_bonferroni(caplog: pytest.LogCaptureFixture) -> None:
    p_vals = {"m1": 0.001, "m2": 0.04, "m3": 0.20}

    with caplog.at_level(logging.INFO):
        res = holm_bonferroni(p_vals, alpha=0.05)

    assert res["m1"] is True
    assert res["m3"] is False
    assert "Applying Holm-Bonferroni correction for 3 hypotheses" in caplog.text

    assert holm_bonferroni({}) == {}

    with pytest.raises(ValueError, match="alpha must be between 0 and 1"):
        holm_bonferroni(p_vals, alpha=2.0)


def test_sample_size_and_calibration(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        n = approximate_sample_size(baseline_std=0.02, target_delta=0.03)

    assert n > 0
    assert "Approximated required sample size per group" in caplog.text

    with pytest.raises(ValueError, match="baseline_std must be positive"):
        approximate_sample_size(baseline_std=-0.01, target_delta=0.03)

    with pytest.raises(ValueError, match="target_delta must be positive"):
        approximate_sample_size(baseline_std=0.02, target_delta=0.0)

    with pytest.raises(ValueError, match="alpha must be between 0 and 1"):
        approximate_sample_size(baseline_std=0.02, target_delta=0.03, alpha=1.0)

    with pytest.raises(ValueError, match="power must be between 0 and 1"):
        approximate_sample_size(baseline_std=0.02, target_delta=0.03, power=0.0)

    with caplog.at_level(logging.INFO):
        cal = calibrate_gold_set(np.array([0.8, 0.9]), np.array([0.85, 0.95]))

    assert pytest.approx(cal["mae"], 0.01) == 0.05
    assert "Gold set calibration computed across 2 samples" in caplog.text

    with pytest.raises(ValueError, match="same shape"):
        calibrate_gold_set(np.array([0.8]), np.array([0.85, 0.95]))
