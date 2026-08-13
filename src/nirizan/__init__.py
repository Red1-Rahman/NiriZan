# src/nirizan/__init__.py
"""
NiriZan - Continuous Evaluation Infrastructure for Production AI.

Description
-----------
Provides the public package entry point for NiriZan, a continuous evaluation
framework for production AI systems. The root package exposes the package
version and library-safe logging controls for applications integrating
NiriZan into evaluation, observability, and quality-assurance workflows.

NiriZan is designed around continuous evaluation of probabilistic AI systems,
including trace-based evaluation, quality metrics, regression detection,
evaluation trust and attribution, persistent evaluation history, and
deployment-aware quality gates.

Project
-------
NiriZan — Continuous Evaluation Infrastructure for Production AI

Keywords
--------
continuous AI evaluation, production AI evaluation, AI evaluation framework,
LLM evaluation, RAG evaluation, AI observability, AI testing,
LLM reliability, evaluation infrastructure, AI quality assurance,
AI regression detection, judge drift, system drift, evaluation trust,
statistical evaluation, evaluation pipelines, production AI reliability,
AI evaluation tooling, Python AI evaluation, AI monitoring,
AI quality gates, CI/CD for AI

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

from nirizan._logging import (
    disable_logging,
    enable_logging,
    get_logger,
    set_log_level,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "disable_logging",
    "enable_logging",
    "get_logger",
    "set_log_level",
]
