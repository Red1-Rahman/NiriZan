# ACM/IEEE-CS/AAAI CS2023 Mapping

## Scope

CS2023 is the joint **ACM/IEEE Computer Society/AAAI Computer Science
Curricula 2023** guideline. It defines a computer-science knowledge model
consisting of 17 Knowledge Areas (KAs), together with knowledge units,
topics, learning outcomes, professional dispositions, and competency-area
guidance.

NiriZan is an independent open-source software project, not a computer
science degree programme or accredited curriculum. CS2023 is therefore used
only as a **project-level computer-science knowledge taxonomy** for identifying
areas demonstrated by the repository.

A check indicates that the current NiriZan repository provides reasonable
evidence for the corresponding CS2023 Knowledge Area. It does not imply
curricular accreditation, certification, formal competency assessment,
equivalence to a CS2023 curriculum, or endorsement by ACM, IEEE Computer
Society, or AAAI.

## Knowledge Areas

| Knowledge Area | NiriZan |
|---|:---:|
| AL — Algorithmic Foundations | ✅ |
| AR — Architecture and Organization | ✅ |
| AI — Artificial Intelligence | ✅ |
| DM — Data Management | ✅ |
| FPL — Foundations of Programming Languages | ⬜ |
| GIT — Graphics and Interactive Techniques | ⬜ |
| HCI — Human-Computer Interaction | ⬜ |
| MSF — Mathematical and Statistical Foundations | ✅ |
| NC — Networking and Communication | ⬜ |
| OS — Operating Systems | ⬜ |
| PDC — Parallel and Distributed Computing | ✅ |
| SEC — Security | ✅ |
| SEP — Society, Ethics, and the Profession | ✅ |
| SDF — Software Development Fundamentals | ✅ |
| SE — Software Engineering | ✅ |
| SF — Systems Fundamentals | ✅ |
| SPD — Specialized Platform Development | ⬜ |

## Knowledge Area Justification

- **AL — Algorithmic Foundations** — NiriZan implements algorithmic
  procedures for evaluation, regression detection, statistical comparison,
  metric dispatch, attribution, health scoring, and judge-reliability
  analysis. Experiments additionally evaluate algorithmic behaviour through
  ablation and benchmark workflows.

- **AR — Architecture and Organization** — NiriZan's core contribution is an
  eight-layer, unidirectional architecture spanning instrumentation,
  orchestration, metrics, trust/attribution, storage, regression detection,
  deployment-aware gating, and reporting. Component responsibilities,
  interfaces, data flow, and dependency direction are explicitly defined,
  with architectural boundaries enforced through CI/import-linter.

- **AI — Artificial Intelligence** — NiriZan is specifically designed for
  evaluating probabilistic AI systems, including LLM, RAG, and agent
  workflows. Its implementation includes RAG evaluation, LLM-as-judge
  evaluation, behavioral anchors, evaluator reliability, judge drift,
  attribution, and continuous AI quality assessment.

- **DM — Data Management** — NiriZan defines persistent repositories and
  contracts for traces, evaluation runs, baselines, metrics, and experiment
  state. The system versions evaluation state and separates trace storage
  from evaluation orchestration and reporting.

- **MSF — Mathematical and Statistical Foundations** — Statistical reasoning
  is a central part of NiriZan. The project uses hypothesis testing,
  confidence intervals, effect sizes, bootstrap estimation, Mann–Whitney
  comparisons, Holm–Bonferroni correction, regression analysis, and
  statistical gating to distinguish meaningful quality changes from noise.

- **PDC — Parallel and Distributed Computing** — NiriZan's evaluation
  architecture separates application execution from evaluation, supports
  asynchronous/out-of-band trace emission and evaluation orchestration, and
  coordinates collection, metric dispatch, storage, regression analysis,
  gating, and reporting across independently bounded components.

- **SEC — Security** — Security is addressed through repository security
  testing, CI security checks, controlled data handling, dependency and
  packaging practices, and explicit consideration of evaluation traces and
  stored evaluation state. Security is treated as an engineering concern
  alongside testing and release quality.

- **SEP — Society, Ethics, and the Profession** — NiriZan addresses
  responsible evaluation of AI systems through evaluator-bias analysis,
  judge reliability and drift detection, attribution uncertainty,
  reproducible evidence, statistical decision-making, governance
  documentation, and explicit separation between automated evaluation
  scores and unquestioned ground truth.

- **SDF — Software Development Fundamentals** — NiriZan is implemented as a
  structured Python package using modular source organization, interfaces,
  typed contracts, testing, configuration, packaging, documentation,
  examples, version control, and automated CI/CD quality checks.

- **SE — Software Engineering** — NiriZan demonstrates requirements
  decomposition, modular architecture, interface contracts, separation of
  concerns, verification and testing, configuration management,
  documentation, maintainability, extensibility, CI/CD integration, and
  software-quality controls. The project also treats evaluation itself as a
  software-engineering lifecycle concern for production AI systems.

- **SF — Systems Fundamentals** — NiriZan models an end-to-end evaluation
  system consisting of instrumentation, trace collection, orchestration,
  metric computation, trust analysis, persistence, statistical regression
  detection, deployment gates, and reporting. The architecture explicitly
  defines interactions and responsibilities between these system
  components.

## Competency-Area Context

CS2023 groups Knowledge Areas into representative competency areas:

- **Software Development** — Algorithmic Foundations (AL), Foundations of
  Programming Languages (FPL), Software Development Fundamentals (SDF), and
  Software Engineering (SE).

- **Systems Development** — Systems Fundamentals (SF), Architecture and
  Organization (AR), Operating Systems (OS), Parallel and Distributed
  Computing (PDC), Networking and Communication (NC), Security (SEC), and
  Data Management (DM).

- **Applications Development** — Graphics and Interactive Techniques (GIT),
  Artificial Intelligence (AI), Specialized Platform Development (SPD),
  Human-Computer Interaction (HCI), Security (SEC), and Data Management
  (DM).

Mathematical and Statistical Foundations (MSF) and Society, Ethics, and the
Profession (SEP) contribute across competency areas.

NiriZan primarily demonstrates a **Software + Systems + AI-oriented
competency profile**, with particularly strong evidence in AI, mathematical
and statistical foundations, software engineering, architecture, systems,
and responsible computing.


## Summary

NiriZan's strongest CS2023 alignment is concentrated in:

- **AI** — continuous evaluation of probabilistic AI systems;
- **MSF** — statistical evaluation and regression detection;
- **SE** — production-oriented software engineering;
- **AR** — explicit eight-layer system architecture;
- **SF** — end-to-end evaluation-system design;
- **SDF** — implemented, tested, packaged Python software;
- **AL** — evaluation, comparison, detection, and scoring algorithms;
- **DM** — persistent traces, runs, baselines, and experiment state;
- **PDC** — asynchronous/out-of-band and component-oriented evaluation;
- **SEC** — software and repository security practices;
- **SEP** — responsible, reproducible, and trustworthy AI evaluation.

This profile is consistent with NiriZan's purpose as continuous evaluation
infrastructure for production AI rather than as a general-purpose
computer-science system covering every CS2023 Knowledge Area.

## Source

- ACM/IEEE Computer Society/AAAI, **Computer Science Curricula 2023
  (CS2023)**, Final Report.
- Official CS2023 Knowledge Areas.
- Official CS2023 Revision Report.
