# tests/regression/test_thresholds.py
from __future__ import annotations

import logging

import numpy as np
import pytest

from nirizan.regression.thresholds import (
    holm_bonferroni,
    mann_whitney_regression,
    validate_scores,
)


def test_mann_whitney_detects_lower_candidate_distribution(caplog: pytest.LogCaptureFixture) -> None:
    rng = np.random.default_rng(42)
    candidate = rng.normal(loc=0.3, scale=0.05, size=50).clip(0.0, 1.0)
    baseline = rng.normal(loc=0.8, scale=0.05, size=50).clip(0.0, 1.0)

    with caplog.at_level(logging.INFO):
        stat, p_val = mann_whitney_regression(candidate, baseline)

    assert p_val < 0.001
    assert stat >= 0.0
    assert "Mann-Whitney U test computed" in caplog.text

    with pytest.raises(ValueError, match="Both distributions must contain observations"):
        mann_whitney_regression(np.array([]), baseline)


def test_holm_bonferroni_controls_metric_family(caplog: pytest.LogCaptureFixture) -> None:
    p_values = {
        "metric_a": 0.001,
        "metric_b": 0.02,
        "metric_c": 0.04,
        "metric_d": 0.20,
    }

    with caplog.at_level(logging.DEBUG):
        result = holm_bonferroni(p_values, alpha=0.05)

    assert result["metric_a"] is True
    assert result["metric_b"] is False
    assert result["metric_c"] is False
    assert result["metric_d"] is False

    assert "Applying Holm-Bonferroni correction for 4 hypotheses" in caplog.text

    assert holm_bonferroni({}) == {}

    with pytest.raises(ValueError, match="alpha must be between 0 and 1"):
        holm_bonferroni(p_values, alpha=1.5)


def test_invalid_scores_are_rejected(caplog: pytest.LogCaptureFixture) -> None:
    valid = np.array([0.1, 0.5, 0.9])
    with caplog.at_level(logging.DEBUG):
        validate_scores(valid)
    assert "Successfully validated 3 score observations" in caplog.text

    with pytest.raises(ValueError, match="Scores must be one-dimensional"):
        validate_scores(np.array([[0.5], [0.5]]))

    with pytest.raises(ValueError, match="Score distribution is empty"):
        validate_scores(np.array([]))

    with pytest.raises(ValueError, match="non-finite values"):
        validate_scores(np.array([0.5, np.nan, 0.8]))

    with pytest.raises(ValueError, match="normalized to \\[0, 1\\]"):
        validate_scores(np.array([-0.1, 0.5]))

    with pytest.raises(ValueError, match="normalized to \\[0, 1\\]"):
        validate_scores(np.array([0.5, 1.2]))
