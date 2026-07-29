# ISO/IEC/IEEE 12207 Mapping

## Standard Overview

ISO/IEC/IEEE 12207, Systems and Software Engineering: Software Life Cycle Processes, is a jointly developed international standard maintained by the International Organization for Standardization (ISO), the International Electrotechnical Commission (IEC), and the Institute of Electrical and Electronics Engineers (IEEE). It defines a common framework for the processes, activities, and tasks that apply across the acquisition, development, operation, maintenance, and disposal of software systems. The standard organizes these processes into four groups: agreement processes, organizational project-enabling processes, technical management processes, and technical processes. It does not prescribe a specific lifecycle model (waterfall, iterative, or agile) and is written to be compatible with all of them.

NiriZan is an independent, open-source project released under the GNU General Public License. It has no affiliation with any university, employer, client, or other stakeholder, and it is not seeking or claiming certification or compliance with ISO/IEC/IEEE 12207. This document instead uses the standard as a voluntary reference point: a way of describing NiriZan's own engineering practices in a shared, recognized vocabulary, and a checklist the maintainer can use to keep the project's process disciplined as it grows past a single contributor. The mapping below concentrates on the technical management and technical process groups, since these are the groups relevant to how an open-source systems project is actually planned and built. Agreement processes (acquisition and supply, which govern contractual relationships between an acquirer and a supplier) do not apply, since there is no acquiring organization.

## Process Group Mapping

### Technical Management Processes

| ISO/IEC/IEEE 12207 Process | NiriZan Application |
|---|---|
| Project Planning | The phased development roadmap (instrumentation and trace storage, RAG Triad metrics, experiment tracking and baselines, regression detection and CI gate, drift and judge-reliability layer) defines scope, sequencing, and deliverables for each stage before implementation begins. |
| Project Assessment and Control | Each phase is treated as a checkpoint against the architecture document, so scope and design decisions can be revisited with evidence from the previous phase rather than committed to upfront. |
| Decision Management | Architectural tensions (reference-free versus reference-based evaluation, static versus living benchmarks, cost versus accuracy of judging) are documented explicitly in the architecture document with the position NiriZan takes and the reasoning behind it. |
| Risk Management | Known risks are named directly in the architecture document, including the possibility that a third-party judge model may drift silently, which motivates the Trust and Attribution Layer as a dedicated mitigation. |
| Configuration Management | Every evaluation run is versioned against a specific code commit and a specific data and prompt configuration snapshot, so that any two runs can be compared meaningfully and results remain reproducible over time. |
| Information Management | The Trace Repository and Experiment Store function as the designated source of truth for all traces, inputs, outputs, and historical baselines, rather than allowing evaluation evidence to be scattered across ad hoc logs. |
| Quality Assurance | The Quality Reporting component (System Health Score, Judge Reliability Panel, Drift and Regression Reports) exists specifically to give the project team ongoing visibility into whether the system meets its own quality bar. |

### Technical Processes

| ISO/IEC/IEEE 12207 Process | NiriZan Application |
|---|---|
| Business or Mission Analysis | The problem statement in the project's foundational documentation (that probabilistic AI systems cannot be verified with deterministic pass/fail testing) establishes the mission this project addresses. |
| Stakeholder Needs and Requirements Definition | Requirements are derived from the needs of engineering teams operating RAG pipelines, AI agents, and LLM applications in production, specifically the need to detect regressions and distinguish system drift from judge drift. |
| System/Software Requirements Definition | Functional requirements (reproducible pipelines, benchmark execution, regression detection, experiment tracking, quality reporting, deployment-aware validation) are stated directly in the project README and expanded into concrete components in the architecture document. |
| Architecture Definition | The system architecture document defines the Instrumentation Layer, Evaluator Orchestrator, Metric Engine, Trust and Attribution Layer, Trace Repository, Regression Detection, Deployment-Aware Gate, and Quality Reporting components, along with the data flow between them. |
| Design Definition | Design decisions are stated explicitly at the component level, for example decoupling evaluation from the request and response cycle so that instrumentation does not add latency to production traffic. |
| System/Software Analysis | The literature review synthesizes existing evaluation frameworks (RAGAS, TruLens, HELM, AgentBench) and their tradeoffs to inform which architectural choices NiriZan should make and which gaps it should address. |
| Implementation | The phased roadmap sequences implementation so that later phases depend on stable interfaces from earlier phases, rather than requiring a rewrite as the system grows. |
| Integration | The Metric Engine is deliberately built as a pluggable module so that new metrics can be added without changing the Evaluator Orchestrator, which supports integration of future evaluation methods without destabilizing existing ones. |
| Verification | The Deployment-Aware Gate produces a pass or fail signal with an attached confidence interval, giving teams a defined verification checkpoint before a release proceeds. |
| Validation | The distinction between reference-free evaluation (used for continuous production monitoring) and reference-based evaluation (used for pre-deployment benchmarking against gold answers) reflects two distinct validation contexts, each handled with an appropriate method. |
| Operation | The instrumentation and monitoring components are designed to run continuously against live production traffic, not only at release time, which is the operational use case the standard's lifecycle model anticipates. |
| Maintenance | Historical baselines stored in the Experiment Store allow the Regression Detector to compare current behavior against past behavior, supporting ongoing maintenance decisions as the system or its dependencies change. |

## Applicability Note

This mapping is descriptive, not a compliance claim. NiriZan is not certified against ISO/IEC/IEEE 12207 and is not pursuing certification. The agreement process group does not apply, since there is no acquirer-supplier relationship, and the organizational project-enabling process group is only partially relevant to a project of this scale and structure. What the mapping shows is that the technical management and technical process groups, which describe the actual engineering activities involved in planning, designing, building, and monitoring quality in a software system, already correspond closely to the practices NiriZan's architecture and roadmap set out. Adopting this vocabulary is a choice made for the project's own benefit: clearer documentation, more disciplined process as the contributor base grows, and an easier way for other engineers to understand how the project is run.

## Sources

This document was drafted from secondary summaries, not the primary standard text. Before citing ISO/IEC/IEEE 12207 in any formal writing, verify claims against the primary specification (ISO/IEC/IEEE 12207:2017 or the current edition, available for purchase from ISO, IEC, or IEEE) rather than relying on the summaries below.

- IEEE Standards Association, "ISO/IEC/IEEE International Standard: Systems and software engineering — Software life cycle processes": https://standards.ieee.org/ieee/12207/5672/
- Wikipedia, "ISO/IEC 12207": https://en.wikipedia.org/wiki/ISO/IEC_12207
- arc42 Quality Model, "ISO/IEC/IEEE 12207 - Software Life Cycle Processes": https://quality.arc42.org/standards/iso12207
- Pacific Certifications, "ISO/IEC/IEEE 12207:2017 - Systems and Software Engineering": https://pacificcert.com/iso-iec-ieee-12207-2017-systems-software-engineering/
- ISO/IEC/IEEE 12207:2008(E), full historical standard text (PDF): https://wildart.github.io/MISG5020/standards/IEEE-12207-2008.pdf
