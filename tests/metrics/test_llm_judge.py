# tests/metrics/test_llm_judge.py
from nirizan.metrics.llm_judge import LLMJudge


def dummy_completion(prompt: str) -> str:
    return '{"score": 0.85, "reasoning": "Output aligns with input."}'


def test_llm_judge_evaluation():
    judge = LLMJudge(
        metric_name="groundedness",
        prompt_template="Input: {input}, Output: {output}",
        completion_fn=dummy_completion,
    )

    res = judge.evaluate(input_text="Sky color?", output_text="Blue")
    assert res.score == 0.85
    assert res.metric_name == "groundedness"
    assert res.metadata["reasoning"] == "Output aligns with input."
