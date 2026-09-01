# tests/trust/test_attribution.py
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import numpy as np
import pytest

from nirizan.trust.attribution import (
    AttributionEngine,
    AttributionVerdict,
    DriftAttribution,
)


@pytest.fixture
def engine() -> AttributionEngine:
    """Deterministic engine suitable for unit tests."""
    return AttributionEngine(
        alpha=0.05,
        confidence_level=0.95,
        n_bootstrap=2000,
        seed=42,
    )


@pytest.fixture
def stable_scores() -> list[float]:
    return [
        0.88,
        0.89,
        0.90,
        0.91,
        0.92,
        0.90,
        0.89,
        0.91,
        0.90,
        0.88,
    ]


# ---------------------------------------------------------------------------
# Happy path and core attribution logic
# ---------------------------------------------------------------------------


def test_attribution_no_drift(
    engine: AttributionEngine,
    stable_scores: list[float],
) -> None:
    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=stable_scores,
        anchor_rescored_scores=stable_scores.copy(),
        prod_baseline_scores=stable_scores,
        prod_candidate_scores=stable_scores.copy(),
    )

    assert isinstance(verdict, AttributionVerdict)
    assert verdict.attribution == DriftAttribution.NONE
    assert verdict.anchor_set_id == "anchor-v1"
    assert verdict.system_score_delta == pytest.approx(0.0)
    assert verdict.judge_score_delta == pytest.approx(0.0)
    assert verdict.evaluated_at.tzinfo is not None
    assert verdict.evaluated_at.utcoffset() == timezone.utc.utcoffset(
        verdict.evaluated_at
    )
    assert verdict.explanation


def test_attribution_system_drift(engine: AttributionEngine) -> None:
    baseline = [
        0.88,
        0.89,
        0.90,
        0.91,
        0.92,
        0.90,
        0.89,
        0.91,
        0.90,
        0.88,
    ]
    candidate = [
        0.55,
        0.56,
        0.57,
        0.58,
        0.59,
        0.57,
        0.56,
        0.58,
        0.57,
        0.55,
    ]

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=baseline.copy(),
        anchor_rescored_scores=baseline.copy(),
        prod_baseline_scores=baseline,
        prod_candidate_scores=candidate,
    )

    assert verdict.attribution == DriftAttribution.SYSTEM_DRIFT
    assert verdict.system_score_delta < -0.25
    assert verdict.judge_score_delta == pytest.approx(0.0)


def test_attribution_judge_drift(engine: AttributionEngine) -> None:
    anchor_ref = [
        0.88,
        0.89,
        0.90,
        0.91,
        0.92,
        0.90,
        0.89,
        0.91,
        0.90,
        0.88,
    ]
    anchor_rescored = [
        0.55,
        0.56,
        0.57,
        0.58,
        0.59,
        0.57,
        0.56,
        0.58,
        0.57,
        0.55,
    ]
    production = [
        0.88,
        0.89,
        0.90,
        0.91,
        0.92,
        0.90,
        0.89,
        0.91,
        0.90,
        0.88,
    ]

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=anchor_ref,
        anchor_rescored_scores=anchor_rescored,
        prod_baseline_scores=production,
        prod_candidate_scores=production.copy(),
    )

    assert verdict.attribution == DriftAttribution.JUDGE_DRIFT
    assert verdict.judge_score_delta < -0.25
    assert verdict.system_score_delta == pytest.approx(0.0)


def test_attribution_joint_drift(engine: AttributionEngine) -> None:
    anchor_ref = [
        0.88,
        0.89,
        0.90,
        0.91,
        0.92,
        0.90,
        0.89,
        0.91,
        0.90,
        0.88,
    ]
    anchor_rescored = [
        0.55,
        0.56,
        0.57,
        0.58,
        0.59,
        0.57,
        0.56,
        0.58,
        0.57,
        0.55,
    ]
    baseline = [
        0.88,
        0.89,
        0.90,
        0.91,
        0.92,
        0.90,
        0.89,
        0.91,
        0.90,
        0.88,
    ]
    candidate = [
        0.55,
        0.56,
        0.57,
        0.58,
        0.59,
        0.57,
        0.56,
        0.58,
        0.57,
        0.55,
    ]

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=anchor_ref,
        anchor_rescored_scores=anchor_rescored,
        prod_baseline_scores=baseline,
        prod_candidate_scores=candidate,
    )

    assert verdict.attribution == DriftAttribution.JOINT_DRIFT
    assert verdict.judge_score_delta < -0.25
    assert verdict.system_score_delta < -0.25


@pytest.mark.parametrize(
    ("anchor_ref", "anchor_rescored", "expected_direction"),
    [
        ([0.8] * 10, [0.8] * 10, 0),
        ([0.8] * 10, [0.9] * 10, 1),
        ([0.9] * 10, [0.8] * 10, -1),
    ],
)
def test_judge_delta_direction(
    engine: AttributionEngine,
    anchor_ref: list[float],
    anchor_rescored: list[float],
    expected_direction: int,
) -> None:
    scores = [0.8] * 10

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=anchor_ref,
        anchor_rescored_scores=anchor_rescored,
        prod_baseline_scores=scores,
        prod_candidate_scores=scores.copy(),
    )

    if expected_direction > 0:
        assert verdict.judge_score_delta > 0
    elif expected_direction < 0:
        assert verdict.judge_score_delta < 0
    else:
        assert verdict.judge_score_delta == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "alpha",
    [0.0, 1.0, -0.01, 1.01],
)
def test_invalid_alpha_raises(alpha: float) -> None:
    with pytest.raises(
        ValueError,
        match="alpha must be strictly between 0 and 1",
    ):
        AttributionEngine(alpha=alpha)


@pytest.mark.parametrize(
    "confidence_level",
    [0.0, 1.0, -0.01, 1.01],
)
def test_invalid_confidence_level_raises(confidence_level: float) -> None:
    with pytest.raises(
        ValueError,
        match="confidence_level must be strictly between 0 and 1",
    ):
        AttributionEngine(confidence_level=confidence_level)


@pytest.mark.parametrize("n_bootstrap", [0, -1])
def test_invalid_n_bootstrap_raises(n_bootstrap: int) -> None:
    with pytest.raises(
        ValueError,
        match="n_bootstrap must be at least 1",
    ):
        AttributionEngine(n_bootstrap=n_bootstrap)


@pytest.mark.parametrize("seed", [-1, -42])
def test_negative_seed_raises(seed: int) -> None:
    with pytest.raises(
        ValueError,
        match="seed must be non-negative",
    ):
        AttributionEngine(seed=seed)


def test_none_seed_is_valid() -> None:
    engine = AttributionEngine(seed=None)

    assert engine.seed is None


# ---------------------------------------------------------------------------
# Input validation and error handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_scores",
    [
        [],
        [np.nan],
        [np.inf],
        [-np.inf],
    ],
)
def test_invalid_score_inputs_are_inconclusive(
    engine: AttributionEngine,
    invalid_scores: list[float],
) -> None:
    valid = [0.8] * 10

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=invalid_scores,
        anchor_rescored_scores=valid,
        prod_baseline_scores=valid,
        prod_candidate_scores=valid,
    )

    assert verdict.attribution == DriftAttribution.INCONCLUSIVE
    assert verdict.system_score_delta == 0.0
    assert verdict.judge_score_delta == 0.0
    assert "Inconclusive attribution" in verdict.explanation


@pytest.mark.parametrize(
    "invalid_argument",
    [
        "anchor_ref_scores",
        "anchor_rescored_scores",
        "prod_baseline_scores",
        "prod_candidate_scores",
    ],
)
def test_each_invalid_score_group_is_detected(
    engine: AttributionEngine,
    invalid_argument: str,
) -> None:
    valid = [0.8] * 10
    inputs = {
        "anchor_ref_scores": valid.copy(),
        "anchor_rescored_scores": valid.copy(),
        "prod_baseline_scores": valid.copy(),
        "prod_candidate_scores": valid.copy(),
    }

    inputs[invalid_argument] = []

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        **inputs,
    )

    assert verdict.attribution == DriftAttribution.INCONCLUSIVE
    assert invalid_argument in verdict.explanation


@pytest.mark.parametrize(
    "anchor_set_id",
    [
        "",
        "anchor-v1",
        "anchor/v1",
        "anchor set with spaces",
    ],
)
def test_anchor_set_id_is_preserved(
    engine: AttributionEngine,
    stable_scores: list[float],
    anchor_set_id: str,
) -> None:
    verdict = engine.analyze(
        anchor_set_id=anchor_set_id,
        anchor_ref_scores=stable_scores,
        anchor_rescored_scores=stable_scores.copy(),
        prod_baseline_scores=stable_scores,
        prod_candidate_scores=stable_scores.copy(),
    )

    assert verdict.anchor_set_id == anchor_set_id


# ---------------------------------------------------------------------------
# Small-sample behavior
# ---------------------------------------------------------------------------


def test_small_sample_uses_bootstrap_only(
    engine: AttributionEngine,
) -> None:
    small_baseline = [0.8, 0.8, 0.8, 0.8]
    small_candidate = [0.2, 0.2, 0.2, 0.2]

    # return_value configured so an accidental MWU call fails cleanly at
    # assert_not_called() instead of crashing on tuple unpacking.
    with patch(
        "nirizan.trust.attribution.mann_whitney_regression",
        return_value=(0.0, 1.0),
    ) as mann_whitney:
        verdict = engine.analyze(
            anchor_set_id="anchor-small",
            anchor_ref_scores=small_baseline,
            anchor_rescored_scores=small_baseline.copy(),
            prod_baseline_scores=small_baseline,
            prod_candidate_scores=small_candidate,
        )

    mann_whitney.assert_not_called()

    assert verdict.attribution == DriftAttribution.SYSTEM_DRIFT
    assert verdict.system_score_delta < 0


def test_mann_whitney_is_used_when_both_groups_have_at_least_five_samples(
    engine: AttributionEngine,
) -> None:
    baseline = [0.8] * 5
    candidate = [0.2] * 5

    with patch(
        "nirizan.trust.attribution.mann_whitney_regression",
        return_value=(0.0, 0.001),
    ) as mann_whitney:
        verdict = engine.analyze(
            anchor_set_id="anchor-v1",
            anchor_ref_scores=baseline,
            anchor_rescored_scores=baseline.copy(),
            prod_baseline_scores=baseline,
            prod_candidate_scores=candidate,
        )

    assert mann_whitney.call_count == 2
    # Judge hypothesis is evaluated first (two-sided), then the system
    # hypothesis (one-sided "less").
    alternatives = [
        call_kwargs["alternative"]
        for _, call_kwargs in mann_whitney.call_args_list
    ]
    assert alternatives == ["two-sided", "less"]
    assert verdict.attribution == DriftAttribution.SYSTEM_DRIFT
    assert verdict.system_score_delta == pytest.approx(-0.6)


def test_mann_whitney_is_skipped_when_only_baseline_is_small(
    engine: AttributionEngine,
) -> None:
    baseline = [0.8] * 4
    candidate = [0.2] * 5

    # return_value configured so an accidental MWU call fails cleanly at
    # assert_not_called() instead of crashing on tuple unpacking.
    with patch(
        "nirizan.trust.attribution.mann_whitney_regression",
        return_value=(0.0, 1.0),
    ) as mann_whitney:
        verdict = engine.analyze(
            anchor_set_id="anchor-v1",
            anchor_ref_scores=baseline,
            anchor_rescored_scores=baseline.copy(),
            prod_baseline_scores=baseline,
            prod_candidate_scores=candidate,
        )

    mann_whitney.assert_not_called()
    assert verdict.attribution == DriftAttribution.SYSTEM_DRIFT


def test_mann_whitney_is_skipped_when_only_candidate_is_small(
    engine: AttributionEngine,
) -> None:
    """A small production candidate skips only the system-side MWU call.

    The judge-side comparison (anchor reference vs rescored) still has 5
    observations per group, so Mann-Whitney runs exactly once for it. The
    mock must therefore be configured with a valid ``(statistic, p_value)``
    return value: the previous unconfigured MagicMock could not be unpacked
    into two values and crashed before the system side was ever evaluated.

    Anchor values (0.6) deliberately differ from production values (0.8,
    0.2) so the call-args assertion proves which groups reached MWU.
    """
    anchor_ref = [0.6] * 5
    anchor_rescored = [0.6] * 5  # judge is stable
    prod_baseline = [0.8] * 5
    prod_candidate = [0.2] * 4  # small candidate group

    with patch(
        "nirizan.trust.attribution.mann_whitney_regression",
        return_value=(0.0, 1.0),
    ) as mann_whitney:
        verdict = engine.analyze(
            anchor_set_id="anchor-v1",
            anchor_ref_scores=anchor_ref,
            anchor_rescored_scores=anchor_rescored,
            prod_baseline_scores=prod_baseline,
            prod_candidate_scores=prod_candidate,
        )

    # MWU ran exactly once: the judge-side comparison on the anchor groups.
    mann_whitney.assert_called_once()
    mann_whitney.assert_called_once_with(
        anchor_rescored,
        anchor_ref,
        alternative="two-sided",
    )

    # The system-side comparison never reached MWU (candidate has only 4
    # scores); bootstrap-only evidence carries it: delta = -0.6 with a
    # CI of [-0.6, -0.6], which excludes zero.
    assert verdict.attribution == DriftAttribution.SYSTEM_DRIFT
    assert verdict.system_score_delta == pytest.approx(-0.6)
    assert verdict.judge_score_delta == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Statistical decision logic
# ---------------------------------------------------------------------------


def test_shift_evidence_uses_two_sided_alternative_for_judge(
    engine: AttributionEngine,
) -> None:
    baseline = [0.8] * 10
    candidate = [0.7] * 10

    with patch(
        "nirizan.trust.attribution.mann_whitney_regression",
        return_value=(0.0, 0.001),
    ) as mann_whitney:
        engine._shift_evidence(
            baseline,
            candidate,
            alternative="two-sided",
        )

    mann_whitney.assert_called_once_with(
        candidate,
        baseline,
        alternative="two-sided",
    )


def test_shift_evidence_uses_less_alternative_for_system(
    engine: AttributionEngine,
) -> None:
    baseline = [0.8] * 10
    candidate = [0.7] * 10

    with patch(
        "nirizan.trust.attribution.mann_whitney_regression",
        return_value=(0.0, 0.001),
    ) as mann_whitney:
        engine._shift_evidence(
            baseline,
            candidate,
            alternative="less",
        )

    mann_whitney.assert_called_once_with(
        candidate,
        baseline,
        alternative="less",
    )


def test_holm_bonferroni_can_prevent_marginal_judge_shift(
    engine: AttributionEngine,
) -> None:
    """A marginal judge p-value must not bypass the shared correction."""

    def fake_shift_evidence(
        _baseline: list[float],
        _candidate: list[float],
        *,
        alternative: str,
    ) -> tuple[float, float, str, bool]:
        if alternative == "two-sided":
            return -0.20, 0.04, "mock", True

        return -0.30, 0.20, "mock", True

    with patch.object(
        engine,
        "_shift_evidence",
        side_effect=fake_shift_evidence,
    ):
        verdict = engine.analyze(
            anchor_set_id="anchor-v1",
            anchor_ref_scores=[0.9] * 10,
            anchor_rescored_scores=[0.7] * 10,
            prod_baseline_scores=[0.9] * 10,
            prod_candidate_scores=[0.6] * 10,
        )

    assert verdict.attribution == DriftAttribution.NONE


def test_holm_bonferroni_allows_strong_system_drift(
    engine: AttributionEngine,
) -> None:
    def fake_shift_evidence(
        _baseline: list[float],
        _candidate: list[float],
        *,
        alternative: str,
    ) -> tuple[float, float, str, bool]:
        if alternative == "two-sided":
            return 0.0, 0.80, "mock", False

        return -0.30, 0.001, "mock", True

    with patch.object(
        engine,
        "_shift_evidence",
        side_effect=fake_shift_evidence,
    ):
        verdict = engine.analyze(
            anchor_set_id="anchor-v1",
            anchor_ref_scores=[0.9] * 10,
            anchor_rescored_scores=[0.9] * 10,
            prod_baseline_scores=[0.9] * 10,
            prod_candidate_scores=[0.6] * 10,
        )

    assert verdict.attribution == DriftAttribution.SYSTEM_DRIFT
    assert verdict.system_score_delta == pytest.approx(-0.30)
    assert verdict.judge_score_delta == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("judge_p", "system_p", "expected"),
    [
        (0.001, 0.001, DriftAttribution.JOINT_DRIFT),
        (0.001, 0.50, DriftAttribution.JUDGE_DRIFT),
        (0.50, 0.001, DriftAttribution.SYSTEM_DRIFT),
        (0.50, 0.50, DriftAttribution.NONE),
    ],
)
def test_attribution_decision_matrix(
    engine: AttributionEngine,
    judge_p: float,
    system_p: float,
    expected: DriftAttribution,
) -> None:
    def fake_shift_evidence(
        _baseline: list[float],
        _candidate: list[float],
        *,
        alternative: str,
    ) -> tuple[float, float, str, bool]:
        if alternative == "two-sided":
            return -0.20, judge_p, "mock", judge_p < 0.05

        return -0.20, system_p, "mock", system_p < 0.05

    with patch.object(
        engine,
        "_shift_evidence",
        side_effect=fake_shift_evidence,
    ):
        verdict = engine.analyze(
            anchor_set_id="anchor-v1",
            anchor_ref_scores=[0.9] * 10,
            anchor_rescored_scores=[0.7] * 10,
            prod_baseline_scores=[0.9] * 10,
            prod_candidate_scores=[0.7] * 10,
        )

    assert verdict.attribution == expected


def test_positive_system_delta_cannot_be_classified_as_system_drift(
    engine: AttributionEngine,
) -> None:
    """A significant improvement must not be reported as system regression."""

    def fake_shift_evidence(
        _baseline: list[float],
        _candidate: list[float],
        *,
        alternative: str,
    ) -> tuple[float, float, str, bool]:
        if alternative == "two-sided":
            return 0.0, 1.0, "mock", False

        return 0.20, 0.001, "mock", True

    with patch.object(
        engine,
        "_shift_evidence",
        side_effect=fake_shift_evidence,
    ):
        verdict = engine.analyze(
            anchor_set_id="anchor-v1",
            anchor_ref_scores=[0.8] * 10,
            anchor_rescored_scores=[0.8] * 10,
            prod_baseline_scores=[0.7] * 10,
            prod_candidate_scores=[0.9] * 10,
        )

    assert verdict.attribution == DriftAttribution.NONE
    assert verdict.system_score_delta == pytest.approx(0.20)


def test_bootstrap_significance_is_required_for_judge_shift(
    engine: AttributionEngine,
) -> None:
    def fake_shift_evidence(
        _baseline: list[float],
        _candidate: list[float],
        *,
        alternative: str,
    ) -> tuple[float, float, str, bool]:
        if alternative == "two-sided":
            return -0.30, 0.001, "mock", False

        return 0.0, 1.0, "mock", False

    with patch.object(
        engine,
        "_shift_evidence",
        side_effect=fake_shift_evidence,
    ):
        verdict = engine.analyze(
            anchor_set_id="anchor-v1",
            anchor_ref_scores=[0.9] * 10,
            anchor_rescored_scores=[0.6] * 10,
            prod_baseline_scores=[0.8] * 10,
            prod_candidate_scores=[0.8] * 10,
        )

    assert verdict.attribution == DriftAttribution.NONE


def test_bootstrap_significance_is_required_for_system_shift(
    engine: AttributionEngine,
) -> None:
    def fake_shift_evidence(
        _baseline: list[float],
        _candidate: list[float],
        *,
        alternative: str,
    ) -> tuple[float, float, str, bool]:
        if alternative == "two-sided":
            return 0.0, 1.0, "mock", False

        return -0.30, 0.001, "mock", False

    with patch.object(
        engine,
        "_shift_evidence",
        side_effect=fake_shift_evidence,
    ):
        verdict = engine.analyze(
            anchor_set_id="anchor-v1",
            anchor_ref_scores=[0.8] * 10,
            anchor_rescored_scores=[0.8] * 10,
            prod_baseline_scores=[0.8] * 10,
            prod_candidate_scores=[0.5] * 10,
        )

    assert verdict.attribution == DriftAttribution.NONE


# ---------------------------------------------------------------------------
# Reproducibility and result integrity
# ---------------------------------------------------------------------------


def test_seed_makes_bootstrap_result_reproducible() -> None:
    scores_a = [
        0.70,
        0.72,
        0.74,
        0.76,
        0.78,
        0.80,
        0.82,
        0.84,
    ]
    scores_b = [
        0.40,
        0.42,
        0.44,
        0.46,
        0.48,
        0.50,
        0.52,
        0.54,
    ]

    engine_a = AttributionEngine(
        alpha=0.05,
        confidence_level=0.95,
        n_bootstrap=2000,
        seed=123,
    )
    engine_b = AttributionEngine(
        alpha=0.05,
        confidence_level=0.95,
        n_bootstrap=2000,
        seed=123,
    )

    result_a = engine_a._shift_evidence(
        scores_a,
        scores_b,
        alternative="two-sided",
    )
    result_b = engine_b._shift_evidence(
        scores_a,
        scores_b,
        alternative="two-sided",
    )

    assert result_a == result_b


def test_evaluated_at_is_timezone_aware_utc(
    engine: AttributionEngine,
    stable_scores: list[float],
) -> None:
    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=stable_scores,
        anchor_rescored_scores=stable_scores.copy(),
        prod_baseline_scores=stable_scores,
        prod_candidate_scores=stable_scores.copy(),
    )

    assert verdict.evaluated_at.tzinfo is not None
    assert verdict.evaluated_at.utcoffset() is not None
    assert verdict.evaluated_at.utcoffset() == timezone.utc.utcoffset(
        verdict.evaluated_at
    )
    assert verdict.evaluated_at <= datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enum and model integrity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        DriftAttribution.NONE,
        DriftAttribution.SYSTEM_DRIFT,
        DriftAttribution.JUDGE_DRIFT,
        DriftAttribution.JOINT_DRIFT,
        DriftAttribution.INCONCLUSIVE,
    ],
)
def test_all_drift_attribution_values_are_valid(
    value: DriftAttribution,
) -> None:
    assert value.value in {
        "none",
        "system_drift",
        "judge_drift",
        "joint_drift",
        "inconclusive",
    }


# ---------------------------------------------------------------------------
# Regression tests: small-sample comparisons must not enter Holm-Bonferroni
# as fabricated p-values (see PR review discussion on issue #37).
# ---------------------------------------------------------------------------


def test_small_sample_non_significant_side_does_not_suppress_real_drift(
    engine: AttributionEngine,
) -> None:
    """A stable small-sample comparison must not tighten the correction
    threshold applied to a genuine, marginal p-value on the other side.

    Before the fix, an insignificant small-sample bootstrap decision was
    encoded as p=1.0 and joined the Holm-Bonferroni family, which changed
    the threshold applied to the real p-value from alpha (m=1) to alpha/2
    (m=2) and caused a real p=0.0399 judge shift to be rejected.
    """
    anchor_ref = [0.90, 0.88, 0.92, 0.89, 0.91, 0.87, 0.93, 0.90, 0.88, 0.92]
    anchor_rescored = [0.85, 0.90, 0.83, 0.88, 0.91, 0.86, 0.89, 0.84, 0.90, 0.87]

    # Small (n=4), genuinely stable production comparison: bootstrap CI
    # should straddle zero.
    prod_baseline = [0.80, 0.81, 0.79, 0.80]
    prod_candidate = [0.80, 0.79, 0.81, 0.80]

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=anchor_ref,
        anchor_rescored_scores=anchor_rescored,
        prod_baseline_scores=prod_baseline,
        prod_candidate_scores=prod_candidate,
    )

    assert verdict.attribution == DriftAttribution.JUDGE_DRIFT
    assert verdict.system_score_delta == pytest.approx(0.0)


def test_small_sample_significant_side_is_not_over_corrected(
    engine: AttributionEngine,
) -> None:
    """A bootstrap-significant small-sample comparison must be accepted on
    its own evidence, without needing to survive a multi-hypothesis
    correction it has no p-value to participate in."""
    small_baseline = [0.80, 0.81, 0.79, 0.80]
    small_candidate = [0.40, 0.41, 0.39, 0.40]
    stable = [0.9] * 10

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=stable,
        anchor_rescored_scores=stable.copy(),
        prod_baseline_scores=small_baseline,
        prod_candidate_scores=small_candidate,
    )

    assert verdict.attribution == DriftAttribution.SYSTEM_DRIFT


def test_holm_bonferroni_family_excludes_small_sample_side(
    engine: AttributionEngine,
) -> None:
    """`_shift_evidence` reports `p_value=None`, not a placeholder float,
    when Mann-Whitney U was not run, and that `None` never reaches
    `holm_bonferroni`."""
    small_baseline = [0.8, 0.8, 0.8, 0.8]
    small_candidate = [0.2, 0.2, 0.2, 0.2]

    _, p_value, method, _ = engine._shift_evidence(
        small_baseline,
        small_candidate,
        alternative="less",
    )

    assert p_value is None
    assert method == "bootstrap_ci_only(n<5, uncorrected)"

    with patch("nirizan.trust.attribution.holm_bonferroni") as mock_holm:
        mock_holm.return_value = {}
        engine.analyze(
            anchor_set_id="anchor-v1",
            anchor_ref_scores=small_baseline,
            anchor_rescored_scores=small_baseline.copy(),
            prod_baseline_scores=small_baseline,
            prod_candidate_scores=small_candidate,
        )

    # Neither comparison produced a p-value, so holm_bonferroni is never
    # even called (empty family is short-circuited).
    mock_holm.assert_not_called()
