# ISO/IEC/IEEE 12207 Engineering Practice Mapping

## Scope

ISO/IEC/IEEE 12207, *Systems and Software Engineering - Software Life Cycle Processes*, provides a framework for software life-cycle processes. NiriZan uses the standard as a voluntary engineering-practice taxonomy.

A check indicates that the current repository provides reasonable evidence for the corresponding process. It does not constitute certification, compliance, or conformance with ISO/IEC/IEEE 12207.

## Process Mapping

### Technical Management Processes

| ISO/IEC/IEEE 12207 Process     | NiriZan |
| ------------------------------ | :-----: |
| Project Planning               |    ✅    |
| Project Assessment and Control |    ✅    |
| Decision Management            |    ✅    |
| Risk Management                |    ✅    |
| Configuration Management       |    ✅    |
| Information Management         |    ✅    |
| Quality Assurance              |    ✅    |

### Technical Processes

| ISO/IEC/IEEE 12207 Process                    | NiriZan |
| --------------------------------------------- | :-----: |
| Business or Mission Analysis                  |    ✅    |
| Stakeholder Needs and Requirements Definition |    ✅    |
| System/Software Requirements Definition       |    ✅    |
| Architecture Definition                       |    ✅    |
| Design Definition                             |    ✅    |
| System/Software Analysis                      |    ✅    |
| Implementation                                |    ✅    |
| Integration                                   |    ✅    |
| Verification                                  |    ✅    |
| Validation                                    |    ✅    |
| Operation                                     |    ⬜    |
| Maintenance                                   |    ✅    |

### Other Process Groups

| ISO/IEC/IEEE 12207 Process Group          | NiriZan |
| ----------------------------------------- | :-----: |
| Agreement Processes                       |    ⬜    |
| Organizational Project-Enabling Processes |    ⬜    |

## Justification

* **Project Planning** — The repository maintains documented architecture, contracts, experiments, development guidance, and staged implementation work that establish project scope and engineering direction.

* **Project Assessment and Control** — Experiments, regression detection, statistical gates, CI workflows, and benchmark results provide mechanisms for assessing implementation and evaluation outcomes.

* **Decision Management** — Architecture and research documentation records significant design choices and trade-offs, including evaluation methodology, judge selection, statistical testing, and system boundaries.

* **Risk Management** — Judge drift, system drift, evaluator reliability, regression, and reproducibility are treated as explicit engineering risks and addressed by dedicated NiriZan components.

* **Configuration Management** — The Git repository, versioned code, configuration, experiment notebooks, packaging metadata, and CI workflows provide controlled project configuration and reproducible development history.

* **Information Management** — NiriZan defines trace, run, metric, baseline, and evaluation data structures and provides storage abstractions for preserving evaluation evidence.

* **Quality Assurance** — Automated tests, CI, security checks, architectural checks, statistical regression gates, and quality reporting provide mechanisms for maintaining software and evaluation quality.

* **Business or Mission Analysis** — NiriZan addresses the engineering problem of continuously evaluating probabilistic AI systems where conventional deterministic testing is insufficient.

* **Stakeholder Needs and Requirements Definition** — The project targets practical needs of teams operating RAG systems, agents, and other production AI applications, particularly continuous quality monitoring and reliable evaluation.

* **System/Software Requirements Definition** — Core requirements such as instrumentation, evaluation, experiment tracking, regression detection, judge reliability, reporting, and deployment-aware gating are reflected in the project's architecture and implementation.

* **Architecture Definition** — The repository defines and implements a layered architecture covering instrumentation, orchestration, metrics, trust and attribution, storage, regression detection, deployment-aware gating, and reporting.

* **Design Definition** — Component contracts and interfaces define how major subsystems interact while maintaining separation of concerns and extensibility.

* **System/Software Analysis** — The literature review and experiments examine existing evaluation approaches and their trade-offs, providing evidence for NiriZan's design decisions.

* **Implementation** — NiriZan is implemented as a Python package under `src/nirizan/`, supported by tests, examples, experiments, packaging configuration, and CI.

* **Integration** — Instrumentation, evaluation, orchestration, regression detection, trust attribution, storage, reporting, and deployment gating are designed to operate as an integrated evaluation pipeline.

* **Verification** — Automated tests and CI validate software behavior, interfaces, security properties, and architectural constraints; statistical gates additionally provide defined release-quality checks.

* **Validation** — Experiments and benchmark evaluations assess whether implemented evaluation mechanisms behave as intended against representative AI evaluation scenarios.

* **Maintenance** — NiriZan is actively maintained as an open-source software project through corrective fixes, refactoring, dependency and configuration updates, documentation changes, testing, CI/CD maintenance, security improvements, and versioned releases. Regression detection and historical evaluation further support maintenance decisions as the implementation evolves.

## Applicability Note

This is a voluntary project-level mapping, not an ISO/IEC/IEEE 12207 compliance assessment. Agreement processes are outside the project's current scope because NiriZan does not operate through an acquirer-supplier relationship. Organizational project-enabling processes are likewise not treated as a current primary scope of the project.

The unchecked Operation and Maintenance processes reflect the current evidence boundary rather than a claim that NiriZan cannot support those activities in the future.

## Sources

* IEEE Standards Association, *ISO/IEC/IEEE 12207 — Systems and Software Engineering — Software Life Cycle Processes*: https://standards.ieee.org/ieee/12207/5672/
* ISO, *ISO/IEC/IEEE 12207:2017 — Systems and software engineering — Software life cycle processes*: https://www.iso.org/standard/63712.html
