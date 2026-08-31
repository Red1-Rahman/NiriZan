# src/nirizan/trust/__init__.py
"""
NiriZan trust package.

Description
-----------
Provides trust and attribution primitives for distinguishing changes in an
evaluated AI system from changes in the evaluator or judge. Includes
human-labeled anchor items, persistent anchor sets, drift attribution
verdicts, and the attribution engine used to analyze score shifts across
reference, rescored, baseline, and candidate evaluations.

Anchor sets provide fixed evaluation inputs with expected outputs and human
labels. The attribution engine compares anchor score changes with production
score changes to classify observed drift as system drift, judge drift, or no
detected drift.

Project
-------
NiriZan — Continuous Evaluation Infrastructure for Production AI

Keywords
--------
AI evaluation trust, evaluation trustworthiness, evaluation attribution,
drift attribution, judge drift, evaluator drift, system drift,
judge drift detection, system drift detection, behavioral anchors,
anchor sets, evaluation anchors, human-labeled anchors, human evaluation,
reference evaluation, anchor rescoring, score shift attribution,
evaluation stability, evaluator reliability, attribution verdicts,
AI evaluation reliability, production AI trust

Author
------
Redwan Rahman

License
-------
GPL-3.0-or-later

Citation
--------
Rahman, R. NiriZan (Version 0.3.0) [Computer software].
https://github.com/Red1-Rahman/NiriZan

BibTeX
------
@software{Rahman_NiriZan,
  author = {Rahman, Redwan},
  license = {GPL-3.0-or-later},
  title = {{NiriZan}},
  url = {https://github.com/Red1-Rahman/NiriZan},
  version = {0.3.0}
}
"""
