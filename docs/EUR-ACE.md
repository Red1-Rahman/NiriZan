# EUR-ACE Mapping

## Standard Overview

EUR-ACE (European Accredited Engineer) is a framework of standards for the accreditation of engineering degree programs across the European Higher Education Area, operated by ENAEE, the European Network for Accreditation of Engineering Education. EUR-ACE accredits degree programs, not individuals or projects. The EUR-ACE Framework Standards define Programme Outcomes under six headings: Knowledge and Understanding, Engineering Analysis, Engineering Design, Investigations, Engineering Practice, and Transferable Skills, specified separately for First Cycle (bachelor's level) and Second Cycle (master's level) programs.

NiriZan is an independent, open-source project with no connection to any European or other higher education institution, and it is not part of any degree program that could be assessed under EUR-ACE. This document borrows the six EUR-ACE Programme Outcome headings for the same reason a project might reference any well-structured competency framework: as a lens for describing, honestly and specifically, what kind of engineering thinking the project involved. It is a self-assessment exercise, not an accreditation claim of any kind.

## Programme Outcome Mapping

### Knowledge and Understanding

EUR-ACE expects graduates to hold knowledge and understanding of the scientific and mathematical principles underlying their branch of engineering, a systematic understanding of key concepts in that branch, and awareness of the wider multidisciplinary context of engineering.

NiriZan's design draws on knowledge from software engineering (distributed tracing, orchestration, pluggable system architecture), statistics (confidence intervals, regression detection, calibration), and applied machine learning (retrieval-augmented generation, LLM-as-judge methodology). The literature review demonstrates awareness of the wider context of AI evaluation research, situating the project's design decisions against RAGAS, TruLens, HELM, and AgentBench rather than treating the problem in isolation.

### Engineering Analysis

EUR-ACE expects graduates to identify a problem, clarify its specification, consider possible methods of solution, and select and correctly implement the most appropriate method, using approaches that can include mathematical analysis and computational modelling.

The literature review analyzes the tradeoffs between reference-free and reference-based evaluation, between static and living benchmarks, and between low-cost lightweight judges and higher-cost LLM-based judges. The architecture document then selects specific approaches for NiriZan based on this analysis, for example supporting both reference-free and reference-based evaluation for different deployment contexts rather than defaulting to a single method.

### Engineering Design

EUR-ACE expects graduates to design solutions to meet defined and specified requirements, working within realistic constraints.

The system architecture document defines a complete design: the Instrumentation Layer, Evaluator Orchestrator, Metric Engine, Trust and Attribution Layer, Trace Repository and Experiment Store, Regression Detection, Deployment-Aware Gate, and Quality Reporting. Constraints are addressed directly, for example the requirement that evaluation must not sit on the user-facing critical path, which shapes the decision to run instrumentation asynchronously.

### Investigations

EUR-ACE expects graduates to conduct investigations of technical problems in their field, including literature searches, design and conduct of experiments, and interpretation of results.

The literature review constitutes a structured investigation of the current state of AI evaluation research, conducted through search and synthesis across primary sources on RAG evaluation, LLM-as-judge reliability, agentic benchmarking, and production drift monitoring. Findings from this investigation are interpreted directly into architectural decisions and identified gaps that motivate NiriZan's specific approach.

### Engineering Practice

EUR-ACE expects graduates to demonstrate understanding of applicable techniques and methods, and their limitations, and awareness of non-technical implications of engineering practice.

The project's phased development approach reflects sound engineering practice by avoiding premature commitment to an unvalidated architecture. The architecture document also states the limitations of its own design choices directly, for example noting that some proposed components are inspired by research patterns that require further validation against primary sources before implementation, rather than presenting every design decision as settled.

### Transferable Skills

EUR-ACE expects graduates to demonstrate skills such as effective communication, project and time management, and the ability to work as part of a team.

The project's documentation set, including the README, architecture document, literature review, and roadmap, demonstrates written communication of a technical design to varied audiences. The decision to structure development in phases with defined deliverables at each stage demonstrates project management practice suited to a project that may extend beyond a single contributor over time.

## Applicability Note

NiriZan holds no EUR-ACE accreditation and is not eligible for one, since accreditation applies to degree programs assessed over their full duration, not to an independent open-source project. This mapping does not constitute, imply, or work toward EUR-ACE accreditation in any form. It is included only because the six outcome headings provide a clear, recognized structure for reflecting on the engineering competencies exercised while designing and building the project.

## Sources

This document was drafted from secondary summaries, not the primary ENAEE document. Before citing EUR-ACE Programme Outcomes in any formal writing, verify against the primary source below rather than relying on the summaries used here.

- ENAEE, "EUR-ACE Framework Standards and Guidelines" (primary source, current edition, adopted following the Bergen Conference EQF alignment): https://www.enaee.eu/wp-content/uploads/2022/03/EAFSG-04112021-English-1-1.pdf
- ENAEE, "EUR-ACE Framework Standards and Guidelines" overview page: https://www.enaee.eu/eur-ace-system/standards-and-guidelines/
- ENAEE, "EUR-ACE system" overview: https://www.enaee.eu/eur-ace-system/
- CTI Commission, "EUR-ACE Framework Standards for the Accreditation of Engineering Programmes" (earlier edition, useful for historical comparison): https://www.cti-commission.fr/wp-content/uploads/2008/04/A1_EUR-ACE_Frwrk_Stds_Final_05_11_17.pdf
- ResearchGate, "EUR-ACE: A common European quality label for accredited engineering programmes" (academic discussion of the framework's structure and rationale): https://www.researchgate.net/publication/229000950_EUR-ACE_A_common_European_quality_label_for_accredited_engineering_programmes
