# src/nirizan/metrics/__init__.py
"""
NiriZan metrics package.

Description
-----------
Provides metric models, scoring protocols, concrete evaluation methods, and
statistical utilities for assessing production AI system quality. Includes
RAG Triad scoring, behavioral anchor similarity, lightweight classifier
judging, LLM-as-judge evaluation, score validation, regression statistics,
bootstrap confidence intervals, Holm-Bonferroni correction, sample-size
estimation, and gold-set calibration.

The package supports both trace-scoped metrics and text-scoped judge
evaluators. Trace-scoped metrics consume NiriZan instrumentation traces,
while lightweight and LLM judges provide directly callable text evaluation
interfaces.

Package-level statistical surface
---------------------------------
The package re-exports two layers of statistics:

* **Canonical primitives** from ``nirizan.metrics.stats``: ``bootstrap_delta_ci``,
  ``cohens_d``, ``validate_score_matrix``, the permutation engine
  (``permutation_test`` / ``permutation_p_value``), and the two multivariate
  structure statistics (``scale_logvar_statistic``, ``dependence_max_t_statistic``
  and their test variants). These are the shapes that downstream code should
  integrate against.
* **Logging-wrapped gating entry points** from
  ``nirizan.metrics.statistical_gating``: ``approximate_sample_size``,
  ``calibrate_gold_set``, ``holm_bonferroni``, ``mann_whitney_regression``,
  ``validate_scores``. These wrap the canonical primitives and emit INFO-level
  log lines describing each statistical decision.

Note on ``bootstrap_delta_ci``: the package-level name refers to the
**canonical 3-tuple** version from ``nirizan.metrics.stats``
(``(delta_hat, ci_lower, ci_upper)``), not the deprecated 2-tuple shim in
``statistical_gating``. Callers that need the 2-tuple shape must import
``nirizan.metrics.statistical_gating.bootstrap_delta_ci`` explicitly.

Project
-------
NiriZan — Continuous Evaluation Infrastructure for Production AI

Keywords
--------
AI evaluation, LLM evaluation, RAG evaluation, RAG Triad, context relevance,
groundedness, answer relevance, LLM-as-a-judge, LLM judge, lightweight judge,
classifier evaluation, behavioral anchors, semantic similarity,
AI quality metrics, metric scoring, statistical gating, regression detection,
Mann-Whitney U test, bootstrap confidence intervals, Holm-Bonferroni,
gold-set calibration, sample size estimation, evaluation statistics,
permutation tests, multivariate structure testing,
production AI evaluation

Author
------
Redwan Rahman

License
-------
Apache-2.0

Citation
--------
Rahman, R. NiriZan (Version 0.4.0) [Computer software].
https://github.com/Red1-Rahman/NiriZan

BibTeX
------
@software{Rahman_NiriZan,
  author = {Rahman, Redwan},
  license = {Apache-2.0},
  title = {{NiriZan}},
  url = {https://github.com/Red1-Rahman/NiriZan},
  version = {0.4.0}
}
"""

from nirizan.metrics.statistical_gating import (
    approximate_sample_size,
    calibrate_gold_set,
    holm_bonferroni,
    mann_whitney_regression,
    validate_scores,
)
from nirizan.metrics.stats import (
    bootstrap_delta_ci,
    calculate_bootstrap_ci,
    calculate_sample_size,
    cohens_d,
    compute_calibration_metrics,
    compute_holm_bonferroni,
    compute_mann_whitney_u,
    dependence_max_t_statistic,
    dependence_max_t_test,
    permutation_p_value,
    permutation_test,
    scale_logvar_statistic,
    scale_logvar_test,
    validate_score_matrix,
)

__all__ = [
    # Logging-wrapped gating & evaluation routines (from statistical_gating)
    "approximate_sample_size",
    "calibrate_gold_set",
    "holm_bonferroni",
    "mann_whitney_regression",
    "validate_scores",
    # Canonical statistical primitives (from stats)
    "bootstrap_delta_ci",  # 3-tuple: (delta_hat, ci_lower, ci_upper)
    "calculate_bootstrap_ci",  # backward-compat alias for bootstrap_delta_ci
    "calculate_sample_size",
    "cohens_d",
    "compute_calibration_metrics",
    "compute_holm_bonferroni",
    "compute_mann_whitney_u",
    # Permutation-test engine
    "permutation_p_value",
    "permutation_test",
    # Multivariate structure-track statistics
    "dependence_max_t_statistic",
    "dependence_max_t_test",
    "scale_logvar_statistic",
    "scale_logvar_test",
    # Matrix validation for the structure track
    "validate_score_matrix",
]
