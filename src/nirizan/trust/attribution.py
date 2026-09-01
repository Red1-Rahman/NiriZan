# src/nirizan/trust/attribution.py
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict

from nirizan.metrics.stats import (
    bootstrap_delta_ci,
    holm_bonferroni,
    mann_whitney_regression,
    validate_scores,
)


class DriftAttribution(str, Enum):
    NONE = "none"
    SYSTEM_DRIFT = "system_drift"
    JUDGE_DRIFT = "judge_drift"
    JOINT_DRIFT = "joint_drift"
    INCONCLUSIVE = "inconclusive"


class AttributionVerdict(BaseModel):
    model_config = ConfigDict(strict=True)

    attribution: DriftAttribution
    anchor_set_id: str
    system_score_delta: float
    judge_score_delta: float
    evaluated_at: datetime
    explanation: str


# scipy's Mann-Whitney U asymptotic approximation is unreliable below this
# per-group size; below it we rely on the bootstrap CI alone.
_MIN_GROUP_SIZE_FOR_MWU = 5


class AttributionEngine:
    """Attribute observed score changes to judge or system drift.

    Judge drift is evaluated using the anchor set, comparing the reference
    scores against the rescored values with a two-sided hypothesis.

    System drift is evaluated on production scores, comparing the candidate
    system against the production baseline with a one-sided hypothesis that
    candidate scores are lower.

    Both hypotheses are evaluated together and their p-values are subjected
    to a shared Holm-Bonferroni correction before statistical significance is
    accepted.

    Bootstrap confidence intervals are always computed and must exclude zero
    before a shift can be attributed. Mann-Whitney U is additionally used
    when both groups contain enough observations for the asymptotic
    approximation to be meaningful.

    All timestamps produced by this component are timezone-aware UTC
    datetimes, matching the repository-wide timestamp convention.
    """

    def __init__(
        self,
        alpha: float = 0.05,
        confidence_level: float = 0.95,
        n_bootstrap: int = 10000,
        seed: int | None = None,
    ) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must be strictly between 0 and 1.")

        if not 0.0 < confidence_level < 1.0:
            raise ValueError("confidence_level must be strictly between 0 and 1.")

        if n_bootstrap < 1:
            raise ValueError("n_bootstrap must be at least 1.")

        if seed is not None and seed < 0:
            raise ValueError("seed must be non-negative.")

        self.alpha = alpha
        self.confidence_level = confidence_level
        self.n_bootstrap = n_bootstrap
        self.seed = seed

    def _shift_evidence(
        self,
        baseline: list[float],
        candidate: list[float],
        *,
        alternative: str,
    ) -> tuple[float, float, str, bool]:
        """Return statistical evidence for a candidate-vs-baseline shift.

        Returns:
            A tuple containing:

            - mean delta (candidate mean - baseline mean)
            - p-value
            - statistical method used
            - whether the bootstrap confidence interval excludes zero

        For groups smaller than ``_MIN_GROUP_SIZE_FOR_MWU``, Mann-Whitney U
        is skipped and the bootstrap result is used as the sole evidence.
        """

        delta, ci_lo, ci_hi = bootstrap_delta_ci(
            candidate,
            baseline,
            confidence_level=self.confidence_level,
            n_bootstrap=self.n_bootstrap,
            seed=self.seed,
        )

        bootstrap_significant = not (ci_lo <= 0.0 <= ci_hi)

        if (
            len(baseline) >= _MIN_GROUP_SIZE_FOR_MWU
            and len(candidate) >= _MIN_GROUP_SIZE_FOR_MWU
        ):
            _, p_value = mann_whitney_regression(
                candidate,
                baseline,
                alternative=alternative,
            )
            method = "bootstrap_ci+mann_whitney"
        else:
            # There is no independent asymptotic p-value available in the
            # small-sample path. Encode the bootstrap decision so the shared
            # Holm-Bonferroni decision layer can remain unchanged.
            p_value = 0.0 if bootstrap_significant else 1.0
            method = "bootstrap_ci_only(n<5)"

        return delta, p_value, method, bootstrap_significant

    def analyze(
        self,
        anchor_set_id: str,
        anchor_ref_scores: list[float],
        anchor_rescored_scores: list[float],
        prod_baseline_scores: list[float],
        prod_candidate_scores: list[float],
    ) -> AttributionVerdict:
        """Analyze anchor and production score changes and attribute drift."""

        score_inputs = {
            "anchor_ref_scores": anchor_ref_scores,
            "anchor_rescored_scores": anchor_rescored_scores,
            "prod_baseline_scores": prod_baseline_scores,
            "prod_candidate_scores": prod_candidate_scores,
        }

        for name, scores in score_inputs.items():
            try:
                validate_scores(scores)
            except ValueError:
                return AttributionVerdict(
                    attribution=DriftAttribution.INCONCLUSIVE,
                    anchor_set_id=anchor_set_id,
                    system_score_delta=0.0,
                    judge_score_delta=0.0,
                    evaluated_at=datetime.now(timezone.utc),
                    explanation=(
                        f"Inconclusive attribution: '{name}' is empty or "
                        "contains non-finite values."
                    ),
                )

        # Judge hypothesis:
        #   H1: anchor rescored scores differ from reference scores.
        judge_delta, judge_p, judge_method, judge_boot_sig = self._shift_evidence(
            anchor_ref_scores,
            anchor_rescored_scores,
            alternative="two-sided",
        )

        # System hypothesis:
        #   H1: candidate production scores are lower than baseline scores.
        system_delta, system_p, system_method, system_boot_sig = self._shift_evidence(
            prod_baseline_scores,
            prod_candidate_scores,
            alternative="less",
        )

        # The two hypotheses are tested in the same attribution decision,
        # therefore they share one multiple-testing correction.
        corrected = holm_bonferroni(
            {
                "judge": judge_p,
                "system": system_p,
            },
            alpha=self.alpha,
        )

        has_judge_shift = corrected["judge"] and judge_boot_sig

        # Statistical evidence alone is insufficient for system regression:
        # the observed candidate-vs-baseline delta must also point downward.
        has_system_shift = (
            corrected["system"]
            and system_boot_sig
            and system_delta < 0.0
        )

        if has_judge_shift and has_system_shift:
            verdict = DriftAttribution.JOINT_DRIFT
            explanation = (
                f"Joint drift (Holm-Bonferroni corrected, alpha={self.alpha}): "
                f"anchor rescored mean shifted {judge_delta:+.4f} "
                f"({judge_method}, p={judge_p:.4g}); candidate system scores "
                f"dropped {system_delta:+.4f} "
                f"({system_method}, p={system_p:.4g})."
            )
        elif has_judge_shift:
            verdict = DriftAttribution.JUDGE_DRIFT
            explanation = (
                f"Judge drift: anchor rescored mean shifted {judge_delta:+.4f} "
                f"({judge_method}, p={judge_p:.4g}, rejected after "
                f"Holm-Bonferroni correction at alpha={self.alpha})."
            )
        elif has_system_shift:
            verdict = DriftAttribution.SYSTEM_DRIFT
            explanation = (
                f"System drift: candidate scores dropped {system_delta:+.4f} "
                f"({system_method}, p={system_p:.4g}, rejected after "
                f"Holm-Bonferroni correction at alpha={self.alpha})."
            )
        else:
            verdict = DriftAttribution.NONE
            explanation = (
                f"No statistically significant drift "
                f"(judge delta {judge_delta:+.4f}, "
                f"system delta {system_delta:+.4f}; "
                f"Holm-Bonferroni corrected at alpha={self.alpha})."
            )

        return AttributionVerdict(
            attribution=verdict,
            anchor_set_id=anchor_set_id,
            system_score_delta=system_delta,
            judge_score_delta=judge_delta,
            evaluated_at=datetime.now(timezone.utc),
            explanation=explanation,
        )
