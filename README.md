<div align="center">

# NiriZan

### Continuous Evaluation Infrastructure for Production AI

*"Inspection through Measurement"*
*"Engineering Trust Through Continuous Evaluation"*

<br>

[![CI](https://github.com/Red1-Rahman/NiriZan/actions/workflows/ci.yml/badge.svg)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/ci.yml)
[![Packaging](https://github.com/Red1-Rahman/NiriZan/actions/workflows/packaging.yml/badge.svg)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/packaging.yml)
[![Cross-platform](https://github.com/Red1-Rahman/NiriZan/actions/workflows/cross-platform.yml/badge.svg)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/cross-platform.yml)
[![VirusTotal Security Scan](https://github.com/Red1-Rahman/NiriZan/actions/workflows/virustotal.yml/badge.svg)](https://github.com/Red1-Rahman/NiriZan/actions/workflows/virustotal.yml)

</div>

---

## Why NiriZan?

Modern AI systems are probabilistic rather than deterministic. Traditional software testing alone cannot determine whether a retrieval pipeline, language model, or AI agent is performing correctly. NiriZan exists to provide continuous, reproducible evaluation infrastructure that enables teams to measure quality, detect regressions, compare experiments, and build confidence in production AI systems.

NiriZan is the first open-source framework to provide automated judge drift attribution, fixed anchor sets with repeatable, on-demand rescoring, rigorous statistical gating (Mann-Whitney + Holm-Bonferroni), trust-weighted health scoring, and CI/CD-integrated regression gating in a single, architecturally disciplined Python package.

---

## Installation

```bash
pip install nirizan
```

Package: [pypi.org/project/nirizan](https://pypi.org/project/nirizan/)

---

## What NiriZan Does

1. **Automated judge-drift attribution.** `AttributionEngine` produces a three-state verdict, `NONE`, `JUDGE_DRIFT`, or `SYSTEM_DRIFT`, distinguishing a quality drop in the system under test from a change in the judge measuring it.
2. **Fixed evaluation anchors, rescored on demand.** A versioned `AnchorSet` is never edited in place; updating it means creating a new `anchor_set_id`, so historical comparisons stay meaningful.
3. **Statistically rigorous regression gating.** Mann-Whitney U tests with Holm-Bonferroni correction for multiple comparisons, Cohen's d effect sizes, and bootstrap confidence intervals (5,000 resamples), not a bare threshold on a single score.
4. **Trust-weighted health scoring.** `compute_system_health_score` discounts the aggregate score when the attribution verdict signals judge unreliability, not just system degradation.
5. **An 8-layer, unidirectional architecture**, `instrumentation → orchestrator → metrics → trust → storage → regression → gate → reporting`, enforced by `import-linter` in CI, not just documented as a diagram.

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

For architecture, contracts, module reference docs, and the evaluation results behind the claims above, see [`docs/`](docs/).

[The Ruler Can Change Too: Navigating Judge Drift in Production AI Evaluation](https://nirizan.hashnode.dev/the-ruler-can-change-too-navigating-judge-drift-in-production-ai-evaluation), the first NiriZan engineering post, covering the judge-drift problem and the fixed-anchor, statistical-attribution approach this project takes to it.

---

## License

Copyright (C) 2026 Redwan Rahman

This program is free software: you can redistribute it and/or modify it under the terms of the **GNU General Public License** as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

---

## Author

**Redwan Rahman**
[github.com/Red1-Rahman](https://github.com/Red1-Rahman)
