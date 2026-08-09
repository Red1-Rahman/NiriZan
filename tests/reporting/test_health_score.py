# tests/reporting/test_health_score.py
import pytest
from nirizan.reporting.health_score import compute_system_health_score
from nirizan.trust.attribution import DriftAttribution


def test_health_score_no_drift():
    # Base quality = 0.90, confidence = 0.95 -> 0.90 * 0.95 * 100 * 1.0 = 85.5
    score = compute_system_health_score(
        quality_score=0.90,
        confidence=0.95,
        attribution=DriftAttribution.NONE,
    )
    assert score == 85.5


def test_health_score_judge_drift_penalty():
    # Base = 85.5 * 0.90 = 76.95 -> rounded to 77.0
    score = compute_system_health_score(
        quality_score=0.90,
        confidence=0.95,
        attribution=DriftAttribution.JUDGE_DRIFT,
    )
    assert score == 77.0


def test_health_score_system_drift_penalty():
    # Base = 85.5 * 0.80 = 68.4
    score = compute_system_health_score(
        quality_score=0.90,
        confidence=0.95,
        attribution=DriftAttribution.SYSTEM_DRIFT,
    )
    assert score == 68.4


def test_health_score_bounds_and_rounding():
    score_max = compute_system_health_score(
        quality_score=1.0,
        confidence=1.0,
        attribution=DriftAttribution.NONE,
    )
    assert score_max == 100.0

    score_min = compute_system_health_score(
        quality_score=0.0,
        confidence=0.0,
        attribution=DriftAttribution.SYSTEM_DRIFT,
    )
    assert score_min == 0.0
