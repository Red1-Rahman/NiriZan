<div align="center">

# NiriZan

### Continuous Evaluation Infrastructure for Production AI

*"Inspection through Measurement"*
*"Engineering Trust Through Continuous Evaluation"*

<br>

[![CI](https://github.com/Red1-Rahman/NiriZan/actions/workflows/ci.yml/badge.svg)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/ci.yml)
[![Packaging](https://github.com/Red1-Rahman/NiriZan/actions/workflows/packaging.yml/badge.svg)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/packaging.yml)
[![Cross-platform](https://github.com/Red1-Rahman/NiriZan/actions/workflows/cross-platform.yml/badge.svg)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/cross-platform.yml)   
[![Security (CIA)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/security.yml/badge.svg)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/security.yml)
[![Scorecard supply-chain security](https://github.com/Red1-Rahman/NiriZan/actions/workflows/scorecard.yml/badge.svg)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/scorecard.yml)   
[![Documentation](https://img.shields.io/badge/Docs-Read%20the%20Docs-blue)](https://nirizan.readthedocs.io/en/latest/)
[![Wikidata](https://img.shields.io/badge/Wikidata-Q141130494-990000)](https://www.wikidata.org/wiki/Q141130494)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

</div>

---

## Why NiriZan?

Modern AI systems are probabilistic rather than deterministic. Traditional software testing alone cannot determine whether a retrieval pipeline, language model, or AI agent is performing correctly. NiriZan exists to provide continuous, reproducible evaluation infrastructure that enables teams to measure quality, detect regressions, compare experiments, and build confidence in production AI systems.

NiriZan is an open-source framework to provide automated judge drift attribution, fixed anchor sets with repeatable, on-demand rescoring, rigorous statistical gating (Mann-Whitney + Holm-Bonferroni), multivariate structure-drift detection, trust-weighted health scoring, and CI/CD-integrated regression gating in a single, architecturally disciplined Python package.

---

## Installation

```bash
pip install nirizan
```

Package: [pypi.org/project/nirizan](https://pypi.org/project/nirizan/)

---

## What NiriZan Does

1. **Automated judge-drift attribution.** `AttributionEngine` uses bootstrap confidence intervals and Mann-Whitney U tests with Holm-Bonferroni correction to produce a five-state verdict: `NONE`, `SYSTEM_DRIFT`, `JUDGE_DRIFT`, `JOINT_DRIFT`, or `INCONCLUSIVE`. It distinguishes a quality drop in the system under test from a change in the judge measuring it, and separately flags when both shifted at once or when there wasn't enough data to tell.
2. **Fixed evaluation anchors, rescored on demand.** A versioned `AnchorSet` is never edited in place; updating it means creating a new `anchor_set_id`, so historical comparisons stay meaningful.
3. **Statistically rigorous regression gating.** Mann-Whitney U tests with Holm-Bonferroni correction for multiple comparisons, Cohen's d effect sizes, and bootstrap confidence intervals (5,000 resamples), not a bare threshold on a single score.
4. **Multivariate structure detection.** A second regression track catches changes in how metrics vary together (variance-only and correlation-only drift) that per-metric tests cannot see, using permutation-calibrated tests. In its default mode it can raise a warning but never block a deploy on its own, because these tests are undirected; an opt-in strict mode allows blocking.
5. **Trust-weighted health scoring.** `compute_system_health_score` discounts the aggregate score when the attribution verdict signals judge unreliability, not just system degradation.
6. **An 8-layer, unidirectional architecture**, `instrumentation → orchestrator → metrics → trust → storage → regression → gate → reporting`, enforced by `import-linter` in CI, not just documented as a diagram.

---

## What is NiriZan?

NiriZan is an open-source continuous evaluation infrastructure for production AI systems. It enables engineers and researchers to systematically measure, benchmark, validate, and monitor the quality of:

- **Retrieval-Augmented Generation (RAG)** pipelines
- **AI agents**
- **Large Language Model (LLM)** applications
- **Custom AI workflows**

Unlike orchestration frameworks that focus on building AI applications, NiriZan focuses on engineering confidence in AI systems. It provides:

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

## Where the Name Comes From

NiriZan is a fusion of two words from two languages, each contributing a core idea behind the project.

| Niri | Zan |
|---|---|
| **Origin:** নিরীক্ষা (*Nirikkha*) - Bangla/Bengali | **Origin:** ميزان (*Mīzān*) - Arabic |
| **Meaning:** Inspection · Evaluation · Verification · Audit | **Meaning:** Scale · Balance · Measurement · Criterion |

Together, **Niri + Zan** captures the essence of the project: inspecting AI systems and measuring them against a balanced standard of quality.

---

## Read More

For the complete user guide, see the **[NiriZan User Manual](docs/user-manual.md)**.

For architecture, contracts, module reference docs, and the evaluation results behind the claims above, see [`docs/`](docs/).

See **[CHANGELOG.md](CHANGELOG.md)** for release history and notable changes between versions.

[The Ruler Can Change Too: Navigating Judge Drift in Production AI Evaluation](https://nirizan.hashnode.dev/the-ruler-can-change-too-navigating-judge-drift-in-production-ai-evaluation), the first NiriZan engineering post, covering the judge-drift problem and the fixed-anchor, statistical-attribution approach this project takes to it.

---

## License

Copyright 2026 Redwan Rahman

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for the full text.

Releases 0.1.0 to 0.3.0 were published under GPL-3.0-or-later and remain available under those terms. Version 0.4.0 and later are licensed under Apache-2.0.

---

## Author

**Redwan Rahman**
[github.com/Red1-Rahman](https://github.com/Red1-Rahman)
