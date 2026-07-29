# Washington Accord Mapping

## Standard Overview

The Washington Accord, first signed in 1989, is an international agreement among the bodies responsible for accrediting undergraduate and postgraduate engineering degree programs. Signatories recognize the substantial equivalence of programs accredited by one another, meaning that a graduate of any signatory's accredited program is recognized by the other signatories as having met the academic requirements for entry into professional engineering practice. The Accord accredits degree programs, not individuals and not projects. It establishes a set of twelve Graduate Attributes, developed by the International Engineering Alliance, that describe the knowledge, skills, and professional qualities an accredited program must enable its graduates to demonstrate.

NiriZan is an independent, open-source project with no connection to any university, degree program, or accreditation process. It is not a capstone project, a coursework submission, or a credential-seeking exercise. The Washington Accord has no direct application to a project like this, since there is no program, no graduate, and no accrediting body involved. This document instead borrows the twelve Graduate Attributes as an independent, well-established checklist of engineering competencies, and uses it to reflect honestly on which of those competencies the process of building NiriZan has actually exercised. The purpose is self-assessment, not accreditation.

## Graduate Attribute Mapping

| Graduate Attribute | NiriZan Application |
|---|---|
| GA1: Engineering Knowledge | The project applies knowledge of software engineering fundamentals, distributed systems concepts (tracing, orchestration), and statistical reasoning (confidence intervals, regression detection) to the design of an evaluation infrastructure. |
| GA2: Problem Analysis | The literature review identifies and analyzes the core problem, that probabilistic AI systems cannot be verified with deterministic testing, by examining existing RAG evaluation frameworks, LLM-as-judge research, and drift detection literature before proposing a solution. |
| GA3: Design and Development of Solutions | The system architecture document specifies a complete, componentized solution, including the Instrumentation Layer, Metric Engine, Trust and Attribution Layer, and Deployment-Aware Gate, with documented design decisions and tradeoffs at each stage. |
| GA4: Conduct Investigations of Complex Problems | The literature review conducts a structured investigation across multiple sources (RAGAS, TruLens, HELM, AgentBench, and drift monitoring research) to identify architectural tensions and gaps that inform the project's own design choices. |
| GA5: Modern Tool Usage | The project's technical approach draws on modern evaluation tooling patterns (OpenTelemetry-style tracing, pluggable metric engines, CI/CD integration for deployment gating) appropriate to current software engineering practice. |
| GA6: The Engineer and Society | NiriZan's stated purpose, to help engineering teams build justified confidence in AI systems before those systems affect users, addresses a concern with direct consequences for the people who rely on AI-driven products and services. |
| GA7: Environment and Sustainability | The project's continuous monitoring approach is designed to catch quality regressions early, which reduces the computational waste associated with running unnecessary re-evaluation cycles or shipping AI systems that must be rolled back and rebuilt after failing in production. |
| GA8: Ethics | The project's engineering standards documentation addresses ethical considerations explicitly, including the risk of judge bias distorting evaluation outcomes and the importance of not presenting an unvalidated automated score as ground truth. |
| GA9: Individual and Team Work | The phased development roadmap is structured so that each phase produces a stable, usable deliverable that later contributors or team members could build on without requiring a rewrite of prior work. |
| GA10: Communication | The project documentation set, including the README, architecture document, literature review, and this engineering standards mapping, is written to communicate design intent and reasoning clearly to both technical and non-technical readers. |
| GA11: Project Management and Finance | The decision to pursue phased, incremental development rather than a single monolithic build reflects a deliberate project management choice intended to reduce the risk of wasted effort on unvalidated architecture. |
| GA12: Lifelong Learning | The project required engaging with unfamiliar research areas, including LLM-as-judge reliability research and production drift detection, that were not necessarily covered in a standard curriculum, and synthesizing them into an original design. |

## Applicability Note

NiriZan holds no Washington Accord accreditation, does not require one, and is not affiliated with any institution that could seek one on its behalf. The Accord governs entire degree programs evaluated over years of coursework, not a single open-source project maintained independently. This mapping is a voluntary, honest self-reflection exercise: it uses a well-known and internationally recognized competency framework to describe, attribute by attribute, what kinds of engineering thinking went into the project. It carries no accreditation status and makes no claim beyond that.

## Sources

This document was drafted from secondary summaries, not the primary IEA document. Before citing the Washington Accord or its Graduate Attributes in any formal writing, verify against the primary source below rather than relying on the summaries used here.

- International Engineering Alliance, "Graduate Attributes and Professional Competencies" (primary source for the twelve Graduate Attributes, WA1-WA12, and the supporting Knowledge Profile WK1-WK8): https://www.ieagreements.org/assets/Uploads/Documents/Policy/Graduate-Attributes-and-Professional-Competencies.pdf
- International Engineering Alliance, "Washington Accord" overview: https://www.internationalengineeringalliance.org/accords/washington-accord
- Engineering Council (UK), "Washington Accord": https://www.engc.org.uk/international-recognition/international-accords/washington-accord
- Wikipedia, "Washington Accord (credentials)": https://en.wikipedia.org/wiki/Washington_Accord_(credentials)
- ENAEE, Hanrahan, "Toward Global Recognition of Engineering Qualifications" (comparative discussion of Washington Accord graduate attributes against other frameworks): https://www.enaee.eu/wp-content/uploads/2018/11/Hanrahan-ENAEE-Conf-2013.pdf
