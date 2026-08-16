# NiriZan

### Continuous Evaluation Infrastructure for Production AI

*"Inspection through Measurement" — "Engineering Trust Through Continuous Evaluation"*

[![CI](https://github.com/Red1-Rahman/NiriZan/actions/workflows/ci.yml/badge.svg)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/ci.yml)
[![Packaging](https://github.com/Red1-Rahman/NiriZan/actions/workflows/packaging.yml/badge.svg)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/packaging.yml)
[![Cross-platform](https://github.com/Red1-Rahman/NiriZan/actions/workflows/cross-platform.yml/badge.svg)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/cross-platform.yml)
[![Security (CIA)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/security.yml/badge.svg)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/security.yml)

---

## Why NiriZan?

Modern AI systems are probabilistic rather than deterministic. Traditional software testing alone cannot determine whether a retrieval pipeline, language model, or AI agent is performing correctly. NiriZan exists to provide continuous, reproducible evaluation infrastructure that enables teams to measure quality, detect regressions, compare experiments, and build confidence in production AI systems.

NiriZan is an open-source framework providing automated judge-drift attribution, fixed anchor sets with repeatable on-demand rescoring, rigorous statistical gating (Mann-Whitney + Holm-Bonferroni), trust-weighted health scoring, and CI/CD-integrated regression gating in a single, architecturally disciplined Python package.

---

## Installation

```bash
pip install nirizan
```

Package: [pypi.org/project/nirizan](https://pypi.org/project/nirizan/)

---

## What NiriZan Does

1. **Automated judge-drift attribution.** `AttributionEngine` produces a three-state verdict — `NONE`, `JUDGE_DRIFT`, or `SYSTEM_DRIFT` — distinguishing a quality drop in the system under test from a change in the judge measuring it.
2. **Fixed evaluation anchors, rescored on demand.** A versioned `AnchorSet` is never edited in place; updating it means creating a new `anchor_set_id`, so historical comparisons stay meaningful.
3. **Statistically rigorous regression gating.** Mann-Whitney U tests with Holm-Bonferroni correction for multiple comparisons, Cohen's d effect sizes, and bootstrap confidence intervals (5,000 resamples) — not a bare threshold on a single score.
4. **Trust-weighted health scoring.** `compute_system_health_score` discounts the aggregate score when the attribution verdict signals judge unreliability, not just system degradation.
5. **An 8-layer, unidirectional architecture** — `instrumentation → orchestrator → metrics → trust → storage → regression → gate → reporting` — enforced by `import-linter` in CI, not just documented as a diagram.

---

## What is NiriZan?

NiriZan is an open-source continuous evaluation infrastructure for production AI systems. It enables engineers and researchers to systematically measure, benchmark, validate, and monitor the quality of:

- **Retrieval-Augmented Generation (RAG)** pipelines
- **AI agents**
- **Large Language Model (LLM)** applications
- **Custom AI workflows**

Unlike orchestration frameworks that focus on building AI applications, NiriZan focuses on engineering confidence in AI systems:

| Capability | Description |
|---|---|
| Reproducible evaluation pipelines | Consistent, repeatable test runs across environments |
| Benchmark execution | Standardized quality benchmarking for AI systems |
| Regression detection | Automated flagging of quality drops between versions |
| Experiment tracking | Full history of runs, configs, and results |
| Quality reporting | Clear, actionable reports on system performance |
| Deployment-aware validation | Checks tuned to pre-, during-, and post-deployment stages |

### Vision

The long-term vision of NiriZan is to become the **engineering quality layer for production AI**, ensuring that every AI application can be continuously measured before, during, and after deployment.

---

## Where to Go Next

- [User Manual](user-manual.md) — installation, guides, and API usage
- [Architecture](architecture.md) — system design and component breakdown
- [Literature Review](literature-review.md) — the research grounding NiriZan's design
- [Governance → Data Policy](governance/DATA_POLICY.md) and [KPI Definitions](governance/KPI-Definitions.md)
- [Standards Mapping](standards/ISO-IEC-IEEE.md) — alignment with ISO/IEC/IEEE, UN SDG, ACM CS2023, EUR-ACE, and Washington Accord
- [Research Lab](experiments.md) — the experiment notebooks behind NiriZan's design
- [Contributing](community/contributing.md), [Code of Conduct](community/code-of-conduct.md), [Code of Ethics](community/code-of-ethics.md), and [Security Policy](community/security.md)
- Citing NiriZan? Use the [CITATION.cff](https://github.com/Red1-Rahman/NiriZan/blob/main/CITATION.cff) file in the repo root.

---

## License

Copyright (C) 2026 Redwan Rahman. Licensed under the **GNU General Public License v3.0 or later**.

**Author:** Redwan Rahman — [github.com/Red1-Rahman](https://github.com/Red1-Rahman)
