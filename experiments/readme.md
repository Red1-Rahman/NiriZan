# NiriZan Experiment Lab

Welcome to the **NiriZan Experiment Lab**. This directory serves as an open workbench for exploratory research, prototyping, algorithm design, ablation studies, empirical benchmarking, and judge model testing before concepts are formalised and ported into the core system (`src/nirizan/`).

---

## Purpose & Scope

The notebooks in this directory support any exploratory, research-driven, or experimental workflow for continuous AI evaluation, including but not limited to:

* **Metric & Algorithm Prototyping**: Developing and testing new evaluation techniques, RAG metrics, context relevance algorithms, and multi-turn agent quality checks.
* **Ablation Studies & Model Comparison**: Benchmarking lightweight ML models, embedding techniques, and various LLM-as-a-judge setups for accuracy, latency, alignment, and cost trade-offs.
* **Empirical Overhead Benchmarking**: Measuring span serialization speed, async trace collection throughput, background exporter latency, and repository persistence performance.
* **Statistical & Calibration Research**: Experimenting with confidence interval bounds, Z-score thresholds, gold set recalibration, and deployment gate decision logic.
* **Drift & Behavioral Analysis**: Investigating anchor sets, embedding similarity bands, and methods to disambiguate actual system performance drops from evaluator model drift.
* **Ad-hoc Research & Integrations**: Testing third-party libraries, trying out new open-source models, and evaluating custom dataset performance.

---

## Experiment Index

The notebooks below are ordered according to the experimental progression of NiriZan, from instrumentation and evaluation primitives through statistical regression detection, reliability analysis, package validation, and empirical benchmarking.

| # | Notebook | Description |
|---:|---|---|
| 1 | [`01_instrumentation_trace_storage.ipynb`](https://github.com/Red1-Rahman/NiriZan/blob/main/experiments/01_instrumentation_trace_storage.ipynb) | **Instrumentation & Trace Storage** — Explores NiriZan's tracing and storage foundations, including span and trace creation, parent-child relationships, trace identifiers, serialization, asynchronous trace emission, and persistence through the trace repository layer. |
| 2 | [`02_RAG_Triad.ipynb`](https://github.com/Red1-Rahman/NiriZan/blob/main/experiments/02_RAG_Triad.ipynb) | **RAG Triad Evaluation** — Prototypes and evaluates the three core RAG quality dimensions: context relevance, groundedness, and answer relevance. The experiment also examines embedding-based evaluation and optional LLM-as-a-judge comparisons. |
| 3 | [`03_Experiment_Tracking_and_Baselines.ipynb`](https://github.com/Red1-Rahman/NiriZan/blob/main/experiments/03_Experiment_Tracking_and_Baselines.ipynb) | **Experiment Tracking & Baselines** — Explores versioned evaluation runs, baseline creation, run comparisons, commit and dataset tracking, multi-turn session tracking, and the mechanisms required to establish reproducible evaluation baselines. |
| 4 | [`04_regression_detection_ci_gate.ipynb`](https://github.com/Red1-Rahman/NiriZan/blob/main/experiments/04_regression_detection_ci_gate.ipynb) | **Regression Detection & CI Gate** — Develops the statistical regression-detection pipeline, including hypothesis testing, effect sizes, bootstrap confidence intervals, multiple-testing correction, baseline handling, subgroup analysis, severity classification, and automated CI/CD deployment decisions. |
| 5 | [`04v2_regression_detection_ci_gate.ipynb`](https://github.com/Red1-Rahman/NiriZan/blob/main/experiments/04v2_regression_detection_ci_gate.ipynb) | **Regression Detection & CI Gate — v2** — Refines the regression-detection experiment around NiriZan's domain contracts and production-oriented data structures while evaluating statistical detection, effect sizing, bootstrap intervals, multiple-testing correction, sliding-window baselines, dataset compatibility, slicing, severity classification, and CI/CD decisions. |
| 6 | [`05_drift_and_judge_reliability.ipynb`](https://github.com/Red1-Rahman/NiriZan/blob/main/experiments/05_drift_and_judge_reliability.ipynb) | **Drift & Judge Reliability** — Investigates behavioral anchor sets and evaluator reliability, with emphasis on distinguishing genuine system-quality degradation from changes or drift in the judge model itself. |
| 7 | [`06_testPYPI.ipynb`](https://github.com/Red1-Rahman/NiriZan/blob/main/experiments/06_testPYPI.ipynb) | **TestPyPI & Package Validation** — Validates the distributed `nirizan` package from TestPyPI and exercises its public API through an end-to-end tracing, SQLite persistence, behavioral-anchor, and reporting workflow. |
| 8 | [`07_evaluation_ablation_and_benchmarking.ipynb`](https://github.com/Red1-Rahman/NiriZan/blob/main/experiments/07_evaluation_ablation_and_benchmarking.ipynb) | **Evaluation Ablation & Benchmarking** — Provides empirical benchmarking of NiriZan's evaluation mechanisms, including judge-human agreement, false-alarm behavior, statistical power, instrumentation overhead, baseline strategies, and regression-gate ablations. |

> **Note:** `04b_statistical_gating.ipynb` is a supporting statistical-gating experiment and is intentionally not included in the primary eight-notebook index above.

---

## Experimental Progression

The experiments broadly follow the development of NiriZan's evaluation infrastructure:

```text
01  Instrumentation & Trace Storage
        ↓
02  RAG Triad Evaluation
        ↓
03  Experiment Tracking & Baselines
        ↓
04  Regression Detection & CI Gate
        ↓
04v2  Contract-Aligned Regression Detection
        ↓
05  Drift & Judge Reliability
        ↓
06  TestPyPI & Package Validation
        ↓
07  Evaluation Ablation & Benchmarking
```

This progression reflects the broader research methodology behind NiriZan:

**observe → evaluate → establish baselines → detect regressions → attribute drift → validate reliability → benchmark**

---

## Running Notebooks in Cloud Environments (Colab / Kaggle)

Experiment notebooks can be executed directly in free cloud GPU/CPU environments like Google Colab or Kaggle without requiring local environment setup.

### 1. Launching

Header badges can be added at the top of notebooks for one-click launching:

* **Google Colab**: Installs NiriZan directly via `pip install "git+https://github.com/Red1-Rahman/NiriZan.git@main"`
* **Kaggle**: Executes directly within Kaggle Notebook instances.

### 2. Managing Secrets & API Keys

Never hardcode API keys, tokens, or credentials inside notebooks. Use platform-native secrets managers:

* **Google Colab**:

  ```python
  from google.colab import userdata

  api_key = userdata.get('OPENAI_API_KEY')
  ```

* **Kaggle**: Store credentials using Kaggle's notebook secrets and retrieve them through the platform's supported secret-management interface.

### 3. Reproducibility

When running an experiment:

1. Install the required dependencies explicitly.
2. Record the package version or Git commit used.
3. Keep API keys and credentials outside the notebook source.
4. Fix random seeds where applicable.
5. Record important model, dataset, and configuration choices.
6. Avoid relying on hidden local state or files that are not available in the repository.

---

## Relationship to the Core System

Experiments are **not automatically production code**.

A successful experiment should normally proceed through:

```text
Experiment
    ↓
Validation
    ↓
Statistical / Empirical Evidence
    ↓
Design / Contract Review
    ↓
Production Implementation
    ↓
Tests & CI
    ↓
src/nirizan/
```

The `experiments/` directory may therefore contain exploratory implementations, temporary dependencies, benchmark harnesses, synthetic data, visualization code, and alternative approaches that are intentionally unsuitable for direct inclusion in the core package.

---

## Experiment Conventions

When adding a new notebook:

* Use a descriptive filename with a numeric experiment prefix.
* Clearly state the research question or hypothesis near the beginning.
* Document required dependencies and environment assumptions.
* Keep secrets out of notebook cells.
* Prefer reproducible datasets and fixed seeds where appropriate.
* Report experimental limitations and known sources of bias.
* Separate exploratory code from conclusions.
* Link the experiment to the relevant architecture, contracts, issue, or research question when applicable.
* Update this index when adding, renaming, or removing an indexed notebook.

### Naming

Use the following general convention:

```text
NN_<short_descriptive_name>.ipynb
```

For revisions of an existing experiment, retain the relationship to the original experiment, for example:

```text
04_regression_detection_ci_gate.ipynb
04v2_regression_detection_ci_gate.ipynb
```

<div align="center">
Rahman, R. NiriZan (Version 0.1.0) [Computer software]. https://github.com/Red1-Rahman/NiriZan
</div>
