# src/nirizan/reporting/judge_reliability.py
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from nirizan._logging import get_logger
from nirizan.trust.attribution import AttributionVerdict, DriftAttribution

logger = get_logger(__name__)

DEFAULT_JUDGE_DRIFT_RATE_WARNING = 0.10


class JudgeReliabilityStatus(str, Enum):
    """Coarse status for the Judge Reliability Panel, analogous to RegressionSeverity."""

    STABLE = "stable"
    UNSTABLE = "unstable"


class JudgeReliabilityMetrics(BaseModel):
    """Longitudinal summary of judge behavior over a window of AttributionVerdicts."""

    model_config = ConfigDict(strict=True)

    anchor_set_id: str
    period_start: datetime
    period_end: datetime
    verdict_count: int = Field(ge=1)
    judge_drift_rate: float = Field(ge=0.0, le=1.0)
    system_drift_rate: float = Field(ge=0.0, le=1.0)
    joint_drift_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    inconclusive_rate: float = Field(ge=0.0, le=1.0, default=0.0)
    none_rate: float = Field(ge=0.0, le=1.0)
    mean_judge_score_delta: float
    judge_score_delta_std: float
    mean_calibration_mae: float | None = None
    status: JudgeReliabilityStatus
    flagged_verdicts: list[AttributionVerdict] = Field(default_factory=list)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _std(values: list[float], mean_value: float) -> float:
    if len(values) < 2:
        return 0.0
    variance = sum((v - mean_value) ** 2 for v in values) / (len(values) - 1)
    return float(variance**0.5)


def judge_score_delta_series(
    verdicts: list[AttributionVerdict],
) -> list[tuple[datetime, float]]:
    """Time series of judge_score_delta across every verdict, drift or not."""
    return sorted(
        ((v.evaluated_at, v.judge_score_delta) for v in verdicts),
        key=lambda point: point[0],
    )


def system_score_delta_series(
    verdicts: list[AttributionVerdict],
) -> list[tuple[datetime, float]]:
    """Time series of system_score_delta across every verdict, drift or not."""
    return sorted(
        ((v.evaluated_at, v.system_score_delta) for v in verdicts),
        key=lambda point: point[0],
    )


def compute_judge_reliability(
    verdicts: list[AttributionVerdict],
    *,
    calibration_errors: list[dict[str, float]] | None = None,
    drift_rate_warning: float = DEFAULT_JUDGE_DRIFT_RATE_WARNING,
) -> JudgeReliabilityMetrics:
    """Aggregate a window of AttributionVerdicts into a reliability summary."""
    if not verdicts:
        logger.error("compute_judge_reliability called with an empty verdict list.")
        raise ValueError("At least one AttributionVerdict is required.")

    anchor_set_ids = {v.anchor_set_id for v in verdicts}
    if len(anchor_set_ids) > 1:
        logger.error(
            "compute_judge_reliability received verdicts from multiple anchor sets: %s",
            anchor_set_ids,
        )
        raise ValueError(
            "All verdicts must share one anchor_set_id; "
            f"got {sorted(anchor_set_ids)}."
        )

    total = len(verdicts)
    judge_drift_count = sum(
        1 for v in verdicts if v.attribution in (DriftAttribution.JUDGE_DRIFT, DriftAttribution.JOINT_DRIFT)
    )
    system_drift_count = sum(
        1 for v in verdicts if v.attribution in (DriftAttribution.SYSTEM_DRIFT, DriftAttribution.JOINT_DRIFT)
    )
    joint_drift_count = sum(
        1 for v in verdicts if v.attribution == DriftAttribution.JOINT_DRIFT
    )
    inconclusive_count = sum(
        1 for v in verdicts if v.attribution == DriftAttribution.INCONCLUSIVE
    )
    none_count = sum(
        1 for v in verdicts if v.attribution == DriftAttribution.NONE
    )

    # INCONCLUSIVE verdicts carry a judge_score_delta of 0.0 as a placeholder
    # for "not measured," not a real observation of zero drift. Including
    # them here would silently bias mean_judge_score_delta toward zero and
    # understate judge_score_delta_std. Exclude them from the delta series;
    # they are still counted in inconclusive_rate and flagged_verdicts.
    measured_verdicts = [
        v for v in verdicts if v.attribution != DriftAttribution.INCONCLUSIVE
    ]
    if not measured_verdicts:
        logger.error(
            "compute_judge_reliability received only INCONCLUSIVE verdicts for "
            "anchor_set_id=%s; cannot compute delta statistics.",
            verdicts[0].anchor_set_id,
        )
        raise ValueError(
            "At least one non-INCONCLUSIVE verdict is required to compute "
            "judge_score_delta statistics."
        )

    judge_deltas = [v.judge_score_delta for v in measured_verdicts]
    mean_judge_delta = _mean(judge_deltas)

    judge_drift_rate = judge_drift_count / total
    status = (
        JudgeReliabilityStatus.UNSTABLE
        if judge_drift_rate > drift_rate_warning
        else JudgeReliabilityStatus.STABLE
    )

    mean_calibration_mae = None
    if calibration_errors:
        maes = [c["mae"] for c in calibration_errors if "mae" in c]
        if maes:
            mean_calibration_mae = _mean(maes)

    metrics = JudgeReliabilityMetrics(
        anchor_set_id=verdicts[0].anchor_set_id,
        period_start=min(v.evaluated_at for v in verdicts),
        period_end=max(v.evaluated_at for v in verdicts),
        verdict_count=total,
        judge_drift_rate=judge_drift_rate,
        system_drift_rate=system_drift_count / total,
        joint_drift_rate=joint_drift_count / total,
        inconclusive_rate=inconclusive_count / total,
        none_rate=none_count / total,
        mean_judge_score_delta=mean_judge_delta,
        judge_score_delta_std=_std(judge_deltas, mean_judge_delta),
        mean_calibration_mae=mean_calibration_mae,
        status=status,
        flagged_verdicts=[
            v for v in verdicts if v.attribution != DriftAttribution.NONE
        ],
    )

    if status == JudgeReliabilityStatus.UNSTABLE:
        logger.warning(
            "Judge reliability UNSTABLE for anchor_set_id=%s: "
            "judge_drift_rate=%.3f over %d verdicts",
            metrics.anchor_set_id,
            judge_drift_rate,
            total,
        )
    else:
        logger.info(
            "Judge reliability STABLE for anchor_set_id=%s: "
            "judge_drift_rate=%.3f over %d verdicts",
            metrics.anchor_set_id,
            judge_drift_rate,
            total,
        )

    return metrics
