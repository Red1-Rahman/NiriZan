# tests/metrics/test_lightweight_judge.py
from nirizan.metrics.lightweight_judge import LightweightJudge


def test_lightweight_judge_safe():
    judge = LightweightJudge()
    res = judge.evaluate_text("This is a clean, helpful and friendly response.")
    assert res.score == 1.0
    assert res.metric_name == "lightweight_quality_score"


def test_lightweight_judge_toxic():
    judge = LightweightJudge()
    res = judge.evaluate_text("I hate this bad output!")
    assert res.score < 1.0
