# Literature Review: Continuous Evaluation Infrastructure for Production AI Systems

## Context for NiriZan

This review surveys the current landscape of evaluation methods, frameworks, and benchmarks for Retrieval-Augmented Generation (RAG) pipelines, LLM applications, and AI agents. It is structured to support the design rationale for NiriZan, an open-source continuous evaluation infrastructure for production AI systems.

---

## 1. Introduction

### 1.1 The Shift from Deterministic to Probabilistic Systems
- Traditional software testing assumes deterministic input-output mappings and pass/fail assertions.
- Modern AI systems (LLMs, RAG pipelines, agents) produce probabilistic, context-dependent outputs, so correctness must be measured on a spectrum rather than verified as binary.
- Establishes the motivation for continuous, statistical evaluation infrastructure rather than one-time test suites.

### 1.2 Scope of This Review
- Covers four areas: RAG evaluation, general LLM application evaluation frameworks, LLM-as-a-judge methodology, agentic benchmarking, and production drift monitoring.
- Notes exclusion criteria (e.g. non-peer-reviewed marketing content used only as background, not as cited evidence).

---

## 2. Evaluation of RAG Systems

### 2.1 Foundational Frameworks
- **RAGAS** (Es et al., 2024) — reference-free evaluation suite; introduces the "RAG Triad": context relevance, faithfulness/groundedness, answer relevance.
- Discuss why reference-free evaluation matters for production settings where ground-truth answers are unavailable at scale.

### 2.2 Empirical Validation of RAG Metrics
- **Evaluating RAG Metrics in Applied Contexts** (Brabant, 2026) — compares Ragas, DeepEval, RAGChecker, and Opik against human annotator judgments; surfaces correlation gaps between automated metrics and human scoring.
- Use this to discuss limitations of existing metrics and justify NiriZan's need for pluggable, cross-validated metric support rather than a single fixed metric suite.

### 2.3 Extensions Beyond RAGAS
- **Knowledge-Graph Based RAG Evaluation** (Dong et al., 2025) — extends RAGAS with multi-hop reasoning and semantic clustering for finer-grained scoring.
- Discuss the trend toward richer, structure-aware evaluation as RAG pipelines grow more complex (multi-hop retrieval, agentic RAG).

### 2.4 Synthesis
- Summarize open problems: metric-human correlation, computational cost of reference-free evaluation, generalizability across domains.

---

## 3. General-Purpose LLM Evaluation Frameworks

### 3.1 Feedback-Function-Based Evaluation
- **TruLens** (TruEra) — feedback functions as a composable, extensible evaluation primitive; supports the RAG Triad plus custom domain-specific checks.
- Discuss the "scalable vs. meaningful" tradeoff TruLens identifies (human eval vs. NLP metrics vs. LLM-based judges).

### 3.2 Holistic, Multi-Metric Benchmarking
- **HELM** (Liang et al., 2022, Stanford CRFM) — taxonomizes scenarios and metrics (accuracy, calibration, robustness, fairness, bias, toxicity, efficiency); emphasizes transparency and reproducibility as first-class goals.
- Discuss HELM's living-benchmark model as a precedent for NiriZan's "continuously measured" philosophy.

### 3.3 Comparative Analysis
- Compare RAGAS, TruLens, and HELM along axes relevant to NiriZan's design: reference-free vs. reference-based, single-domain vs. holistic, static vs. continuous/living benchmark.
- Identify the gap: most tools focus on either RAG-specific metrics or broad model benchmarking, few unify continuous production monitoring with reproducible experiment tracking.

---

## 4. LLM-as-a-Judge: Promise and Limitations

### 4.1 Rationale for Model-Based Judging
- Motivate why LLM-as-a-judge emerged as a scalable alternative to human annotation.

### 4.2 Bias and Reliability Concerns
- **A Survey on LLM-as-a-Judge** (Gu et al., 2024) — formal definition, classification, and reliability-oriented benchmark for judge systems.
- **Judging the Judges** (Shi et al., 2024) — position bias study across pairwise/list-wise settings; introduces repetition stability, position consistency, preference fairness metrics.
- **Reliability without Validity** (Norman, Rivera & Hughes, 2026) — large-scale evaluation showing high test-retest reliability can coexist with severe position bias; proposes a Minimum Viable Validation Protocol.

### 4.3 Implications for Evaluation Infrastructure
- Argue that judge-based metrics require their own validation layer (consistency checks, bias audits) rather than being treated as ground truth.
- Directly motivates a NiriZan design requirement: judge reliability should itself be a tracked, versioned, and monitored metric.

---

## 5. Agentic Benchmarking

### 5.1 From Static QA to Interactive Evaluation
- Contrast static benchmarks (MMLU, HumanEval-style single-turn tasks) with interactive, multi-turn agent evaluation.

### 5.2 Multi-Environment Benchmarks
- **AgentBench** (Liu et al., 2023, ICLR'24) — 8 distinct interactive environments testing reasoning, planning, tool use; identifies failure modes such as task-limit exceedance and invalid actions.
- Discuss relevance to evaluating AI agents built on tool use, multi-step planning, and long-horizon tasks.

### 5.3 Open Challenges
- Note the proliferation of domain-specific agent benchmarks (legal, clinical, financial) as evidence that general benchmarks alone are insufficient. Frame this as support for NiriZan's extensible, domain-agnostic evaluation approach rather than a fixed benchmark suite.

---

## 6. Continuous Monitoring and Drift Detection

### 6.1 Data Drift vs. Concept Drift
- Define both terms precisely and distinguish their causes (input distribution shift vs. shift in input-output relationships).
- **AWS Prescriptive Guidance: Detecting Drift in Production Applications** — multi-layered drift detection combining statistical tests on prompt embeddings with LLM-based semantic analysis.

### 6.2 Drift in Generative Systems Specifically
- Discuss why classical drift metrics (e.g. Kolmogorov-Smirnov tests) are less effective for high-dimensional generative outputs.
- **Generative AI and Digital Ecosystem Resilience** (2026 survey) — formal definition of concept drift and its extension to semantic and behavioral drift dimensions in LLM systems.

### 6.3 Implications for Deployment-Aware Validation
- Connect drift detection literature to NiriZan's regression-detection and deployment-gating design goals: establishing baselines, continuous comparison against production traffic, and threshold-based alerting.

---

## 7. Synthesis and Positioning of NiriZan

### 7.1 Summary of Gaps in Existing Literature and Tooling
- Fragmentation: RAG-specific tools (RAGAS), general LLM benchmarks (HELM), agent benchmarks (AgentBench), and drift-monitoring practices exist largely as separate ecosystems.
- Reliability of automated judges is an active, unresolved research problem rather than a solved primitive.
- Few frameworks combine reproducible experiment tracking (versioned runs, baselines) with continuous production-facing monitoring in a single system.

### 7.2 How NiriZan Addresses These Gaps
- Positions NiriZan as a unifying evaluation layer: pluggable metrics (RAG Triad and beyond), judge-reliability tracking, agent-task evaluation, and drift-aware regression detection in one reproducible pipeline.
- Frame this against the "engineering quality layer" vision from the project README.

### 7.3 Open Research Questions for Future Work
- How to validate judge reliability continuously in production without excessive cost.
- How to standardize drift metrics across RAG, agentic, and generative-text systems.
- How to benchmark evaluation frameworks themselves (meta-evaluation).

---

## References

*(Populate in your citation style of choice, e.g. APA or IEEE. Suggested entries below; verify details before final submission.)*

1. Es, S., James, J., Espinosa-Anke, L., & Schockaert, S. (2024). RAGAS: Automated Evaluation of Retrieval Augmented Generation. *Proceedings of the 18th Conference of the European Chapter of the Association for Computational Linguistics: System Demonstrations*, 150-158.
2. Brabant, Q. (2026). Evaluating RAG Metrics in Applied Contexts: An Experiment, Its Findings and Its Limitations. *arXiv:2607.07302*.
3. Dong, S., et al. (2025). Knowledge-Graph Based RAG System Evaluation Framework. *arXiv:2510.02549*.
4. Liang, P., et al. (2022). Holistic Evaluation of Language Models. *arXiv:2211.09110*.
5. TruEra. TruLens: Evaluation and Tracking for LLM Experiments and AI Agents. [github.com/truera/trulens](https://github.com/truera/trulens)
6. Gu, J., et al. (2024). A Survey on LLM-as-a-Judge. *arXiv:2411.15594*.
7. Shi, L., et al. (2024). Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge. *arXiv:2406.07791*.
8. Norman, J. D., Rivera, M. U., & Hughes, D. A. (2026). Reliability without Validity: A Systematic, Large-Scale Evaluation of LLM-as-a-Judge Models Across Agreement, Consistency, and Bias. *arXiv:2606.19544*.
9. Liu, X., et al. (2023). AgentBench: Evaluating LLMs as Agents. *arXiv:2308.03688*.
10. AWS Prescriptive Guidance. Detecting Drift in Production Applications. [docs.aws.amazon.com](https://docs.aws.amazon.com/prescriptive-guidance/latest/gen-ai-lifecycle-operational-excellence/prod-monitoring-drift.html)
11. Generative AI and Digital Ecosystem Resilience: A Proactive Lifecycle-Based Survey. (2026). *arXiv:2606.00136*.
