# src/nirizan/gate/ci.py
from __future__ import annotations

import json
from typing import TextIO

from nirizan.gate.verdict import GateVerdict


def format_gate_summary(verdict: GateVerdict) -> str:
    lines = [
        "| Metric | Severity | P-Value | Effect Size |",
        "|---|---|---:|---:|",
    ]

    for regression in verdict.regression_verdicts:
        p_value = (
            f"{regression.p_value:.4e}"
            if regression.p_value is not None
            else "n/a"
        )

        effect_size = (
            f"{regression.effect_size:.3f}"
            if regression.effect_size is not None
            else "n/a"
        )

        lines.append(
            f"| {regression.metric_name} "
            f"| {regression.severity.value} "
            f"| {p_value} "
            f"| {effect_size} |"
        )

    lines.append("")
    lines.append(
        f"**Gate:** {'PASS' if verdict.passed else 'BLOCK'}"
    )
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
    output.write(format_gate_summary(verdict))
    output.write("\n")


def gate_exit_code(verdict: GateVerdict) -> int:
    return 0 if verdict.passed else 1


def serialize_gate_verdict(verdict: GateVerdict) -> str:
    return json.dumps(
        verdict.model_dump(mode="json"),
        indent=2,
    )
