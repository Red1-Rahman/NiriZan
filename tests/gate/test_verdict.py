# tests/gate/test_verdict.py
from __future__ import annotations

import logging
from uuid import UUID, uuid4

import numpy as np
import pytest

from nirizan.gate.verdict import (
    bootstrap_delta_ci,
    evaluate_gate,
    select_decision_metric,
)
from nirizan.metrics.stats import bootstrap_delta_ci as stats_bootstrap_delta_ci
from nirizan.regression.comparator import (
    RegressionSeverity,
    RegressionVerdict,
)
from nirizan.regression.multivariate import (
    MultivariateMethod,
    MultivariateVerdict,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


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


def _multivariate_verdict(
    severity: RegressionSeverity,
    *,
    method: MultivariateMethod = MultivariateMethod.SCALE,
    baseline_id: UUID | None = None,
    run_id: UUID | None = None,
    p_value: float = 0.5,
    effect_size: float = 0.0,
    inconclusive: bool = False,
) -> MultivariateVerdict:
    return MultivariateVerdict(
        method=method,
        severity=severity,
        p_value=p_value,
        statistic=0.0,
        effect_size=effect_size,
        baseline_id=baseline_id or uuid4(),
        run_id=run_id or uuid4(),
        explanation="test",
        inconclusive=inconclusive,
    )


# ---------------------------------------------------------------------------
# Univariate gate behaviour (existing, unchanged in spirit)
# ---------------------------------------------------------------------------


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
    assert "1 univariate blocking, 0 multivariate blocking" in caplog.text


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
    with pytest.raises(ValueError, match="Both distributions must contain observations."):
        bootstrap_delta_ci(np.array([]), np.array([1.0]))

    with pytest.raises(ValueError, match="n_bootstrap must be positive."):
        bootstrap_delta_ci(np.array([1.0]), np.array([1.0]), n_bootstrap=0)

    with pytest.raises(ValueError, match="confidence must be between 0 and 1."):
        bootstrap_delta_ci(np.array([1.0]), np.array([1.0]), confidence=1.5)


# ---------------------------------------------------------------------------
# Multivariate verdicts on the gate
# ---------------------------------------------------------------------------


def test_gate_backward_compatible_when_multivariate_verdicts_omitted(
    sample_verdict_none: RegressionVerdict,
) -> None:
    """Omitting the new argument must reproduce the pre-multivariate behavior
    exactly: ``passed=True`` for a single NONE verdict, and an empty list
    on the GateVerdict.
    """
    scores = {
        "groundedness": (np.array([0.9, 0.85]), np.array([0.91, 0.87])),
    }

    result = evaluate_gate(verdicts=[sample_verdict_none], scores_by_metric=scores)

    assert result.passed is True
    assert result.multivariate_verdicts == []


def test_gate_backward_compatible_when_multivariate_verdicts_none(
    sample_verdict_none: RegressionVerdict,
) -> None:
    """Explicit ``None`` is treated the same as omitted."""
    scores = {
        "groundedness": (np.array([0.9, 0.85]), np.array([0.91, 0.87])),
    }

    result = evaluate_gate(
        verdicts=[sample_verdict_none],
        scores_by_metric=scores,
        multivariate_verdicts=None,
    )

    assert result.passed is True
    assert result.multivariate_verdicts == []


def test_gate_fails_on_multivariate_blocking(
    sample_verdict_none: RegressionVerdict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A BLOCKING multivariate verdict flips ``passed`` to False even when
    every univariate verdict is NONE.
    """
    scores = {
        "groundedness": (np.array([0.9, 0.85]), np.array([0.91, 0.87])),
    }
    mv_blocking = _multivariate_verdict(RegressionSeverity.BLOCKING)

    with caplog.at_level(logging.WARNING):
        result = evaluate_gate(
            verdicts=[sample_verdict_none],
            scores_by_metric=scores,
            multivariate_verdicts=[mv_blocking],
        )

    assert result.passed is False
    assert "1 univariate blocking, 1 multivariate blocking" in caplog.text
    assert result.multivariate_verdicts == [mv_blocking]


def test_gate_passes_on_multivariate_warning(
    sample_verdict_none: RegressionVerdict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A multivariate WARNING does not flip ``passed``; warnings are
    informational, not blocking.
    """
    scores = {
        "groundedness": (np.array([0.9, 0.85]), np.array([0.91, 0.87])),
    }
    mv_warning = _multivariate_verdict(RegressionSeverity.WARNING, p_value=0.01)

    with caplog.at_level(logging.INFO):
        result = evaluate_gate(
            verdicts=[sample_verdict_none],
            scores_by_metric=scores,
            multivariate_verdicts=[mv_warning],
        )

    assert result.passed is True
    assert "Gate evaluation result: PASSED" in caplog.text
    assert result.multivariate_verdicts == [mv_warning]


def test_gate_carries_multivariate_verdicts_through(
    sample_verdict_none: RegressionVerdict,
) -> None:
    """Every passed-in multivariate verdict must appear on the returned
    GateVerdict, in order, unmodified. This is the contract Reporting
    relies on for the structure table.
    """
    scores = {
        "groundedness": (np.array([0.9, 0.85]), np.array([0.91, 0.87])),
    }
    mv_scale = _multivariate_verdict(RegressionSeverity.WARNING, method=MultivariateMethod.SCALE)
    mv_dependence = _multivariate_verdict(
        RegressionSeverity.NONE, method=MultivariateMethod.DEPENDENCE
    )

    result = evaluate_gate(
        verdicts=[sample_verdict_none],
        scores_by_metric=scores,
        multivariate_verdicts=[mv_scale, mv_dependence],
    )

    assert result.multivariate_verdicts == [mv_scale, mv_dependence]
    assert result.multivariate_verdicts[0].method == MultivariateMethod.SCALE
    assert result.multivariate_verdicts[1].method == MultivariateMethod.DEPENDENCE


def test_gate_ignores_inconclusive_multivariate_verdicts(
    sample_verdict_none: RegressionVerdict,
) -> None:
    """An INCONCLUSIVE multivariate verdict carries severity=NONE and
    must not flip ``passed``. INCONCLUSIVE means "the structure test
    could not run", not "a structure regression was detected."
    """
    scores = {
        "groundedness": (np.array([0.9, 0.85]), np.array([0.91, 0.87])),
    }
    mv_inconclusive = _multivariate_verdict(RegressionSeverity.NONE, inconclusive=True)

    result = evaluate_gate(
        verdicts=[sample_verdict_none],
        scores_by_metric=scores,
        multivariate_verdicts=[mv_inconclusive],
    )

    assert result.passed is True
    assert result.multivariate_verdicts == [mv_inconclusive]
    assert result.multivariate_verdicts[0].inconclusive is True


def test_gate_fails_when_both_tracks_block(
    sample_verdict_blocking: RegressionVerdict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When both tracks block, the log line reports both counts."""
    scores = {
        "answer_relevance": (np.array([0.4, 0.5]), np.array([0.9, 0.88])),
    }
    mv_blocking = _multivariate_verdict(RegressionSeverity.BLOCKING)

    with caplog.at_level(logging.WARNING):
        result = evaluate_gate(
            verdicts=[sample_verdict_blocking],
            scores_by_metric=scores,
            multivariate_verdicts=[mv_blocking],
        )

    assert result.passed is False
    assert "1 univariate blocking, 1 multivariate blocking" in caplog.text


def test_select_decision_metric_is_univariate_only(
    sample_verdict_blocking: RegressionVerdict,
) -> None:
    """Regression guard: ``select_decision_metric`` must be called with
    univariate verdicts only. Multivariate verdicts lack ``metric_name``
    and the downstream ``scores_by_metric`` lookup would raise KeyError,
    so the decision function's contract excludes them by design. This
    test documents that a univariate verdict alone is what the function
    expects.
    """
    selected = select_decision_metric([sample_verdict_blocking])
    assert selected.metric_name == "answer_relevance"


# ---------------------------------------------------------------------------
# Shim consistency with stats.bootstrap_delta_ci
# ---------------------------------------------------------------------------


def test_bootstrap_delta_ci_shim_matches_stats_canonical() -> None:
    """The gate's 2-tuple shim must produce the same interval as the
    canonical 3-tuple ``stats.bootstrap_delta_ci`` for the same seed and
    inputs. This is what makes the shim a genuine delegation rather than
    an independent reimplementation.
    """
    candidate = np.array([0.4, 0.5, 0.6, 0.5, 0.4])
    baseline = np.array([0.7, 0.8, 0.9, 0.8, 0.7])

    _, stats_low, stats_high = stats_bootstrap_delta_ci(
        candidate, baseline, n_bootstrap=200, confidence_level=0.95, seed=7
    )
    shim_low, shim_high = bootstrap_delta_ci(
        candidate, baseline, n_bootstrap=200, confidence=0.95, seed=7
    )

    assert shim_low == pytest.approx(stats_low)
    assert shim_high == pytest.approx(stats_high)


def test_bootstrap_delta_ci_shim_returns_two_tuple() -> None:
    """Shape contract: the shim returns exactly ``(ci_low, ci_high)``,
    not the 3-tuple that ``stats.bootstrap_delta_ci`` returns. Callers
    of the gate API rely on this shape.
    """
    candidate = np.array([0.4, 0.5, 0.6, 0.5, 0.4])
    baseline = np.array([0.7, 0.8, 0.9, 0.8, 0.7])
    result = bootstrap_delta_ci(candidate, baseline, n_bootstrap=200, seed=1)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert result[0] <= result[1]
