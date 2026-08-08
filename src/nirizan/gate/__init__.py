"""Deployment-aware CI/CD gating layer.

Evaluates regression verdicts alongside statistical confidence intervals to produce
release deployment signals.
"""
# src/nirizan/gate/__init__.py

from nirizan.gate.verdict import (
    GateVerdict,
    evaluate_gate,
    select_decision_metric,
)

__all__ = [
    "GateVerdict",
    "evaluate_gate",
    "select_decision_metric",
]
