# src/nirizan/regression/comparator.py
from __future__ import annotations

import math
from enum import Enum
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from nirizan._logging import get_logger
from nirizan.regression.thresholds import (
    DEFAULT_ALPHA,
    DEFAULT_BLOCKING_EFFECT,
    DEFAULT_WARNING_EFFECT,
    holm_bonferroni,
    mann_whitney_regression,
    validate_scores,
)

logger = get_logger(__name__)


class RegressionSeverity(str, Enum):
    NONE = "none"
    WARNING = "warning"
    BLOCKING = "blocking"


class RegressionVerdict(BaseModel):
    model_config = ConfigDict(strict=True)

    metric_name: str
    severity: RegressionSeverity
    z_score: float | None = None
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    effect_size: float | None = None
    baseline_id: UUID
    run_id: UUID
    explanation: str


def cohens_d(
    candidate: np.ndarray,
    baseline: np.ndarray,
) -> float:
    validate_scores(candidate)
    validate_scores(baseline)

    candidate_std = candidate.std(ddof=1)
    baseline_std = baseline.std(ddof=1)

    pooled_std = math.sqrt((candidate_std**2 + baseline_std**2) / 2.0)

    if pooled_std == 0.0:
        return 0.0

    return float((candidate.mean() - baseline.mean()) / pooled_std)


def mean_delta(
    candidate: np.ndarray,
    baseline: np.ndarray,
) -> float:
    return float(candidate.mean() - baseline.mean())


def classify_severity(
    *,
    significant: bool,
    effect_size: float,
    warning_effect: float = DEFAULT_WARNING_EFFECT,
    blocking_effect: float = DEFAULT_BLOCKING_EFFECT,
) -> RegressionSeverity:
    if warning_effect >= 0.0:
        raise ValueError("warning_effect must be negative.")

    if blocking_effect >= warning_effect:
        raise ValueError("blocking_effect must be more negative than warning_effect.")

    if not significant:
        return RegressionSeverity.NONE

    if effect_size <= blocking_effect:
        return RegressionSeverity.BLOCKING

    if effect_size <= warning_effect:
        return RegressionSeverity.WARNING

    return RegressionSeverity.NONE


class BaselineComparator:
    def __init__(
        self,
        *,
        alpha: float = DEFAULT_ALPHA,
        warning_effect: float = DEFAULT_WARNING_EFFECT,
        blocking_effect: float = DEFAULT_BLOCKING_EFFECT,
    ) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must be between 0 and 1.")

        self.alpha = alpha
        self.warning_effect = warning_effect
        self.blocking_effect = blocking_effect

        logger.debug(
            "Initialized BaselineComparator (alpha=%.4f, warning_effect=%.2f, blocking_effect=%.2f)",
            alpha,
            warning_effect,
            blocking_effect,
        )

    def compare_metric(
        self,
        *,
        metric_name: str,
        candidate: np.ndarray,
        baseline: np.ndarray,
        baseline_id: UUID,
        run_id: UUID,
    ) -> RegressionVerdict:
        validate_scores(candidate)
        validate_scores(baseline)

        logger.debug(
            "Comparing metric '%s' for candidate run_id=%s vs baseline_id=%s",
            metric_name,
            run_id,
            baseline_id,
        )

        _, p_value = mann_whitney_regression(
            candidate,
            baseline,
        )

        effect = cohens_d(candidate, baseline)

        severity = classify_severity(
            significant=p_value < self.alpha,
            effect_size=effect,
            warning_effect=self.warning_effect,
            blocking_effect=self.blocking_effect,
        )

        delta = mean_delta(candidate, baseline)

        logger.debug(
            "Metric '%s': delta=%.4f, p_value=%.4e, cohens_d=%.3f -> severity=%s",
            metric_name,
            delta,
            p_value,
            effect,
            severity.value,
        )

        if severity == RegressionSeverity.BLOCKING:
            logger.warning(
                "Blocking regression detected on metric '%s' (Cohen's d=%.3f, p=%.4e)",
                metric_name,
                effect,
                p_value,
            )

        return RegressionVerdict(
            metric_name=metric_name,
            severity=severity,
            z_score=None,
            p_value=p_value,
            effect_size=effect,
            baseline_id=baseline_id,
            run_id=run_id,
            explanation=(
                f"candidate-baseline delta={delta:.4f}; p={p_value:.4e}; Cohen's d={effect:.3f}"
            ),
        )

    def compare(
        self,
        *,
        candidate_scores: dict[str, np.ndarray],
        baseline_scores: dict[str, np.ndarray],
        baseline_id: UUID,
        run_id: UUID,
    ) -> list[RegressionVerdict]:
        """Compare all metrics and apply family-wise correction."""
        metric_names = sorted(set(candidate_scores) | set(baseline_scores))

        logger.info(
            "Comparing %d metric(s) between candidate run_id=%s and baseline_id=%s",
            len(metric_names),
            run_id,
            baseline_id,
        )

        verdicts: list[RegressionVerdict] = []

        for metric_name in metric_names:
            if metric_name not in candidate_scores:
                raise ValueError(f"Candidate is missing metric: {metric_name}")

            if metric_name not in baseline_scores:
                raise ValueError(f"Baseline is missing metric: {metric_name}")

            verdicts.append(
                self.compare_metric(
                    metric_name=metric_name,
                    candidate=candidate_scores[metric_name],
                    baseline=baseline_scores[metric_name],
                    baseline_id=baseline_id,
                    run_id=run_id,
                )
            )

        p_values = {
            verdict.metric_name: verdict.p_value
            for verdict in verdicts
            if verdict.p_value is not None
        }

        corrected = holm_bonferroni(
            p_values,
            alpha=self.alpha,
        )

        final: list[RegressionVerdict] = []

        for verdict in verdicts:
            if verdict.severity != RegressionSeverity.NONE and not corrected.get(
                verdict.metric_name, False
            ):
                logger.info(
                    "Reclassified metric '%s' severity from %s to NONE after Holm-Bonferroni correction",
                    verdict.metric_name,
                    verdict.severity.value,
                )
                final.append(
                    verdict.model_copy(
                        update={
                            "severity": RegressionSeverity.NONE,
                            "explanation": (
                                f"{verdict.explanation}; "
                                "not significant after "
                                "Holm-Bonferroni correction"
                            ),
                        }
                    )
                )
            else:
                final.append(verdict)

        logger.info(
            "Baseline comparison complete for run_id=%s (%d verdict(s) generated)",
            run_id,
            len(final),
        )

        return final
