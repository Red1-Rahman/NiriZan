# tests/regression/test_comparator.py
import logging
from uuid import uuid4

import numpy as np
import pytest
from nirizan.regression.comparator import (
    BaselineComparator,
    RegressionSeverity,
    RegressionVerdict,
    classify_severity,
    cohens_d,
)


@pytest.fixture
def sample_ids() -> tuple[uuid4, uuid4]:
    return uuid4(), uuid4()


def test_severe_negative_effect_is_blocking() -> None:
    severity = classify_severity(
        significant=True,
        effect_size=-0.8,
        warning_effect=-0.2,
        blocking_effect=-0.5,
    )
    assert severity == RegressionSeverity.BLOCKING


def test_moderate_negative_effect_is_warning() -> None:
    severity = classify_severity(
        significant=True,
        effect_size=-0.35,
        warning_effect=-0.2,
        blocking_effect=-0.5,
    )
    assert severity == RegressionSeverity.WARNING


def test_non_significant_change_is_none() -> None:
    severity = classify_severity(
        significant=False,
        effect_size=-0.9,
        warning_effect=-0.2,
        blocking_effect=-0.5,
    )
    assert severity == RegressionSeverity.NONE


def test_multiple_metrics_receive_holm_correction(
    sample_ids: tuple[uuid4, uuid4],
    caplog: pytest.LogCaptureFixture,
) -> None:
    baseline_id, run_id = sample_ids
    comparator = BaselineComparator(alpha=0.05)

    rng = np.random.default_rng(42)

    # Metric 1: Strong regression
    candidate_1 = rng.normal(loc=0.3, scale=0.1, size=50)
    baseline_1 = rng.normal(loc=0.8, scale=0.1, size=50)

    # Metric 2: Marginal regression that should be corrected away
    candidate_2 = rng.normal(loc=0.48, scale=0.1, size=30)
    baseline_2 = rng.normal(loc=0.52, scale=0.1, size=30)

    candidate_scores = {
        "groundedness": candidate_1,
        "answer_relevance": candidate_2,
    }
    baseline_scores = {
        "groundedness": baseline_1,
        "answer_relevance": baseline_2,
    }

    with caplog.at_level(logging.INFO):
        verdicts = comparator.compare(
            candidate_scores=candidate_scores,
            baseline_scores=baseline_scores,
            baseline_id=baseline_id,
            run_id=run_id,
        )

    assert len(verdicts) == 2
    assert "Comparing 2 metric(s)" in caplog.text
    assert "Baseline comparison complete" in caplog.text


def test_comparator_returns_nirizan_regression_verdict(
    sample_ids: tuple[uuid4, uuid4],
    caplog: pytest.LogCaptureFixture,
) -> None:
    baseline_id, run_id = sample_ids
    comparator = BaselineComparator()

    candidate = np.array([0.9, 0.85, 0.88, 0.92, 0.89])
    baseline = np.array([0.91, 0.87, 0.90, 0.93, 0.88])

    with caplog.at_level(logging.DEBUG):
        verdict = comparator.compare_metric(
            metric_name="groundedness",
            candidate=candidate,
            baseline=baseline,
            baseline_id=baseline_id,
            run_id=run_id,
        )

    assert isinstance(verdict, RegressionVerdict)
    assert verdict.metric_name == "groundedness"
    assert verdict.baseline_id == baseline_id
    assert verdict.run_id == run_id
    assert "Comparing metric 'groundedness'" in caplog.text


def test_blocking_regression_logging(
    sample_ids: tuple[uuid4, uuid4],
    caplog: pytest.LogCaptureFixture,
) -> None:
    baseline_id, run_id = sample_ids
    comparator = BaselineComparator(
        alpha=0.05,
        warning_effect=-0.2,
        blocking_effect=-0.5,
    )

    candidate = np.array([0.2, 0.25, 0.21, 0.23, 0.22, 0.24])
    baseline = np.array([0.8, 0.85, 0.82, 0.84, 0.83, 0.86])

    with caplog.at_level(logging.WARNING):
        verdict = comparator.compare_metric(
            metric_name="safety_score",
            candidate=candidate,
            baseline=baseline,
            baseline_id=baseline_id,
            run_id=run_id,
        )

    assert verdict.severity == RegressionSeverity.BLOCKING
    assert "Blocking regression detected on metric 'safety_score'" in caplog.text


def test_cohens_d_zero_variance() -> None:
    candidate = np.array([1.0, 1.0, 1.0])
    baseline = np.array([1.0, 1.0, 1.0])
    assert cohens_d(candidate, baseline) == 0.0


def test_invalid_comparator_params() -> None:
    with pytest.raises(ValueError, match="alpha must be between 0 and 1."):
        BaselineComparator(alpha=1.5)

    with pytest.raises(ValueError, match="warning_effect must be negative."):
        classify_severity(
            significant=True,
            effect_size=-0.5,
            warning_effect=0.1,
            blocking_effect=-0.5,
        )

    with pytest.raises(
        ValueError,
        match="blocking_effect must be more negative than warning_effect.",
    ):
        classify_severity(
            significant=True,
            effect_size=-0.5,
            warning_effect=-0.5,
            blocking_effect=-0.2,
        )
