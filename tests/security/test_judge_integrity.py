# tests/security/test_judge_integrity.py
"""LLM judge output validation regression coverage."""

import pytest

from nirizan.metrics.llm_judge import LLMJudge, LLMJudgeResponse


@pytest.mark.parametrize("completion", ['{"score": NaN}', '{"score": 150}'])
@pytest.mark.xfail(strict=True, reason="tracked: NZ-SEC-006")
def test_judge_rejects_nonfinite_or_out_of_range_scores(completion):
    # Finding NZ-SEC-006: judge accepts JSON NaN and clamps out-of-range
    # values silently.
    #
    # Require an explicit invalid-result signal, not merely "any finite score
    # that isn't exactly 1.0". If the fix instead silently clamps both bad
    # inputs to 0.0, that is still a fabricated result presented as a real
    # evaluation and should NOT satisfy this test -- a 0.0 "quality" score
    # for a malformed judge response is as misleading as a clamped 1.0,
    # just in the opposite direction on the gate. The fix is expected to
    # either raise, or return a result that is distinguishably marked
    # invalid (e.g. a None score, an error field, or a raised
    # LLMJudgeResponse validation error) so callers can tell "judge said 0"
    # from "judge response was garbage".
    judge = LLMJudge(
        metric_name="quality",
        prompt_template="{input} {output}",
        completion_fn=lambda _: completion,
    )
    raised_or_marked_invalid = False
    try:
        result = judge.evaluate(input_text="x", output_text="y")
    except Exception:
        raised_or_marked_invalid = True
    else:
        # Accept any explicit invalidity signal the eventual fix chooses to
        # expose; adjust this once NZ-SEC-006's result contract is decided.
        raised_or_marked_invalid = (
            getattr(result, "score", None) is None or getattr(result, "is_valid", True) is False
        )

    assert raised_or_marked_invalid, (
        "judge.evaluate() must reject or explicitly flag a non-finite/"
        "out-of-range score rather than silently returning a plausible-"
        "looking numeric result"
    )


@pytest.mark.xfail(strict=True, reason="tracked: NZ-SEC-006b")
def test_evaluate_constructs_and_validates_response_model(monkeypatch):
    # Finding NZ-SEC-006b: LLMJudgeResponse exists but evaluate() never
    # constructs or validates against it, so malformed completions bypass
    # whatever validation the model defines.
    judge = LLMJudge(
        metric_name="quality",
        prompt_template="{input} {output}",
        completion_fn=lambda _: '{"score": 0.5, "reasoning": "ok"}',
    )
    constructed = []
    original = LLMJudgeResponse.model_validate

    def recording_validate(value, *args, **kwargs):
        constructed.append(value)
        return original(value, *args, **kwargs)

    monkeypatch.setattr(LLMJudgeResponse, "model_validate", classmethod(recording_validate))
    judge.evaluate(input_text="x", output_text="y")
    assert constructed, "LLMJudgeResponse remains dead/unvalidated code in evaluate()"
