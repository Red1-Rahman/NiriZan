# src/nirizan/metrics/llm_judge.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from nirizan._logging import get_logger
from nirizan.metrics.base import MetricResult

logger = get_logger(__name__)


class LLMJudgeResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    score: float = Field(ge=0.0, le=1.0)
    reasoning: str


class LLMJudge(BaseModel):
    """Prompted LLM-as-judge metric evaluator."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    metric_name: str
    prompt_template: str
    completion_fn: Callable[[str], str]

    def _build_prompt(self, input_text: str, output_text: str, context: str | None = None) -> str:
        return self.prompt_template.format(
            input=input_text,
            output=output_text,
            context=context or "",
        )

    def evaluate(
        self,
        *,
        input_text: str,
        output_text: str,
        context: str | None = None,
        trace_id: UUID | None = None,
    ) -> MetricResult:
        actual_trace_id = trace_id or uuid4()
        logger.info(
            "Evaluating LLMJudge metric_name='%s' for trace_id=%s",
            self.metric_name,
            actual_trace_id,
        )

        prompt = self._build_prompt(input_text, output_text, context)
        logger.debug("Prompt built for metric_name='%s': %s", self.metric_name, prompt)

        raw_completion = self.completion_fn(prompt)

        try:
            parsed = json.loads(raw_completion)
            score = float(parsed["score"])
            reasoning = str(parsed.get("reasoning", ""))
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning(
                "Failed to parse LLMJudge output for metric_name='%s': %s (error: %s)",
                self.metric_name,
                raw_completion[:100],
                exc,
            )
            score = 0.0
            reasoning = f"Failed to parse judge output: {raw_completion[:100]}"

        score = max(0.0, min(1.0, score))

        logger.info(
            "LLMJudge metric_name='%s' evaluated score=%.4f for trace_id=%s",
            self.metric_name,
            score,
            actual_trace_id,
        )

        return MetricResult(
            metric_name=self.metric_name,
            trace_id=actual_trace_id,
            score=score,
            computed_at=datetime.now(timezone.utc),
            details={"reasoning": reasoning, "prompt": prompt},
        )
