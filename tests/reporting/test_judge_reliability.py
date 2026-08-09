# tests/reporting/test_judge_reliability.py
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from nirizan.reporting.judge_reliability import (
    DEFAULT_JUDGE_DRIFT_RATE_WARNING,
    JudgeReliabilityMetrics,
    JudgeReliabilityStatus,
    compute_judge_reliability,
    judge_score_delta_series,
    system_score_delta_series,
)
from nirizan.trust.attribution import AttributionVerdict, DriftAttribution


def _make_verdict(
    *,
    anchor_set_id: str = "anchor-1",
    attribution: DriftAttribution = DriftAttribution.NONE,
    judge_score_delta: float = 0.01,
    system_score_delta: float = -0.02,
    evaluated_at: datetime | None = None,
) -> AttributionVerdict:
    return AttributionVerdict(
        attribution=attribution,
        anchor_set_id=anchor_set_id,
        system_score_delta=system_score_delta,
        judge_score_delta=judge_score_delta,
        evaluated_at=evaluated_at or datetime.now(timezone.utc),
        explanation="Test verdict",
    )


def test_compute_judge_reliability_empty_raises():
    with pytest.raises(ValueError, match="At least one AttributionVerdict is required"):
        compute_judge_reliability([])


def test_compute_judge_reliability_mixed_anchor_sets_raises():
    v1 = _make_verdict(anchor_set_id="anchor-1")
    v2 = _make_verdict(anchor_set_id="anchor-2")
    with pytest.raises(ValueError, match="All verdicts must share one anchor_set_id"):
        compute_judge_reliability([v1, v2])


def test_compute_judge_reliability_stable_status():
    now = datetime.now(timezone.utc)
    verdicts = [
        _make_verdict(
            attribution=DriftAttribution.NONE,
            judge_score_delta=0.01,
            evaluated_at=now - timedelta(hours=2),
        ),
        _make_verdict(
            attribution=DriftAttribution.SYSTEM_DRIFT,
            judge_score_delta=0.02,
            evaluated_at=now - timedelta(hours=1),
        ),
        _make_verdict(
            attribution=DriftAttribution.NONE,
            judge_score_delta=-0.01,
            evaluated_at=now,
        ),
    ]

    metrics = compute_judge_reliability(verdicts)

    assert isinstance(metrics, JudgeReliabilityMetrics)
    assert metrics.anchor_set_id == "anchor-1"
    assert metrics.verdict_count == 3
    assert metrics.status == JudgeReliabilityStatus.STABLE
    assert metrics.judge_drift_rate == 0.0
    assert pytest.approx(metrics.system_drift_rate) == 1 / 3
    assert pytest.approx(metrics.none_rate) == 2 / 3
    assert len(metrics.flagged_verdicts) == 1
    assert metrics.flagged_verdicts[0].attribution == DriftAttribution.SYSTEM_DRIFT


def test_compute_judge_reliability_unstable_status():
    now = datetime.now(timezone.utc)
    # 2 out of 5 verdicts have JUDGE_DRIFT (40% > 10% warning threshold)
    verdicts = [
        _make_verdict(attribution=DriftAttribution.JUDGE_DRIFT, evaluated_at=now - timedelta(minutes=i))
        for i in range(2)
    ] + [
        _make_verdict(attribution=DriftAttribution.NONE, evaluated_at=now - timedelta(minutes=i + 2))
        for i in range(3)
    ]

    metrics = compute_judge_reliability(verdicts)

    assert metrics.status == JudgeReliabilityStatus.UNSTABLE
    assert pytest.approx(metrics.judge_drift_rate) == 0.40
    assert len(metrics.flagged_verdicts) == 2


def test_compute_judge_reliability_custom_warning_threshold():
    now = datetime.now(timezone.utc)
    # 1 out of 4 verdicts has JUDGE_DRIFT (25%)
    verdicts = [
        _make_verdict(attribution=DriftAttribution.JUDGE_DRIFT, evaluated_at=now),
    ] + [
        _make_verdict(attribution=DriftAttribution.NONE, evaluated_at=now - timedelta(minutes=i + 1))
        for i in range(3)
    ]

    # With 30% warning threshold, 25% should remain STABLE
    metrics = compute_judge_reliability(verdicts, drift_rate_warning=0.30)
    assert metrics.status == JudgeReliabilityStatus.STABLE

    # With 20% warning threshold, 25% should be UNSTABLE
    metrics_unstable = compute_judge_reliability(verdicts, drift_rate_warning=0.20)
    assert metrics_unstable.status == JudgeReliabilityStatus.UNSTABLE


def test_compute_judge_reliability_single_verdict_std_zero():
    verdict = _make_verdict(judge_score_delta=0.05)
    metrics = compute_judge_reliability([verdict])

    assert metrics.verdict_count == 1
    assert metrics.mean_judge_score_delta == 0.05
    assert metrics.judge_score_delta_std == 0.0
    assert metrics.period_start == metrics.period_end


def test_compute_judge_reliability_calibration_mae():
    verdicts = [_make_verdict()]
    calibration_errors = [
        {"mae": 0.04, "rmse": 0.06},
        {"mae": 0.08, "rmse": 0.10},
        {"other": 1.0},  # missing 'mae' should be safely ignored
    ]

    metrics = compute_judge_reliability(verdicts, calibration_errors=calibration_errors)
    assert metrics.mean_calibration_mae == pytest.approx(0.06)


def test_judge_score_delta_series_sorting():
    t0 = datetime.now(timezone.utc) - timedelta(hours=2)
    t1 = datetime.now(timezone.utc) - timedelta(hours=1)
    t2 = datetime.now(timezone.utc)

    # Pass in unsorted order
    verdicts = [
        _make_verdict(judge_score_delta=0.2, evaluated_at=t1),
        _make_verdict(judge_score_delta=0.3, evaluated_at=t2),
        _make_verdict(judge_score_delta=0.1, evaluated_at=t0),
    ]

    series = judge_score_delta_series(verdicts)
    assert series == [(t0, 0.1), (t1, 0.2), (t2, 0.3)]


def test_system_score_delta_series_sorting():
    t0 = datetime.now(timezone.utc) - timedelta(hours=2)
    t1 = datetime.now(timezone.utc)

    verdicts = [
        _make_verdict(system_score_delta=-0.3, evaluated_at=t1),
        _make_verdict(system_score_delta=-0.1, evaluated_at=t0),
    ]

    series = system_score_delta_series(verdicts)
    assert series == [(t0, -0.1), (t1, -0.3)]
