# tests/reporting/test_dashboard.py
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from nirizan.gate.verdict import GateVerdict
from nirizan.regression.comparator import RegressionSeverity, RegressionVerdict
from nirizan.regression.multivariate import (
    MultivariateMethod,
    MultivariateVerdict,
)
from nirizan.reporting.dashboard import (
    DashboardSnapshot,
    assemble_dashboard_snapshot,
)
from nirizan.reporting.judge_reliability import JudgeReliabilityStatus
from nirizan.trust.attribution import AttributionVerdict, DriftAttribution


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
        evaluated_at=evaluated_at or datetime.now(UTC),
        explanation="Dashboard test verdict",
    )


def _make_multivariate_verdict(
    method: MultivariateMethod = MultivariateMethod.SCALE,
    severity: RegressionSeverity = RegressionSeverity.NONE,
    *,
    p_value: float = 0.5,
    effect_size: float = 0.0,
    inconclusive: bool = False,
    baseline_id: UUID | None = None,
    run_id: UUID | None = None,
) -> MultivariateVerdict:
    return MultivariateVerdict(
        method=method,
        severity=severity,
        p_value=p_value,
        statistic=0.0,
        effect_size=effect_size,
        baseline_id=baseline_id or uuid4(),
        run_id=run_id or uuid4(),
        explanation="Dashboard test structure verdict",
        inconclusive=inconclusive,
    )


# ---------------------------------------------------------------------------
# Minimal snapshot (backward compatibility)
# ---------------------------------------------------------------------------


def test_assemble_dashboard_snapshot_minimal() -> None:
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
    assert snapshot.multivariate_verdicts == []
    assert snapshot.gate_verdict is None


def test_assemble_dashboard_snapshot_generated_at_is_utc_aware() -> None:
    """The generated_at timestamp must be timezone-aware UTC, not naive."""
    snapshot = assemble_dashboard_snapshot(
        system_type="rag_pipeline",
        quality_score=0.5,
        confidence=0.5,
    )
    assert snapshot.generated_at.tzinfo is not None
    assert snapshot.generated_at.utcoffset() == timedelta(0)


# ---------------------------------------------------------------------------
# Full snapshot (univariate + attribution)
# ---------------------------------------------------------------------------


def test_assemble_dashboard_snapshot_full() -> None:
    now = datetime.now(UTC)
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

    # Narrow the nullable field for the type checker before accessing it.
    assert snapshot.latest_attribution is not None
    assert snapshot.latest_attribution == attr_verdicts[1]
    assert snapshot.latest_attribution.attribution == DriftAttribution.JUDGE_DRIFT

    assert snapshot.judge_reliability is not None
    assert snapshot.judge_reliability.verdict_count == 2
    assert snapshot.judge_reliability.mean_calibration_mae == pytest.approx(0.05)
    assert snapshot.judge_reliability.status == JudgeReliabilityStatus.UNSTABLE

    assert len(snapshot.regression_verdicts) == 1
    assert snapshot.gate_verdict is not None
    assert snapshot.gate_verdict.passed is True


# ---------------------------------------------------------------------------
# Latest attribution selection
# ---------------------------------------------------------------------------


def test_assemble_dashboard_snapshot_latest_attribution_selection() -> None:
    t0 = datetime.now(UTC) - timedelta(hours=2)
    t1 = datetime.now(UTC)

    # Put oldest last in the list to verify sorting by evaluated_at.
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

    # Narrow before accessing members.
    assert snapshot.latest_attribution is not None
    # Latest evaluated_at is JUDGE_DRIFT.
    assert snapshot.latest_attribution.attribution == DriftAttribution.JUDGE_DRIFT
    # Health score uses JUDGE_DRIFT (0.9 multiplier) -> 100.0 * 0.9 = 90.0
    assert snapshot.health_score == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


def test_assemble_dashboard_snapshot_handles_mixed_anchor_sets_gracefully() -> None:
    # compute_judge_reliability will raise ValueError on mixed anchor sets.
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

    # Dashboard generation completes without crashing.
    assert snapshot.system_type == "llm_app"
    assert snapshot.judge_reliability is None  # Skipped due to validation failure
    assert snapshot.latest_attribution is not None  # Latest attribution recorded


# ---------------------------------------------------------------------------
# Multivariate verdicts on the snapshot
# ---------------------------------------------------------------------------


def test_assemble_dashboard_snapshot_without_multivariate_gives_empty_list() -> None:
    """Omitting the arg reproduces the pre-multivariate behavior."""
    snapshot = assemble_dashboard_snapshot(
        system_type="rag_pipeline",
        quality_score=0.8,
        confidence=0.8,
    )
    assert snapshot.multivariate_verdicts == []


def test_assemble_dashboard_snapshot_none_multivariate_gives_empty_list() -> None:
    """Explicit None is treated the same as omitted."""
    snapshot = assemble_dashboard_snapshot(
        system_type="rag_pipeline",
        quality_score=0.8,
        confidence=0.8,
        multivariate_verdicts=None,
    )
    assert snapshot.multivariate_verdicts == []


def test_assemble_dashboard_snapshot_carries_multivariate_verdicts() -> None:
    """Multivariate verdicts passed in are carried through, in order,
    unmodified. Reporting relies on this for its structure-track panel.
    """
    mv_scale = _make_multivariate_verdict(
        method=MultivariateMethod.SCALE,
        severity=RegressionSeverity.WARNING,
        p_value=0.0123,
        effect_size=0.42,
    )
    mv_dependence = _make_multivariate_verdict(
        method=MultivariateMethod.DEPENDENCE,
        severity=RegressionSeverity.NONE,
        p_value=0.8731,
        effect_size=0.05,
    )

    snapshot = assemble_dashboard_snapshot(
        system_type="rag_pipeline",
        quality_score=0.9,
        confidence=0.9,
        multivariate_verdicts=[mv_scale, mv_dependence],
    )

    assert snapshot.multivariate_verdicts == [mv_scale, mv_dependence]
    assert snapshot.multivariate_verdicts[0].method == MultivariateMethod.SCALE
    assert snapshot.multivariate_verdicts[1].method == MultivariateMethod.DEPENDENCE


def test_multivariate_verdicts_do_not_affect_health_score() -> None:
    """The structure track is informational for the snapshot. Its presence
    must not change the numeric health score, which is driven entirely by
    quality_score, confidence, and the attribution signal.
    """
    baseline_snapshot = assemble_dashboard_snapshot(
        system_type="rag_pipeline",
        quality_score=0.9,
        confidence=0.9,
    )

    mv_blocking = _make_multivariate_verdict(
        method=MultivariateMethod.SCALE,
        severity=RegressionSeverity.BLOCKING,
        p_value=0.0001,
        effect_size=0.9,
    )
    with_mv_snapshot = assemble_dashboard_snapshot(
        system_type="rag_pipeline",
        quality_score=0.9,
        confidence=0.9,
        multivariate_verdicts=[mv_blocking],
    )

    assert with_mv_snapshot.health_score == baseline_snapshot.health_score


def test_multivariate_verdicts_inconclusive_flag_survives() -> None:
    """An INCONCLUSIVE structure verdict must retain its flag through the
    snapshot, since Reporting needs to distinguish it from a NONE verdict.
    """
    mv_inconclusive = _make_multivariate_verdict(
        method=MultivariateMethod.SCALE,
        severity=RegressionSeverity.NONE,
        inconclusive=True,
    )

    snapshot = assemble_dashboard_snapshot(
        system_type="rag_pipeline",
        quality_score=0.9,
        confidence=0.9,
        multivariate_verdicts=[mv_inconclusive],
    )

    assert len(snapshot.multivariate_verdicts) == 1
    assert snapshot.multivariate_verdicts[0].inconclusive is True


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_dashboard_snapshot_serializes_multivariate_verdicts() -> None:
    """The snapshot must round-trip through JSON with multivariate verdicts
    intact, since dashboards serialize snapshots to send them downstream.
    """
    mv_scale = _make_multivariate_verdict(
        method=MultivariateMethod.SCALE,
        severity=RegressionSeverity.WARNING,
        p_value=0.0123,
        effect_size=0.42,
    )

    snapshot = assemble_dashboard_snapshot(
        system_type="rag_pipeline",
        quality_score=0.9,
        confidence=0.9,
        multivariate_verdicts=[mv_scale],
    )

    dumped = snapshot.model_dump(mode="json")
    assert "multivariate_verdicts" in dumped
    assert len(dumped["multivariate_verdicts"]) == 1
    assert dumped["multivariate_verdicts"][0]["method"] == "scale"
    assert dumped["multivariate_verdicts"][0]["severity"] == "warning"
    assert dumped["multivariate_verdicts"][0]["inconclusive"] is False


def test_dashboard_snapshot_serializes_empty_multivariate_list() -> None:
    """The key must exist even when no multivariate verdicts ran, so
    downstream consumers can rely on it being present.
    """
    snapshot = assemble_dashboard_snapshot(
        system_type="rag_pipeline",
        quality_score=0.9,
        confidence=0.9,
    )
    dumped = snapshot.model_dump(mode="json")
    assert dumped["multivariate_verdicts"] == []
