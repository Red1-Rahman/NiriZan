# EUR-ACE Mapping

## Scope

EUR-ACE (European Accredited Engineer) is an accreditation framework for engineering degree programmes, not for individual projects or software products. NiriZan has no EUR-ACE accreditation or institutional affiliation.

This document uses the six EUR-ACE Programme Outcome headings as a **self-assessment taxonomy** for mapping engineering practices demonstrated by the current NiriZan project. A check indicates that the project provides reasonable evidence for the corresponding area; it does not imply accreditation or formal compliance.

## Programme Outcome Mapping

| EUR-ACE Programme Outcome   | NiriZan |
| --------------------------- | :-----: |
| Knowledge and Understanding |    ✅    |
| Engineering Analysis        |    ✅    |
| Engineering Design          |    ✅    |
| Investigations              |    ✅    |
| Engineering Practice        |    ✅    |
| Transferable Skills         |    ✅    |

## Justification

* **Knowledge and Understanding** — NiriZan applies concepts from software engineering, distributed tracing, statistical evaluation, machine learning, RAG evaluation, LLM-as-a-judge methodology, and AI system reliability. Its literature review situates the project against established evaluation systems and research.

* **Engineering Analysis** — The project analyzes evaluation trade-offs including reference-based versus reference-free evaluation, lightweight versus LLM-based judges, regression detection, statistical gating, and evaluator drift, and translates these considerations into concrete system design decisions.

* **Engineering Design** — NiriZan implements a modular continuous-evaluation architecture covering instrumentation, orchestration, metrics, trust and attribution, storage, regression detection, deployment-aware gating, and reporting. The design also addresses practical constraints such as keeping evaluation out of the user-facing critical path.

* **Investigations** — The project includes a structured literature review, experimental notebooks, ablation studies, benchmarking, regression experiments, and judge-reliability investigations. These activities provide evidence for investigating technical alternatives and evaluating the resulting system.

* **Engineering Practice** — The repository demonstrates software engineering practices through automated testing, CI/CD workflows, packaging, security checks, architectural boundary enforcement, documentation, reproducible experiments, and statistical quality gates.

* **Transferable Skills** — NiriZan demonstrates technical communication and project organization through its README, architecture and contract documentation, user manual, literature review, governance documentation, standards mappings, experiments, examples, and contribution guidance.

## Applicability Note

This mapping is a project-level self-assessment and does not constitute, imply, or seek EUR-ACE accreditation. EUR-ACE accreditation applies to engineering degree programmes assessed through the appropriate accreditation process.

## Sources

* ENAEE, *EUR-ACE Framework Standards and Guidelines*: https://www.enaee.eu/wp-content/uploads/2022/03/EAFSG-04112021-English-1-1.pdf
* ENAEE, *EUR-ACE Framework Standards and Guidelines*: https://www.enaee.eu/eur-ace-system/standards-and-guidelines/
* ENAEE, *EUR-ACE System*: https://www.enaee.eu/eur-ace-system/
