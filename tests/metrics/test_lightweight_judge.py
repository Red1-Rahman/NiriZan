# tests/metrics/test_lightweight_judge.py
import logging
from uuid import uuid4

import pytest

from nirizan.metrics.lightweight_judge import LightweightJudge


def test_lightweight_judge_safe(caplog: pytest.LogCaptureFixture) -> None:
    judge = LightweightJudge()
    trace_id = uuid4()
    with caplog.at_level(logging.INFO):
        res = judge.evaluate_text(
            "This is a clean, helpful and friendly response.",
            trace_id=trace_id,
        )

    assert res.score == 1.0
    assert res.metric_name == "lightweight_quality_score"
    assert res.trace_id == trace_id
    assert (
        f"Evaluating LightweightJudge metric_name='lightweight_quality_score' for trace_id={trace_id}"
        in caplog.text
    )
    assert "evaluated score=1.0000" in caplog.text


def test_lightweight_judge_toxic(caplog: pytest.LogCaptureFixture) -> None:
    judge = LightweightJudge()
    trace_id = uuid4()
    with caplog.at_level(logging.INFO):
        res = judge.evaluate_text(
            "I hate this bad output!",
            trace_id=trace_id,
        )

    assert res.score < 1.0
    assert res.trace_id == trace_id
    assert (
        f"Evaluating LightweightJudge metric_name='lightweight_quality_score' for trace_id={trace_id}"
        in caplog.text
    )


def test_lightweight_judge_empty_text(caplog: pytest.LogCaptureFixture) -> None:
    judge = LightweightJudge()
    trace_id = uuid4()
    with caplog.at_level(logging.WARNING):
        res = judge.evaluate_text("   ", trace_id=trace_id)

    assert res.score == 0.0
    assert res.trace_id == trace_id
    assert (
        "Empty or whitespace-only text provided for metric_name='lightweight_quality_score'"
        in caplog.text
    )
