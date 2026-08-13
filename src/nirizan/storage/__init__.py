# src/nirizan/storage/__init__.py
"""
NiriZan storage package.

Description
-----------
Provides persistence interfaces, storage models, and concrete repositories
for traces, spans, evaluation runs, baselines, experiment history, and
sessions. Includes SQLite-backed persistence for traces, baselines, and
experiment runs, as well as lightweight in-memory repositories for runs and
sessions.

The package separates public domain models from storage representations.
Trace and span records provide serialization boundaries for SQLite persistence,
while repository protocols and interfaces expose asynchronous storage
operations to the rest of the evaluation pipeline.

Project
-------
NiriZan — Continuous Evaluation Infrastructure for Production AI

Keywords
--------
AI evaluation storage, evaluation persistence, trace storage, trace repository,
span storage, span persistence, run repository, experiment store,
experiment history, baseline repository, evaluation baselines,
session repository, SQLite persistence, asynchronous SQLite,
in-memory repository, trace serialization, span serialization,
run persistence, metric result persistence, evaluation data storage,
AI observability storage, historical evaluation runs, repository interfaces

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
