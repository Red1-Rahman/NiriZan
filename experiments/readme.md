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
