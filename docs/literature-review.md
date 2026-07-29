# Literature Review: Continuous Evaluation Infrastructure for Production AI Systems
> **Version 1.1.1**

## Context for NiriZan

This review surveys the current landscape of evaluation methods, frameworks, and benchmarks for Retrieval-Augmented Generation (RAG) pipelines, LLM applications, and AI agents. It is structured to support the design rationale for NiriZan, an open-source continuous evaluation infrastructure for production AI systems.

---

## 1. Introduction

### 1.1 The Shift from Deterministic to Probabilistic Systems
- Traditional software testing assumes deterministic input-output mappings and pass/fail assertions.
- Modern AI systems (LLMs, RAG pipelines, agents) produce probabilistic, context-dependent outputs, so correctness must be measured on a spectrum rather than verified as binary.
- Establishes the motivation for continuous, statistical evaluation infrastructure rather than one-time test suites.

---

## 2. Evaluation of RAG Systems

### 2.1 Foundational Frameworks
- **RAGAS** (Es et al., 2024) — reference-free evaluation suite; introduces the "RAG Triad": context relevance, faithfulness/groundedness, answer relevance.
- Discuss why reference-free evaluation matters for production settings where ground-truth answers are unavailable at scale.

### 2.2 Statistically Calibrated Evaluation: ARES
- **ARES** (Saad-Falcon et al., 2024) — an Automated RAG Evaluation System that fine-tunes lightweight LM judges on synthetic training data to score context relevance, answer faithfulness, and answer relevance, then calibrates those judge predictions using Prediction-Powered Inference (PPI) against a small set of human-annotated datapoints (as few as a few hundred).
- ARES reports better ranking accuracy than RAGAS and a few-shot GPT-3.5 judge across knowledge-intensive tasks in KILT and SuperGLUE, and its judges remain effective across domain shifts.
- This is the direct precedent for the "Statistical Gating" component in NiriZan's architecture: calibrating a cheap, high-volume judge against a small trusted gold set to produce a confidence-bounded score rather than a raw, uncalibrated one.

### 2.3 Fine-Grained Diagnostic Evaluation: RAGChecker
- **RAGChecker** (Ru et al., 2024) — a fine-grained evaluation framework incorporating diagnostic metrics for both the retrieval and generation modules of a RAG system separately, rather than scoring the pipeline as a single opaque unit.
- RAGChecker's meta-evaluation shows significantly better correlation with human judgment than prior metrics, and its component-level decomposition (retrieval quality, generation quality, retrieval-generation alignment) surfaces specific, actionable error sources rather than a single aggregate score.
- Relevant to NiriZan's design principle that a quality drop should be localizable to a specific stage (retrieval vs. generation vs. tool use), not just flagged as "the RAG pipeline got worse."

### 2.4 Empirical Validation of RAG Metrics
- **Evaluating RAG Metrics in Applied Contexts** (Brabant, 2026) — compares Ragas, DeepEval, RAGChecker, and Opik against human annotator judgments; surfaces correlation gaps between automated metrics and human scoring.
- Use this to discuss limitations of existing metrics and justify NiriZan's need for pluggable, cross-validated metric support rather than a single fixed metric suite.

### 2.5 Extensions Beyond RAGAS
- **Knowledge-Graph Based RAG Evaluation** (Dong et al., 2025) — extends RAGAS with multi-hop reasoning and semantic clustering for finer-grained scoring.
- Discuss the trend toward richer, structure-aware evaluation as RAG pipelines grow more complex (multi-hop retrieval, agentic RAG).

### 2.6 Synthesis
- Summarize open problems: metric-human correlation, computational cost of reference-free evaluation, generalizability across domains, and the tension between component-level diagnosis (RAGChecker) and calibrated aggregate scoring (ARES), both of which NiriZan's Metric Engine needs to support rather than choosing one over the other.

---

## 3. General-Purpose LLM Evaluation Frameworks

### 3.1 Feedback-Function-Based Evaluation
- **TruLens** (TruEra) — feedback functions as a composable, extensible evaluation primitive; supports the RAG Triad plus custom domain-specific checks.
- Discuss the "scalable vs. meaningful" tradeoff TruLens identifies (human eval vs. NLP metrics vs. LLM-based judges).

### 3.2 Holistic, Multi-Metric Benchmarking
- **HELM** (Liang et al., 2022, Stanford CRFM) — taxonomizes scenarios and metrics (accuracy, calibration, robustness, fairness, bias, toxicity, efficiency); emphasizes transparency and reproducibility as first-class goals.
- Discuss HELM's living-benchmark model as a precedent for NiriZan's "continuously measured" philosophy.

### 3.3 Pairwise and Preference-Based Evaluation: MT-Bench and Chatbot Arena
- **Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena** (Zheng et al., 2023) — introduces MT-Bench (80 multi-turn, human-crafted questions) and Chatbot Arena (crowdsourced pairwise battles), and systematically studies whether strong LLM judges (e.g. GPT-4) agree with human preference judgments.
- Reports over 80% agreement between GPT-4 and human judges, roughly matching human-human agreement, but also identifies specific, named failure modes: position bias (favoring whichever response is shown first), verbosity bias (favoring longer responses regardless of quality), and self-enhancement bias (a model favoring outputs similar to its own style).
- This paper is the origin point for the entire "LLM-as-a-judge has systematic, nameable biases" literature that Section 4 builds on, and is worth citing directly rather than only through later surveys that summarize it.

### 3.4 Comparative Analysis
- Compare RAGAS, ARES, RAGChecker, TruLens, HELM, and MT-Bench along axes relevant to NiriZan's design: reference-free vs. reference-based, single-domain vs. holistic, static vs. continuous/living benchmark, aggregate vs. component-level diagnosis.
- Identify the gap: most tools focus on either RAG-specific metrics, broad model benchmarking, or preference-based pairwise comparison; few unify continuous production monitoring with reproducible experiment tracking across all of RAG, agents, and general LLM applications at once.

---

## 4. LLM-as-a-Judge: Promise and Limitations

### 4.1 Rationale for Model-Based Judging
- Motivate why LLM-as-a-judge emerged as a scalable alternative to human annotation, tracing the lineage back to Zheng et al.'s (2023) original framing (Section 3.3).

### 4.2 Bias and Reliability Concerns
- **A Survey on LLM-as-a-Judge** (Gu et al., 2024) — formal definition, classification, and reliability-oriented benchmark for judge systems.
- **Judging the Judges** (Shi et al., 2024) — position bias study across pairwise/list-wise settings; introduces repetition stability, position consistency, preference fairness metrics.
- **Reliability without Validity** (Norman, Rivera & Hughes, 2026) — large-scale evaluation showing high test-retest reliability can coexist with severe position bias; proposes a Minimum Viable Validation Protocol.

### 4.3 Agent-as-a-Judge: Extending Judging to Agentic Trajectories
- **Agent-as-a-Judge: Evaluate Agents with Agents** (Zhuge et al., 2024) — argues that evaluating an agentic system by its final output alone ignores the step-by-step reasoning and decision-making that define agentic behavior, and proposes using an agentic system (not a single-turn LLM judge) to evaluate another agentic system's entire task-solving trajectory.
- Introduces DevAI, a benchmark of 55 realistic automated AI development tasks with 365 hierarchical, manually annotated requirements, and reports that Agent-as-a-Judge substantially outperforms LLM-as-a-Judge in agreement with human expert evaluators while being far cheaper than full manual review.
- Directly relevant to NiriZan's agentic evaluation scope: a judge that only inspects final output cannot localize where in a multi-step agent trajectory a failure occurred, which is the same localization problem RAGChecker (Section 2.3) addresses for RAG pipelines.

### 4.4 Implications for Evaluation Infrastructure
- Argue that judge-based metrics require their own validation layer (consistency checks, bias audits) rather than being treated as ground truth.
- Directly motivates a NiriZan design requirement: judge reliability should itself be a tracked, versioned, and monitored metric.

---

## 5. Agentic Benchmarking

### 5.1 From Static QA to Interactive Evaluation
- Contrast static benchmarks (MMLU, HumanEval-style single-turn tasks) with interactive, multi-turn agent evaluation.

### 5.2 Multi-Environment, General-Purpose Agent Benchmarks
- **AgentBench** (Liu et al., 2023, ICLR'24) — 8 distinct interactive environments testing reasoning, planning, tool use; identifies failure modes such as task-limit exceedance and invalid actions.
- **AgencyBench** (Li et al., 2026, ACL 2026) — a benchmark targeting the "1M-token era" of autonomous agents, evaluating 6 core agentic capabilities across 32 real-world scenarios comprising 138 tasks, each requiring an average of 90 tool calls and roughly 1 million tokens to resolve. Uses a user-simulation agent to provide iterative feedback and a Docker sandbox for automated rubric-based assessment, addressing the scalability bottleneck created by benchmarks that depend on human-in-the-loop feedback.
- AgencyBench's finding that closed-source models substantially outperform open-source models (48.4% vs. 32.1% success) and that performance varies by agentic scaffold is relevant to NiriZan's need to evaluate agent quality independent of which underlying model or framework produced the agent.

### 5.3 Web-Based and Navigation Benchmarks
- **WebArena** (Zhou et al., 2024, ICLR) — a realistic, reproducible browser environment built from four fully functional, self-hosted website domains (e-commerce, social forum, collaborative software development, content management), evaluating whether an agent's actions achieve the intended functional outcome rather than matching a scripted trace.
- WebArena reports a wide gap between agent performance (best GPT-4-based agent: 14.41% task success) and human performance (78.24%), which is a useful empirical anchor for how much headroom currently exists in agentic web-task evaluation.
- Mind2Web (referenced in the broader web-agent literature) extends this line of work toward cross-domain generalization and richer grounding annotations for agent actions across many real website domains rather than four self-hosted ones.

### 5.4 Software Engineering Benchmarks
- **SWE-bench** (Jimenez et al., 2024, ICLR) — the original repository-level coding benchmark, which tasks an agent with resolving real GitHub issues given the full repository as context, and verifies correctness by executing a human-written test suite extracted from the repository's actual post-resolution state.
- SWE-bench Verified is a human-validated subset addressing known quality issues in the original dataset (ambiguous issue descriptions, flaky tests). A body of follow-up work (SWE-PolyBench, SWE-Bench++, SWE-Explore) has since extended this paradigm to multiple languages and finer-grained sub-capabilities such as repository exploration, which is relevant background for why "success rate" alone under-specifies what a coding agent benchmark should measure.
- Directly relevant to NiriZan's software-engineering-adjacent evaluation scope, and to the "integrity-checked evaluation" gap identified in Section 7: SWE-bench-family research has specifically documented "solution leakage," where a benchmark's issue description inadvertently contains the answer, inflating apparent agent competence.

### 5.5 Benchmark Integrity and Gaming
- **We Scored 100% on AI Benchmarks Without Solving a Single Problem** (Berkeley RDI) — demonstrates that certain agentic benchmarks can be defeated without genuine task-solving capability, by exploiting artifacts of how the benchmark verifies success rather than what it intends to measure.
- This is a direct empirical grounding for the "integrity-checked evaluation" gap already identified in NiriZan's architecture document: a benchmark or evaluation pipeline that only checks a final success signal, without verifying that the signal was earned through genuine task execution, can be gamed. NiriZan's proposed integrity-checking analysis modules exist specifically to guard against this class of failure.

### 5.6 Open Challenges
- Note the proliferation of domain-specific and capability-specific agent benchmarks (SWE-bench for coding, WebArena/Mind2Web for web navigation, AgencyBench for long-horizon multi-tool tasks, PlanBench/bAbI for planning and state tracking) as evidence that general benchmarks alone are insufficient. Frame this as support for NiriZan's extensible, domain-agnostic evaluation approach rather than a fixed benchmark suite.

---

## 6. Continuous Monitoring and Drift Detection

### 6.1 Data Drift vs. Concept Drift
- Define both terms precisely and distinguish their causes (input distribution shift vs. shift in input-output relationships).
- **AWS Prescriptive Guidance: Detecting Drift in Production Applications** — multi-layered drift detection combining statistical tests on prompt embeddings with LLM-based semantic analysis.

### 6.2 Attributing Drift to the System or the Judge
- **Who Drifted: the System or the Judge? Anytime-Valid Attribution in LLM Evaluation Pipelines** (Li, 2026) — proposes an anytime-valid statistical procedure for disambiguating whether an observed quality change in a production LLM evaluation pipeline originates from the system under evaluation or from the judge model itself changing behavior (e.g. via a silent provider-side model update). The method uses a fixed, human-labeled anchor set re-scored at a steady interleave alongside production traffic, a betting e-process on the judge-versus-human gap, and a guard-window rule producing a verdict in {none, system, judge}. On real judge version changes, it detects judge drift in 60 of 60 runs with zero misattribution, while a naive rolling z-test (described as the industry-default approach) false-alarms on 75% of drift-free streams.
- This is the direct research precedent for NiriZan's Trust & Attribution Layer and its three-state verdict (no drift, system drift, judge drift), down to the anchor-set mechanism itself. **Correction from version 1.0.0:** an earlier version of this review cited arXiv:2606.00136 in this context; direct verification found that ID belongs to an unrelated paper on adversarial synthetic content detection. The correct source for this claim is arXiv:2606.15474, cited above and in the reference list.

### 6.3 Drift in Generative Systems Specifically
- Discuss why classical drift metrics (e.g. Kolmogorov-Smirnov tests) are less effective for high-dimensional generative outputs, and why semantic/behavioral drift needs its own detection approach distinct from classical feature-distribution drift, as motivated by the judge-drift problem in Section 6.2.

### 6.4 Implications for Deployment-Aware Validation
- Connect drift detection literature to NiriZan's regression-detection and deployment-gating design goals: establishing baselines, continuous comparison against production traffic, and threshold-based alerting.

---

## 7. Synthesis and Positioning of NiriZan

### 7.1 Summary of Gaps in Existing Literature and Tooling
- Fragmentation: RAG-specific tools (RAGAS, ARES, RAGChecker), general LLM benchmarks (HELM, MT-Bench), agent benchmarks (AgentBench, AgencyBench, WebArena, SWE-bench), and drift-monitoring/attribution research exist largely as separate ecosystems with little integration between them.
- Reliability of automated judges is an active, unresolved research problem rather than a solved primitive, spanning both single-turn LLM judges (Section 4.2) and agentic judges (Section 4.3).
- Benchmark integrity is a documented, exploitable weakness (Section 5.5), not a hypothetical concern, and few evaluation frameworks build in defenses against it.
- Few frameworks combine reproducible experiment tracking (versioned runs, baselines) with continuous production-facing monitoring and judge-vs-system drift attribution in a single system.

### 7.2 How NiriZan Addresses These Gaps
- Positions NiriZan as a unifying evaluation layer: pluggable metrics (RAG Triad and beyond, informed by both ARES's calibrated-judge approach and RAGChecker's component-level diagnosis), judge-reliability tracking, agent-task evaluation informed by both general-purpose (AgentBench, AgencyBench) and domain-specific (WebArena, SWE-bench) benchmarking paradigms, and drift-aware regression detection grounded directly in the system-vs-judge attribution literature (Li, 2026), all within one reproducible pipeline.
- Frame this against the "engineering quality layer" vision from the project README.

### 7.3 Open Research Questions for Future Work
- How to validate judge reliability continuously in production without excessive cost, building on ARES's PPI-based calibration approach and the anytime-valid attribution method in Section 6.2.
- How to standardize drift metrics across RAG, agentic, and generative-text systems.
- How to benchmark evaluation frameworks themselves (meta-evaluation), including defending against the benchmark-gaming failure modes documented in Section 5.5.
- How to extend Agent-as-a-Judge-style trajectory evaluation to non-coding agentic domains without requiring bespoke, hand-annotated benchmarks for every new domain.

---

## References

*(Populate in your citation style of choice, e.g. APA or IEEE. Verify formatting details before final submission. Every arXiv ID below was checked directly against its arxiv.org abstract page as part of this revision.)*

1. Es, S., James, J., Espinosa-Anke, L., & Schockaert, S. (2024). RAGAS: Automated Evaluation of Retrieval Augmented Generation. *Proceedings of the 18th Conference of the European Chapter of the Association for Computational Linguistics: System Demonstrations*, 150–158.
2. Saad-Falcon, J., Khattab, O., Potts, C., & Zaharia, M. (2024). ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems. *Proceedings of NAACL 2024*. arXiv:2311.09476.
3. Ru, D., Qiu, L., Hu, X., Zhang, T., Shi, P., Chang, S., Cheng, J., Wang, C., Sun, S., Li, H., Zhang, Z., Wang, B., Jiang, J., He, T., Wang, Z., Liu, P., Zhang, Y., & Zhang, Z. (2024). RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation. arXiv:2408.08067.
4. Brabant, Q. (2026). Evaluating RAG Metrics in Applied Contexts: An Experiment, Its Findings and Its Limitations. Orange Research, Lannion, France. arXiv:2607.07302.
5. Dong, S., et al. (2025). Knowledge-Graph Based RAG System Evaluation Framework. arXiv:2510.02549.
6. Liang, P., Bommasani, R., Lee, T., Tsipras, D., Soylu, D., Yasunaga, M., Zhang, Y., Narayanan, D., Wu, Y., Kumar, A., et al. (2022). Holistic Evaluation of Language Models. Center for Research on Foundation Models (CRFM), Stanford Institute for Human-Centered Artificial Intelligence. arXiv:2211.09110. Published in *Transactions on Machine Learning Research* (TMLR), 2023; OpenReview: [openreview.net/forum?id=iO4LZibEqW](https://openreview.net/forum?id=iO4LZibEqW).
7. TruEra. TruLens: Evaluation and Tracking for LLM Experiments and AI Agents. [github.com/truera/trulens](https://github.com/truera/trulens)
8. Zheng, L., Chiang, W.-L., Sheng, Y., Zhuang, S., Wu, Z., Zhuang, Y., Lin, Z., Li, Z., Li, D., Xing, E. P., Zhang, H., Gonzalez, J. E., & Stoica, I. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. *Advances in Neural Information Processing Systems*, 36. arXiv:2306.05685.
9. Gu, J., et al. (2024). A Survey on LLM-as-a-Judge. arXiv:2411.15594.
10. Shi, L., et al. (2024). Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge. arXiv:2406.07791.
11. Norman, J. D., Rivera, M. U., & Hughes, D. A. (2026). Reliability without Validity: A Systematic, Large-Scale Evaluation of LLM-as-a-Judge Models Across Agreement, Consistency, and Bias. UC Berkeley School of Information. arXiv:2606.19544.
12. Zhuge, M., Zhao, C., Ashley, D. R., Wang, W., Khizbullin, D., Xiong, Y., Liu, Z., Chang, E., Krishnamoorthi, R., Tian, Y., Shi, Y., Chandra, V., & Schmidhuber, J. (2024). Agent-as-a-Judge: Evaluate Agents with Agents. *Proceedings of the 42nd International Conference on Machine Learning*, PMLR 267. arXiv:2410.10934.
13. Liu, X., Yu, H., Zhang, H., Xu, Y., Lei, X., Lai, H., Gu, Y., Ding, H., Men, K., Yang, K., Zhang, S., Deng, X., Zeng, A., Du, Z., Zhang, C., Shen, S., Zhang, T., Su, Y., Sun, H., Huang, M., Dong, Y., & Tang, J. (2023). AgentBench: Evaluating LLMs as Agents. Tsinghua University, The Ohio State University, UC Berkeley. arXiv:2308.03688.
14. Li, K., Shi, J., Xiao, Y., Jiang, M., Sun, J., Wu, Y., Fu, D., Xia, S., Cai, X., Xu, T., Si, W., Li, W., Wang, D., & Liu, P. (2026). AgencyBench: Benchmarking the Frontiers of Autonomous Agents in 1M-Token Real-World Contexts. *Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics*. arXiv:2601.11044.
15. Zhou, S., Xu, F. F., Zhu, H., Zhou, X., Lo, R., Sridhar, A., Cheng, X., Bisk, Y., Fried, D., Alon, U., et al. (2024). WebArena: A Realistic Web Environment for Building Autonomous Agents. *Proceedings of the Twelfth International Conference on Learning Representations*. arXiv:2307.13854.
16. Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O., & Narasimhan, K. (2024). SWE-bench: Can Language Models Resolve Real-World GitHub Issues? *Proceedings of the International Conference on Learning Representations*. arXiv:2310.06770.
17. Berkeley RDI. We Scored 100% on AI Benchmarks Without Solving a Single Problem. Berkeley RDI blog. [Verify exact URL and publication date before formal citation; sourced as a blog post rather than a peer-reviewed paper.]
18. AWS Prescriptive Guidance. Detecting Drift in Production Applications. [docs.aws.amazon.com](https://docs.aws.amazon.com/prescriptive-guidance/latest/gen-ai-lifecycle-operational-excellence/prod-monitoring-drift.html)
19. Li, Y. (2026). Who Drifted: the System or the Judge? Anytime-Valid Attribution in LLM Evaluation Pipelines. arXiv:2606.15474.
