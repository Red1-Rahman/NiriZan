# tests/reporting/test_dashboard.py
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from nirizan.gate.verdict import GateVerdict
from nirizan.regression.comparator import RegressionSeverity, RegressionVerdict
from nirizan.reporting.dashboard import DashboardSnapshot, assemble_dashboard_snapshot
from nirizan.reporting.judge_reliability import JudgeReliabilityStatus
from nirizan.trust.attribution import AttributionVerdict, DriftAttribution


def _make_attribution_verdict(
    *,
    anchor_set_id: str = "anchor-1",
    attribution: DriftAttribution = DriftAttribution.NONE,
    evaluated_at: datetime | None = None,
) -> AttributionVerdict:
    return AttributionVerdict(
        attribution=attribution,
        anchor_set_id=anchor_set_id,
        system_score_delta=0.0,
        judge_score_delta=0.0,
        evaluated_at=evaluated_at or datetime.now(timezone.utc),
        explanation="Dashboard test verdict",
    )


def test_assemble_dashboard_snapshot_minimal():
    snapshot = assemble_dashboard_snapshot(
        system_type="rag_pipeline",
        quality_score=0.85,
        confidence=0.90,
    )

    assert isinstance(snapshot, DashboardSnapshot)
    assert snapshot.system_type == "rag_pipeline"
    # base_score = 0.85 * 0.90 * 100.0 = 76.5 (multiplier 1.0 for NONE)
    assert snapshot.health_score == pytest.approx(76.5)
    assert snapshot.latest_attribution is None
    assert snapshot.judge_reliability is None
    assert snapshot.regression_verdicts == []
    assert snapshot.gate_verdict is None


def test_assemble_dashboard_snapshot_full():
    now = datetime.now(timezone.utc)
    t_old = now - timedelta(hours=1)

    attr_verdicts = [
        _make_attribution_verdict(attribution=DriftAttribution.NONE, evaluated_at=t_old),
        _make_attribution_verdict(attribution=DriftAttribution.JUDGE_DRIFT, evaluated_at=now),
    ]

    reg_verdict = RegressionVerdict(
        metric_name="context_relevance",
        severity=RegressionSeverity.WARNING,
        baseline_id=uuid4(),
        run_id=uuid4(),
        explanation="Slight quality drop",
    )

    run_id = uuid4()
    gate_verdict = GateVerdict(
        passed=True,
        confidence_interval=(0.80, 0.92),
        regression_verdicts=[reg_verdict],
        run_id=run_id,
    )

    snapshot = assemble_dashboard_snapshot(
        system_type="agent_workflow",
        quality_score=0.90,
        confidence=0.95,
        attribution_verdicts=attr_verdicts,
        regression_verdicts=[reg_verdict],
        gate_verdict=gate_verdict,
        calibration_errors=[{"mae": 0.05}],
    )

    # Health score check:
    # base_score = 0.90 * 0.95 * 100.0 = 85.5
    # JUDGE_DRIFT multiplier = 0.90 -> 85.5 * 0.90 = 76.95 -> rounded to 77.0
    assert snapshot.health_score == pytest.approx(77.0)
    assert snapshot.latest_attribution == attr_verdicts[1]
    assert snapshot.latest_attribution.attribution == DriftAttribution.JUDGE_DRIFT

    assert snapshot.judge_reliability is not None
    assert snapshot.judge_reliability.verdict_count == 2
    assert snapshot.judge_reliability.mean_calibration_mae == pytest.approx(0.05)
    assert snapshot.judge_reliability.status == JudgeReliabilityStatus.UNSTABLE

    assert len(snapshot.regression_verdicts) == 1
    assert snapshot.gate_verdict is not None
    assert snapshot.gate_verdict.passed is True


def test_assemble_dashboard_snapshot_latest_attribution_selection():
    t0 = datetime.now(timezone.utc) - timedelta(hours=2)
    t1 = datetime.now(timezone.utc)

    # Put oldest last in the list to verify sorting by evaluated_at
    attr_verdicts = [
        _make_attribution_verdict(attribution=DriftAttribution.JUDGE_DRIFT, evaluated_at=t1),
        _make_attribution_verdict(attribution=DriftAttribution.SYSTEM_DRIFT, evaluated_at=t0),
    ]

    snapshot = assemble_dashboard_snapshot(
        system_type="llm_app",
        quality_score=1.0,
        confidence=1.0,
        attribution_verdicts=attr_verdicts,
    )

    # Latest evaluated_at is JUDGE_DRIFT
    assert snapshot.latest_attribution.attribution == DriftAttribution.JUDGE_DRIFT
    # Health score uses JUDGE_DRIFT (0.9 multiplier) -> 100.0 * 0.9 = 90.0
    assert snapshot.health_score == pytest.approx(90.0)


def test_assemble_dashboard_snapshot_handles_mixed_anchor_sets_gracefully():
    # compute_judge_reliability will raise ValueError on mixed anchor sets
    attr_verdicts = [
        _make_attribution_verdict(anchor_set_id="anchor-A"),
        _make_attribution_verdict(anchor_set_id="anchor-B"),
    ]

    snapshot = assemble_dashboard_snapshot(
        system_type="llm_app",
        quality_score=0.80,
        confidence=0.90,
        attribution_verdicts=attr_verdicts,
    )

    # Dashboard generation completes without crashing
    assert snapshot.system_type == "llm_app"
    assert snapshot.judge_reliability is None  # Skipped due to validation failure
    assert snapshot.latest_attribution is not None  # Latest attribution is still recorded
