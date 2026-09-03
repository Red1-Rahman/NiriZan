# src/nirizan/regression/multivariate.py
from __future__ import annotations

from uuid import UUID

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from nirizan._logging import get_logger
from nirizan.metrics.stats import frobenius_covariance_permutation, validate_score_matrix
from nirizan.regression.thresholds import DEFAULT_ALPHA

logger = get_logger(__name__)

DEFAULT_N_PERM = 200


class CovarianceShiftVerdict(BaseModel):
    """Verdict for Track 3: whether the joint second-moment structure of a
    correlated metric set has shifted between a baseline and a candidate run.

    Kept as its own model, not a field on regression.comparator.RegressionVerdict,
    for the same reason AttributionVerdict, RegressionVerdict, and GateVerdict
    are each kept separate in docs/contracts.md: this answers a structurally
    different question (did the covariance/correlation structure change) than
    a per-metric location test, and needs its own explanation rather than
    sharing one that was written for a different hypothesis.
    """

    model_config = ConfigDict(strict=True)

    statistic: float
    p_value: float = Field(ge=0.0, le=1.0)
    correlation_statistic: float | None = None
    correlation_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    baseline_id: UUID
    run_id: UUID
    is_drift: bool
    explanation: str


def _diagnose_shift(
    *,
    is_drift: bool,
    correlation_p_value: float | None,
    alpha: float,
) -> str:
    """Best-effort attribution of a detected shift to variance vs. correlation change.

    This function only produces explanation text. is_drift itself is decided
    solely by the primary covariance-based test in
    CovarianceShiftDetector.evaluate, never by this function or by the
    correlation-only sub-test: a pure variance shift is still real
    second-moment drift and must not be reclassified as a non-event just
    because the relationship between metrics didn't change.
    """
    if not is_drift:
        return "no significant covariance-structure drift detected"

    if correlation_p_value is None:
        return (
            "covariance-structure drift detected; the correlation-only "
            "diagnostic could not be computed (a metric had zero variance "
            "in one of the two groups), so whether this is a pure variance "
            "shift, a correlation shift, or both cannot be determined"
        )

    if correlation_p_value < alpha:
        return (
            "covariance-structure drift detected, and the correlation-only "
            "sub-test is also significant: the relationship between metrics "
            "appears to have changed, not just an individual metric's spread"
        )

    return (
        "covariance-structure drift detected, but the correlation-only "
        "sub-test is not significant: this looks like a variance change on "
        "one or more metrics rather than a change in how metrics relate to "
        "one another"
    )


class CovarianceShiftDetector:
    """Track 3: detects joint second-moment structure drift between a
    baseline and a candidate run, via Frobenius-norm permutation testing.

    Deliberately narrow: this class answers one question (did the covariance
    structure shift) and reports a diagnostic breakdown of what kind of shift
    it looks like. It does not replace, gate, or combine with Track 1's
    BaselineComparator.
    """

    def __init__(
        self,
        *,
        alpha: float = DEFAULT_ALPHA,
        n_perm: int = DEFAULT_N_PERM,
        seed: int | None = None,
    ) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must be between 0 and 1.")
        if n_perm <= 0:
            raise ValueError("n_perm must be positive.")

        self.alpha = alpha
        self.n_perm = n_perm
        self.seed = seed

        logger.debug(
            "Initialized CovarianceShiftDetector (alpha=%.4f, n_perm=%d)",
            alpha,
            n_perm,
        )

    def evaluate(
        self,
        *,
        candidate: np.ndarray,
        baseline: np.ndarray,
        baseline_id: UUID,
        run_id: UUID,
    ) -> CovarianceShiftVerdict:
        """Evaluate covariance-structure drift for one candidate/baseline pair.

        candidate and baseline are [n_samples, n_metrics] score matrices, the
        same shape Run.metric_results produces once pivoted from long to wide
        (one row per run, one column per metric_name).
        """
        validate_score_matrix(candidate)
        validate_score_matrix(baseline)

        logger.debug(
            "Evaluating covariance-structure shift for run_id=%s vs baseline_id=%s",
            run_id,
            baseline_id,
        )

        stat, p_value = frobenius_covariance_permutation(
            candidate,
            baseline,
            use_correlation=False,
            n_perm=self.n_perm,
            seed=self.seed,
        )

        is_drift = p_value < self.alpha

        correlation_stat: float | None
        correlation_p: float | None
        try:
            correlation_stat, correlation_p = frobenius_covariance_permutation(
                candidate,
                baseline,
                use_correlation=True,
                n_perm=self.n_perm,
                seed=self.seed,
            )
        except ValueError as exc:
            logger.debug(
                "Correlation-only diagnostic skipped for run_id=%s: %s", run_id, exc
            )
            correlation_stat, correlation_p = None, None

        explanation = _diagnose_shift(
            is_drift=is_drift,
            correlation_p_value=correlation_p,
            alpha=self.alpha,
        )

        if is_drift:
            logger.warning(
                "Covariance-structure drift detected for run_id=%s (stat=%.4f, p=%.4e)",
                run_id,
                stat,
                p_value,
            )

        return CovarianceShiftVerdict(
            statistic=stat,
            p_value=p_value,
            correlation_statistic=correlation_stat,
            correlation_p_value=correlation_p,
            baseline_id=baseline_id,
            run_id=run_id,
            is_drift=is_drift,
            explanation=explanation,
        )
