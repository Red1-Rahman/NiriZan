# src/nirizan/gate/ci.py
"""CI-facing formatting and exit-code helpers for gate verdicts.

The summary renders two tables when both tracks produced verdicts: the
univariate table first (one row per metric, the primary decision signal)
and the structure track table second (one row per multivariate method).
When ``multivariate_verdicts`` is empty, the structure table is omitted
entirely, so the output is byte-identical to the pre-multivariate-track
behavior for callers that do not run the structure track.
"""

from __future__ import annotations

import json
from typing import TextIO

from nirizan._logging import get_logger
from nirizan.gate.verdict import GateVerdict

logger = get_logger(__name__)


def format_gate_summary(verdict: GateVerdict) -> str:
    lines = [
        "| Metric | Severity | P-Value | Effect Size |",
        "|---|---|---:|---:|",
    ]

    for regression in verdict.regression_verdicts:
        p_value = f"{regression.p_value:.4e}" if regression.p_value is not None else "n/a"
        effect_size = (
            f"{regression.effect_size:.3f}" if regression.effect_size is not None else "n/a"
        )
        lines.append(
            f"| {regression.metric_name} "
            f"| {regression.severity.value} "
            f"| {p_value} "
            f"| {effect_size} |"
        )

    # Structure track table, rendered only when verdicts are present so
    # callers that do not run the multivariate track see unchanged output.
    if verdict.multivariate_verdicts:
        lines.append("")
        lines.append("**Structure track (multivariate):**")
        lines.append("")
        lines.append("| Method | Severity | P-Value | Effect Size | Inconclusive |")
        lines.append("|---|---|---:|---:|:---:|")
        for mv in verdict.multivariate_verdicts:
            inconclusive = "yes" if mv.inconclusive else "no"
            lines.append(
                f"| {mv.method.value} "
                f"| {mv.severity.value} "
                f"| {mv.p_value:.4e} "
                f"| {mv.effect_size:.3f} "
                f"| {inconclusive} |"
            )

    lines.append("")
    lines.append(f"**Gate:** {'PASS' if verdict.passed else 'BLOCK'}")
    lines.append(
        "**95% bootstrap CI:** "
        f"`{verdict.confidence_interval[0]:.6f}, "
        f"{verdict.confidence_interval[1]:.6f}`"
    )

    return "\n".join(lines)


def write_github_summary(
    verdict: GateVerdict,
    *,
    output: TextIO,
) -> None:
    logger.info(
        "Writing GitHub CI summary for run_id=%s (passed=%s, "
        "univariate_verdicts=%d, multivariate_verdicts=%d)",
        verdict.run_id,
        verdict.passed,
        len(verdict.regression_verdicts),
        len(verdict.multivariate_verdicts),
    )
    output.write(format_gate_summary(verdict))
    output.write("\n")


def gate_exit_code(verdict: GateVerdict) -> int:
    if verdict.passed:
        logger.info("CI Gate PASSED for run_id=%s", verdict.run_id)
        return 0
    logger.error("CI Gate BLOCKED for run_id=%s", verdict.run_id)
    return 1


def serialize_gate_verdict(verdict: GateVerdict) -> str:
    logger.debug("Serializing GateVerdict for run_id=%s", verdict.run_id)
    return json.dumps(
        verdict.model_dump(mode="json"),
        indent=2,
    )
