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
    """Distinguishes judge drift from system drift using statistical evidence
    (bootstrap confidence intervals, corroborated by a Mann-Whitney U test
    when sample size allows) rather than a raw mean-difference threshold.

    Two hypotheses are evaluated per call -- "did the judge shift?" and "did
    the system regress?" -- so a Holm-Bonferroni correction is applied across
    them before either is treated as significant, reusing the same
    correction NiriZan's regression gate already relies on.
    """

    def __init__(
        self,
        alpha: float = 0.05,
        confidence_level: float = 0.95,
        n_bootstrap: int = 10000,
        seed: int | None = None,
    ) -> None:
        if not (0.0 < alpha < 1.0):
            raise ValueError("alpha must be strictly between 0 and 1.")
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
        """Return (delta, p_value, method, bootstrap_significant) for whether
        `candidate` differs from `baseline`.
        """
        delta, ci_lo, ci_hi = bootstrap_delta_ci(
            candidate,
            baseline,
            confidence_level=self.confidence_level,
            n_bootstrap=self.n_bootstrap,
            seed=self.seed,
        )
        bootstrap_significant = not (ci_lo <= 0.0 <= ci_hi)

        if len(baseline) >= _MIN_GROUP_SIZE_FOR_MWU and len(candidate) >= _MIN_GROUP_SIZE_FOR_MWU:
            _, p_value = mann_whitney_regression(candidate, baseline, alternative=alternative)
            method = "bootstrap_ci+mann_whitney"
        else:
            # Small-sample fallback (n < 5 in either group): skip Mann-Whitney
            # rather than misapply it, and let the bootstrap CI's own
            # (necessarily wider, more conservative) result stand alone.
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

        judge_delta, judge_p, judge_method, judge_boot_sig = self._shift_evidence(
            anchor_ref_scores, anchor_rescored_scores, alternative="two-sided"
        )
        system_delta, system_p, system_method, system_boot_sig = self._shift_evidence(
            prod_baseline_scores, prod_candidate_scores, alternative="less"
        )

        corrected = holm_bonferroni({"judge": judge_p, "system": system_p}, alpha=self.alpha)

        has_judge_shift = corrected["judge"] and judge_boot_sig
        has_system_shift = corrected["system"] and system_boot_sig and system_delta < 0

        if has_judge_shift and has_system_shift:
            verdict = DriftAttribution.JOINT_DRIFT
            exp = (
                f"Joint drift (Holm-Bonferroni corrected, alpha={self.alpha}): "
                f"anchor rescored mean shifted {judge_delta:+.4f} "
                f"({judge_method}, p={judge_p:.4g}); candidate system scores "
                f"dropped {system_delta:+.4f} ({system_method}, p={system_p:.4g})."
            )
        elif has_judge_shift:
            verdict = DriftAttribution.JUDGE_DRIFT
            exp = (
                f"Judge drift: anchor rescored mean shifted {judge_delta:+.4f} "
                f"({judge_method}, corrected p={judge_p:.4g} < alpha={self.alpha})."
            )
        elif has_system_shift:
            verdict = DriftAttribution.SYSTEM_DRIFT
            exp = (
                f"System drift: candidate scores dropped {system_delta:+.4f} "
                f"({system_method}, corrected p={system_p:.4g} < alpha={self.alpha})."
            )
        else:
            verdict = DriftAttribution.NONE
            exp = (
                f"No statistically significant drift (judge delta "
                f"{judge_delta:+.4f}, system delta {system_delta:+.4f}; "
                f"Holm-Bonferroni corrected at alpha={self.alpha})."
            )

        return AttributionVerdict(
            attribution=verdict,
            anchor_set_id=anchor_set_id,
            system_score_delta=system_delta,
            judge_score_delta=judge_delta,
            evaluated_at=datetime.now(timezone.utc),
            explanation=exp,
        )
