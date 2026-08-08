# tests/metrics/test_llm_judge.py
import logging
from uuid import uuid4

import pytest
from nirizan.metrics.llm_judge import LLMJudge


def dummy_completion(prompt: str) -> str:
    return '{"score": 0.85, "reasoning": "Output aligns with input."}'


def dummy_bad_completion(prompt: str) -> str:
    return "invalid json output"


def test_llm_judge_evaluation(caplog: pytest.LogCaptureFixture) -> None:
    judge = LLMJudge(
        metric_name="groundedness",
        prompt_template="Input: {input}, Output: {output}",
        completion_fn=dummy_completion,
    )

    trace_id = uuid4()
    with caplog.at_level(logging.INFO):
        res = judge.evaluate(
            input_text="Sky color?",
            output_text="Blue",
            trace_id=trace_id,
        )

    assert res.score == 0.85
    assert res.metric_name == "groundedness"
    assert res.details["reasoning"] == "Output aligns with input."
    assert f"Evaluating LLMJudge metric_name='groundedness' for trace_id={trace_id}" in caplog.text
    assert "evaluated score=0.8500" in caplog.text


def test_llm_judge_parse_failure_logging(caplog: pytest.LogCaptureFixture) -> None:
    judge = LLMJudge(
        metric_name="groundedness",
        prompt_template="Input: {input}, Output: {output}",
        completion_fn=dummy_bad_completion,
    )

    trace_id = uuid4()
    with caplog.at_level(logging.WARNING):
        res = judge.evaluate(
            input_text="Sky color?",
            output_text="Blue",
            trace_id=trace_id,
        )

    assert res.score == 0.0
    assert "Failed to parse judge output" in str(res.details["reasoning"])
    assert "Failed to parse LLMJudge output for metric_name='groundedness'" in caplog.text
