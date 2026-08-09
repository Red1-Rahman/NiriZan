# src/nirizan/reporting/health_score.py
from __future__ import annotations

from nirizan.trust.attribution import DriftAttribution


def compute_system_health_score(
    quality_score: float,
    confidence: float,
    attribution: DriftAttribution,
) -> float:
    """Computes composite System Health Score on a 0-100 scale."""
    base_score = quality_score * confidence * 100.0

    penalty_multipliers = {
        DriftAttribution.NONE: 1.00,
        DriftAttribution.JUDGE_DRIFT: 0.90,
        DriftAttribution.SYSTEM_DRIFT: 0.80,
    }

    multiplier = penalty_multipliers.get(attribution, 0.70)
    return round(base_score * multiplier, 1)
