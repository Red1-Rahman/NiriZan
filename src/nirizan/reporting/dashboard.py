# src/nirizan/reporting/dashboard.py
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from nirizan._logging import get_logger
from nirizan.gate.verdict import CovarianceTrackResult, GateVerdict
from nirizan.regression.comparator import RegressionVerdict
from nirizan.reporting.health_score import compute_system_health_score
from nirizan.reporting.judge_reliability import (
    JudgeReliabilityMetrics,
    compute_judge_reliability,
)
from nirizan.trust.attribution import AttributionVerdict, DriftAttribution

logger = get_logger(__name__)


class DashboardSnapshot(BaseModel):
    """Assembled reporting data for one system_type at one point in time.

    This model is data only. It does not render anything; a CLI, notebook,
    or future web UI is responsible for turning this into something a human
    looks at (see architecture.md 3.8: Dashboard, Judge Reliability Panel,
    Drift & Regression Reports are three views over one underlying signal
    set, not three separate computations).
    """

    model_config = ConfigDict(strict=True)

    generated_at: datetime
    system_type: str
    health_score: float = Field(ge=0.0, le=100.0)
    latest_attribution: AttributionVerdict | None = None
    judge_reliability: JudgeReliabilityMetrics | None = None
    regression_verdicts: list[RegressionVerdict] = Field(default_factory=list)
    covariance_verdicts: list[CovarianceTrackResult] = Field(default_factory=list)
    gate_verdict: GateVerdict | None = None


def assemble_dashboard_snapshot(
    *,
    system_type: str,
    quality_score: float,
    confidence: float,
    attribution_verdicts: list[AttributionVerdict] | None = None,
    regression_verdicts: list[RegressionVerdict] | None = None,
    covariance_verdicts: list[CovarianceTrackResult] | None = None,
    gate_verdict: GateVerdict | None = None,
    calibration_errors: list[dict[str, float]] | None = None,
) -> DashboardSnapshot:
    """Combine health score, judge reliability, and regression/gate/covariance
    output into one snapshot.

    quality_score and confidence feed the health score directly (see
    reporting/health_score.py); they are not derived here, since deciding
    which metric's score and confidence represent "the" system quality is a
    call site decision, not something this function should guess at.

    attribution_verdicts, if supplied, should be pre-fetched by the caller
    (see judge_reliability.py's module docstring on why this stays
    storage-decoupled). If empty or omitted, health score falls back to
    DriftAttribution.NONE (no attribution history to penalize against) and
    judge_reliability is left unset rather than fabricated from nothing.

    covariance_verdicts, if supplied, carries Track 3 (covariance-structure
    drift, #46) results directly -- it is not derived from gate_verdict even
    when gate_verdict.covariance_verdicts is also populated, since a caller
    may be assembling a snapshot from a standalone drift-monitoring run that
    never went through gate evaluation at all. It does not feed
    health_score; Track 3 stays a visibility-only diagnostic here exactly as
    it does in GateVerdict.
    """
    latest_attribution: AttributionVerdict | None = None
    judge_reliability: JudgeReliabilityMetrics | None = None
    attribution_for_health = DriftAttribution.NONE

    if attribution_verdicts:
        latest_attribution = max(attribution_verdicts, key=lambda v: v.evaluated_at)
        attribution_for_health = latest_attribution.attribution
        try:
            judge_reliability = compute_judge_reliability(
                attribution_verdicts,
                calibration_errors=calibration_errors,
            )
        except ValueError:
            # Mixed anchor sets or other aggregation failure; log and
            # continue with health score alone rather than failing the
            # whole snapshot over a panel-only computation.
            logger.warning(
                "Skipping judge reliability aggregation for system_type=%s: "
                "verdict set failed validation (see prior log line).",
                system_type,
            )

    health_score = compute_system_health_score(
        quality_score=quality_score,
        confidence=confidence,
        attribution=attribution_for_health,
    )

    logger.info(
        "Assembled dashboard snapshot for system_type=%s: health_score=%.1f, "
        "attribution=%s, regression_verdicts=%d, covariance_verdicts=%d, gate_passed=%s",
        system_type,
        health_score,
        attribution_for_health.value,
        len(regression_verdicts) if regression_verdicts else 0,
        len(covariance_verdicts) if covariance_verdicts else 0,
        gate_verdict.passed if gate_verdict is not None else "n/a",
    )

    return DashboardSnapshot(
        generated_at=datetime.now(timezone.utc),
        system_type=system_type,
        health_score=health_score,
        latest_attribution=latest_attribution,
        judge_reliability=judge_reliability,
        regression_verdicts=regression_verdicts or [],
        covariance_verdicts=covariance_verdicts or [],
        gate_verdict=gate_verdict,
    )
