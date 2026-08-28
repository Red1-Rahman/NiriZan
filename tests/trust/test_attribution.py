# tests/trust/test_attribution.py
from __future__ import annotations

import numpy as np
import pytest
from nirizan.trust.attribution import (
    AttributionEngine,
    DriftAttribution,
)


@pytest.fixture
def engine() -> AttributionEngine:
    return AttributionEngine(significance_threshold=0.05)


def test_attribution_no_drift(engine: AttributionEngine) -> None:
    ref_scores = [0.90, 0.90, 0.90, 0.90]
    rescored = [0.90, 0.90, 0.90, 0.90]
    baseline = [0.90, 0.90, 0.90, 0.90]
    candidate = [0.90, 0.90, 0.90, 0.90]

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=ref_scores,
        anchor_rescored_scores=rescored,
        prod_baseline_scores=baseline,
        prod_candidate_scores=candidate,
    )

    assert verdict.attribution == DriftAttribution.NONE
    assert verdict.anchor_set_id == "anchor-v1"
    assert abs(verdict.system_score_delta) < 0.001
    assert abs(verdict.judge_score_delta) < 0.001
    assert len(verdict.explanation) > 0


def test_attribution_system_drift(engine: AttributionEngine) -> None:
    ref_scores = [0.90, 0.90, 0.90]
    rescored = [0.90, 0.90, 0.91]
    baseline = [0.90, 0.90, 0.91]
    candidate = [0.68, 0.68, 0.68]

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=ref_scores,
        anchor_rescored_scores=rescored,
        prod_baseline_scores=baseline,
        prod_candidate_scores=candidate,
    )

    assert verdict.attribution == DriftAttribution.SYSTEM_DRIFT
    assert verdict.system_score_delta < -0.10
    assert abs(verdict.judge_score_delta) < 0.05
    assert "System drift detected" in verdict.explanation


def test_attribution_judge_drift(engine: AttributionEngine) -> None:
    ref_scores = [0.90, 0.90, 0.90]
    rescored = [0.70, 0.70, 0.70]
    baseline = [0.90, 0.90, 0.90]
    candidate = [0.89, 0.90, 0.88]

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=ref_scores,
        anchor_rescored_scores=rescored,
        prod_baseline_scores=baseline,
        prod_candidate_scores=candidate,
    )

    assert verdict.attribution == DriftAttribution.JUDGE_DRIFT
    assert verdict.judge_score_delta < -0.10
    assert abs(verdict.system_score_delta) < 0.05
    assert "Judge drift detected" in verdict.explanation


def test_attribution_joint_drift(engine: AttributionEngine) -> None:
    ref_scores = [0.90, 0.90, 0.90]
    rescored = [0.70, 0.70, 0.70]
    baseline = [0.90, 0.90, 0.91]
    candidate = [0.68, 0.68, 0.68]

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=ref_scores,
        anchor_rescored_scores=rescored,
        prod_baseline_scores=baseline,
        prod_candidate_scores=candidate,
    )

    assert verdict.attribution == DriftAttribution.JOINT_DRIFT
    assert verdict.judge_score_delta < -0.10
    assert verdict.system_score_delta < -0.10
    assert "Joint drift detected" in verdict.explanation


def test_attribution_inconclusive_empty(engine: AttributionEngine) -> None:
    scores = [0.90, 0.90, 0.90]

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=[],
        anchor_rescored_scores=scores,
        prod_baseline_scores=scores,
        prod_candidate_scores=scores,
    )

    assert verdict.attribution == DriftAttribution.INCONCLUSIVE
    assert verdict.system_score_delta == 0.0
    assert verdict.judge_score_delta == 0.0
    assert "Inconclusive attribution" in verdict.explanation


def test_attribution_inconclusive_nan(engine: AttributionEngine) -> None:
    ref_scores = [0.90, np.nan, 0.90]
    scores = [0.90, 0.90, 0.90]

    verdict = engine.analyze(
        anchor_set_id="anchor-v1",
        anchor_ref_scores=ref_scores,
        anchor_rescored_scores=scores,
        prod_baseline_scores=scores,
        prod_candidate_scores=scores,
    )

    assert verdict.attribution == DriftAttribution.INCONCLUSIVE
    assert verdict.system_score_delta == 0.0
    assert verdict.judge_score_delta == 0.0
    assert "non-finite values" in verdict.explanation
