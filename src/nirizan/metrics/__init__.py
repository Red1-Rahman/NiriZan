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
production AI evaluation

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
