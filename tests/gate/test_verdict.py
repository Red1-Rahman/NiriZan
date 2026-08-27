# tests/gate/test_verdict.py
from __future__ import annotations

import logging
from uuid import uuid4

import numpy as np
import pytest

from nirizan.gate.verdict import (
    bootstrap_delta_ci,
    evaluate_gate,
    select_decision_metric,
)
from nirizan.regression.comparator import (
    RegressionSeverity,
    RegressionVerdict,
)


@pytest.fixture
def sample_verdict_none() -> RegressionVerdict:
    return RegressionVerdict(
        metric_name="groundedness",
        severity=RegressionSeverity.NONE,
        p_value=0.5,
        effect_size=-0.01,
        baseline_id=uuid4(),
        run_id=uuid4(),
        explanation="No regression",
    )


@pytest.fixture
def sample_verdict_warning() -> RegressionVerdict:
    return RegressionVerdict(
        metric_name="context_relevance",
        severity=RegressionSeverity.WARNING,
        p_value=0.03,
        effect_size=-0.25,
        baseline_id=uuid4(),
        run_id=uuid4(),
        explanation="Warning regression",
    )


@pytest.fixture
def sample_verdict_blocking() -> RegressionVerdict:
    return RegressionVerdict(
        metric_name="answer_relevance",
        severity=RegressionSeverity.BLOCKING,
        p_value=0.001,
        effect_size=-0.75,
        baseline_id=uuid4(),
        run_id=uuid4(),
        explanation="Blocking regression",
    )


def test_blocking_regression_fails_gate(
    sample_verdict_none: RegressionVerdict,
    sample_verdict_blocking: RegressionVerdict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    scores = {
        "groundedness": (np.array([0.9, 0.85]), np.array([0.91, 0.87])),
        "answer_relevance": (np.array([0.4, 0.5]), np.array([0.9, 0.88])),
    }
    verdicts = [sample_verdict_none, sample_verdict_blocking]

    with caplog.at_level(logging.INFO):
        result = evaluate_gate(verdicts=verdicts, scores_by_metric=scores)

    assert result.passed is False
    assert "Gate evaluation result: BLOCKED" in caplog.text
    assert "1 blocking regression(s)" in caplog.text


def test_warning_regression_passes_gate(
    sample_verdict_none: RegressionVerdict,
    sample_verdict_warning: RegressionVerdict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    scores = {
        "groundedness": (np.array([0.9, 0.85]), np.array([0.91, 0.87])),
        "context_relevance": (
            np.array([0.7, 0.75]),
            np.array([0.85, 0.88]),
        ),
    }
    verdicts = [sample_verdict_none, sample_verdict_warning]

    with caplog.at_level(logging.INFO):
        result = evaluate_gate(verdicts=verdicts, scores_by_metric=scores)

    assert result.passed is True
    assert "Gate evaluation result: PASSED" in caplog.text


def test_decision_metric_prefers_blocking_regression(
    sample_verdict_none: RegressionVerdict,
    sample_verdict_warning: RegressionVerdict,
    sample_verdict_blocking: RegressionVerdict,
) -> None:
    verdicts = [
        sample_verdict_none,
        sample_verdict_warning,
        sample_verdict_blocking,
    ]
    selected = select_decision_metric(verdicts)

    assert selected.metric_name == "answer_relevance"
    assert selected.severity == RegressionSeverity.BLOCKING


def test_decision_metric_breaks_ties_with_effect_size(
    sample_verdict_blocking: RegressionVerdict,
) -> None:
    b_id = uuid4()
    r_id = uuid4()
    more_severe_blocking = RegressionVerdict(
        metric_name="latency_penalty",
        severity=RegressionSeverity.BLOCKING,
        p_value=0.0001,
        effect_size=-0.95,
        baseline_id=b_id,
        run_id=r_id,
        explanation="Larger effect size",
    )
    verdicts = [sample_verdict_blocking, more_severe_blocking]
    selected = select_decision_metric(verdicts)

    assert selected.metric_name == "latency_penalty"


def test_gate_contains_bootstrap_confidence_interval(
    sample_verdict_none: RegressionVerdict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    scores = {
        "groundedness": (
            np.array([0.8, 0.82, 0.81, 0.83]),
            np.array([0.81, 0.80, 0.82, 0.84]),
        )
    }

    with caplog.at_level(logging.DEBUG):
        result = evaluate_gate(
            verdicts=[sample_verdict_none],
            scores_by_metric=scores,
        )

    assert len(result.confidence_interval) == 2
    assert result.confidence_interval[0] <= result.confidence_interval[1]
    assert "Computing bootstrap delta CI" in caplog.text
    assert "Bootstrap CI computed:" in caplog.text


def test_bootstrap_delta_ci_validation() -> None:
    with pytest.raises(
        ValueError, match="Both distributions must contain observations."
    ):
        bootstrap_delta_ci(np.array([]), np.array([1.0]))

    with pytest.raises(ValueError, match="n_bootstrap must be positive."):
        bootstrap_delta_ci(np.array([1.0]), np.array([1.0]), n_bootstrap=0)

    with pytest.raises(
        ValueError, match="confidence must be between 0 and 1."
    ):
        bootstrap_delta_ci(np.array([1.0]), np.array([1.0]), confidence=1.5)
