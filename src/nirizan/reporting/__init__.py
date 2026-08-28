# src/nirizan/reporting
"""
NiriZan reporting package.

Description
-----------
Provides quality reporting and human-auditable summaries for continuously
evaluated AI systems. Includes System Health Score computation, longitudinal
Judge Reliability metrics, judge and system drift time series, and
DashboardSnapshot aggregation across attribution, regression, and deployment
gate signals.

The reporting layer combines upstream evaluation signals into structured
reporting data without depending on a particular presentation interface.
Dashboard snapshots can therefore be consumed by CLIs, notebooks, monitoring
interfaces, or future web dashboards.

Project
-------
NiriZan — Continuous Evaluation Infrastructure for Production AI

Keywords
--------
AI quality reporting, AI evaluation reporting, evaluation dashboard,
evaluation dashboard data, system health score, AI health score,
quality health score, judge reliability, evaluator reliability,
judge reliability metrics, judge drift rate, system drift rate,
judge score delta, system score delta, drift time series,
evaluation drift reporting, attribution reporting, regression reporting,
regression verdict reporting, deployment gate reporting,
dashboard snapshot, evaluation snapshot, longitudinal evaluation,
evaluation trend analysis, calibration error, calibration MAE,
human-auditable AI evaluation, continuous evaluation reporting,
production AI quality monitoring

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
