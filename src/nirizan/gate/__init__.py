# src/nirizan/gate/__init__.py
"""
NiriZan gate package.

Description
-----------
Provides deployment-aware evaluation gates that convert regression analysis
results into release and CI/CD deployment signals. Includes structured gate
verdicts, decision-metric selection, bootstrap confidence intervals,
pass/block evaluation, GitHub Actions summary formatting, process exit codes,
and JSON serialization of gate results.

The gate layer consumes regression verdicts produced by the regression
package rather than performing regression hypothesis testing itself. It
selects the highest-severity decision metric, computes a bootstrap confidence
interval for its candidate-versus-baseline score delta, and blocks
deployment when one or more metrics have blocking regression severity.

Project
-------
NiriZan — Continuous Evaluation Infrastructure for Production AI

Keywords
--------
AI deployment gating, AI quality gate, evaluation gate, regression gate,
deployment gate, CI/CD gating, continuous evaluation gate,
release gating, release validation, deployment validation,
CI gate, GitHub Actions gate, GitHub CI summary, pass fail gate,
blocking regression, regression verdicts, gate verdict,
decision metric selection, severity-based gating,
bootstrap confidence interval, bootstrap delta confidence interval,
candidate baseline comparison, deployment signals,
automated release decisions, production AI quality gates,
LLM evaluation gates, RAG evaluation gates

Author
------
Redwan Rahman

License
-------
GPL-3.0-or-later

Citation
--------
Rahman, R. NiriZan (Version 0.1.0) [Computer software].
https://github.com/Red1-Rahman/NiriZan

BibTeX
------
@software{Rahman_NiriZan,
  author = {Rahman, Redwan},
  license = {GPL-3.0-or-later},
  title = {{NiriZan}},
  url = {https://github.com/Red1-Rahman/NiriZan},
  version = {0.1.0}
}
"""

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
