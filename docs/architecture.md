# NiriZan Architecture

This document describes the proposed system architecture for NiriZan, a continuous evaluation infrastructure for production AI systems. It translates the literature review findings and architecture research into concrete components, data flow, and design decisions.

> **Note on sourcing:** Some components below (the attribution monitor, behavioral anchor detector, and statistical gating approach) are inspired by research patterns identified during literature research and are referenced by descriptive name rather than as confirmed, individually verified citations. Treat these as design inspiration to validate against primary sources before finalizing implementation details.

---

## 1. Design Principles

NiriZan's architecture is guided by five principles, derived directly from the literature review:

1. **Probabilistic systems need statistical evaluation, not pass/fail assertions.** Every core component should produce a score with a confidence interval, not a boolean.
2. **Evaluation must not sit on the user-facing critical path.** Instrumentation and judging happen out-of-band from the application response.
3. **A quality drop can come from the system or the judge.** The architecture must be able to tell these apart.
4. **Different domains need different metrics, but one pipeline.** RAG, agents, and general LLM apps should flow through the same orchestration and tracking layer, not separate silos.
5. **Support both reference-free and reference-based evaluation.** Production monitoring favors reference-free (no ground truth available at scale); pre-deployment benchmarking favors reference-based (gold answers available).

---

## 2. High-Level System Design

```mermaid
flowchart TB
    subgraph APP["Instrumented AI Application"]
        A1[RAG Pipeline]
        A2[AI Agent]
        A3[LLM Application]
    end

    subgraph INSTR["Instrumentation Layer"]
        I1["OpenTelemetry-style Tracing<br/>(planning, retrieval, tool use, generation spans)"]
    end

    subgraph ORCH["Evaluator Orchestrator"]
        O1[Run Scheduler]
        O2[Trace Collector]
        O3[Metric Dispatcher]
    end

    subgraph METRICS["Metric Engine (Pluggable)"]
        M1["RAG Triad<br/>Context Relevance / Groundedness / Answer Relevance"]
        M2["Lightweight Judge Layer<br/>(fine-tuned classifiers)"]
        M3["LLM-as-Judge Layer<br/>(prompted models, higher cost)"]
        M4["Statistical Gating<br/>(gold-set calibration, confidence intervals)"]
        M5["Behavioral Anchor Detector<br/>(agent persona / drift, embedding similarity)"]
    end

    subgraph TRUST["Trust & Attribution Layer"]
        T1["Anchor Set<br/>(fixed, human-labeled)"]
        T2["Attribution Engine<br/>System Drift vs Judge Drift"]
    end

    subgraph STORE["Trace Repository & Experiment Store"]
        S1[(Traces / Inputs / Outputs)]
        S2[(Versioned Runs<br/>code commit + data snapshot)]
        S3[(Historical Baselines)]
    end

    subgraph REG["Regression Detection"]
        R1[Baseline Comparator]
        R2["Threshold Alerts<br/>Z-score / statistical test"]
    end

    subgraph GATE["Deployment-Aware Gate"]
        G1["CI/CD Integration<br/>GitHub Actions / GitLab CI"]
        G2["Pass/Fail Signal<br/>with confidence interval"]
    end

    subgraph REPORT["Quality Reporting"]
        D1["Dashboard<br/>System Health Score"]
        D2["Judge Reliability Panel"]
        D3["Drift & Regression Reports"]
    end

    APP --> INSTR
    INSTR --> ORCH
    O2 --> S1
    O3 --> METRICS
    METRICS --> S1
    METRICS --> TRUST
    T1 --> T2
    METRICS --> T2
    T2 --> S2
    S1 --> S2
    S2 --> S3
    S3 --> REG
    METRICS --> REG
    REG --> GATE
    REG --> REPORT
    TRUST --> REPORT
    METRICS --> REPORT
    GATE --> D1
```

---

## 3. Component Breakdown

### 3.1 Instrumentation Layer

**Purpose:** Capture what actually happened inside a RAG pipeline, agent, or LLM call, at a granular enough level to localize failures.

- Uses OpenTelemetry-style span tracing: separate spans for planning, retrieval, tool use, and generation.
- Runs as a lightweight SDK hook in the target application, not a wrapper that blocks the response path.
- **Design decision:** evaluation is decoupled from the request/response cycle. Traces are emitted asynchronously to avoid adding latency to production traffic.

### 3.2 Evaluator Orchestrator

**Purpose:** The control plane that manages the lifecycle of an evaluation run.

- **Run Scheduler:** triggers evaluation runs (on-demand, scheduled, or in response to a percentage of live production traffic).
- **Trace Collector:** ingests spans from the instrumentation layer into the Trace Repository.
- **Metric Dispatcher:** routes traces to the relevant metrics based on system type (RAG, agent, general LLM app).

### 3.3 Metric Engine (Pluggable)

This is intentionally modular so new metrics can be added without changing the orchestration layer.

| Module | What it does | When to use |
|---|---|---|
| RAG Triad | Context relevance, groundedness, answer relevance | RAG pipelines, reference-free |
| Lightweight Judge Layer | Fast, cheap fine-tuned classifiers (e.g. DeBERTa-scale) trained on synthetic in-domain pairs | High-volume production monitoring where LLM-judge cost is prohibitive |
| LLM-as-Judge Layer | Prompted larger models scoring outputs | Pre-deployment benchmarking, lower-volume evaluation, cases needing nuanced judgment |
| Statistical Gating | Calibrates lightweight judge output against a small human-labeled gold set, producing confidence intervals | Deployment gates that need a high-confidence pass/fail signal |
| Behavioral Anchor Detector | Embedding similarity between prompts/responses and labeled "aligned" vs "deviation" anchor sentences | Long-session agents, detecting persona or constraint drift |

**Design decision:** reference-free metrics (RAG Triad, anchor detection) run continuously against production traffic. Reference-based metrics (accuracy against gold answers, AgentBench-style task completion) run at pre-deployment or scheduled benchmark stages, since gold answers aren't available for live traffic.

### 3.4 Trust & Attribution Layer

**Purpose:** Answer the question "did the system get worse, or did the judge change?"

- **Anchor Set:** a small, fixed, human-labeled set of queries and expected responses, re-scored at a steady rate alongside production traffic.
- **Attribution Engine:** compares current judge behavior on the anchor set against historical judge behavior. Produces a three-state verdict: no drift, system drift, or judge drift.
- **Design decision:** this layer exists specifically because judge models (especially third-party API-based judges) can change silently, and conflating judge drift with system regression would make every other part of the pipeline untrustworthy.

### 3.5 Trace Repository & Experiment Store

**Purpose:** Source of truth for everything measured.

- Stores raw traces, inputs, intermediate retrieval steps, and final outputs.
- Every run is versioned against a specific code commit and data/prompt configuration snapshot, so any two runs are comparable.
- Maintains historical baselines used by the Regression Detector.

### 3.6 Regression Detection

**Purpose:** Detect quality drops between versions or over time.

- Compares current run metrics against historical baselines using statistical tests (e.g. Z-score, or the kind of test appropriate to the metric's distribution).
- Feeds both the deployment gate (blocking) and the reporting layer (informational).

### 3.7 Deployment-Aware Gate

**Purpose:** Let evaluation results actually block or approve a release, not just report on it after the fact.

- Integrates with CI/CD (GitHub Actions, GitLab CI, or similar) as a build step.
- Emits a pass/fail signal with an attached confidence interval, not just a raw score, so teams can set risk-appropriate thresholds.

### 3.8 Quality Reporting

**Purpose:** Make results visible and actionable for engineering teams.

- **System Health Score:** an aggregated view combining retrieval relevance, agent plan quality, and drift signals into one summary metric, inspired by aggregation approaches used in tools like Deepchecks.
- **Judge Reliability Panel:** tracks judge consistency and bias longitudinally, as a first-class, dashboarded metric rather than an afterthought.
- **Drift & Regression Reports:** surfaces what changed, when, and whether it was attributed to the system or the judge.

---

## 4. Key Architectural Tensions and How NiriZan Resolves Them

| Tension | Positions in the literature | NiriZan's approach |
|---|---|---|
| Reference-free vs. reference-based evaluation | RAGAS/TruLens favor reference-free; AgentBench/HELM rely on gold references | Support both: reference-free for continuous production monitoring, reference-based for pre-deployment benchmarking |
| Static vs. living benchmarks | Static benchmarks risk data leakage and memorization; some proposals favor continuously refreshed evaluation sets | Support living data pipelines so benchmark data can be refreshed rather than going stale |
| Judge agreement metrics | Raw exact-match agreement overstates judge quality; Cohen's kappa is a more honest metric; position bias affects even strong models | Track judge reliability (including bias and consistency) as its own longitudinal metric, not just a one-time validation step |
| Cost vs. accuracy of judging | LLM-as-judge is accurate but expensive at scale; lightweight classifiers are cheap but need calibration | Use lightweight judges for volume, calibrate against a small gold set with statistical gating, reserve LLM-as-judge for lower-volume, higher-stakes evaluation |

---

## 5. Identified Gaps NiriZan Aims to Fill

1. **Unified RAG + agent + drift pipeline.** Most existing tools specialize in one domain; NiriZan aggregates retrieval quality, agent behavior, and drift into a single pipeline and health score.
2. **Judge-reliability tracking as a first-class, dashboarded metric**, not a one-off audit.
3. **Integrity-checked evaluation.** Guard against benchmark gaming (e.g. an agent reading reference answers directly rather than solving the task) through integrity-checking analysis modules.
4. **Data freshness and ownership signals.** A RAG system can score well on faithfulness while still answering from stale or unowned data; NiriZan should track data freshness/ownership metadata alongside inference-layer scores.

---

## 6. Summary Table for Design Doc Reference

| NiriZan Component | Inspiration | Problem Solved |
|---|---|---|
| Evaluator Orchestrator | AgentBench-style multi-environment testing | Coordinating multi-turn, multi-domain evaluation runs |
| Statistical Gating | Prediction-powered inference (PPI) style calibration | High-confidence regression gating at low cost |
| Attribution Engine | Judge-vs-system drift attribution research | Disambiguating whether a score drop is the system or the judge |
| Behavioral Anchor Detector | Embedding-based persona/behavior monitoring | Real-time agent drift detection, cheap enough for continuous use |
| Holistic Reporter | HELM's multi-metric, multi-scenario visibility model | Giving teams one place to see overall AI system quality |
