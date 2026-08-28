# src/nirizan/trust/attribution.py
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import numpy as np
from pydantic import BaseModel, ConfigDict


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


class AttributionEngine:
    def __init__(self, significance_threshold: float = 0.05):
        self.significance_threshold = significance_threshold

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
            if not scores or not all(np.isfinite(x) for x in scores):
                return AttributionVerdict(
                    attribution=DriftAttribution.INCONCLUSIVE,
                    anchor_set_id=anchor_set_id,
                    system_score_delta=0.0,
                    judge_score_delta=0.0,
                    evaluated_at=datetime.now(timezone.utc),
                    explanation=f"Inconclusive attribution: '{name}' is empty or contains non-finite values.",
                )

        anchor_ref_mean = float(np.mean(anchor_ref_scores))
        anchor_rescored_mean = float(np.mean(anchor_rescored_scores))
        prod_baseline_mean = float(np.mean(prod_baseline_scores))
        prod_candidate_mean = float(np.mean(prod_candidate_scores))

        judge_delta = anchor_rescored_mean - anchor_ref_mean
        system_delta = prod_candidate_mean - prod_baseline_mean

        has_judge_shift = abs(judge_delta) >= self.significance_threshold
        has_system_shift = abs(system_delta) >= self.significance_threshold and system_delta < 0

        if has_judge_shift and has_system_shift:
            verdict = DriftAttribution.JOINT_DRIFT
            exp = (
                f"Joint drift detected: Anchor rescored mean shifted by {judge_delta:+.4f} "
                f"and candidate system scores dropped by {system_delta:+.4f}."
            )
        elif has_judge_shift:
            verdict = DriftAttribution.JUDGE_DRIFT
            exp = f"Judge drift detected: Anchor rescored mean shifted by {judge_delta:+.4f}."
        elif has_system_shift:
            verdict = DriftAttribution.SYSTEM_DRIFT
            exp = f"System drift detected: Candidate scores dropped by {system_delta:+.4f}."
        else:
            verdict = DriftAttribution.NONE
            exp = "No statistically significant system or judge drift detected."

        return AttributionVerdict(
            attribution=verdict,
            anchor_set_id=anchor_set_id,
            system_score_delta=system_delta,
            judge_score_delta=judge_delta,
            evaluated_at=datetime.now(timezone.utc),
            explanation=exp,
        )
