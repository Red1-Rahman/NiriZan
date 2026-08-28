# src/nirizan/orchestrator/__init__.py
"""
NiriZan orchestrator package.

Description
-----------
Coordinates trace ingestion, asynchronous persistence, metric execution, and
on-demand evaluation runs. Provides a background TraceCollector for buffering
and persisting incoming traces, a CollectorExporter adapter for connecting
instrumentation exporters to the collector, a MetricDispatcher for routing
traces to explicitly registered metrics, and a RunScheduler for triggering
evaluation runs against stored traces.

The orchestrator uses narrow local protocols for trace and run persistence,
keeping execution coordination decoupled from concrete storage
implementations. Trace ingestion can attach the current Git commit and data
snapshot metadata before persistence, while evaluation results are assembled
into versioned Run models for downstream storage and regression analysis.

Project
-------
NiriZan — Continuous Evaluation Infrastructure for Production AI

Keywords
--------
AI evaluation orchestration, evaluation orchestration, trace ingestion,
trace collection, asynchronous trace processing, background trace worker,
trace buffering, trace persistence, metric dispatch, metric dispatcher,
metric registration, evaluation scheduling, evaluation runs,
on-demand evaluation, evaluation pipeline, trace routing,
metric execution, collector exporter, async evaluation,
repository decoupling, evaluation run scheduling, code version tracking,
data snapshot tracking, production AI evaluation pipeline

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
