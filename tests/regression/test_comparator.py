# tests/regression/test_comparator.py
import logging
from uuid import UUID, uuid4

import numpy as np
import pytest
from nirizan.regression.comparator import (
    BaselineComparator,
    RegressionSeverity,
    RegressionVerdict,
    classify_severity,
    cohens_d,
    mean_delta,
)


@pytest.fixture
def sample_ids() -> tuple[UUID, UUID]:
    return uuid4(), uuid4()


# ---------------------------------------------------------------------------
# classify_severity
# ---------------------------------------------------------------------------


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


def test_effect_just_above_warning_threshold_is_none() -> None:
    # -0.19 is smaller in magnitude than the warning threshold of -0.2;
    # a significant but tiny effect must not be classified as a regression.
    severity = classify_severity(
        significant=True,
        effect_size=-0.19,
        warning_effect=-0.2,
        blocking_effect=-0.5,
    )
    assert severity == RegressionSeverity.NONE


def test_effect_at_exactly_blocking_threshold_is_blocking() -> None:
    # The classifier uses <=, so an effect exactly at the threshold counts.
    severity = classify_severity(
        significant=True,
        effect_size=-0.5,
        warning_effect=-0.2,
        blocking_effect=-0.5,
    )
    assert severity == RegressionSeverity.BLOCKING


def test_equal_warning_and_blocking_effect_raises() -> None:
    """``classify_severity`` requires ``blocking_effect`` to be *strictly*
    more negative than ``warning_effect`` (``if blocking_effect >=
    warning_effect: raise ValueError(...)``). Equal thresholds are
    ambiguous (which branch should an effect exactly at that value take?)
    and the function rejects the call outright rather than picking an
    implicit tie-break. This is a distinct boundary from
    ``test_effect_at_exactly_blocking_threshold_is_blocking``, which uses
    two genuinely *different* threshold values and expects a normal
    classification, not an error.
    """
    with pytest.raises(
        ValueError,
        match="blocking_effect must be more negative than warning_effect.",
    ):
        classify_severity(
            significant=True,
            effect_size=-0.5,
            warning_effect=-0.5,
            blocking_effect=-0.5,
        )


# ---------------------------------------------------------------------------
# BaselineComparator.compare
# ---------------------------------------------------------------------------


def test_multiple_metrics_receive_holm_correction(
    sample_ids: tuple[UUID, UUID],
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

    # The strong regression must survive; the marginal one may be
    # corrected away, but nothing should be BLOCKING on the marginal metric.
    by_name = {v.metric_name: v for v in verdicts}
    assert by_name["groundedness"].severity == RegressionSeverity.BLOCKING
    assert by_name["answer_relevance"].severity != RegressionSeverity.BLOCKING


def test_holm_correction_demotes_metric_significant_only_before_correction(
    sample_ids: tuple[UUID, UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deterministic counterpart to ``test_multiple_metrics_receive_holm_
    correction``. That test only asserts the marginal metric isn't
    BLOCKING, which is also true if the metric were simply WARNING and
    Holm correction did nothing at all -- it can't distinguish "corrected
    away" from "was never significant enough to matter".

    This test pins the exact p-values via mocking so the demotion is
    unambiguous: with two metrics at alpha=0.05, Holm's rank-1 threshold
    is alpha/2=0.025. A metric with p=0.04 is significant under the naive
    p < alpha check (0.04 < 0.05) -- so its raw per-metric severity is
    WARNING -- but fails the stricter Holm rank-1 threshold (0.04 >
    0.025), so the family-wise correction step must demote it to NONE and
    record that in its explanation. The second metric (p=0.06) is not
    naively significant either way, so its verdict must be left untouched.
    """
    baseline_id, run_id = sample_ids
    comparator = BaselineComparator(alpha=0.05, warning_effect=-0.2, blocking_effect=-0.5)

    # metric_a is processed first (metric_names are sorted alphabetically
    # inside BaselineComparator.compare), so the first value each iterator
    # yields corresponds to metric_a and the second to metric_b.
    p_values_by_call = iter([0.04, 0.06])
    effects_by_call = iter([-0.3, -0.3])

    def fake_mann_whitney_regression(
        candidate: np.ndarray, baseline: np.ndarray
    ) -> tuple[float, float]:
        return 0.0, next(p_values_by_call)

    def fake_cohens_d(candidate: np.ndarray, baseline: np.ndarray) -> float:
        return next(effects_by_call)

    monkeypatch.setattr(
        "nirizan.regression.comparator.mann_whitney_regression",
        fake_mann_whitney_regression,
    )
    monkeypatch.setattr("nirizan.regression.comparator.cohens_d", fake_cohens_d)

    candidate_scores = {
        "metric_a": np.array([0.3, 0.3, 0.3, 0.3, 0.3]),
        "metric_b": np.array([0.3, 0.3, 0.3, 0.3, 0.3]),
    }
    baseline_scores = {
        "metric_a": np.array([0.3, 0.3, 0.3, 0.3, 0.3]),
        "metric_b": np.array([0.3, 0.3, 0.3, 0.3, 0.3]),
    }

    verdicts = comparator.compare(
        candidate_scores=candidate_scores,
        baseline_scores=baseline_scores,
        baseline_id=baseline_id,
        run_id=run_id,
    )
    by_name = {v.metric_name: v for v in verdicts}

    # metric_a was WARNING pre-correction (p=0.04 < alpha, effect -0.3)
    # but must be demoted to NONE once Holm's stricter rank-1 threshold
    # (0.025) is applied, with the demotion recorded in the explanation.
    assert by_name["metric_a"].severity == RegressionSeverity.NONE
    assert by_name["metric_a"].p_value == pytest.approx(0.04)
    assert "not significant after" in by_name["metric_a"].explanation
    assert "Holm-Bonferroni correction" in by_name["metric_a"].explanation

    # metric_b was never significant under the naive per-metric check
    # (p=0.06 >= alpha), so it must be untouched by the correction step:
    # NONE, but without the correction annotation appended.
    assert by_name["metric_b"].severity == RegressionSeverity.NONE
    assert by_name["metric_b"].p_value == pytest.approx(0.06)
    assert "Holm-Bonferroni correction" not in by_name["metric_b"].explanation


def test_compare_raises_on_missing_metric(
    sample_ids: tuple[UUID, UUID],
) -> None:
    baseline_id, run_id = sample_ids
    comparator = BaselineComparator()

    candidate_scores = {"a": np.array([0.1, 0.2, 0.3, 0.4, 0.5])}
    baseline_scores = {
        "a": np.array([0.1, 0.2, 0.3, 0.4, 0.5]),
        "b": np.array([0.1, 0.2, 0.3, 0.4, 0.5]),
    }

    # candidate_scores is missing "b" (present in baseline_scores). Metric
    # names are iterated in sorted order ("a", then "b"); "a" is present on
    # both sides, so the first raise happens on "b".
    with pytest.raises(ValueError, match="Candidate is missing metric: b"):
        comparator.compare(
            candidate_scores=candidate_scores,
            baseline_scores=baseline_scores,
            baseline_id=baseline_id,
            run_id=run_id,
        )

    # Swapped: now "baseline_scores" (the old candidate_scores, {"a"}) is
    # missing "b", which is present in the new "candidate_scores" (the old
    # baseline_scores, {"a", "b"}). Sorted iteration hits "a" first (present
    # on both sides), then "b": present in candidate, missing from baseline.
    with pytest.raises(ValueError, match="Baseline is missing metric: b"):
        comparator.compare(
            candidate_scores=baseline_scores,
            baseline_scores=candidate_scores,
            baseline_id=baseline_id,
            run_id=run_id,
        )


def test_compare_with_no_metrics_returns_empty_list(
    sample_ids: tuple[UUID, UUID],
) -> None:
    """Neither dict has any keys, so ``metric_names`` is empty and the
    per-metric loop never runs. This must resolve cleanly to an empty
    verdict list rather than raising or behaving in some other implicit,
    previously-unverified way.
    """
    baseline_id, run_id = sample_ids
    comparator = BaselineComparator()

    verdicts = comparator.compare(
        candidate_scores={},
        baseline_scores={},
        baseline_id=baseline_id,
        run_id=run_id,
    )
    assert verdicts == []


# ---------------------------------------------------------------------------
# BaselineComparator.compare_metric
# ---------------------------------------------------------------------------


def test_comparator_returns_nirizan_regression_verdict(
    sample_ids: tuple[UUID, UUID],
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
    sample_ids: tuple[UUID, UUID],
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


def test_compare_metric_populates_effect_size_and_explanation(
    sample_ids: tuple[UUID, UUID],
) -> None:
    baseline_id, run_id = sample_ids
    comparator = BaselineComparator()

    candidate = np.array([0.2, 0.25, 0.21, 0.23, 0.22, 0.24])
    baseline = np.array([0.8, 0.85, 0.82, 0.84, 0.83, 0.86])

    verdict = comparator.compare_metric(
        metric_name="safety_score",
        candidate=candidate,
        baseline=baseline,
        baseline_id=baseline_id,
        run_id=run_id,
    )

    assert verdict.effect_size is not None
    assert verdict.effect_size < 0.0
    assert verdict.p_value is not None
    assert "Cohen's d" in verdict.explanation


# ---------------------------------------------------------------------------
# cohens_d — re-export contract
# ---------------------------------------------------------------------------


def test_cohens_d_is_the_stats_module_version() -> None:
    """Regression guard: ``comparator.cohens_d`` must be the canonical
    ``metrics.stats.cohens_d``, not a local reimplementation. The
    consolidation moved this function out of ``comparator.py``; this test
    fails immediately if a future change reintroduces a local definition
    (silently diverging the two) instead of importing.
    """
    from nirizan.metrics.stats import cohens_d as canonical

    assert cohens_d is canonical


def test_cohens_d_reexport_behaves_correctly() -> None:
    """The re-exported callable must still produce the zero-variance
    result the old local implementation produced."""
    candidate = np.array([0.5, 0.5, 0.5])
    baseline = np.array([0.5, 0.5, 0.5])
    assert cohens_d(candidate, baseline) == 0.0


# ---------------------------------------------------------------------------
# mean_delta
# ---------------------------------------------------------------------------


def test_mean_delta_positive_when_candidate_higher() -> None:
    candidate = np.array([0.6, 0.7, 0.8])
    baseline = np.array([0.2, 0.3, 0.4])
    assert mean_delta(candidate, baseline) == pytest.approx(0.4)


def test_mean_delta_negative_when_candidate_lower() -> None:
    candidate = np.array([0.2, 0.3, 0.4])
    baseline = np.array([0.6, 0.7, 0.8])
    assert mean_delta(candidate, baseline) == pytest.approx(-0.4)


def test_mean_delta_zero_when_equal_means() -> None:
    candidate = np.array([0.5, 0.5, 0.5])
    baseline = np.array([0.5, 0.5, 0.5])
    assert mean_delta(candidate, baseline) == 0.0


# ---------------------------------------------------------------------------
# Package-level exports
# ---------------------------------------------------------------------------


def test_regression_package_exports_expected_names() -> None:
    """``nirizan.regression`` must continue to export the public surface
    documented in the package docstring, including ``cohens_d`` which
    now routes through ``comparator`` from ``metrics.stats``.
    """
    import nirizan.regression as regression

    expected = {
        "BaselineComparator",
        "RegressionSeverity",
        "RegressionVerdict",
        "classify_severity",
        "cohens_d",
        "mean_delta",
    }
    missing = expected - set(regression.__all__)
    assert not missing, f"Missing from regression.__all__: {sorted(missing)}"

    for name in expected:
        assert hasattr(regression, name), f"regression.{name} is not importable"


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


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


def test_default_comparator_uses_documented_threshold_constants(
    sample_ids: tuple[UUID, UUID],
) -> None:
    """Regression guard: ``BaselineComparator``'s defaults must match the
    module-level ``DEFAULT_ALPHA`` / ``DEFAULT_WARNING_EFFECT`` /
    ``DEFAULT_BLOCKING_EFFECT`` constants from ``thresholds.py``, not a
    locally hardcoded value that could silently drift out of sync with the
    single source of truth for those thresholds.
    """
    from nirizan.regression.thresholds import (
        DEFAULT_ALPHA,
        DEFAULT_BLOCKING_EFFECT,
        DEFAULT_WARNING_EFFECT,
    )

    comparator = BaselineComparator()
    assert comparator.alpha == DEFAULT_ALPHA
    assert comparator.warning_effect == DEFAULT_WARNING_EFFECT
    assert comparator.blocking_effect == DEFAULT_BLOCKING_EFFECT
