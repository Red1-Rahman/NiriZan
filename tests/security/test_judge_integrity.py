"""LLM judge output validation regression coverage."""

import math

import pytest

from nirizan.metrics.llm_judge import LLMJudge, LLMJudgeResponse


@pytest.mark.parametrize("completion", ['{"score": NaN}', '{"score": 150}'])
@pytest.mark.xfail(strict=True, reason="tracked: NZ-SEC-006")
def test_judge_rejects_nonfinite_or_out_of_range_scores(completion):
    # Finding NZ-SEC-006: judge accepts JSON NaN and clamps out-of-range values silently.
    judge = LLMJudge(metric_name="quality", prompt_template="{input} {output}",
                     completion_fn=lambda _: completion)
    result = judge.evaluate(input_text="x", output_text="y")
    assert math.isfinite(result.score) and 0 <= result.score <= 1
    assert result.score != 1.0


def test_evaluate_constructs_and_validates_response_model(monkeypatch):
    judge = LLMJudge(metric_name="quality", prompt_template="{input} {output}",
                     completion_fn=lambda _: '{"score": 0.5, "reasoning": "ok"}')
    constructed = []
    original = LLMJudgeResponse.model_validate
    def recording_validate(value, *args, **kwargs):
        constructed.append(value)
        return original(value, *args, **kwargs)
    monkeypatch.setattr(LLMJudgeResponse, "model_validate", classmethod(recording_validate))
    judge.evaluate(input_text="x", output_text="y")
    assert constructed, "LLMJudgeResponse remains dead/unvalidated code in evaluate()"
