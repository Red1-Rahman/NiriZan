# src/nirizan/regression/__init__.py
"""
NiriZan regression package.

Description
-----------
Provides statistical regression detection for comparing candidate evaluation
results against historical baselines. Includes baseline comparison,
Mann-Whitney U testing for detecting lower candidate scores, Cohen's d effect
size estimation, mean score deltas, regression severity classification,
p-value correction using Holm-Bonferroni, and structured regression verdicts.

The regression layer validates metric-score distributions before statistical
analysis and evaluates both statistical significance and effect-size
thresholds to classify regressions as none, warning, or blocking. When
multiple metrics are compared together, Holm-Bonferroni correction is applied
to control the family-wise error rate across the metric decision family.

Project
-------
NiriZan — Continuous Evaluation Infrastructure for Production AI

Keywords
--------
AI regression detection, evaluation regression detection, LLM regression
testing, RAG regression testing, baseline comparison, evaluation baselines,
metric regression, statistical regression testing, Mann-Whitney U test,
Mann-Whitney regression test, Cohen's d, effect size, mean score delta,
regression severity, blocking regression, warning regression,
regression verdict, statistical significance, p-value correction,
Holm-Bonferroni correction, multiple comparisons, family-wise error rate,
metric score validation, candidate baseline comparison, quality regression,
production AI regression testing, evaluation quality gates

Author
------
Redwan Rahman

License
-------
GPL-3.0-or-later

Citation
--------
Rahman, R. NiriZan (Version 0.2.0) [Computer software].
https://github.com/Red1-Rahman/NiriZan

BibTeX
------
@software{Rahman_NiriZan,
  author = {Rahman, Redwan},
  license = {GPL-3.0-or-later},
  title = {{NiriZan}},
  url = {https://github.com/Red1-Rahman/NiriZan},
  version = {0.2.0}
}
"""

from nirizan.regression.comparator import (
    BaselineComparator,
    RegressionSeverity,
    RegressionVerdict,
    classify_severity,
    cohens_d,
    mean_delta,
)

__all__ = [
    "BaselineComparator",
    "RegressionSeverity",
    "RegressionVerdict",
    "classify_severity",
    "cohens_d",
    "mean_delta",
]
